"""Composição da arte final dos slides (Pillow): fundo IA + gradiente + tipografia.

Layout 1080x1350 (4:5, feed): fundo cover-crop, gradiente escuro na base,
headline em caixa bold, body de apoio, tag do projeto no topo e paginação
nos carrosséis.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

CANVAS_W, CANVAS_H = 1080, 1350
MARGIN = 84

HEADLINE_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
BODY_FONTS = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def _load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size)


def _hex_to_rgb(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        return None
    try:
        return tuple(int(v[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return None


def _paste_logo(canvas: Image.Image, logo_path: Path, x: int, y: int, max_h: int, max_w: int) -> int:
    """Cola a logo (respeitando transparência) e devolve a largura ocupada."""
    logo = Image.open(logo_path).convert("RGBA")
    scale = min(max_h / logo.height, max_w / logo.width, 1.0)
    size = (max(1, round(logo.width * scale)), max(1, round(logo.height * scale)))
    logo = logo.resize(size, Image.LANCZOS)
    canvas.paste(logo, (x, y), logo)
    return size[0]


def _cover_crop(image: Image.Image, width: int, height: int) -> Image.Image:
    scale = max(width / image.width, height / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)), Image.LANCZOS
    )
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_headline(draw: ImageDraw.ImageDraw, text: str, max_width: int) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    size = 88
    while size > 44:
        font = _load_font(HEADLINE_FONTS, size)
        lines = _wrap(draw, text, font, max_width)
        if len(lines) <= 3 and all(draw.textlength(l, font=font) <= max_width for l in lines):
            return font, lines
        size -= 6
    font = _load_font(HEADLINE_FONTS, 44)
    return font, _wrap(draw, text, font, max_width)


def compose_slide(
    background_path: Path,
    output_path: Path,
    headline: str,
    body: str = "",
    brand: str = "",
    slide_number: int | None = None,
    slide_total: int | None = None,
    show_swipe_hint: bool = False,
    logo_path: Path | None = None,
    accent_color: str | None = None,
    text_theme: str = "dark",
) -> None:
    light = text_theme == "light"
    accent = _hex_to_rgb(accent_color)

    # Cores de texto conforme o tema da marca
    text_color = (18, 18, 22) if light else (255, 255, 255)
    body_color = (60, 60, 68) if light else (226, 226, 232)
    stroke_color = (255, 255, 255) if light else (0, 0, 0)
    scrim_color = (248, 248, 250) if light else (8, 8, 12)
    muted = (90, 90, 98) if light else (235, 235, 240)

    canvas = _cover_crop(Image.open(background_path).convert("RGB"), CANVAS_W, CANVAS_H)

    # Gradiente para legibilidade: escurece (ou clareia) a base e o topo
    overlay = Image.new("L", (1, CANVAS_H), 0)
    for y in range(CANVAS_H):
        t = y / CANVAS_H
        alpha = int(55 * max(0.0, 0.28 - t) / 0.28)  # topo (logo/paginação)
        if t > 0.45:
            alpha = int(238 * ((t - 0.45) / 0.55) ** 1.4)  # base (texto)
        overlay.putpixel((0, y), min(alpha, 238))
    gradient = overlay.resize((CANVAS_W, CANVAS_H))
    scrim = Image.new("RGB", (CANVAS_W, CANVAS_H), scrim_color)
    canvas = Image.composite(scrim, canvas, gradient)

    draw = ImageDraw.Draw(canvas)
    max_text_width = CANVAS_W - 2 * MARGIN

    # Topo: logo (se houver) senão nome do projeto; paginação à direita
    tag_font = _load_font(BODY_FONTS, 30)
    if logo_path is not None and logo_path.exists():
        try:
            _paste_logo(canvas, logo_path, MARGIN, MARGIN - 18, max_h=66, max_w=340)
        except Exception:  # noqa: BLE001 — logo inválida não deve quebrar a arte
            if brand:
                draw.text((MARGIN, MARGIN - 14), brand.upper(), font=tag_font, fill=muted)
    elif brand:
        draw.text(
            (MARGIN, MARGIN - 14),
            brand.upper(),
            font=tag_font,
            fill=muted,
            stroke_width=1,
            stroke_fill=stroke_color,
        )
    if slide_number is not None and slide_total is not None and slide_total > 1:
        page = f"{slide_number}/{slide_total}"
        page_width = draw.textlength(page, font=tag_font)
        draw.text(
            (CANVAS_W - MARGIN - page_width, MARGIN - 14),
            page,
            font=tag_font,
            fill=accent or muted,
            stroke_width=1,
            stroke_fill=stroke_color,
        )

    # Texto ancorado na base
    body_font = _load_font(BODY_FONTS, 40)
    body_lines = _wrap(draw, body, body_font, max_text_width) if body.strip() else []
    headline_font, headline_lines = _fit_headline(draw, headline, max_text_width)

    headline_line_height = int(headline_font.size * 1.16)
    body_line_height = int(body_font.size * 1.35)
    block_height = (
        len(headline_lines) * headline_line_height
        + (24 + len(body_lines) * body_line_height if body_lines else 0)
    )
    y = CANVAS_H - MARGIN - 30 - block_height
    if show_swipe_hint:
        y -= 46

    # Barra de acento na cor da marca acima da headline
    if accent:
        bar_y = y - 26
        draw.rectangle([MARGIN, bar_y, MARGIN + 76, bar_y + 8], fill=accent)

    for line in headline_lines:
        draw.text(
            (MARGIN, y),
            line,
            font=headline_font,
            fill=text_color,
            stroke_width=2,
            stroke_fill=stroke_color,
        )
        y += headline_line_height
    if body_lines:
        y += 24
        for line in body_lines:
            draw.text((MARGIN, y), line, font=body_font, fill=body_color)
            y += body_line_height

    if show_swipe_hint:
        hint_font = _load_font(BODY_FONTS, 34)
        hint = "deslize  ›"
        hint_width = draw.textlength(hint, font=hint_font)
        draw.text(
            (CANVAS_W - MARGIN - hint_width, CANVAS_H - MARGIN - 20),
            hint,
            font=hint_font,
            fill=accent or muted,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas = canvas.filter(ImageFilter.SHARPEN)
    canvas.save(output_path, "JPEG", quality=90)
