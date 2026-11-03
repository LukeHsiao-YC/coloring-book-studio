"""Command line: python3 -m cbs <command> ...   (run `python3 -m cbs -h` for help)"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config
from .book import BOOKS, Book

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

TEMPLATE = """\
title: "{title}"
subtitle: ""
author: ""
trim: 8.5x11          # 8.5x11 / 8.5x8.5 / 8x10
paper: white          # white / cream（影響書脊寬度）
age: "{age}"            # 3-5 或 6-9，單頁可用 age: 覆寫
provider: gemini      # gemini / openai，單頁可用 provider: 覆寫
blank_backs: true     # 每張圖背面留白，避免麥克筆透色
front_matter: [belongs_to, test_colors]   # 書名頁之後的固定頁，可刪
cast: {cast}
cover_page: p01       # 封面用哪一頁的圖

pages:
  - id: p01
    characters: [小白]
    scene: Xiao Bai hugging a big round apple with both arms, smiling.
  - id: p02
    characters: [小黃]
    scene: Xiao Huang sitting on the ground holding a big beach ball above its head. One simple sun in a corner.
"""


def cmd_new(a):
    d = BOOKS / a.book
    if (d / "book.yaml").exists():
        sys.exit(f"books/{a.book} 已經存在")
    d.mkdir(parents=True)
    (d / "book.yaml").write_text(TEMPLATE.format(title=a.title or a.book, age=a.age, cast=a.cast),
                                 encoding="utf-8")
    print(f"已建立 books/{a.book}/book.yaml")


def cmd_prompt(a):
    from .prompts import build_prompt
    b = Book(a.book)
    print(build_prompt(b, b.page(a.page)))
    if b.cast:
        print("\n[記得一併上傳角色參考圖：" + ", ".join(str(r) for r in b.cast.references) + "]")


def cmd_prompts(a):
    """All page prompts in one Markdown file, for generating in the Gemini / ChatGPT web app."""
    from .prompts import build_prompt
    b = Book(a.book)
    lines = [f"# {b.title}：每頁提示詞", "",
             "在 Gemini 或 ChatGPT 開一個新對話，第一則訊息先上傳角色參考圖："
             + "、".join(r.name for r in (b.cast.references if b.cast else [])) + "，然後依序貼上每一頁。", ""]
    for p in b.pages:
        if p.type != "coloring" or (a.missing and b.versions(p.id)):
            continue
        lines += [f"## {p.id}" + (f"：{p.caption}" if p.caption else ""), "", "```", build_prompt(b, p), "```", ""]
    out = b.dir / "prompts.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"→ {out}")


def cmd_gen(a):
    from .generate import generate_page
    b = Book(a.book)
    targets = [b.page(p) for p in a.pages] if a.pages else [p for p in b.pages if p.type == "coloring"]
    if a.missing:
        targets = [p for p in targets if not b.versions(p.id)]
    for p in targets:
        print(f"生成 {p.id} ({a.provider or p.provider}) ...", flush=True)
        try:
            print("  →", generate_page(b, p, a.provider).relative_to(b.dir))
        except Exception as e:  # keep going with the other pages
            print(f"  ✗ 失敗：{e}")


def cmd_import(a):
    from .generate import import_image
    b = Book(a.book)
    print("→", import_image(b, b.page(a.page), Path(a.file)).relative_to(b.dir))


def cmd_status(a):
    b = Book(a.book)
    for p in b.pages:
        if p.type != "coloring":
            print(f"{p.id:6} 活動頁 {p.type}")
            continue
        vs = b.versions(p.id)
        sel = b.selected_raw(p)
        print(f"{p.id:6} {p.age:4} {p.provider:7} 版本 {list(vs) or '-'}  使用 {sel.name if sel else '（尚無圖）'}")


def pricing(pages: int) -> str:
    c = config
    cost = c.PRINT_FIXED_USD + max(0, pages - c.PRINT_FIXED_MAX_PAGES) * c.PRINT_PER_PAGE_USD
    lines = [f"定價試算（Amazon.com，{pages} 頁，印刷成本約 ${cost:.2f}，請以 KDP 計算機為準）",
             "  售價    版稅率  每本實拿   廣告打平 ACoS"]
    for price in c.PRICE_POINTS_USD:
        rate = c.ROYALTY_RATE_HIGH if price >= c.ROYALTY_THRESHOLD_USD else c.ROYALTY_RATE_LOW
        net = price * rate - cost
        acos = f"{net / price * 100:5.1f}%" if net > 0 else "  —"
        lines.append(f"  ${price:<6} {int(rate * 100)}%    ${net:5.2f}     {acos}")
    return "\n".join(lines)


def cmd_build(a):
    from .clean import clean_and_vectorize
    from .layout import art_box, build_cover, build_interior
    from .preflight import check_interior
    from .preview import contact_sheet

    from .activities import ACTIVITIES

    b = Book(a.book)
    box = art_box(b.trim)
    metrics, rows, missing = [], [], []
    items = {}
    # pass 1: coloring pages (activities such as spot-the-difference reuse their cleaned art)
    for p in b.pages:
        if p.type != "coloring":
            if p.type not in ACTIVITIES:
                sys.exit(f"{p.id}: 不認得的頁面類型 '{p.type}'，可用：coloring, {', '.join(ACTIVITIES)}")
            continue
        raw = b.selected_raw(p)
        if not raw:
            missing.append(p.id)
            continue
        m = clean_and_vectorize(raw, b.dir / "clean", b.dir / "vector", p.id, p.age, box)
        metrics.append(m)
        items[p.id] = dict(kind="art", svg=Path(m["svg"]), caption=p.caption)
        side = raw.with_suffix(".txt")
        prov = side.read_text(encoding="utf-8").split(":", 1)[1].strip() if side.exists() else "?"
        rows.append(dict(page=p.id, version=raw.stem.rsplit("_v", 1)[1], provider=prov.split(" ")[0],
                         raw=raw, clean=b.dir / "clean" / f"{p.id}.png"))
        thick = f"（原 {m['original_stroke_mm']} mm，已加粗）" if m["stroke_mm"] != m["original_stroke_mm"] else ""
        print(f"✓ {p.id}  線條 {m['stroke_mm']} mm{thick}  小區塊 {m['tiny_regions']}  灰階 {m['gray_pct']}%")

    # pass 2: activity pages
    answers = []
    icons = b.cast.icons if b.cast else {}
    for p in b.pages:
        if p.type == "coloring":
            continue
        prepare, draw, answer = ACTIVITIES[p.type]
        ctx = dict(book=b, page=p, spec=p.spec or {}, icons=icons)
        state = prepare(ctx) if prepare else {}
        items[p.id] = dict(kind="activity", draw=lambda c, bx, d=draw, s=state, x=ctx: d(c, bx, s, x))
        if answer and b.answers:
            label = (p.spec or {}).get("title") or p.type
            answers.append((label, lambda c, bx, f=answer, s=state, x=ctx: f(c, bx, s, x)))
        print(f"✓ {p.id}  活動頁：{p.type}")
    ordered = [items[p.id] for p in b.pages if p.id in items]
    if not ordered:
        sys.exit("沒有任何頁面可以排版")

    out = b.dir / "out"
    interior = out / "interior.pdf"
    n = build_interior(b.trim, ordered, b.front_matter, b.blank_backs, interior,
                       back_note=(b.back_page == "note"), answers=answers)
    errors, warns = check_interior(interior, b.trim, metrics, {p.id: p.age for p in b.pages})
    if missing:
        warns.insert(0, f"尚無圖片、未排入的頁面：{', '.join(missing)}")
    for r in rows:
        r["warn_count"] = sum(1 for w in warns if w.startswith(r["page"] + ":"))
    contact_sheet(rows, out / "preview.png")

    cover_id = b.data.get("cover_page") or b.pages[0].id
    cover_svg = b.dir / "vector" / f"{cover_id}.svg"
    size = build_cover(b.trim, n, b.paper, b.title, b.data.get("subtitle", ""), b.data.get("author", ""),
                       cover_svg if cover_svg.exists() else None, out / "cover.pdf")
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = [f"內頁：{n} 頁 → out/interior.pdf",
             f"封面：{size['width_in']} x {size['height_in']} 吋，書脊 {size['spine_in']} 吋"
             f"（{'可' if size['spine_text_allowed'] else '不可'}放書脊文字）→ out/cover.pdf",
             "預覽：out/preview.png", ""]
    lines += [f"✗ {e}" for e in errors] or ["✓ 沒有會被 KDP 退件的錯誤"]
    lines += [f"! {w}" for w in warns]
    n_designs = len(ordered)
    lines += ["", f"設計數：{n_designs}（著色 {len(metrics)}、活動 {n_designs - len(metrics)}）", "", pricing(n)]
    report = "\n".join(lines)
    (out / "report.txt").write_text(report, encoding="utf-8")
    print("\n" + report)


def main():
    ap = argparse.ArgumentParser(prog="python3 -m cbs", description="KDP 兒童著色本工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("new", help="建立新書")
    s.add_argument("book"); s.add_argument("--title"); s.add_argument("--cast", default="cats")
    s.add_argument("--age", default="3-5", choices=list(config.AGE_PRESETS)); s.set_defaults(f=cmd_new)
    s = sub.add_parser("prompt", help="印出某頁的完整提示詞（手動生圖用）")
    s.add_argument("book"); s.add_argument("page"); s.set_defaults(f=cmd_prompt)
    s = sub.add_parser("prompts", help="把所有頁面的提示詞存成 prompts.md（網頁版生圖用）")
    s.add_argument("book"); s.add_argument("--missing", action="store_true", help="只列還沒有圖的頁面")
    s.set_defaults(f=cmd_prompts)
    s = sub.add_parser("gen", help="用 API 生圖（不指定頁面＝全部）")
    s.add_argument("book"); s.add_argument("pages", nargs="*")
    s.add_argument("--provider", choices=["gemini", "openai"])
    s.add_argument("--missing", action="store_true", help="只生還沒有圖的頁面"); s.set_defaults(f=cmd_gen)
    s = sub.add_parser("import", help="匯入手動生成的圖片")
    s.add_argument("book"); s.add_argument("page"); s.add_argument("file"); s.set_defaults(f=cmd_import)
    s = sub.add_parser("status", help="列出每頁的版本"); s.add_argument("book"); s.set_defaults(f=cmd_status)
    s = sub.add_parser("build", help="清理、向量化、排版、封面、規格檢查")
    s.add_argument("book"); s.set_defaults(f=cmd_build)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
