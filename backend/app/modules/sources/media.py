"""Utilitários ffmpeg para mídia enviada pelo usuário: probe, detecção de cortes,
thumbnails e previews de segmentos."""

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.logging import get_logger
from app.modules.video.ffmpeg import run_ffmpeg

logger = get_logger("sources.media")

# Segmentação: cortes de cena + janelas de tamanho controlado
SCENE_THRESHOLD = 0.30
MIN_SEGMENT_SECONDS = 1.2
MAX_SEGMENT_SECONDS = 10.0
FALLBACK_WINDOW_SECONDS = 5.0


@dataclass
class MediaInfo:
    duration: float
    width: int
    height: int
    has_audio: bool
    fps: float


def probe_media(path: Path) -> MediaInfo:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-show_streams",
            "-of", "json", str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe falhou para {path.name}: {result.stderr[-500:]}")
    data = json.loads(result.stdout)
    duration = float(data.get("format", {}).get("duration") or 0.0)
    width = height = 0
    fps = 30.0
    has_audio = False
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and not width:
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
            rate = stream.get("avg_frame_rate") or "30/1"
            try:
                num, den = rate.split("/")
                fps = float(num) / float(den) if float(den) else 30.0
            except (ValueError, ZeroDivisionError):
                fps = 30.0
        if stream.get("codec_type") == "audio":
            has_audio = True
    return MediaInfo(duration=duration, width=width, height=height, has_audio=has_audio, fps=fps)


def detect_scene_cuts(path: Path, threshold: float = SCENE_THRESHOLD) -> list[float]:
    """Retorna os timestamps (s) onde há troca de cena/plano no vídeo."""
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-i", str(path),
            "-vf", f"select='gt(scene,{threshold})',metadata=print:file=-",
            "-an", "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
    )
    cuts: list[float] = []
    for line in result.stdout.splitlines():
        match = re.search(r"pts_time:([\d.]+)", line)
        if match:
            cuts.append(float(match.group(1)))
    return sorted(set(cuts))


def build_segments(duration: float, cuts: list[float]) -> list[tuple[float, float]]:
    """Converte cortes em segmentos [start, end), mesclando os muito curtos e
    quebrando os muito longos em janelas."""
    boundaries = [0.0] + [c for c in cuts if 0.0 < c < duration] + [duration]
    raw = [(boundaries[i], boundaries[i + 1]) for i in range(len(boundaries) - 1)]

    # Mescla segmentos curtos demais com o seguinte
    merged: list[tuple[float, float]] = []
    for start, end in raw:
        if merged and (end - start) < MIN_SEGMENT_SECONDS:
            prev_start, _ = merged[-1]
            merged[-1] = (prev_start, end)
        elif not merged and (end - start) < MIN_SEGMENT_SECONDS:
            merged.append((start, end))
        else:
            merged.append((start, end))
    # Um segmento inicial minúsculo pode ter sobrado: mescla com o próximo
    if len(merged) >= 2 and (merged[0][1] - merged[0][0]) < MIN_SEGMENT_SECONDS:
        merged[1] = (merged[0][0], merged[1][1])
        merged.pop(0)

    # Quebra segmentos longos em janelas de tamanho razoável
    final: list[tuple[float, float]] = []
    for start, end in merged:
        length = end - start
        if length <= MAX_SEGMENT_SECONDS:
            final.append((start, end))
            continue
        pieces = max(int(round(length / FALLBACK_WINDOW_SECONDS)), 2)
        step = length / pieces
        for i in range(pieces):
            final.append((start + i * step, start + (i + 1) * step))

    return [(round(s, 3), round(e, 3)) for s, e in final if (e - s) >= 0.4]


def extract_thumbnail(video_path: Path, at_second: float, output: Path, width: int = 480) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-ss", f"{max(at_second, 0):.3f}",
            "-i", str(video_path),
            "-frames:v", "1",
            "-vf", f"scale={width}:-2",
            "-q:v", "3",
            str(output),
        ],
        description=f"thumbnail em {at_second:.1f}s",
    )


def extract_preview(video_path: Path, start: float, end: float, output: Path, height: int = 540) -> None:
    """Gera um clipe mp4 leve do segmento para pré-visualização no painel."""
    output.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-ss", f"{max(start, 0):.3f}",
            "-t", f"{max(end - start, 0.1):.3f}",
            "-i", str(video_path),
            "-vf", f"scale=-2:{height}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
            "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart",
            str(output),
        ],
        description=f"preview do segmento {start:.1f}-{end:.1f}s",
    )


def make_image_thumbnail(image_path: Path, output: Path, width: int = 480) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        ["-i", str(image_path), "-vf", f"scale={width}:-2", "-q:v", "3", str(output)],
        description="thumbnail de imagem",
    )
