"""Activity pages drawn by code: no image generation needed.

Each page in book.yaml can set `type:` to one of ACTIVITIES below. Every activity gets the
page's full yaml entry as `spec`, so options are read from there (see README for the list).
"""
from __future__ import annotations

import math
import random
import subprocess
from collections import deque
from pathlib import Path

import cv2
import numpy as np
from reportlab.lib.units import inch, mm
from reportlab.lib.utils import ImageReader

LW = 1.3 * mm          # outline width for anything a child colors (≈3.7 pt)
LW_THIN = 1.2          # writing lines, table rules (pt)
TITLE_H = 0.85 * inch
FONT, BOLD = "CBS", "CBS-Bold"


# ---------------------------------------------------------------- helpers
def title(c, text, x, y, w, h, size=30):
    """Title centred in the top band of the box; returns the y below the band."""
    top = y + h
    s = size
    while c.stringWidth(text, BOLD, s) > w and s > 14:
        s -= 1
    c.setFont(BOLD, s)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(x + w / 2, top - s, text)
    return top - TITLE_H


def subtitle(c, text, x, ybase, w, size=14):
    s = size
    while c.stringWidth(text, FONT, s) > w and s > 9:
        s -= 0.5
    c.setFont(FONT, s)
    c.drawCentredString(x + w / 2, ybase, text)


def icon(c, ctx, key, x, y, h, align="left"):
    """Draw a character icon with its bottom-left (or bottom-right) at x, y."""
    path = ctx["icons"].get(key) if key else None
    if not path or not Path(path).exists():
        return 0
    img = ImageReader(str(path))
    iw, ih = img.getSize()
    w = h * iw / ih
    if align == "right":
        x -= w
    elif align == "center":
        x -= w / 2
    c.drawImage(img, x, y, w, h)
    return w


def star_points(cx, cy, r_out, r_in=None, n=5):
    r_in = r_in or r_out * 0.45
    pts = []
    for i in range(n * 2):
        a = math.pi / 2 + i * math.pi / n
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def polygon(c, pts, stroke_w=LW, close=True):
    p = c.beginPath()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    if close:
        p.close()
    c.setLineWidth(stroke_w)
    c.setLineJoin(1)
    c.setLineCap(1)
    c.drawPath(p, stroke=1, fill=0)


def checkbox(c, x, y, size, label, font_size=14):
    c.setLineWidth(LW_THIN * 1.5)
    c.roundRect(x, y, size, size, 3, stroke=1, fill=0)
    c.setFont(FONT, font_size)
    c.drawString(x + size + 8, y + size * 0.2, label)


# ---------------------------------------------------------------- simple goal drawings
def draw_goal(c, kind, cx, y, h):
    c.setLineWidth(LW)
    c.setLineJoin(1)
    c.setLineCap(1)
    if kind == "tent":
        polygon(c, [(cx - h * 0.6, y), (cx, y + h), (cx + h * 0.6, y)])
        polygon(c, [(cx - h * 0.2, y), (cx, y + h * 0.5), (cx + h * 0.2, y)])
    elif kind == "house":
        c.rect(cx - h * 0.4, y, h * 0.8, h * 0.55)
        polygon(c, [(cx - h * 0.5, y + h * 0.55), (cx, y + h), (cx + h * 0.5, y + h * 0.55)])
        c.rect(cx - h * 0.1, y, h * 0.2, h * 0.32)
    elif kind == "flower":
        c.line(cx, y, cx, y + h * 0.55)
        r = h * 0.14
        for i in range(6):
            a = i * math.pi / 3
            c.circle(cx + 1.7 * r * math.cos(a), y + h * 0.72 + 1.7 * r * math.sin(a), r)
        c.circle(cx, y + h * 0.72, r)
    elif kind == "ball":
        r = h * 0.45
        c.circle(cx, y + r, r)
        c.arc(cx - r * 0.5, y, cx + r * 0.5, y + 2 * r, 90, 180)
        c.arc(cx - r * 0.5, y, cx + r * 0.5, y + 2 * r, -90, 180)
    else:  # tree
        c.rect(cx - h * 0.08, y, h * 0.16, h * 0.4)
        c.circle(cx, y + h * 0.66, h * 0.32)


