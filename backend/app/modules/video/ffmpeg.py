"""Helpers finos sobre os binários ffmpeg/ffprobe."""

import json
import subprocess
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger("ffmpeg")


def run_ffmpeg(args: list[str], description: str = "ffmpeg") -> None:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    logger.debug("%s: %s", description, " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{description} falhou: {result.stderr[-2000:]}")


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe falhou para {path}: {result.stderr[-500:]}")
    return float(json.loads(result.stdout)["format"]["duration"])
