"""Catálogo de transições do modo edit + geração das prévias de exemplo.

Cada transição (exceto "auto") tem uma prévia em vídeo gerada com FFmpeg:
dois clipes de gradiente animado emendados com o xfade correspondente.
As prévias são geradas sob demanda e cacheadas em storage/transitions/.
"""

from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.video.ffmpeg import run_ffmpeg

logger = get_logger("editing.transitions")

PREVIEW_SIZE = "480x270"
PREVIEW_CLIP_SECONDS = 1.3
PREVIEW_TRANSITION_SECONDS = 0.5


@dataclass(frozen=True)
class Transition:
    id: str  # nome do xfade ("none" = corte seco, "auto" = decidido pelo estilo)
    label: str
    description: str


TRANSITIONS: list[Transition] = [
    Transition("auto", "Automático", "Segue o estilo de edição escolhido"),
    Transition("none", "Corte seco", "Sem transição — o clássico jump cut"),
    Transition("fade", "Crossfade", "Fusão suave entre os trechos"),
    Transition("fadeblack", "Fade preto", "Escurece e revela o próximo trecho"),
    Transition("fadewhite", "Flash branco", "Clarão rápido entre os trechos"),
    Transition("dissolve", "Dissolve", "Fusão granulada, textura de filme"),
    Transition("smoothleft", "Varredura", "Varredura suave da direita para a esquerda"),
    Transition("slideleft", "Deslizar", "O próximo trecho empurra o atual"),
    Transition("circleopen", "Círculo", "O próximo trecho abre em círculo"),
    Transition("radial", "Radial", "Varredura em ponteiro de relógio"),
    Transition("pixelize", "Pixelizado", "Transição em mosaico de pixels"),
    Transition("hblur", "Desfoque", "Borra e revela o próximo trecho"),
    Transition("zoomin", "Zoom", "Mergulha com zoom no próximo trecho"),
]

TRANSITION_IDS = {t.id for t in TRANSITIONS}
# xfade válidos (sem os pseudo-ids)
XFADE_IDS = TRANSITION_IDS - {"auto", "none"}


def previews_dir() -> Path:
    return get_settings().storage_dir / "transitions"


def preview_relpath(transition_id: str) -> str | None:
    if transition_id == "auto":
        return None
    return f"transitions/{transition_id}.mp4"


def _clip_source(color_a: str, color_b: str) -> str:
    return (
        f"gradients=size={PREVIEW_SIZE}:speed=0.6:nb_colors=2:"
        f"c0={color_a}:c1={color_b}:duration={PREVIEW_CLIP_SECONDS + 1.0}:rate=30"
    )


def _generate_preview(transition_id: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    clip_a = _clip_source("0x6d28d9", "0x0ea5e9")  # roxo -> azul
    clip_b = _clip_source("0xf59e0b", "0xec4899")  # laranja -> rosa

    if transition_id == "none":
        # Corte seco: os dois clipes emendados sem transição
        filters = (
            f"[0:v]trim=duration={PREVIEW_CLIP_SECONDS},setpts=PTS-STARTPTS[a];"
            f"[1:v]trim=duration={PREVIEW_CLIP_SECONDS},setpts=PTS-STARTPTS[b];"
            "[a][b]concat=n=2:v=1:a=0[v]"
        )
    else:
        offset = PREVIEW_CLIP_SECONDS - PREVIEW_TRANSITION_SECONDS / 2
        filters = (
            f"[0:v][1:v]xfade=transition={transition_id}:"
            f"duration={PREVIEW_TRANSITION_SECONDS}:offset={offset:.3f}[v]"
        )

    run_ffmpeg(
        [
            "-f", "lavfi", "-i", clip_a,
            "-f", "lavfi", "-i", clip_b,
            "-filter_complex", filters,
            "-map", "[v]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output),
        ],
        description=f"prévia da transição {transition_id}",
    )


def ensure_previews() -> None:
    """Gera as prévias que ainda não existem (idempotente, roda em segundos)."""
    for transition in TRANSITIONS:
        rel = preview_relpath(transition.id)
        if rel is None:
            continue
        output = get_settings().storage_dir / rel
        if output.is_file():
            continue
        try:
            _generate_preview(transition.id, output)
        except Exception:  # noqa: BLE001
            logger.exception("Falha ao gerar prévia da transição %s", transition.id)
