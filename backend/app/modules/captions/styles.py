"""Presets de estilo de legenda.

As legendas são renderizadas como PNGs transparentes (Pillow) e sobrepostas
no vídeo — com destaque palavra a palavra (estilo karaokê TikTok/Reels).
"""

from dataclasses import dataclass, field

RGB = tuple[int, int, int]


@dataclass
class CaptionStyle:
    name: str
    # Ordem de preferência de fontes (arquivos do macOS); usa a primeira que existir
    font_candidates: list[str] = field(
        default_factory=lambda: [
            "/System/Library/Fonts/Supplemental/Arial Black.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    )
    font_size: int = 78
    text_color: RGB = (255, 255, 255)       # palavras não destacadas
    highlight_color: RGB = (255, 231, 0)    # palavra sendo falada
    outline_color: RGB = (0, 0, 0)
    outline_width: int = 6
    margin_bottom: int = 620  # distância do centro do texto até a base do vídeo
    uppercase: bool = True
    max_words_per_block: int = 3
    highlight_scale: float = 1.08  # leve aumento da palavra ativa


PRESETS: dict[str, CaptionStyle] = {
    "default": CaptionStyle(name="default"),
    "minimal": CaptionStyle(
        name="minimal",
        font_candidates=[
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ],
        font_size=64,
        highlight_color=(255, 255, 255),
        outline_width=3,
        uppercase=False,
        max_words_per_block=4,
        highlight_scale=1.0,
    ),
    "green_pop": CaptionStyle(
        name="green_pop",
        font_size=84,
        highlight_color=(127, 255, 0),
        max_words_per_block=2,
    ),
}


def get_style(name: str | None) -> CaptionStyle:
    return PRESETS.get(name or "default", PRESETS["default"])
