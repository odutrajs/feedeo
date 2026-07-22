"""Módulo 6: motor de montagem do vídeo.

Estratégia: um único comando ffmpeg com filter_complex que:
1. anima cada imagem com Ken Burns (zoompan) pela duração da cena — ou, quando a
   cena usa um trecho de vídeo enviado (modo creative), recorta o trecho, ajusta
   para 9:16 e faz LOOP do segmento quando ele é mais curto que a cena (o vídeo
   nunca congela em frame estático);
2. emenda as cenas com transições xfade centradas nas fronteiras da timeline;
3. sobrepõe o stream de legendas (PNGs transparentes via concat demuxer);
4. normaliza a narração (loudnorm) e mistura trilha sonora com ducking
   automático (sidechaincompress) quando há música;
5. exporta H.264 1080x1920 com AAC.
"""

from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.modules.video.ffmpeg import run_ffmpeg

TRANSITION_DURATION = 0.4
MAX_ZOOM = 1.12


@dataclass
class SceneClip:
    duration: float  # scene duration from the timeline (seconds)
    motion: str  # zoom_in / zoom_out / pan_left / pan_right (imagens)
    image_path: Path | None = None  # cenas de imagem (IA ou enviada)
    video_path: Path | None = None  # cenas com trecho de vídeo enviado
    video_start: float = 0.0  # início do trecho dentro do vídeo-fonte (s)
    video_end: float = 0.0  # fim do trecho dentro do vídeo-fonte (s)


def _zoompan_expr(motion: str, frames: int) -> str:
    """Ken Burns expressions per motion type. `on` is the output frame number."""
    progress = f"(on/{max(frames - 1, 1)})"
    center_x = "iw/2-(iw/zoom/2)"
    center_y = "ih/2-(ih/zoom/2)"
    if motion == "zoom_out":
        z = f"{MAX_ZOOM}-{MAX_ZOOM - 1:.4f}*{progress}"
        x, y = center_x, center_y
    elif motion == "pan_left":
        z = f"{MAX_ZOOM}"
        x = f"(iw-iw/zoom)*(1-{progress})"
        y = center_y
    elif motion == "pan_right":
        z = f"{MAX_ZOOM}"
        x = f"(iw-iw/zoom)*{progress}"
        y = center_y
    else:  # zoom_in (default)
        z = f"1+{MAX_ZOOM - 1:.4f}*{progress}"
        x, y = center_x, center_y
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:fps=%FPS%:s=%SIZE%"


def render_video(
    clips: list[SceneClip],
    narration_path: Path,
    captions_path: Path | None,
    output_path: Path,
    music_path: Path | None = None,
    music_volume: float = 0.22,
) -> None:
    settings = get_settings()
    fps = settings.video_fps
    width, height = settings.video_width, settings.video_height
    n = len(clips)
    if n == 0:
        raise RuntimeError("Nenhuma cena para renderizar")

    total_duration = sum(c.duration for c in clips)

    # Each clip is extended by the transition time so the xfade midpoint lands
    # exactly on the scene boundary; the extra tail is trimmed by -t at the end.
    durations = [c.duration + TRANSITION_DURATION for c in clips]

    inputs: list[str] = []
    for clip in clips:
        if clip.video_path is not None:
            inputs += ["-i", str(clip.video_path)]
        else:
            inputs += ["-i", str(clip.image_path)]
    narration_index = n
    inputs += ["-i", str(narration_path)]
    next_index = n + 1
    captions_index = None
    if captions_path is not None:
        captions_index = next_index
        next_index += 1
        inputs += ["-f", "concat", "-safe", "0", "-i", str(captions_path)]
    music_index = None
    if music_path is not None:
        music_index = next_index
        inputs += ["-stream_loop", "-1", "-i", str(music_path)]

    filters: list[str] = []

    # --- video: per-scene stream (Ken Burns para imagens, loop para clipes) ---
    for i, clip in enumerate(clips):
        if clip.video_path is not None:
            # Trecho real: recorta, enquadra em 9:16 e faz LOOP do segmento
            # quando ele é mais curto que a cena — o vídeo nunca congela.
            seg_duration = max(clip.video_end - clip.video_start, 0.1)
            seg_frames = max(int(round(seg_duration * fps)), 2)
            filters.append(
                f"[{i}:v]trim=start={clip.video_start:.3f}:end={clip.video_end:.3f},"
                f"setpts=PTS-STARTPTS,fps={fps},"
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"loop=loop=-1:size={seg_frames}:start=0,"
                f"trim=duration={durations[i]:.3f},setpts=PTS-STARTPTS,"
                f"format=yuv420p,settb=AVTB[v{i}]"
            )
            continue
        frames = max(int(round(durations[i] * fps)), 2)
        zoompan = (
            _zoompan_expr(clip.motion or "zoom_in", frames)
            .replace("%FPS%", str(fps))
            .replace("%SIZE%", f"{width}x{height}")
        )
        filters.append(
            f"[{i}:v]scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
            f"crop={width * 2}:{height * 2},{zoompan},format=yuv420p,settb=AVTB[v{i}]"
        )

    # --- video: xfade chain ----------------------------------------------------
    if n == 1:
        last_video = "v0"
    else:
        offset = 0.0
        previous = "v0"
        for i in range(1, n):
            offset += clips[i - 1].duration
            out = f"x{i}"
            filters.append(
                f"[{previous}][v{i}]xfade=transition=fade:"
                f"duration={TRANSITION_DURATION}:offset={offset - TRANSITION_DURATION / 2:.3f}[{out}]"
            )
            previous = out
        last_video = previous

    # --- video: overlay caption stream ---------------------------------------
    if captions_index is not None:
        filters.append(f"[{captions_index}:v]format=rgba,settb=AVTB[cap]")
        filters.append(
            f"[{last_video}][cap]overlay=0:0:eof_action=pass:format=auto[vcap]"
        )
        last_video = "vcap"

    # --- audio -----------------------------------------------------------------
    if music_index is not None:
        filters.append(
            f"[{narration_index}:a]loudnorm=I=-16:TP=-1.5:LRA=11,asplit=2[voice][voice_sc]"
        )
        filters.append(f"[{music_index}:a]volume={music_volume}[bgm0]")
        filters.append(
            "[bgm0][voice_sc]sidechaincompress=threshold=0.03:ratio=8:attack=80:release=500[bgm]"
        )
        filters.append("[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]")
    else:
        filters.append(f"[{narration_index}:a]loudnorm=I=-16:TP=-1.5:LRA=11[aout]")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            *inputs,
            "-filter_complex", ";".join(filters),
            "-map", f"[{last_video}]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-c:a", "aac",
            "-b:a", "192k",
            "-t", f"{total_duration:.3f}",
            "-movflags", "+faststart",
            str(output_path),
        ],
        description="renderização do vídeo final",
    )