# ---------------------------------------------------------------- maze
def _maze(rows, cols, seed):
    rnd = random.Random(seed)
    openings = {(r, k): set() for r in range(rows) for k in range(cols)}
    seen = {(0, 0)}
    stack = [(0, 0)]
    moves = {"N": (-1, 0), "S": (1, 0), "W": (0, -1), "E": (0, 1)}
    back = {"N": "S", "S": "N", "W": "E", "E": "W"}
    while stack:
        r, k = stack[-1]
        options = [(d, (r + dr, k + dk)) for d, (dr, dk) in moves.items()
                   if 0 <= r + dr < rows and 0 <= k + dk < cols and (r + dr, k + dk) not in seen]
        if not options:
            stack.pop()
            continue
        d, nxt = rnd.choice(options)
        openings[(r, k)].add(d)
        openings[nxt].add(back[d])
        seen.add(nxt)
        stack.append(nxt)
    # solution path by BFS
    goal = (rows - 1, cols - 1)
    prev = {(0, 0): None}
    q = deque([(0, 0)])
    while q:
        cur = q.popleft()
        if cur == goal:
            break
        for d in openings[cur]:
            dr, dk = moves[d]
            nxt = (cur[0] + dr, cur[1] + dk)
            if nxt not in prev:
                prev[nxt] = cur
                q.append(nxt)
    path, cur = [], goal
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return openings, path[::-1]


def maze_prepare(ctx):
    s = ctx["spec"]
    young = ctx["page"].age == "3-5"
    rows = int(s.get("rows", 6 if young else 9))
    cols = int(s.get("cols", 5 if young else 7))
    openings, path = _maze(rows, cols, s.get("seed", ctx["page"].id))
    return dict(rows=rows, cols=cols, openings=openings, path=path)


def _draw_maze_grid(c, st, x, y, w, h, solution=False):
    rows, cols, op = st["rows"], st["cols"], st["openings"]
    cell = min(w / cols, h / rows)
    mw, mh = cell * cols, cell * rows
    x0, ytop = x + (w - mw) / 2, y + (h - mh) / 2 + mh
    c.setLineWidth(LW if not solution else LW * 0.7)
    c.setLineCap(1)
    for r in range(rows):
        for k in range(cols):
            cx, cy = x0 + k * cell, ytop - r * cell
            if "N" not in op[(r, k)] and not (r == 0 and k == 0):
                c.line(cx, cy, cx + cell, cy)
            if "W" not in op[(r, k)]:
                c.line(cx, cy, cx, cy - cell)
            if k == cols - 1:
                c.line(cx + cell, cy, cx + cell, cy - cell)
            if r == rows - 1 and k != cols - 1:
                c.line(cx, cy - cell, cx + cell, cy - cell)
    if solution:
        pts = [(x0 + (k + 0.5) * cell, ytop - (r + 0.5) * cell) for r, k in st["path"]]
        pts = [(pts[0][0], ytop + cell * 0.4)] + pts + [(pts[-1][0], ytop - mh - cell * 0.4)]
        c.saveState()
        c.setDash(6, 4)
        polygon(c, pts, stroke_w=LW * 1.2, close=False)
        c.restoreState()
    return x0, ytop, cell, mw, mh


def maze_draw(c, box, st, ctx):
    x, y, w, h = box
    s = ctx["spec"]
    below = title(c, s.get("title", "Find the way!"), x, y, w, h)
    if s.get("text"):
        subtitle(c, s["text"], x, below + 0.25 * inch, w)
    band = 1.15 * inch
    x0, ytop, cell, mw, mh = _draw_maze_grid(c, st, x, y + band, w, below - y - 2 * band)
    icon(c, ctx, s.get("start"), x0 + cell / 2, ytop + 0.08 * inch, band - 0.2 * inch, align="center")
    draw_goal(c, s.get("goal", "tree"), x0 + mw - cell / 2, y + 0.1 * inch, band - 0.25 * inch)


def maze_answer(c, box, st, ctx):
    x, y, w, h = box
    _draw_maze_grid(c, st, x, y, w, h, solution=True)


# ---------------------------------------------------------------- tracing
def tracing_draw(c, box, st, ctx):
    x, y, w, h = box
    s = ctx["spec"]
    below = title(c, s.get("title", "Trace the words"), x, y, w, h)
    words = [str(t).upper() for t in s.get("words", [])][:5]
    if not words:
        raise SystemExit(f"{ctx['page'].id}: tracing 需要 words")
    row_h = (below - y) / len(words)
    for i, word in enumerate(words):
        top = below - i * row_h
        size = row_h * 0.42
        while c.stringWidth(word, BOLD, size) + 4 * len(word) > w * 0.95 and size > 20:
            size -= 1
        t = c.beginText()
        t.setFont(BOLD, size)
        t.setCharSpace(4)
        t.setTextRenderMode(1)          # outline only
        tw = c.stringWidth(word, BOLD, size) + 4 * (len(word) - 1)
        t.setTextOrigin(x + (w - tw) / 2, top - size * 0.95)
        t.textOut(word)
        c.saveState()
        c.setLineWidth(1.6)
        c.setDash(3, 2.5)
        c.drawText(t)
        c.restoreState()
        # handwriting guide: top, dashed middle, base line
        gh = row_h * 0.3
        base = top - row_h + row_h * 0.12
        c.setLineWidth(LW_THIN)
        c.line(x, base, x + w, base)
        c.line(x, base + gh, x + w, base + gh)
        c.saveState()
        c.setDash(4, 4)
        c.line(x, base + gh / 2, x + w, base + gh / 2)
        c.restoreState()


