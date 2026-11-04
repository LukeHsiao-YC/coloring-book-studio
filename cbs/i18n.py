"""Built-in text for each edition language. `en` = English only; `zh` = Traditional Chinese
with zhuyin plus English."""

TEXT = {
    "belongs_to": {"en": "This book belongs to:", "zh": "這本書屬於："},
    "test_colors": {"en": "Test your colors", "zh": "試試你的顏色"},
    "answers": {"en": "Answers", "zh": "解答"},
    "back_note": {
        "en": "This page is left blank on purpose to stop markers bleeding through. "
              "Tip: slide a sheet of paper behind the page you are coloring.",
        "zh": "這一頁特意留白，避免畫筆透到下一張圖。塗色時，可以在頁面下面墊一張紙。",
    },
    "plan_days": {"en": ["Saturday", "Sunday"], "zh": ["星期六", "星期日"]},
    "plan_slots": {"en": ["Morning", "Afternoon", "Evening"], "zh": ["早上", "下午", "晚上"]},
    "ideas_title": {"en": "Things I want to try:", "zh": "我想試試看："},
    "week_days": {"en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                  "zh": ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]},
    "i_did": {"en": "I did:", "zh": "我做了："},
}


def t(key: str, lang: str):
    entry = TEXT[key]
    return entry.get(lang, entry["en"])
