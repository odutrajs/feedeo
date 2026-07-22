"""Presets de estilo do modo edit.

Cada estilo é um conjunto de parâmetros que controla o quão agressiva é a
edição automática (cortes de silêncio, vícios de fala) e o acabamento do
render (transições, punch-ins de zoom).

Referências dos presets:
- dynamic: ritmo TikTok/Reels — jump cuts agressivos e punch-in alternado.
- vlog: ritmo YouTube casual — cortes médios, crossfade em saltos grandes.
- clean: educacional/corporativo — só remove ar morto longo, sem zoom.
- podcast: longform — remove apenas silêncios muito longos, nada mais.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EditStyle:
    id: str
    label: str
    description: str
    # --- análise ---------------------------------------------------------
    # Gap de fala (s) acima do qual o trecho vira corte de silêncio
    silence_gap: float = 0.8
    # Respiro mantido em volta da fala ao cortar silêncio (s)
    pad_before_speech: float = 0.12
    pad_after_speech: float = 0.18
    # Remove hesitações alongadas ("ééé", "hummm")
    remove_fillers: bool = True
    # Pausa (s) que separa duas "frases" para detecção de retake
    utterance_gap: float = 0.7
    # Similaridade mínima (0-100) para considerar uma frase retake da anterior
    retake_similarity: float = 78.0
    # --- render ----------------------------------------------------------
    # Crossfade em cortes que removeram mais que `transition_min_removed` segundos
    transitions: bool = False
    transition_duration: float = 0.35
    transition_min_removed: float = 3.0
    # Punch-in: alterna zoom sutil entre clipes consecutivos (estilo talking head)
    punch_in: bool = False
    punch_in_zoom: float = 1.08
    extra: dict = field(default_factory=dict)


EDIT_STYLES: dict[str, EditStyle] = {
    style.id: style
    for style in [
        EditStyle(
            id="dynamic",
            label="Dinâmico (TikTok/Reels)",
            description=(
                "Jump cuts agressivos, zero ar morto, punch-in de zoom alternado. "
                "Ideal para conteúdo rápido de rede social."
            ),
            silence_gap=0.35,
            pad_before_speech=0.08,
            pad_after_speech=0.10,
            remove_fillers=True,
            transitions=False,
            punch_in=True,
        ),
        EditStyle(
            id="vlog",
            label="Vlog (YouTube casual)",
            description=(
                "Cortes de ritmo médio, crossfade suave quando um trecho grande é "
                "removido. O clássico estilo vlog."
            ),
            silence_gap=0.6,
            pad_before_speech=0.10,
            pad_after_speech=0.15,
            remove_fillers=True,
            transitions=True,
        ),
        EditStyle(
            id="clean",
            label="Educacional / Clean",
            description=(
                "Remove só o ar morto mais longo e os erros; preserva o ritmo "
                "natural da fala. Para aulas, tutoriais e conteúdo corporativo."
            ),
            silence_gap=1.0,
            pad_before_speech=0.15,
            pad_after_speech=0.25,
            remove_fillers=False,
            transitions=True,
        ),
        EditStyle(
            id="podcast",
            label="Podcast / Longform",
            description=(
                "Só limpeza: remove silêncios muito longos e trechos marcados com "
                "'corta'. Não mexe no ritmo da conversa."
            ),
            silence_gap=2.0,
            pad_before_speech=0.25,
            pad_after_speech=0.35,
            remove_fillers=False,
            transitions=False,
        ),
    ]
}

DEFAULT_STYLE_ID = "vlog"


def get_style(style_id: str | None) -> EditStyle:
    return EDIT_STYLES.get(style_id or "", EDIT_STYLES[DEFAULT_STYLE_ID])
