"""Módulo 7: legendas com destaque palavra a palavra (estilo karaokê).

O FFmpeg do Homebrew não inclui libass, então as legendas são renderizadas
como PNGs transparentes em tamanho de tela cheia (um por estado de palavra
destacada) e viram um stream de vídeo via concat demuxer, sobreposto ao
vídeo final com um único filtro overlay — rápido e com controle total de
estilo.
"""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.modules.captions.styles import CaptionStyle


@dataclass
class CaptionFrame:
    path: Path
    start: float
    end: float


def _load_font(style: CaptionStyle, size: int) -> ImageFont.FreeTypeFont:
    for candidate in style.font_candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size)


def group_words(words: list[dict], max_words: int, max_span: float = 1.6) -> list[list[dict]]:
    """Split the word stream into short caption blocks (TikTok/Reels style)."""
    blocks: list[list[dict]] = []
    current: list[dict] = []
    for word in words:
        if current:
            span = word["end"] - current[0]["start"]
            scene_changed = word["scene_index"] != current[0]["scene_index"]
            if len(current) >= max_words or span > max_span or scene_changed:
                blocks.append(current)
                current = []
        current.append(word)
    if current:
        blocks.append(current)
    return blocks


def _render_block_frame(
    texts: list[str],
    highlight_index: int,
    style: CaptionStyle,
    width: int,
    height: int,
) -> Image.Image:
    """Render one full-frame transparent PNG with the block's words,
    highlighting the word at `highlight_index`."""
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    max_text_width = width - 120
    font_size = style.font_size
    font = _load_font(style, font_size)
    space = draw.textlength("  ", font=font)

    def total_width(f: ImageFont.FreeTypeFont, sp: float) -> float:
        return sum(draw.textlength(t, font=f) for t in texts) + sp * (len(texts) - 1)

    # Auto-shrink until the block fits on one line
    while total_width(font, space) > max_text_width and font_size > 30:
        font_size -= 4
        font = _load_font(style, font_size)
        space = draw.textlength("  ", font=font)

    highlight_font = (
        _load_font(style, int(font_size * style.highlight_scale))
        if style.highlight_scale != 1.0
        else font
    )

    line_width = total_width(font, space)
    x = (width - line_width) / 2
    baseline_y = height - style.margin_bottom

    for i, text in enumerate(texts):
        word_width = draw.textlength(text, font=font)
        is_highlight = i == highlight_index
        use_font = highlight_font if is_highlight else font
        color = style.highlight_color if is_highlight else style.text_color
        # Center the (possibly larger) highlighted word inside its slot
        slot_center = x + word_width / 2
        draw.text(
            (slot_center, baseline_y),
            text,
            font=use_font,
            fill=(*color, 255),
            anchor="mm",
            stroke_width=style.outline_width,
            stroke_fill=(*style.outline_color, 255),
        )
        x += word_width + space

    return canvas


def render_caption_frames(
    words: list[dict],
    style: CaptionStyle,
    output_dir: Path,
    width: int,
    height: int,
) -> list[CaptionFrame]:
    """Render one PNG per highlighted-word state, with its visibility window."""
    output_dir.mkdir(parents=True, exist_ok=True)
    blocks = group_words(words, style.max_words_per_block)
    frames: list[CaptionFrame] = []

    for block_index, block in enumerate(blocks):
        texts = [
            (w["text"].upper() if style.uppercase else w["text"]).strip() for w in block
        ]
        block_start = block[0]["start"]
        natural_end = block[-1]["end"] + 0.25
        if block_index + 1 < len(blocks):
            natural_end = min(natural_end, blocks[block_index + 1][0]["start"])
        block_end = max(natural_end, block_start + 0.15)

        for word_index in range(len(block)):
            start = block_start if word_index == 0 else block[word_index]["start"]
            end = (
                block[word_index + 1]["start"]
                if word_index + 1 < len(block)
                else block_end
            )
            if end <= start:
                continue
            image = _render_block_frame(texts, word_index, style, width, height)
            path = output_dir / f"cap_{block_index:03d}_{word_index}.png"
            image.save(path)
            frames.append(CaptionFrame(path=path, start=start, end=end))

    return frames


def write_concat_file(
    frames: list[CaptionFrame],
    blank_path: Path,
    concat_path: Path,
    total_duration: float,
    width: int,
    height: int,
) -> Path:
    """Build an ffmpeg concat script turning the PNGs into a timed video stream.

    Gaps between caption windows are filled with a fully transparent frame.
    """
    Image.new("RGBA", (width, height), (0, 0, 0, 0)).save(blank_path)

    lines = ["ffconcat version 1.0"]
    cursor = 0.0
    for frame in frames:
        if frame.start > cursor + 0.001:
            lines.append(f"file '{blank_path.name}'")
            lines.append(f"duration {frame.start - cursor:.3f}")
        lines.append(f"file '{frame.path.name}'")
        lines.append(f"duration {frame.end - frame.start:.3f}")
        cursor = frame.end
    if cursor < total_duration:
        lines.append(f"file '{blank_path.name}'")
        lines.append(f"duration {total_duration - cursor:.3f}")
    # concat demuxer requires the last file listed twice to honor its duration
    lines.append(f"file '{blank_path.name}'")

    concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return concat_path
