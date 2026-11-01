"""Image generation through provider APIs, plus manual import.

Generation needs network access to the provider, so it runs on your Mac.
Everything after generation (clean, vectorize, layout, check) runs anywhere.
"""
from __future__ import annotations

import base64
import os
import shutil
from pathlib import Path

from . import config
from .book import Book, Page
from .prompts import build_prompt


def _key(provider: str) -> str:
    env = config.PROVIDERS[provider]["env_key"]
    key = os.environ.get(env)
    if not key:
        raise SystemExit(f"沒有設定 {env}。請在 .env 檔填入 API 金鑰（見 README）。")
    return key


def _gemini(prompt: str, refs: list[Path]) -> bytes:
    from google import genai
    from google.genai import types
    from PIL import Image

    client = genai.Client(api_key=_key("gemini"))
    contents = [prompt] + [Image.open(r) for r in refs]
    try:
        cfg = types.GenerateContentConfig(response_modalities=["IMAGE"],
                                          image_config=types.ImageConfig(aspect_ratio="3:4"))
    except (AttributeError, TypeError):          # older SDK without image_config
        cfg = types.GenerateContentConfig(response_modalities=["IMAGE"])
    resp = client.models.generate_content(model=config.PROVIDERS["gemini"]["model"],
                                          contents=contents, config=cfg)
    for cand in resp.candidates or []:
        for part in cand.content.parts or []:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                data = part.inline_data.data
                return data if isinstance(data, bytes) else base64.b64decode(data)
    raise RuntimeError("Gemini 沒有回傳圖片（可能被安全過濾擋下，試著改寫場景描述）。")


def _openai(prompt: str, refs: list[Path]) -> bytes:
    from openai import OpenAI

    p = config.PROVIDERS["openai"]
    client = OpenAI(api_key=_key("openai"))
    files = [open(r, "rb") for r in refs]
    try:
        if files:
            res = client.images.edit(model=p["model"], image=files, prompt=prompt,
                                     size=p["size"], quality=p["quality"])
        else:
            res = client.images.generate(model=p["model"], prompt=prompt,
                                         size=p["size"], quality=p["quality"])
    finally:
        for f in files:
            f.close()
    return base64.b64decode(res.data[0].b64_json)


PROVIDER_FUNCS = {"gemini": _gemini, "openai": _openai}


def generate_page(book: Book, page: Page, provider: str | None = None) -> Path:
    provider = provider or page.provider
    if provider not in PROVIDER_FUNCS:
        raise SystemExit(f"未知的生圖來源 '{provider}'，可用：{list(PROVIDER_FUNCS)}")
    refs = book.cast.references if book.cast else []
    data = PROVIDER_FUNCS[provider](build_prompt(book, page), refs)
    out = book.next_version_path(page.id, ".png")
    out.write_bytes(data)
    (out.with_suffix(".txt")).write_text(f"provider: {provider}\n", encoding="utf-8")
    return out


def import_image(book: Book, page: Page, src: Path) -> Path:
    """Manual flow: bring in an image you made in the Gemini / ChatGPT web app."""
    if not src.exists():
        raise SystemExit(f"找不到檔案 {src}")
    out = book.next_version_path(page.id, src.suffix.lower())
    shutil.copy(src, out)
    (out.with_suffix(".txt")).write_text(f"provider: manual ({src.name})\n", encoding="utf-8")
    return out
