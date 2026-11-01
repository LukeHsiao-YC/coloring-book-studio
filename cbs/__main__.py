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
    characters: [white]
    scene: White Cat hugging a big round apple with both arms, smiling.
  - id: p02
    characters: [tabby]
    scene: Tabby Cat sitting on the ground holding a big beach ball above its head. One simple sun in a corner.
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


def cmd_gen(a):
    from .generate import generate_page
    b = Book(a.book)
    targets = [b.page(p) for p in a.pages] if a.pages else b.pages
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
        vs = b.versions(p.id)
        sel = b.selected_raw(p)
        print(f"{p.id:6} {p.age:4} {p.provider:7} 版本 {list(vs) or '-'}  使用 {sel.name if sel else '（尚無圖）'}")


def cmd_build(a):
    from .clean import clean_and_vectorize
    from .layout import art_box, build_cover, build_interior
    from .preflight import check_interior
    from .preview import contact_sheet

    b = Book(a.book)
    box = art_box(b.trim)
    metrics, svgs, rows, missing = [], [], [], []
    for p in b.pages:
        raw = b.selected_raw(p)
        if not raw:
            missing.append(p.id)
            continue
        m = clean_and_vectorize(raw, b.dir / "clean", b.dir / "vector", p.id, p.age, box)
        metrics.append(m)
        svgs.append(Path(m["svg"]))
        side = raw.with_suffix(".txt")
        prov = side.read_text(encoding="utf-8").split(":", 1)[1].strip() if side.exists() else "?"
        rows.append(dict(page=p.id, version=raw.stem.rsplit("_v", 1)[1], provider=prov.split(" ")[0],
                         raw=raw, clean=b.dir / "clean" / f"{p.id}.png"))
        print(f"✓ {p.id}  線條 {m['stroke_mm']} mm  小區塊 {m['tiny_regions']}  灰階 {m['gray_pct']}%")
    if not svgs:
        sys.exit("沒有任何頁面有圖片")

    out = b.dir / "out"
    interior = out / "interior.pdf"
    n = build_interior(b.trim, svgs, b.front_matter, b.blank_backs, interior)
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
