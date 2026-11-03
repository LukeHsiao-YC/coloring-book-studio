"""Interior PDF and cover wrap for KDP."""
from __future__ import annotations

import os
from pathlib import Path

import reportlab
from reportlab import rl_config
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import STATE_DEFAULTS
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from svglib.svglib import svg2rlg

from . import config

_FONT_DIR = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
pdfmetrics.registerFont(TTFont("CBS", os.path.join(_FONT_DIR, "Vera.ttf")))      # embedded, KDP-safe
pdfmetrics.registerFont(TTFont("CBS-Bold", os.path.join(_FONT_DIR, "VeraBd.ttf")))
# reportlab and svglib default to the non-embedded Helvetica / Times-Roman; KDP rejects those
rl_config.canvas_basefontname = "CBS"
STATE_DEFAULTS["fontName"] = "CBS"


def margin(trim: str) -> float:
    return config.ART_SAFE_MARGIN_BY_TRIM.get(trim, config.ART_SAFE_MARGIN_IN)


def caption_band(trim: str) -> float:
    return config.CAPTION_BAND_IN.get(trim, 0.75)


def art_box(trim: str) -> tuple[float, float]:
    w, h = config.TRIM_SIZES[trim]
    m = margin(trim)
    return (w - 2 * m, h - 2 * m)


def place_svg(c, svg: Path, x: float, y: float, box_w: float, box_h: float):
    """Draw an SVG centred in the box; returns (left, bottom, scale, svg_width, svg_height)."""
    d = svg2rlg(str(svg))
    W, H = d.width, d.height
    s = min(box_w / W, box_h / H)
    d.scale(s, s)
    ox, oy = x + (box_w - W * s) / 2, y + (box_h - H * s) / 2
    renderPDF.draw(d, c, ox, oy)
    return ox, oy, s, W, H


_draw_svg = place_svg


BACK_NOTE = ("This page is left blank on purpose to stop markers bleeding through. "
             "Tip: slide a sheet of paper behind the page you are coloring.")


def _back_note(c, pw, m):
    c.setFont("CBS", 8.5)
    c.drawCentredString(pw / 2, m, BACK_NOTE)


def _belongs_to(c, pw, ph):
    c.setFont("CBS-Bold", 30)
    c.drawCentredString(pw / 2, ph * 0.58, "This book belongs to:")
    c.setLineWidth(2)
    c.line(pw * 0.2, ph * 0.45, pw * 0.8, ph * 0.45)


def _test_colors(c, pw, ph):
    c.setFont("CBS-Bold", 26)
    c.drawCentredString(pw / 2, ph - 1.4 * inch, "Test your colors")
    c.setLineWidth(1.5)
    cols, rows, size, gap = 5, 6, 1.0 * inch, 0.25 * inch
    x0 = (pw - (cols * size + (cols - 1) * gap)) / 2
    y0 = ph - 2.2 * inch - size
    for r in range(rows):
        for k in range(cols):
            c.roundRect(x0 + k * (size + gap), y0 - r * (size + gap), size, size, 10)


FRONT_MATTER = {"belongs_to": _belongs_to, "test_colors": _test_colors}


