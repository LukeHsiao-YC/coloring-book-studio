"""Book and character files: loading, paths, page versions."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import config

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "books"
CHARACTERS = ROOT / "characters"
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")


@dataclass
class Page:
    id: str
    scene: str
    characters: list
    age: str
    provider: str
    use: int | None          # pinned version number, None = latest
    notes: str = ""
    caption: str = ""
    type: str = "coloring"   # coloring, or an activity type (see cbs/activities.py)
    spec: dict | None = None  # the page's full entry from book.yaml


class Book:
    def __init__(self, book_id: str):
        self.id = book_id
        self.dir = BOOKS / book_id
        if not (self.dir / "book.yaml").exists():
            raise SystemExit(f"找不到 books/{book_id}/book.yaml")
        self.data = yaml.safe_load((self.dir / "book.yaml").read_text(encoding="utf-8"))
        d = self.data
        self.title = d.get("title", book_id)
        self.trim = d.get("trim", "8.5x11")
        if self.trim not in config.TRIM_SIZES:
            raise SystemExit(f"trim 必須是 {list(config.TRIM_SIZES)} 之一")
        self.paper = d.get("paper", "white")
        self.age = str(d.get("age", "3-5"))
        self.provider = d.get("provider", config.DEFAULT_PROVIDER)
        self.blank_backs = bool(d.get("blank_backs", True))
        self.front_matter = d.get("front_matter", ["belongs_to"])
        self.back_page = d.get("back_page", "note")      # blank / note
        self.answers = bool(d.get("answers", True))       # answer page for mazes and spot-the-difference
        self.price = d.get("price")
        self.cast = Cast(d["cast"]) if d.get("cast") else None
        self.pages = [
            Page(id=str(p["id"]), scene=p.get("scene", ""), characters=p.get("characters", []),
                 age=str(p.get("age", self.age)), provider=p.get("provider", self.provider),
                 use=p.get("use"), notes=p.get("notes", ""), caption=p.get("caption", ""),
                 type=p.get("type", "coloring"), spec=p)
            for p in d.get("pages", [])
        ]
        for sub in ("raw", "clean", "vector", "out"):
            (self.dir / sub).mkdir(exist_ok=True)

    def page(self, page_id: str) -> Page:
        for p in self.pages:
            if p.id == page_id:
                return p
        raise SystemExit(f"book.yaml 裡沒有頁面 {page_id}")

    # ----- versions: raw/<id>_v<N>.<ext> -----
    def versions(self, page_id: str) -> dict:
        out = {}
        for f in (self.dir / "raw").iterdir():
            m = re.fullmatch(rf"{re.escape(page_id)}_v(\d+)", f.stem)
            if m and f.suffix.lower() in IMG_EXT:
                out[int(m.group(1))] = f
        return dict(sorted(out.items()))

    def next_version_path(self, page_id: str, ext=".png") -> Path:
        v = max(self.versions(page_id), default=0) + 1
        return self.dir / "raw" / f"{page_id}_v{v}{ext}"

    def selected_raw(self, page: Page) -> Path | None:
        vs = self.versions(page.id)
        if not vs:
            return None
        if page.use is not None:
            if page.use not in vs:
                raise SystemExit(f"{page.id} 指定 use: {page.use}，但找不到這個版本（有 {list(vs)}）")
            return vs[page.use]
        return vs[max(vs)]


class Cast:
    def __init__(self, name: str):
        self.dir = CHARACTERS / name
        f = self.dir / "cast.yaml"
        if not f.exists():
            raise SystemExit(f"找不到 characters/{name}/cast.yaml")
        self.data = yaml.safe_load(f.read_text(encoding="utf-8"))
        self.members = self.data.get("characters", {})
        self.references = [self.dir / r for r in self.data.get("reference_images", [])]
        self.icons = {k: self.dir / v for k, v in (self.data.get("icons") or {}).items()}
        for r in self.references:
            if not r.exists():
                raise SystemExit(f"角色參考圖不存在：{r}")

    def describe(self, keys: list) -> str:
        keys = keys or list(self.members)
        lines = []
        for k in keys:
            if k not in self.members:
                raise SystemExit(f"cast.yaml 沒有角色 '{k}'（有 {list(self.members)}）")
            c = self.members[k]
            lines.append(f"- {c['name']}: {c['look']}")
        shared = self.data.get("shared", "")
        return "\n".join(lines) + (f"\n{shared}" if shared else "")