# ---------------------------------------------------------------- dot to dot
def _shape(name):
    if name == "star":
        pts = star_points(0.5, 0.5, 0.5, 0.21)
        return [(px, py) for px, py in pts]
    if name == "heart":    # evenly spaced along the outline, starting at the top dip, clockwise
        dense = []
        for i in range(800):
            t = 2 * math.pi * i / 800
            dense.append((16 * math.sin(t) ** 3,
                          13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)))
        seg = [math.dist(dense[i], dense[(i + 1) % 800]) for i in range(800)]
        total, n_dots = sum(seg), 20
        pts, acc, k = [], 0.0, 0
        for i in range(800):
            if acc >= k * total / n_dots and k < n_dots:
                pts.append(dense[i])
                k += 1
            acc += seg[i]
    elif name == "tent":
        pts = [(0, 0), (0.35, 0), (0.5, 0.35), (0.65, 0), (1, 0), (0.5, 0.95), (0.55, 1.08), (0.7, 1.02), (0.52, 0.97)]
    elif name == "house":
        pts = [(0.1, 0), (0.4, 0), (0.4, 0.3), (0.6, 0.3), (0.6, 0), (0.9, 0), (0.9, 0.55), (1, 0.55),
               (0.5, 1), (0, 0.55), (0.1, 0.55)]
    elif name == "fish":   # body from top-left round the nose to bottom-left, then the tail
        pts = []
        for i in range(15):
            a = math.radians(150 - 300 * i / 14)
            pts.append((0.6 + 0.4 * math.cos(a), 0.5 + 0.3 * math.sin(a)))
        pts += [(0.0, 0.18), (0.0, 0.82)]
    else:
        raise SystemExit(f"dot_to_dot 不認得形狀 '{name}'，可用：star heart tent house fish")
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    sx = max(xs) - min(xs)
    sy = max(ys) - min(ys)
    sc = max(sx, sy)
    return [((px - min(xs)) / sc + (1 - sx / sc) / 2, (py - min(ys)) / sc + (1 - sy / sc) / 2) for px, py in pts]


def dots_draw(c, box, st, ctx):
    x, y, w, h = box
    s = ctx["spec"]
    below = title(c, s.get("title", "Connect the dots"), x, y, w, h)
    if s.get("text"):
        subtitle(c, s["text"], x, below + 0.25 * inch, w)
    pts = _shape(s.get("shape", "star"))
    band = 1.4 * inch
    area = min(w * 0.85, below - y - band - 0.3 * inch)
    ox, oy = x + (w - area) / 2, y + band + (below - y - band - area) / 2
    P = [(ox + px * area, oy + py * area) for px, py in pts]
    cx = sum(p[0] for p in P) / len(P)
    cy = sum(p[1] for p in P) / len(P)
    for i, (px, py) in enumerate(P, 1):
        c.circle(px, py, 3.2, stroke=0, fill=1)
        dx, dy = px - cx, py - cy
        d = math.hypot(dx, dy) or 1
        c.setFont(BOLD if i == 1 else FONT, 15 if i == 1 else 13)
        c.drawCentredString(px + dx / d * 16, py + dy / d * 16 - 5, str(i))
    icon(c, ctx, s.get("icon"), x + w, y, band - 0.15 * inch, align="right")