def build_interior(trim: str, items: list[dict], front_matter: list[str], blank_backs: bool, out: Path,
                   back_note: bool = True, answers: list[tuple] | None = None) -> int:
    """items: dict(kind="art", svg=Path, caption=str) or dict(kind="activity", draw=fn(c, box)).
    answers: list of (label, fn(c, box)) drawn on answer pages at the end."""
    pw, ph = (v * inch for v in config.TRIM_SIZES[trim])
    bw, bh = (v * inch for v in art_box(trim))
    m = margin(trim) * inch
    cb = caption_band(trim) * inch
    c = canvas.Canvas(str(out), pagesize=(pw, ph), pageCompression=1, initialFontName="CBS")
    c.setTitle("")
    c.setAuthor("")
    c.setCreator("")
    pages = 0

    def blank():
        nonlocal pages
        c.showPage()
        pages += 1

    def back():
        if blank_backs:
            if back_note:
                _back_note(c, pw, m)
            blank()

    for fm in front_matter:
        if fm not in FRONT_MATTER:
            raise SystemExit(f"front_matter 不認得 '{fm}'，可用：{list(FRONT_MATTER)}")
        FRONT_MATTER[fm](c, pw, ph)
        blank()
        if blank_backs:
            blank()
    for it in items:
        if it["kind"] == "activity":
            c.saveState()
            it["draw"](c, (m, m, bw, bh))
            c.restoreState()
        elif it.get("caption"):        # caption sits under the art, inside the safe margin
            cap = it["caption"]
            size = 26 if cb >= 0.75 * inch else 18
            while c.stringWidth(cap, "CBS-Bold", size) > bw and size > 14:
                size -= 1
            c.setFont("CBS-Bold", size)
            c.drawCentredString(pw / 2, m + 0.1 * inch, cap)
            place_svg(c, it["svg"], m, m + cb, bw, bh - cb)
        else:
            place_svg(c, it["svg"], m, m, bw, bh)
        blank()
        back()
    # answer pages: up to two answers per page
    answers = answers or []
    for i in range(0, len(answers), 2):
        c.setFont("CBS-Bold", 28)
        c.drawCentredString(pw / 2, ph - m - 28, "Answers")
        top = ph - m - 0.7 * inch
        chunk = answers[i:i + 2]
        slot = (top - m) / 2
        for j, (label, fn) in enumerate(chunk):
            sy = top - (j + 1) * slot
            c.setFont("CBS-Bold", 15)
            c.drawString(m, sy + slot - 18, label)
            c.saveState()
            fn(c, (m, sy + 0.1 * inch, bw, slot - 0.5 * inch))
            c.restoreState()
        blank()
    if pages % 2:                      # end on an even page count
        blank()
    c.save()
    return pages


def cover_size(trim: str, pages: int, paper: str) -> dict:
    tw, th = config.TRIM_SIZES[trim]
    spine = pages * config.SPINE_PER_PAGE[paper]
    b = config.BLEED_IN
    return dict(width_in=round(b + tw + spine + tw + b, 4), height_in=round(b + th + b, 4),
                spine_in=round(spine, 4), spine_text_allowed=pages >= config.SPINE_TEXT_MIN_PAGES)


def build_cover(trim: str, pages: int, paper: str, title: str, subtitle: str, author: str,
                front_svg: Path | None, out: Path) -> dict:
    """Simple black-and-white cover wrap (back | spine | front). Good for proofs; a designed
    color cover can replace it later using the same size numbers."""
    size = cover_size(trim, pages, paper)
    tw, th = config.TRIM_SIZES[trim]
    b, sp = config.BLEED_IN * inch, size["spine_in"] * inch
    W, H = size["width_in"] * inch, size["height_in"] * inch
    front_x = b + tw * inch + sp                       # left edge of front cover (trim line)
    c = canvas.Canvas(str(out), pagesize=(W, H), pageCompression=1, initialFontName="CBS")
    c.setTitle("")
    c.setAuthor("")
    c.setCreator("")
    safe = 0.375 * inch
    # front: title, art, author
    c.setFont("CBS-Bold", 40)
    c.drawCentredString(front_x + tw * inch / 2, H - b - safe - 50, title)
    if subtitle:
        c.setFont("CBS", 20)
        c.drawCentredString(front_x + tw * inch / 2, H - b - safe - 85, subtitle)
    if front_svg:
        _draw_svg(c, front_svg, front_x + 0.9 * inch, b + 1.3 * inch, tw * inch - 1.8 * inch, th * inch - 3.4 * inch)
    if author:
        c.setFont("CBS", 18)
        c.drawCentredString(front_x + tw * inch / 2, b + safe + 20, author)
    # spine
    if size["spine_text_allowed"] and title:
        c.saveState()
        c.translate(b + tw * inch + sp / 2, H / 2)
        c.rotate(-90)
        c.setFont("CBS-Bold", min(14, sp * 0.6))
        c.drawCentredString(0, -min(14, sp * 0.6) / 3, title)
        c.restoreState()
    c.showPage()
    c.save()
    return size
