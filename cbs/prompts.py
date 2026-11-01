"""Build the full prompt for one page."""
from . import config
from .book import Book, Page


def build_prompt(book: Book, page: Page) -> str:
    preset = config.AGE_PRESETS.get(page.age)
    if not preset:
        raise SystemExit(f"{page.id} 的年齡設定 '{page.age}' 不存在，可用：{list(config.AGE_PRESETS)}")
    parts = [config.BASE_RULES, preset["prompt"]]
    if book.cast:
        parts.append(
            "Characters (match the attached reference images exactly; the line-art sheet shows the target style):\n"
            + book.cast.describe(page.characters)
        )
    parts.append(f"Scene: {page.scene.strip()}")
    if page.notes:
        parts.append(f"Extra instructions: {page.notes.strip()}")
    parts.append("No text on the page other than the chest logo on the jackets.")
    return "\n\n".join(parts)
