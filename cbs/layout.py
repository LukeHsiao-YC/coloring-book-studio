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


def _zh():
    from . import zhuyin
    return zhuyin


def heading_text(c, lang, en, zh, cx, top, size, max_w, overrides=None):
    """English title, or Chinese (with zhuyin) above a smaller English line. Returns the y below."""
    if lang == "zh" and zh:
        Z = _zh()
        Z.draw_centered(c, zh, cx, top - size, size, max_w, overrides)
        es = size * 0.6
        while c.stringWidth(en, "CBS-Bold", es) > max_w and es > 9:
            es -= 0.5
        c.setFont("CBS-Bold", es)
        c.drawCentredString(cx, top - size * 1.55 - es, en)
        return top - size * 1.6 - es * 1.3
    s = size
    while c.stringWidth(en, "CBS-Bold", s) > max_w and s > 12:
        s -= 1
    c.setFont("CBS-Bold", s)
    c.drawCentredString(cx, top - s, en)
    return top - s * 1.3


def _back_note(c, pw, m, lang):
    from .i18n import t
    c.setFont("CBS", 8.5)
    c.drawCentredString(pw / 2, m, t("back_note", "en"))
    if lang == "zh":
        c.setFont(_zh().ZH, 8.5)
        c.drawCentredString(pw / 2, m + 12, t("back_note", "zh"))


def _belongs_to(c, pw, ph, lang, ov):
    from .i18n import t
    heading_text(c, lang, t("belongs_to", "en"), t("belongs_to", "zh"), pw / 2, ph * 0.62, 30, pw * 0.8, ov)
    c.setLineWidth(2)
    c.line(pw * 0.2, ph * 0.45, pw * 0.8, ph * 0.45)


def _test_colors(c, pw, ph, lang, ov):
    from .i18n import t
    below = heading_text(c, lang, t("test_colors", "en"), t("test_colors", "zh"),
                         pw / 2, ph - 0.9 * inch, 26, pw * 0.8, ov)
    c.setLineWidth(1.5)
    cols, rows, size, gap = 5, 6, 1.0 * inch, 0.25 * inch
    x0 = (pw - (cols * size + (cols - 1) * gap)) / 2
    y0 = below - 0.3 * inch - size
    for r in range(rows):
        for k in range(cols):
            c.roundRect(x0 + k * (size + gap), y0 - r * (size + gap), size, size, 10)


FRONT_MATTER = {"belongs_to": _belongs_to, "test_colors": _test_colors}


def caption_height(lines_en, lines_zh, lang) -> float:
    if lang == "zh" and lines_zh:
        return len(lines_zh) * 29 + len(lines_en) * 16 + 14
    return len(lines_en) * 24 + 10 if lines_en else 0


def draw_caption(c, lines_en, lines_zh, lang, cx, bottom, max_w, overrides=None):
    """Poem lines under the picture: English only, or Chinese (zhuyin) then English."""
    y = bottom + caption_height(lines_en, lines_zh, lang) - 6
    if lang == "zh" and lines_zh:
        Z = _zh()
        for ln in lines_zh:
            y -= 29
            Z.draw_centered(c, ln, cx, y + 6, 19.5, max_w, overrides)
        size = 12.5
        for ln in lines_en:
            y -= 16
            c.setFont("CBS", size)
            c.drawCentredString(cx, y + 3, ln)
        return
    size = 17
    for ln in lines_en:
        s = size
        while c.stringWidth(ln, "CBS-Bold", s) > max_w and s > 11:
            s -= 0.5
        y -= 24
        c.setFont("CBS-Bold", s)
        c.drawCentredString(cx, y + 4, ln)


def build_interior(trim: str, items: list[dict], front_matter: list[str], blank_backs: bool, out: Path,
                   back_note: bool = True, answers: list[tuple] | None = None,
                   lang: str = "en", overrides: dict | None = None) -> int:
    """items: dict(kind="art", svg, text_en=[...], text_zh=[...]) or dict(kind="activity", draw=fn(c, box)).
    answers: list of (label_en, label_zh, fn(c, box)) drawn on answer pages at the end."""
    from .i18n import t
    pw, ph = (v * inch for v in config.TRIM_SIZES[trim])
    bw, bh = (v * inch for v in art_box(trim))
    m = margin(trim) * inch
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
                _back_note(c, pw, m, lang)
            blank()

    for fm in front_matter:
        if fm not in FRONT_MATTER:
            raise SystemExit(f"front_matter 不認得 '{fm}'，可用：{list(FRONT_MATTER)}")
        FRONT_MATTER[fm](c, pw, ph, lang, overrides)
        blank()
        if blank_backs:
            blank()
    for it in items:
        if it["kind"] == "activity":
            c.saveState()
            it["draw"](c, (m, m, bw, bh))
            c.restoreState()
        else:
            en, zh = it.get("text_en") or [], it.get("text_zh") or []
            capt = caption_height(en, zh, lang)
            if capt:
                draw_caption(c, en, zh, lang, pw / 2, m, bw, overrides)
            place_svg(c, it["svg"], m, m + capt + (0.1 * inch if capt else 0), bw, bh - capt - (0.1 * inch if capt else 0))
        blank()
        back()
    # answer pages: up to two answers per page
    answers = answers or []
    for i in range(0, len(answers), 2):
        top = heading_text(c, lang, t("answers", "en"), t("answers", "zh"), pw / 2, ph - m, 28, bw, overrides)
        top -= 0.1 * inch
        chunk = answers[i:i + 2]
        slot = (top - m) / 2
        for j, (label_en, label_zh, fn) in enumerate(chunk):
            sy = top - (j + 1) * slot
            label = label_zh if (lang == "zh" and label_zh) else label_en
            if lang == "zh" and label_zh:
                _zh().draw_left(c, label, m, sy + slot - 20, 14, overrides)
            else:
                c.setFont("CBS-Bold", 15)
                c.drawString(m, sy + slot - 18, label)
            c.saveState()
            fn(c, (m, sy + 0.1 * inch, bw, slot - 0.55 * inch))
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
                front_svg: Path | None, out: Path, title_zh: str = "") -> dict:
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
    cx = front_x + tw * inch / 2
    ytop = H - b - safe
    if title_zh:
        c.setFont(_zh().ZH, 44)
        c.drawCentredString(cx, ytop - 46, title_zh)
        ytop -= 56
    ts = 40 if not title_zh else 26
    while c.stringWidth(title, "CBS-Bold", ts) > tw * inch - 2 * safe and ts > 14:
        ts -= 1
    c.setFont("CBS-Bold", ts)
    c.drawCentredString(cx, ytop - ts - 6, title)
    if subtitle:
        ss = 18
        while c.stringWidth(subtitle, "CBS", ss) > tw * inch - 2 * safe and ss > 9:
            ss -= 0.5
        c.setFont("CBS", ss)
        c.drawCentredString(cx, ytop - ts - 6 - ss * 1.9, subtitle)
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
