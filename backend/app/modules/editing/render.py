"""Modo edit: renderiza o corte final a partir dos trechos mantidos.

Estratégia em duas passadas (robusta para dezenas/centenas de jump cuts):

1. Extrai cada trecho mantido como um clipe normalizado (mesmo fps, mesma
   resolução, micro-fades de áudio para não estalar no corte; punch-in de
   zoom alternado quando o estilo pede).
2. Junta os clipes. Cortes normais viram hard cuts (concat sem re-encode);
   nos cortes que removeram um trecho grande do original, os blocos são
   emendados com a transição escolhida (xfade + acrossfade).
3. Passada final de áudio: tratamento de voz (highpass, denoise, de-esser,
   compressão) + loudnorm, com o vídeo copiado sem re-encode.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path

from app.core.logging import get_logger
from app.modules.editing.styles import EditStyle
from app.modules.editing.transitions import XFADE_IDS
from app.modules.sources.media import probe_media
from app.modules.video.ffmpeg import probe_duration, run_ffmpeg

logger = get_logger("editing.render")

AUDIO_FADE = 0.02  # micro-fade nos cortes (s) para evitar cliques

# Formatos de saída por plataforma
ASPECT_PRESETS: dict[str, tuple[int, int] | None] = {
    "original": None,
    "9:16": (1080, 1920),  # TikTok / Reels / Shorts / Stories
    "4:5": (1080, 1350),  # Feed do Instagram
    "1:1": (1080, 1080),  # Quadrado (feed)
    "16:9": (1920, 1080),  # YouTube / horizontal
}

# Cadeias de tratamento de voz (aplicadas na passada final de áudio)
AUDIO_CHAINS: dict[str, str | None] = {
    # off: áudio original, sem processamento
    "off": None,
    # light: remove ronco grave + normaliza o volume
    "light": "highpass=f=75,loudnorm=I=-16:TP=-1.5:LRA=11",
    # full: voz de estúdio — highpass, redução de ruído, de-esser,
    # compressão suave e normalização broadcast
    "full": (
        "highpass=f=75,"
        "afftdn=nr=12:nf=-28,"
        "deesser=i=0.4,"
        "acompressor=threshold=0.125:ratio=3:attack=5:release=180,"
        "loudnorm=I=-16:TP=-1.5:LRA=11"
    ),
}


@dataclass
class KeepSegment:
    start: float  # tempo no vídeo-fonte
    end: float
    # segundos removidos entre o fim do trecho anterior e este (para transições)
    removed_before: float = 0.0

    @property
    def duration(self) -> float:
        return self.end - self.start


def _output_dims(src_w: int, src_h: int, aspect: str) -> tuple[int, int]:
    preset = ASPECT_PRESETS.get(aspect)
    if preset is not None:
        return preset
    # original: só garante dimensões pares
    return max(src_w - src_w % 2, 2), max(src_h - src_h % 2, 2)


def _extract_clip(
    source: Path,
    segment: KeepSegment,
    output: Path,
    width: int,
    height: int,
    fps: float,
    has_audio: bool,
    punch_in: float | None,
) -> None:
    vf = (
        f"fps={fps:.3f},"
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
    )
    if punch_in:
        vf += (
            f",scale=trunc(iw*{punch_in:.3f}/2)*2:trunc(ih*{punch_in:.3f}/2)*2"
            f",crop={width}:{height}"
        )
    vf += ",setsar=1,format=yuv420p"

    args = [
        "-ss", f"{segment.start:.3f}",
        "-t", f"{max(segment.duration, 0.05):.3f}",
        "-i", str(source),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
    ]
    if has_audio:
        fade_out = max(segment.duration - AUDIO_FADE, 0.0)
        args += [
            "-af",
            f"aresample=48000,afade=t=in:st=0:d={AUDIO_FADE},"
            f"afade=t=out:st={fade_out:.3f}:d={AUDIO_FADE}",
            "-c:a", "aac", "-b:a", "192k", "-ac", "2",
        ]
    else:
        args += ["-an"]
    args += ["-movflags", "+faststart", str(output)]
    run_ffmpeg(args, description=f"clipe {segment.start:.1f}-{segment.end:.1f}s")


def _concat_copy(clips: list[Path], output: Path, workdir: Path) -> None:
    if len(clips) == 1:
        shutil.copyfile(clips[0], output)
        return
    list_file = workdir / f"{output.stem}_list.txt"
    list_file.write_text(
        "".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8"
    )
    run_ffmpeg(
        ["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output)],
        description=f"concat de {len(clips)} clipes",
    )


def _crossfade_blocks(
    blocks: list[Path],
    output: Path,
    duration: float,
    has_audio: bool,
    transition: str = "fade",
) -> None:
    """Emenda blocos com xfade/acrossfade (poucos blocos; re-encode)."""
    durations = [probe_duration(b) for b in blocks]
    inputs: list[str] = []
    for block in blocks:
        inputs += ["-i", str(block)]

    filters: list[str] = []
    cum = durations[0]
    prev_v, prev_a = "0:v", "0:a"
    for i in range(1, len(blocks)):
        offset = max(cum - duration, 0.0)
        out_v = f"xv{i}"
        filters.append(
            f"[{prev_v}][{i}:v]xfade=transition={transition}:"
            f"duration={duration}:offset={offset:.3f}[{out_v}]"
        )
        prev_v = out_v
        if has_audio:
            out_a = f"xa{i}"
            filters.append(
                f"[{prev_a}][{i}:a]acrossfade=d={duration}:c1=tri:c2=tri[{out_a}]"
            )
            prev_a = out_a
        cum += durations[i] - duration

    args = [
        *inputs,
        "-filter_complex", ";".join(filters),
        "-map", f"[{prev_v}]",
    ]
    if has_audio:
        args += ["-map", f"[{prev_a}]", "-c:a", "aac", "-b:a", "192k"]
    args += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output),
    ]
    run_ffmpeg(args, description=f"crossfade de {len(blocks)} blocos")


def _process_audio(source: Path, output: Path, chain: str) -> None:
    run_ffmpeg(
        [
            "-i", str(source),
            "-c:v", "copy",
            "-af", chain,
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(output),
        ],
        description="tratamento de áudio",
    )


def render_edit(
    source_path: Path,
    segments: list[KeepSegment],
    style: EditStyle,
    output_path: Path,
    workdir: Path,
    aspect: str = "original",
    transition: str = "auto",
    audio_enhance: str = "full",
    on_progress=None,
) -> dict:
    """Renderiza o corte final; retorna metadados (duração, nº de cortes...)."""
    if not segments:
        raise RuntimeError("Nenhum trecho mantido para renderizar")

    # Resolve a transição efetiva: auto segue o estilo; ids inválidos viram fade
    if transition == "auto":
        use_transitions = style.transitions
        xfade_name = "fade"
    elif transition == "none":
        use_transitions = False
        xfade_name = "fade"
    else:
        use_transitions = True
        xfade_name = transition if transition in XFADE_IDS else "fade"

    info = probe_media(source_path)
    width, height = _output_dims(info.width, info.height, aspect)
    fps = info.fps if 10 <= info.fps <= 60 else 30.0
    workdir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Passada 1: extrai cada trecho mantido como clipe normalizado
    clips: list[Path] = []
    for i, segment in enumerate(segments):
        clip = workdir / f"seg_{i:04d}.mp4"
        punch = (
            style.punch_in_zoom if style.punch_in and i % 2 == 1 else None
        )
        _extract_clip(
            source_path, segment, clip, width, height, fps, info.has_audio, punch
        )
        clips.append(clip)
        if on_progress:
            on_progress(i + 1, len(segments))

    # Passada 2: agrupa em blocos (hard cut dentro do bloco, transição entre blocos)
    blocks: list[list[Path]] = [[clips[0]]]
    for clip, segment in zip(clips[1:], segments[1:]):
        needs_transition = (
            use_transitions and segment.removed_before >= style.transition_min_removed
        )
        if needs_transition:
            blocks.append([clip])
        else:
            blocks[-1].append(clip)

    block_files: list[Path] = []
    for i, block in enumerate(blocks):
        block_file = workdir / f"block_{i:03d}.mp4"
        _concat_copy(block, block_file, workdir)
        block_files.append(block_file)

    joined = workdir / "joined.mp4"
    if len(block_files) == 1:
        shutil.copyfile(block_files[0], joined)
    else:
        _crossfade_blocks(
            block_files, joined, style.transition_duration, info.has_audio, xfade_name
        )

    audio_chain = AUDIO_CHAINS.get(audio_enhance, AUDIO_CHAINS["full"])
    if info.has_audio and audio_chain:
        _process_audio(joined, output_path, audio_chain)
    else:
        shutil.copyfile(joined, output_path)

    final_duration = probe_duration(output_path)
    logger.info(
        "Render: %d trechos, %d blocos, %.1fs -> %.1fs",
        len(segments), len(blocks), info.duration, final_duration,
    )
    return {
        "duration": final_duration,
        "source_duration": info.duration,
        "segments": len(segments),
        "transitions": len(blocks) - 1,
        "transition": xfade_name if use_transitions and len(blocks) > 1 else "none",
        "audio_enhance": audio_enhance if info.has_audio else "off",
        "aspect": aspect,
        "width": width,
        "height": height,
    }
