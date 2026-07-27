"""Modo join: junta N vídeos prontos com uma transição entre cada um."""

from pathlib import Path

from app.core.logging import get_logger
from app.modules.editing.render import (
    KeepSegment,
    _concat_copy,
    _crossfade_blocks,
    _extract_clip,
    _output_dims,
)
from app.modules.editing.transitions import XFADE_IDS
from app.modules.sources.media import probe_media
from app.modules.video.ffmpeg import probe_duration

logger = get_logger("editing.join")

TRANSITION_DURATION = 0.5


def render_join(
    source_paths: list[Path],
    output_path: Path,
    workdir: Path,
    transition: str = "fade",
    aspect: str = "9:16",
    on_progress=None,
) -> dict:
    """Normaliza cada vídeo e emenda com xfade (ou concat seco)."""
    if len(source_paths) < 2:
        raise RuntimeError("São necessários pelo menos 2 vídeos para juntar")

    if transition == "none":
        use_transitions = False
        xfade_name = "fade"
    else:
        use_transitions = True
        xfade_name = transition if transition in XFADE_IDS else "fade"

    infos = [probe_media(p) for p in source_paths]
    first = infos[0]
    width, height = _output_dims(first.width, first.height, aspect)
    fps = first.fps if 10 <= first.fps <= 60 else 30.0
    # Se qualquer clipe tiver áudio, geramos áudio em todos (silêncio nos mudos via extract)
    has_audio = any(info.has_audio for info in infos)

    workdir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    clips: list[Path] = []
    for i, (path, info) in enumerate(zip(source_paths, infos)):
        raw = workdir / f"clip_{i:04d}.mp4"
        segment = KeepSegment(start=0.0, end=max(info.duration, 0.05))
        _extract_clip(
            path,
            segment,
            raw,
            width,
            height,
            fps,
            has_audio=info.has_audio,
            punch_in=None,
        )
        # acrossfade exige áudio em todos os inputs quando algum clipe tem áudio
        if has_audio and not info.has_audio:
            clip = workdir / f"clip_{i:04d}_a.mp4"
            _ensure_silent_audio(raw, clip)
        else:
            clip = raw
        clips.append(clip)
        if on_progress:
            on_progress(i + 1, len(source_paths))

    if not use_transitions:
        _concat_copy(clips, output_path, workdir)
    else:
        _crossfade_blocks(
            clips,
            output_path,
            TRANSITION_DURATION,
            has_audio,
            xfade_name,
        )

    final_duration = probe_duration(output_path)
    source_duration = sum(info.duration for info in infos)
    logger.info(
        "Join: %d vídeos, transição=%s, %.1fs -> %.1fs",
        len(source_paths),
        xfade_name if use_transitions else "none",
        source_duration,
        final_duration,
    )
    return {
        "duration": final_duration,
        "source_duration": source_duration,
        "clips": len(source_paths),
        "transitions": (len(source_paths) - 1) if use_transitions else 0,
        "transition": xfade_name if use_transitions else "none",
        "aspect": aspect,
        "width": width,
        "height": height,
    }


def _ensure_silent_audio(clip: Path, output: Path) -> None:
    """Adiciona faixa de áudio silenciosa a um clipe sem áudio."""
    from app.modules.video.ffmpeg import run_ffmpeg

    duration = probe_duration(clip)
    run_ffmpeg(
        [
            "-i", str(clip),
            "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=48000",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-t", f"{duration:.3f}",
            "-movflags", "+faststart",
            str(output),
        ],
        description="áudio silencioso no clipe",
    )