# ---------------------------------------------------------------- spot the difference
def spot_prepare(ctx):
    s = ctx["spec"]
    src = s.get("source")
    b = ctx["book"]
    pbm = b.dir / "clean" / f"{src}.pbm"
    if not pbm.exists():
        raise SystemExit(f"{ctx['page'].id}: 找不到來源頁 {src} 的清理圖（source 要指向一張已有圖的著色頁）")
    img = cv2.imread(str(pbm), cv2.IMREAD_GRAYSCALE)
    ink = (img < 128).astype(np.uint8)
    H, W = ink.shape
    n, lab, st, cen = cv2.connectedComponentsWithStats(ink, 8)
    # white regions; "background" = any white region touching the border
    wn, wlab = cv2.connectedComponents((1 - ink).astype(np.uint8), connectivity=4)
    border = set(np.unique(np.concatenate([wlab[0], wlab[-1], wlab[:, 0], wlab[:, -1]]))) - {0}
    kernel = np.ones((7, 7), np.uint8)
    cands = []
    for i in range(1, n):
        x0, y0, bw, bh, area = st[i]
        if not (H * W * 0.0003 < area < H * W * 0.008):   # small objects only
            continue
        if min(bw, bh) < 0.025 * W or x0 < 5 or y0 < 5 or x0 + bw > W - 5 or y0 + bh > H - 5:
            continue
        sub = (lab[max(y0 - 4, 0):y0 + bh + 4, max(x0 - 4, 0):x0 + bw + 4] == i).astype(np.uint8)
        # fill the object's own holes (the inside of a star), so only its outside is checked
        ff = sub.copy()
        cv2.floodFill(ff, np.zeros((ff.shape[0] + 2, ff.shape[1] + 2), np.uint8), (0, 0), 2)
        sub = (ff != 2).astype(np.uint8)
        ring = cv2.dilate(sub, kernel) - sub
        around = set(np.unique(wlab[max(y0 - 4, 0):y0 + bh + 4, max(x0 - 4, 0):x0 + bw + 4][ring > 0])) - {0}
        if around and around <= border:      # a stand-alone object, not a detail inside a character
            cands.append((i, x0, y0, bw, bh))
    rnd = random.Random(s.get("seed", ctx["page"].id))
    rnd.shuffle(cands)
    count = int(s.get("count", 5))
    picked, mind = [], 0.12 * math.hypot(W, H)
    for cnd in cands:
        cx, cy = cnd[1] + cnd[3] / 2, cnd[2] + cnd[4] / 2
        if all(math.hypot(cx - p[1] - p[3] / 2, cy - p[2] - p[4] / 2) > mind for p in picked):
            picked.append(cnd)
        if len(picked) == count:
            break
    if len(picked) < 3:
        raise SystemExit(f"{ctx['page'].id}: 來源頁 {src} 找不到足夠的獨立小物件（星星、石頭、花等），請換一頁")
    changed = ink.copy()
    for i, *_ in picked:
        changed[lab == i] = 0
    out_pbm = b.dir / "clean" / f"{ctx['page'].id}_diff.pbm"
    cv2.imwrite(str(out_pbm), (1 - changed) * 255)
    out_svg = b.dir / "vector" / f"{ctx['page'].id}_diff.svg"
    subprocess.run(["potrace", str(out_pbm), "-s", "-t", "8", "-O", "0.3", "-o", str(out_svg)], check=True)
    return dict(original=b.dir / "vector" / f"{src}.svg", changed=out_svg, size=(W, H),
                boxes=[p[1:] for p in picked])


def spot_draw(c, box, st, ctx):
    from .layout import place_svg
    x, y, w, h = box
    s = ctx["spec"]
    n = len(st["boxes"])
    below = title(c, s.get("title", f"Find {n} differences!"), x, y, w, h)
    gap = 0.3 * inch
    W, H = st["size"]
    avail = below - y
    # pick the arrangement that gives each picture the larger scale
    stacked = min(w / W, (avail - gap) / 2 / H)
    side = min((w - gap) / 2 / W, avail / H)
    if stacked >= side:
        slot = (avail - gap) / 2
        place_svg(c, st["original"], x, y + slot + gap, w, slot)
        place_svg(c, st["changed"], x, y, w, slot)
    else:
        half = (w - gap) / 2
        place_svg(c, st["original"], x, y, half, avail)
        place_svg(c, st["changed"], x + half + gap, y, half, avail)
        c.setFont(FONT, 12)
        c.drawCentredString(x + half / 2, y + 2, "")
    c.setLineWidth(1.5)
    if not stacked >= side:
        c.saveState()
        c.setDash(4, 4)
        c.line(x + w / 2, y + 0.2 * inch, x + w / 2, below - 0.1 * inch)
        c.restoreState()


def spot_answer(c, box, st, ctx):
    from .layout import place_svg
    x, y, w, h = box
    ox, oy, sc, W, H = place_svg(c, st["original"], x, y, w, h)
    c.setLineWidth(2.2)
    for bx, by, bw, bh in st["boxes"]:
        cx = ox + (bx + bw / 2) * sc
        cy = oy + (H - by - bh / 2) * sc
        c.circle(cx, cy, max(bw, bh) / 2 * sc + 6)


