"""Magazine-style JPEG cover art for Kindle library thumbnails."""

from __future__ import annotations

import io
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Amazon Send-to-Kindle / KDP recommended portrait ratio (width × height = 1:1.6)
COVER_WIDTH = 1600
COVER_HEIGHT = 2560

# Magazine palette
BG = (13, 13, 18)
ACCENT = (220, 38, 38)
MASTHEAD_BG = (220, 38, 38)
TEXT = (250, 248, 245)
SUBTEXT = (180, 176, 168)
RULE = (80, 76, 72)

# All cover typography scaled +30% for Kindle legibility
FONT_SCALE = 1.3

_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


def _scaled(size: int) -> int:
    return round(size * FONT_SCALE)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = _FONT_CANDIDATES if bold else (
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        *_FONT_CANDIDATES,
    )
    for path in paths:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = (text or "").split()
    if not words:
        return []
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        if draw.textlength(trial, font=font) <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def render_magazine_cover(
    masthead: str,
    headline: str,
    edition_line: str = "",
    teasers: list[str] | None = None,
    teasers_label: str = "",
    editorial: str = "",
) -> bytes:
    """
    Render a portrait magazine-style cover as JPEG bytes.

    Intended for EPUB ``cover-image`` metadata (Kindle library shelf thumbnail).
    """
    img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    margin_x = 40
    content_w = COVER_WIDTH - 2 * margin_x
    y = 0

    # Masthead band
    band_h = _scaled(200)
    draw.rectangle((0, 0, COVER_WIDTH, band_h), fill=MASTHEAD_BG)
    masthead_font = _load_font(_scaled(52), bold=True)
    draw.text((margin_x, _scaled(70)), (masthead or "BiteSIze").upper(), fill=TEXT, font=masthead_font)
    y = band_h + _scaled(80)

    # Edition kicker
    if edition_line:
        kicker_font = _load_font(_scaled(36))
        draw.text((margin_x, y), edition_line, fill=SUBTEXT, font=kicker_font)
        y += _scaled(70)

    # Headline — large serif, magazine stack
    headline_font = _load_font(_scaled(96), bold=True)
    headline_lines = _wrap(draw, headline or masthead, headline_font, content_w)
    for line in headline_lines[:6]:
        draw.text((margin_x, y), line, fill=TEXT, font=headline_font)
        y += _scaled(110)
    y += _scaled(40)

    # Accent rule (no editorial on cover — that lives on the opening spread)
    draw.rectangle((margin_x, y, margin_x + _scaled(180), y + _scaled(8)), fill=ACCENT)
    y += _scaled(50)

    # Inside teasers — distinct stories per section, never the cover line
    blurbs = [h.strip() for h in (teasers or []) if h and h.strip()]
    if blurbs:
        y = max(y, COVER_HEIGHT - _scaled(580))
        if teasers_label:
            label_font = _load_font(_scaled(30))
            draw.text((margin_x, y), teasers_label.upper(), fill=SUBTEXT, font=label_font)
            y += _scaled(44)
        draw.line((margin_x, y, COVER_WIDTH - margin_x, y), fill=RULE, width=2)
        y += _scaled(36)
        blurb_font = _load_font(_scaled(34))
        for blurb in blurbs[:3]:
            wrapped = _wrap(draw, f"▸ {blurb}", blurb_font, content_w)
            for line in wrapped[:2]:
                draw.text((margin_x, y), line, fill=TEXT, font=blurb_font)
                y += _scaled(46)
            y += _scaled(12)

    # Footer branding
    footer_font = _load_font(_scaled(28))
    draw.text(
        (margin_x, COVER_HEIGHT - _scaled(80)),
        "BiteSIze",
        fill=RULE,
        font=footer_font,
    )

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()
