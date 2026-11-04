"""Full-colour cover wrap (back | spine | front) for KDP paperbacks.

Settings live in book.yaml under `cover:` (art, colours) and each edition's `front` / `back`
text. The front art is scaled to fill the front panel including bleed; text is drawn as
vector on top, with fonts embedded."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from . import config
from .layout import cover_size
from .zhuyin import ZH  # registers the rounded CJK/Latin font

ROUND = ZH                  # jf open huninn also has rounded Latin letters
COVER_DPI = 300


def _fit_text(c, text, font, size, max_w, min_size=10):
    while c.stringWidth(text, font, size) > max_w and size > min_size:
        size -= 0.5
    return size


def _outlined(c, text, cx, y, font, size, fill, stroke="#ffffff", width=None):
    """Centred text with a soft white outline so it reads on top of the art."""
    width = width if width is not None else size * 0.16
    t = c.beginText()
    t.setFont(font, size)
    tw = c.stringWidth(text, font, size)
    c.saveState()
    c.setStrokeColor(HexColor(stroke))
    c.setLineWidth(width)
    c.setLineJoin(1)
    t.setTextRenderMode(1)
    t.setTextOrigin(cx - tw / 2, y)
    t.textOut(text)
    c.drawText(t)
    c.restoreState()
    t2 = c.beginText()
    t2.setFont(font, size)
    t2.setTextRenderMode(2)              # fill + thin stroke in the same colour = bolder letters
    t2.setTextOrigin(cx - tw / 2, y)
    t2.textOut(text)
    c.saveState()
    c.setFillColor(HexColor(fill))
    c.setStrokeColor(HexColor(fill))
    c.setLineWidth(size * 0.035)
    c.setLineJoin(1)
    c.drawText(t2)
    c.restoreState()


def _wrap(c, text, font, size, max_w):
    """Greedy word wrap; CJK text wraps between characters."""
    cjk = any("一" <= ch <= "鿿" for ch in text)
    tokens = list(text) if cjk else text.split(" ")
    lines, cur = [], ""
    for tok in tokens:
        trial = (cur + tok) if cjk else (cur + " " + tok).strip()
        if c.stringWidth(trial, font, size) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = tok
    if cur:
        lines.append(cur)
    return lines


def _art_reader(path: Path, need_w_px: int, need_h_px: int, warn: list):
    im = Image.open(path).convert("RGB")
    # cover-crop to the panel's aspect ratio
    target = need_w_px / need_h_px
    w, h = im.size
    if w / h > target:
        nw = int(h * target)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / target)
        top = (h - nh) // 2
        im = im.crop((0, top, w, top + nh))
    dpi = im.size[0] / (need_w_px / COVER_DPI)
    if dpi < COVER_DPI:
        warn.append(f"封面主圖解析度約 {dpi:.0f} DPI（KDP 要 300），已放大處理，印出來可能偏糊；"
                    f"建議換成至少 {need_w_px}×{need_h_px} 像素的原圖")
        im = im.resize((need_w_px, need_h_px), Image.LANCZOS)
    return ImageReader(im)


def build_color_cover(book, edition: str, pages: int, out: Path) -> tuple[dict, list]:
    cfg = book.data.get("cover") or {}
    ed = book.editions.get(edition, {})
    front = ed.get("front") or {}
    back = ed.get("back") or {}
    warn: list[str] = []

    size = cover_size(book.trim, pages, book.paper)
    tw, th = config.TRIM_SIZES[book.trim]
    b = config.BLEED_IN * inch
    sp = size["spine_in"] * inch
    W, H = size["width_in"] * inch, size["height_in"] * inch
    back_x0, back_x1 = b, b + tw * inch                    # back panel trim edges
    front_x0, front_x1 = back_x1 + sp, back_x1 + sp + tw * inch
    safe = 0.375 * inch
    sky = HexColor(cfg.get("back_color", "#cfe7f8"))
    ink = cfg.get("text_color", "#1f3a5f")

    c = canvas.Canvas(str(out), pagesize=(W, H), pageCompression=1)
    c.setTitle("")
    c.setAuthor("")
    c.setCreator("")

    # ---- back + spine background (to the bleed edge)
    c.setFillColor(sky)
    c.rect(0, 0, front_x0, H, stroke=0, fill=1)

    # ---- front art (front panel + right bleed, top and bottom bleed)
    art = book.dir / cfg.get("art", "cover/front_art.png")
    if not art.exists():
        raise SystemExit(f"找不到封面主圖 {art}")
    fw, fh = W - front_x0, H
    reader = _art_reader(art, round(fw / inch * COVER_DPI), round(fh / inch * COVER_DPI), warn)
    c.drawImage(reader, front_x0, 0, fw, fh)

    # ---- front text
    cx = (front_x0 + front_x1) / 2
    max_w = tw * inch - 2 * safe
    y = H - b - safe - 0.15 * inch
    series = front.get("series", book.data.get("series"))
    if series:
        s = _fit_text(c, series.upper(), ROUND, 17, max_w)
        y -= s
        _outlined(c, series.upper(), cx, y, ROUND, s, cfg.get("accent", "#e4572e"), width=s * 0.24)
        y -= 0.16 * inch
    if front.get("title_zh"):
        s = _fit_text(c, front["title_zh"], ROUND, 74, max_w)
        y -= s
        _outlined(c, front["title_zh"], cx, y, ROUND, s, ink)
        y -= 0.18 * inch
    for i, line in enumerate(front.get("title_lines", [])):
        base = 44 if not front.get("title_zh") else 26
        s = _fit_text(c, line, ROUND, base, max_w)
        y -= s * 1.12
        _outlined(c, line, cx, y, ROUND, s, ink)
    if front.get("subtitle"):
        s = _fit_text(c, front["subtitle"], ROUND, 22, max_w)
        y -= s * 1.7
        _outlined(c, front["subtitle"], cx, y, ROUND, s, cfg.get("accent", "#e4572e"), width=s * 0.22)
    if front.get("badge"):
        r = 0.62 * inch
        bx, by = front_x0 + safe + r + 0.1 * inch, y - 0.35 * inch - r
        c.setFillColor(HexColor(cfg.get("badge_color", "#ffd23f")))
        c.setStrokeColor(HexColor("#ffffff"))
        c.setLineWidth(4)
        c.circle(bx, by, r, stroke=1, fill=1)
        lines = front["badge"] if isinstance(front["badge"], list) else [front["badge"]]
        lh = 17
        for k, ln in enumerate(lines):
            s = _fit_text(c, ln, ROUND, 18, r * 1.7)
            c.setFillColor(HexColor(ink))
            c.setFont(ROUND, s)
            c.drawCentredString(bx, by + (len(lines) - 1) * lh / 2 - k * lh - s * 0.35, ln)

    # author along the bottom of the front (must match the author entered on KDP)
    author = front.get("author", book.data.get("author"))
    if author:
        s = _fit_text(c, author, ROUND, 22, max_w)
        _outlined(c, author, cx, b + safe + 0.05 * inch, ROUND, s, ink, width=s * 0.22)

    # ---- back panel
    bx0, bx1 = back_x0 + safe, back_x1 - safe
    bw = bx1 - bx0
    y = H - b - safe - 0.1 * inch
    if back.get("headline"):
        s = _fit_text(c, back["headline"], ROUND, 36, bw)
        y -= s
        c.setFillColor(HexColor(ink))
        c.setFont(ROUND, s)
        c.drawCentredString((bx0 + bx1) / 2, y, back["headline"])
        y -= 0.25 * inch
    for para in back.get("text", []):
        size_ = 17
        for ln in _wrap(c, para, ROUND, size_, bw):
            y -= size_ * 1.45
            c.setFont(ROUND, size_)
            c.drawString(bx0, y, ln)
        y -= 0.12 * inch
    for item in back.get("bullets", []):
        size_ = 16
        wrapped = _wrap(c, item, ROUND, size_, bw - 0.3 * inch)
        for k, ln in enumerate(wrapped):
            y -= size_ * 1.45
            if k == 0:
                c.setFillColor(HexColor(cfg.get("accent", "#e4572e")))
                c.circle(bx0 + 5, y + size_ * 0.32, 3.5, stroke=0, fill=1)
                c.setFillColor(HexColor(ink))
            c.setFont(ROUND, size_)
            c.drawString(bx0 + 0.3 * inch, y, ln)
    # sample pages: white cards with the cleaned line art
    samples = [book.dir / "clean" / f"{p}.png" for p in cfg.get("samples", [])]
    samples = [s_ for s_ in samples if s_.exists()]
    barcode_top = b + 0.25 * inch + 1.2 * inch + 0.2 * inch     # keep KDP's barcode area clear
    if samples:
        y -= 0.3 * inch
        card_h = min(3.6 * inch, y - barcode_top - 0.1 * inch)
        gap = 0.18 * inch
        card_w = min((bw - gap * (len(samples) - 1)) / len(samples), card_h * 0.78)
        total = card_w * len(samples) + gap * (len(samples) - 1)
        x = (bx0 + bx1) / 2 - total / 2
        for k, sp_path in enumerate(samples):
            cy = y - card_h
            c.setFillColor(HexColor("#ffffff"))
            c.setStrokeColor(HexColor(ink))
            c.setLineWidth(1.2)
            c.roundRect(x, cy, card_w, card_h, 8, stroke=1, fill=1)
            img = ImageReader(str(sp_path))
            iw, ih = img.getSize()
            pad = 8
            sc = min((card_w - 2 * pad) / iw, (card_h - 2 * pad) / ih)
            c.drawImage(img, x + (card_w - iw * sc) / 2, cy + (card_h - ih * sc) / 2, iw * sc, ih * sc)
            x += card_w + gap
        y -= card_h
    if back.get("closing"):
        s = _fit_text(c, back["closing"], ROUND, 22, bw - 2.4 * inch)
        c.setFillColor(HexColor(ink))
        c.setFont(ROUND, s)
        c.drawString(bx0, b + 0.25 * inch + 0.55 * inch, back["closing"])
    if y < barcode_top:
        warn.append("封底文字或樣張太多，可能壓到右下角的條碼區，請縮短封底文案")

    # spine: KDP allows text only from 79 pages
    if size["spine_text_allowed"] and front.get("spine"):
        c.saveState()
        c.translate(back_x1 + sp / 2, H / 2)
        c.rotate(-90)
        s = min(14, sp * 0.55)
        c.setFillColor(HexColor(ink))
        c.setFont(ROUND, s)
        c.drawCentredString(0, -s / 3, front["spine"])
        c.restoreState()
    c.showPage()
    c.save()
    return size, warn
