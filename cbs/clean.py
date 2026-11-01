"""Turn a generated image into clean black-and-white line art, measure it, and vectorize it."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np

from . import config


def _potrace_bin() -> str:
    exe = shutil.which("potrace")
    if not exe:
        raise SystemExit("找不到 potrace。Mac 請先執行：brew install potrace")
    return exe


def clean_and_vectorize(raw: Path, clean_dir: Path, vector_dir: Path, page_id: str,
                        age: str, art_box_in: tuple[float, float]) -> dict:
    g = cv2.imread(str(raw), cv2.IMREAD_GRAYSCALE)
    if g is None:
        raise SystemExit(f"讀不到圖片 {raw}")
    h0, w0 = g.shape
    gray_pct = float(((g > 70) & (g < 185)).mean() * 100)   # mid-tones: shading or heavy anti-aliasing

    # 2x upscale gives potrace smoother curves; Otsu picks the black/white cut
    g2 = cv2.resize(g, (w0 * 2, h0 * 2), interpolation=cv2.INTER_CUBIC)
    g2 = cv2.GaussianBlur(g2, (3, 3), 0)
    _, bw = cv2.threshold(g2, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ink = (bw == 0).astype(np.uint8)

    # remove specks (scan dust, stray dots)
    speck = max(40, int(ink.size * 1e-5))
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink, 8)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] < speck:
            ink[lab == i] = 0
    if not ink.any():
        raise SystemExit(f"{page_id}: 圖片清理後是空白的")

    ys, xs = np.nonzero(ink)
    H, W = ink.shape
    edge = 0.008 * max(H, W)
    touches_edge = bool(ys.min() < edge or xs.min() < edge or ys.max() > H - edge or xs.max() > W - edge)

    pad = 10
    ink = ink[max(ys.min() - pad, 0):min(ys.max() + pad, H), max(xs.min() - pad, 0):min(xs.max() + pad, W)]
    ch, cw = ink.shape
    in_per_px = min(art_box_in[0] / cw, art_box_in[1] / ch)
    raster_dpi = 1 / (in_per_px * 2)

    def stroke(ink_img):   # typical stroke width: ridge of the distance transform
        dt = cv2.distanceTransform(ink_img, cv2.DIST_L2, 3)
        ridge = dt[(dt >= cv2.dilate(dt, np.ones((3, 3))) - 1e-6) & (dt > 0.5)]
        return float(np.median(ridge) * 2 * in_per_px * 25.4) if ridge.size else 0.0

    preset = config.AGE_PRESETS[age]
    stroke_mm = original_stroke = stroke(ink)
    # lines thinner than the age preset are thickened evenly (all strokes grow by the same amount)
    lo = preset["target_stroke_mm"][0]
    if config.AUTO_THICKEN and 0 < stroke_mm < lo:
        grow_px = int(round((lo + 0.1 - stroke_mm) / 2 / 25.4 / in_per_px))
        grow_px = min(grow_px, config.AUTO_THICKEN_MAX_PX)
        if grow_px > 0:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow_px + 1, 2 * grow_px + 1))
            ink = cv2.dilate(ink, k)
            stroke_mm = stroke(ink)

    # enclosed white areas too small for the age group
    r_px = (preset["min_region_mm"] / 2) / 25.4 / in_per_px
    n, _, st, _ = cv2.connectedComponentsWithStats((1 - ink).astype(np.uint8), 4)
    areas = st[1:, cv2.CC_STAT_AREA]
    tiny = int(((areas < np.pi * r_px ** 2) & (areas > 4)).sum())

    clean_dir.mkdir(exist_ok=True)
    vector_dir.mkdir(exist_ok=True)
    pbm = clean_dir / f"{page_id}.pbm"
    cv2.imwrite(str(pbm), (1 - ink) * 255)
    cv2.imwrite(str(clean_dir / f"{page_id}.png"), (1 - ink) * 255)
    svg = vector_dir / f"{page_id}.svg"
    subprocess.run([_potrace_bin(), str(pbm), "-s", "-t", "8", "-O", "0.3", "-o", str(svg)], check=True)

    return dict(page=page_id, source=raw.name, source_px=f"{w0}x{h0}", gray_pct=round(gray_pct, 1),
                raster_dpi=round(raster_dpi), stroke_mm=round(stroke_mm, 2),
                original_stroke_mm=round(original_stroke, 2), tiny_regions=tiny,
                regions=int(n - 1), touches_edge=touches_edge, svg=str(svg))
