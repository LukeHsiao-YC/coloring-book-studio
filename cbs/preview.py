"""Contact sheet: every page as raw | cleaned, with its version and warnings."""
from __future__ import annotations

import os
from pathlib import Path

import reportlab
from PIL import Image, ImageDraw, ImageFont

_FONT = os.path.join(os.path.dirname(reportlab.__file__), "fonts", "VeraBd.ttf")


def contact_sheet(rows: list[dict], out: Path, thumb_h: int = 360, cols: int = 3) -> Path:
    """rows: dict(page, version, provider, raw, clean, warn_count)"""
    font = ImageFont.truetype(_FONT, 22)
    cells = []
    for r in rows:
        ims = []
        for p in (r["raw"], r.get("clean")):
            if p and Path(p).exists():
                im = Image.open(p).convert("RGB")
                im.thumbnail((thumb_h, thumb_h))
            else:
                im = Image.new("RGB", (int(thumb_h * 0.75), thumb_h), "#eee")
            ims.append(im)
        w = sum(i.width for i in ims) + 30
        cell = Image.new("RGB", (w, thumb_h + 50), "white")
        x = 10
        for im in ims:
            cell.paste(im, (x, 45))
            x += im.width + 10
        label = f"{r['page']}  v{r['version']}  {r['provider']}"
        if r.get("warn_count"):
            label += f"  [{r['warn_count']} warning]"
        ImageDraw.Draw(cell).text((10, 10), label, fill="#c00" if r.get("warn_count") else "black", font=font)
        cells.append(cell)
    if not cells:
        raise SystemExit("還沒有任何頁面圖片")
    cw = max(c.width for c in cells)
    chh = max(c.height for c in cells)
    nrows = -(-len(cells) // cols)
    sheet = Image.new("RGB", (cols * (cw + 10) + 10, nrows * (chh + 10) + 10), "#bbb")
    for i, c in enumerate(cells):
        sheet.paste(c, (10 + (i % cols) * (cw + 10), 10 + (i // cols) * (chh + 10)))
    sheet.save(out)
    return out
