"""Miniatura 1280x720: fotograma del metraje + texto grande con contorno."""
from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from .media import run

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def make_thumbnail(clip: Path, text: str, channel: str, out: Path) -> Path:
    frame = out.with_suffix(".frame.png")
    run(["-ss", "1.5", "-i", str(clip), "-frames:v", "1",
         "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720", str(frame)])
    img = Image.open(frame).convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.25)
    img = ImageEnhance.Color(img).enhance(1.3)

    # Degradado oscuro a la izquierda para que el texto se lea.
    shade = Image.new("L", img.size)
    px = shade.load()
    for x in range(img.width):
        alpha = int(210 * max(0.0, 1 - x / (img.width * 0.75)))
        for y in range(img.height):
            px[x, y] = alpha
    img.paste(Image.new("RGB", img.size, (0, 8, 20)), (0, 0), shade)

    draw = ImageDraw.Draw(img)
    text = text.upper().strip()
    size = 180
    while size > 60:
        font = _font(size)
        wrapped = "\n".join(textwrap.wrap(text, width=max(6, int(1600 / size))))
        box = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=10, stroke_width=8)
        if box[2] - box[0] <= 1000 and box[3] - box[1] <= 440:
            break
        size -= 6
    y = (img.height - (box[3] - box[1])) // 2 - 20
    draw.multiline_text((60, y), wrapped, font=font, fill=(255, 255, 255), spacing=10,
                        stroke_width=8, stroke_fill=(0, 0, 0))
    draw.rectangle([60, y - 26, 260, y - 14], fill=(0, 200, 255))
    draw.text((60, img.height - 70), channel.upper(), font=_font(36), fill=(0, 200, 255),
              stroke_width=3, stroke_fill=(0, 0, 0))
    img.save(out, "JPEG", quality=90)
    frame.unlink(missing_ok=True)
    return out
