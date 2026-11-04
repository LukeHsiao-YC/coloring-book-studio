"""Traditional Chinese text with zhuyin (bopomofo) drawn to the right of each character,
the way Taiwanese children's books and school textbooks print it.

Readings come from pypinyin, then three layers of correction:
  1. CHAR_DEFAULTS below (house style, e.g. 一 and 不 in their original tone)
  2. the book's `zhuyin:` map in book.yaml  {"phrase or character": "ㄅㄆ ㄇㄈ"}
Every build writes zhuyin_check.md so a person can proof every reading.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from pypinyin import Style, pinyin
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONT_FILE = ROOT / "fonts" / "jf-openhuninn-2.1.ttf"
ZH = "CBS-ZH"
if FONT_FILE.exists() and ZH not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont(ZH, str(FONT_FILE)))

TONES = "ˊˇˋ˙"
# House style: 一 and 不 are printed in their original tone (no tone-sandhi marks).
CHAR_DEFAULTS = {"一": "ㄧ", "不": "ㄅㄨˋ"}
# Characters whose reading often depends on the word, or differs between Taiwan and mainland usage
WATCH = set("了得著樂期挑和長還行重發為乾覺教背便差都種朝傳空當量少相中數地將應幾場只切處藏似露薄落結供強角參率否卡給骰子麼什一不呀啊吧嗎呢兒上")
HAN = re.compile(r"[一-鿿]")


def _norm(z: str) -> str:
    """Store the neutral dot at the end like the other tones (pypinyin: ㄗ˙, Taiwan style: ˙ㄗ)."""
    z = z.strip()
    if "˙" in z:
        z = z.replace("˙", "") + "˙"
    return z


def show(z: str) -> str:
    """Taiwan writing order for people: the neutral dot goes first."""
    return "˙" + z[:-1] if z.endswith("˙") else z


def annotate(text: str, overrides: dict | None = None) -> list[tuple[str, str | None]]:
    """Return [(char, zhuyin or None)] for a line of text."""
    overrides = overrides or {}
    raw = pinyin(text, style=Style.BOPOMOFO, errors=lambda s: [None] * len(s))
    out, i = [], 0
    for ch, r in zip(text, raw):
        z = r[0] if (r and HAN.match(ch)) else None
        if z and ch in CHAR_DEFAULTS:
            z = CHAR_DEFAULTS[ch]
        out.append([ch, _norm(z) if z else None])
    # book overrides: longest phrases first; a phrase maps to space-separated readings
    for phrase in sorted(overrides, key=len, reverse=True):
        readings = str(overrides[phrase]).split()
        if len(readings) != len(phrase):
            raise SystemExit(f"注音修正「{phrase}」的讀音數量（{len(readings)}）和字數不一致")
        start = 0
        while (k := text.find(phrase, start)) != -1:
            for j, z in enumerate(readings):
                out[k + j][1] = _norm(z)
            start = k + 1
    return [tuple(x) for x in out]


def _split(z: str):
    tone = z[-1] if z and z[-1] in TONES else ""
    body = z[:-1] if tone else z
    return body, tone


def advance(ch: str, z: str | None, size: float) -> float:
    if z:
        return size * 1.62
    font = ZH if not ch.isascii() else "CBS-Bold"
    return pdfmetrics.stringWidth(ch, font, size) * (1.0 if not ch.isascii() else 0.82)


def line_width(chars, size: float) -> float:
    return sum(advance(ch, z, size) for ch, z in chars)


def draw_line(c, chars, x: float, baseline: float, size: float):
    """Draw annotated characters starting at x; returns the end x."""
    zs = size * 0.36                     # zhuyin symbol size
    for ch, z in chars:
        if ch.isascii():
            c.setFont("CBS-Bold", size * 0.82)
            c.drawString(x, baseline, ch)
            x += advance(ch, z, size)
            continue
        c.setFont(ZH, size)
        c.drawString(x, baseline, ch)
        if z:
            body, tone = _split(z)
            col_x = x + size * 1.04          # zhuyin column just right of the character
            mid = baseline + size * 0.36     # vertical centre of the character
            n = len(body)
            step = zs * 0.98
            top = mid + n * step / 2         # top of the stacked symbols
            c.setFont(ZH, zs)
            for k, sym in enumerate(body):
                yb = top - (k + 1) * step + zs * 0.12
                c.drawString(col_x, yb, sym)
            if tone == "˙":                  # neutral tone: dot above the column
                c.drawString(col_x, top + zs * 0.05, "˙")
            elif tone:                       # other tones: beside the upper half of the last symbol
                c.setFont(ZH, zs * 0.95)
                last_y = top - n * step + zs * 0.12
                c.drawString(col_x + zs * 0.86, last_y - zs * 0.02, tone)
        x += advance(ch, z, size)
    return x


def draw_centered(c, text: str, cx: float, baseline: float, size: float, max_w: float,
                  overrides: dict | None = None, min_size: float = 10):
    chars = annotate(text, overrides)
    while line_width(chars, size) > max_w and size > min_size:
        size -= 0.5
    draw_line(c, chars, cx - line_width(chars, size) / 2, baseline, size)
    return size


def draw_left(c, text: str, x: float, baseline: float, size: float, overrides: dict | None = None):
    return draw_line(c, annotate(text, overrides), x, baseline, size)


def plain_width(text: str, size: float) -> float:
    """Width of Chinese text without zhuyin (cover, notes)."""
    return pdfmetrics.stringWidth(text, ZH, size)


def check_table(lines: list[tuple[str, str]], overrides: dict, out: Path):
    """Markdown proof sheet: every line with its readings; characters with more than one
    possible reading are flagged so a person checks them."""
    rows = ["# 注音校對表", "",
            "每一行列出每個字的注音。標 ⚠ 的是常見多音字或兩岸讀音不同的字，請特別確認；",
            "標 ✎ 的是已經人工修正過的字。",
            "要修正時，在 book.yaml 的 `zhuyin:` 加一行，例如 `跑得: ㄆㄠˇ ˙ㄉㄜ`。", ""]
    fixed = set("".join(overrides))
    seen = set()
    for where, text in lines:
        if text in seen:
            continue
        seen.add(text)
        cells = []
        for ch, z in annotate(text, overrides):
            if not z:
                continue
            flag = "✎" if ch in fixed else ("⚠" if ch in WATCH else "")
            cells.append(f"{ch}{flag}`{show(z)}`")
        rows.append(f"**{where}**　{text}")
        rows.append("")
        rows.append("　".join(cells))
        rows.append("")
    out.write_text("\n".join(rows), encoding="utf-8")