# ---------------------------------------------------------------- plan, draw, challenge
def plan_draw(c, box, st, ctx):
    x, y, w, h = box
    s = ctx["spec"]
    below = title(c, s.get("title", "My Weekend Plan"), x, y, w, h)
    days = s.get("days", ["Saturday", "Sunday"])
    slots = s.get("slots", ["Morning", "Afternoon", "Evening"])
    ideas = s.get("ideas", [])
    grid_h = (below - y) * (0.58 if ideas else 0.95)
    head = 0.4 * inch
    col_w = (w - 0.15 * inch * (len(days) - 1)) / len(days)
    row_h = (grid_h - head) / len(slots)
    for j, d in enumerate(days):
        cx = x + j * (col_w + 0.15 * inch)
        c.setFont(BOLD, 20)
        c.drawCentredString(cx + col_w / 2, below - head + 8, d)
        for i, sl in enumerate(slots):
            top = below - head - i * row_h
            c.setLineWidth(LW * 0.8)
            c.roundRect(cx, top - row_h + 6, col_w, row_h - 6, 10)
            c.setFont(FONT, 12)
            c.drawString(cx + 8, top - 20, sl)
    if ideas:
        top = below - grid_h - 0.25 * inch
        c.setFont(BOLD, 18)
        c.drawString(x, top - 16, s.get("ideas_title", "Things I want to try:"))
        per_col = math.ceil(len(ideas) / 2)
        line_h = min(0.42 * inch, (top - 0.3 * inch - y - 1.0 * inch) / per_col)
        for i, it in enumerate(ideas):
            colx = x + (i // per_col) * w / 2
            checkbox(c, colx, top - 0.55 * inch - (i % per_col) * line_h, 14, it, 13)
    icon(c, ctx, s.get("icon"), x + w, y, 1.0 * inch, align="right")


def draw_draw(c, box, st, ctx):
    x, y, w, h = box
    s = ctx["spec"]
    below = title(c, s.get("title", "Draw your favorite weekend activity!"), x, y, w, h)
    lines = s.get("lines", ["My favorite activity is"])
    write_h = 0.55 * inch * len(lines) + 0.2 * inch
    c.setLineWidth(LW)
    c.roundRect(x, y + write_h, w, below - y - write_h - 0.1 * inch, 18)
    for i, ln in enumerate(lines):
        base = y + write_h - 0.55 * inch * (i + 1)
        c.setFont(FONT, 15)
        c.drawString(x, base + 4, ln)
        c.setLineWidth(LW_THIN)
        c.line(x + c.stringWidth(ln, FONT, 15) + 8, base, x + w, base)
    icon(c, ctx, s.get("icon"), x + w - 12, y + write_h + 12, 1.1 * inch, align="right")


def challenge_draw(c, box, st, ctx):
    x, y, w, h = box
    s = ctx["spec"]
    below = title(c, s.get("title", "Screen-Free Challenge"), x, y, w, h)
    text = s.get("text", "Color a star each day you try a fun activity instead of a screen!")
    subtitle(c, text, x, below + 0.2 * inch, w, 13)
    days = s.get("days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
    icon_h = 1.0 * inch
    row_h = (below - y - icon_h - 0.1 * inch) / len(days)
    for i, d in enumerate(days):
        top = below - i * row_h
        mid = top - row_h / 2
        c.setFont(BOLD, 15)
        c.drawString(x, mid - 5, d)
        lx = x + max(c.stringWidth(dd, BOLD, 15) for dd in days) + 14
        c.setFont(FONT, 12)
        c.drawString(lx, mid - 4, "I did:")
        c.setLineWidth(LW_THIN)
        c.line(lx + c.stringWidth("I did:", FONT, 12) + 6, mid - 6, x + w - row_h * 1.1, mid - 6)
        r = min(row_h * 0.42, 0.42 * inch)
        polygon(c, star_points(x + w - r - 2, mid, r))
        if i < len(days) - 1:
            c.setLineWidth(0.6)
            c.line(x, top - row_h, x + w, top - row_h)
    keys = s.get("icons", ["小黑", "小黃", "小白"])
    for j, k in enumerate(keys):
        icon(c, ctx, k, x + w / 2 + (j - (len(keys) - 1) / 2) * 1.0 * inch, y, icon_h - 0.1 * inch, align="center")


# name: (prepare, draw, answer)
ACTIVITIES = {
    "maze": (maze_prepare, maze_draw, maze_answer),
    "tracing": (None, tracing_draw, None),
    "dot_to_dot": (None, dots_draw, None),
    "spot_difference": (spot_prepare, spot_draw, spot_answer),
    "plan": (None, plan_draw, None),
    "draw": (None, draw_draw, None),
    "challenge": (None, challenge_draw, None),
}
