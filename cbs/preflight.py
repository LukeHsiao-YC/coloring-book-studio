"""KDP preflight: hard errors (upload would be rejected) and warnings (quality risks)."""
from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from . import config


def _fonts_embedded(reader: PdfReader) -> list[str]:
    missing = set()
    for page in reader.pages:
        res = page.get("/Resources") or {}
        fonts = res.get("/Font") or {}
        for _, ref in fonts.items():
            f = ref.get_object()
            desc = f.get("/FontDescriptor")
            if f.get("/Subtype") == "/Type0":
                desc = f["/DescendantFonts"][0].get_object().get("/FontDescriptor")
            desc = desc.get_object() if desc else None
            if not desc or not any(k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3")):
                missing.add(str(f.get("/BaseFont")))
    return sorted(missing)


def check_interior(pdf: Path, trim: str, metrics: list[dict], ages: dict) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    r = PdfReader(str(pdf))
    n = len(r.pages)
    if n < config.MIN_PAGES:
        errors.append(f"內頁只有 {n} 頁，KDP 平裝本至少要 {config.MIN_PAGES} 頁（再加 {config.MIN_PAGES - n} 頁，"
                      f"有背面空白頁時約等於 {-(-(config.MIN_PAGES - n) // 2)} 張圖）")
    tw, th = config.TRIM_SIZES[trim]
    for i, p in enumerate(r.pages, 1):
        w, h = float(p.mediabox.width) / 72, float(p.mediabox.height) / 72
        if abs(w - tw) > 0.01 or abs(h - th) > 0.01:
            errors.append(f"第 {i} 頁尺寸 {w:.3f}x{h:.3f} 吋，應為 {tw}x{th}")
        if "/Annots" in p:
            errors.append(f"第 {i} 頁有註解，KDP 不接受")
    missing = _fonts_embedded(r)
    if missing:
        errors.append(f"字型沒有內嵌：{', '.join(missing)}")
    if r.is_encrypted:
        errors.append("PDF 有密碼保護")

    for m in metrics:
        pid, age = m["page"], ages[m["page"]]
        preset = config.AGE_PRESETS[age]
        lo, hi = preset["target_stroke_mm"]
        if m["gray_pct"] > 5:
            warns.append(f"{pid}: 原圖有 {m['gray_pct']}% 灰階，可能有陰影或填色，清理後請目視確認")
        if not lo <= m["stroke_mm"] <= hi:
            warns.append(f"{pid}: 線條約 {m['stroke_mm']} mm，{preset['label']}建議 {lo}–{hi} mm")
        if m["tiny_regions"] > preset["max_tiny_regions"]:
            warns.append(f"{pid}: 有 {m['tiny_regions']} 個太小的塗色區（<{preset['min_region_mm']} mm），"
                         f"{preset['label']}建議不超過 {preset['max_tiny_regions']} 個")
        if m["touches_edge"]:
            warns.append(f"{pid}: 原圖內容碰到邊緣，可能有東西被切掉（地平線之類刻意延伸的線可以忽略）")
    return errors, warns
