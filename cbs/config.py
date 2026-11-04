"""KDP print specs and age presets. Edit numbers here, not in the code."""

# ---------- Amazon KDP paperback (black & white interior) ----------
TRIM_SIZES = {               # inches (width, height)
    "8.5x11": (8.5, 11.0),
    "8.5x8.5": (8.5, 8.5),
    "8x10": (8.0, 10.0),
    "8.25x6": (8.25, 6.0),   # landscape
}
BLEED_IN = 0.125             # added top, bottom and outside edge when bleed is on
MIN_PAGES = 24               # KDP paperback minimum
MIN_DPI = 300                # raster images must be at least this at print size

# Minimum margins (inches) by page count, no-bleed books: (max_pages, inside/gutter)
GUTTER_BY_PAGES = [(150, 0.375), (300, 0.5), (500, 0.625), (700, 0.75), (828, 0.875)]
OUTSIDE_MARGIN_NO_BLEED = 0.25
OUTSIDE_MARGIN_BLEED = 0.375

# Spine thickness per page (inches), KDP black & white interior
SPINE_PER_PAGE = {"white": 0.002252, "cream": 0.0025}
SPINE_TEXT_MIN_PAGES = 79    # KDP allows spine text only from this page count

# Pricing (Amazon.com paperback). Royalty split is from KDP's help page (checked 2026-11-03).
# The print cost figures are NOT confirmed for large trim: sources disagree ($2.15 vs $2.84).
# Check KDP's calculator after uploading and update PRINT_FIXED_USD.
ROYALTY_RATE_HIGH = 0.60          # list price >= 9.99
ROYALTY_RATE_LOW = 0.50           # list price <= 9.98
ROYALTY_THRESHOLD_USD = 9.99
PRINT_FIXED_USD = 2.84            # black ink, fixed up to PRINT_FIXED_MAX_PAGES (verify!)
PRINT_FIXED_MAX_PAGES = 108
PRINT_PER_PAGE_USD = 0.017        # each page above the fixed range (verify!)
PRICE_POINTS_USD = [5.99, 6.99, 7.99, 8.99, 9.99]

# Thicken lines that come out thinner than the age preset's minimum (pixels on the 2x working image)
AUTO_THICKEN = True
AUTO_THICKEN_MAX_PX = 8

# Our own safe zone for artwork (stricter than KDP's minimum, so nothing gets trimmed)
ART_SAFE_MARGIN_IN = 0.75
ART_SAFE_MARGIN_BY_TRIM = {"8.25x6": 0.5}   # small pages get a tighter (still KDP-safe) margin
CAPTION_BAND_IN = {"8.25x6": 0.5}          # height reserved for a caption; default 0.75

# ---------- Age presets ----------
AGE_PRESETS = {
    "3-5": {
        "label": "3–5 歲",
        "target_stroke_mm": (1.8, 3.0),   # 5–8 pt; preflight warns outside this range
        "max_tiny_regions": 15,           # enclosed areas smaller than min_region_mm
        "min_region_mm": 6.0,
        "prompt": (
            "Coloring page for ages 3 to 5. VERY thick, bold black outlines. "
            "Very large simple shapes with big areas to color. One main subject that fills most of the page. "
            "No background or only one or two very simple objects. No small details, no tiny decorations."
        ),
    },
    "6-9": {
        "label": "6–9 歲",
        "target_stroke_mm": (1.1, 2.0),   # 3–5 pt is 1.06–1.76 mm
        "max_tiny_regions": 60,
        "min_region_mm": 4.0,
        "prompt": (
            "Coloring page for ages 6 to 9. Medium-weight clean black outlines. "
            "Characters plus a simple scene background with at most 6 background objects. "
            "Keep every coloring area at least fingertip-sized. "
            "No scattered small decorations: no floating leaves, no sprinkled grass tufts, no confetti, no dense patterns."
        ),
    },
}

# Rules added to every prompt (learned from the 2026-11-01 test round)
BASE_RULES = (
    "Children's coloring book page. Pure black line art on a pure white background. "
    "No shading, no gray tones, no color, no gradients, no hatching, no texture fill. "
    "Every area must be a closed shape that a child can color in. "
    "Portrait orientation, 3:4 aspect ratio. No border or frame. "
    "Leave a clear white margin on all four sides: nothing may touch or be cut off by the edges of the image. "
    "The image MUST be a tall portrait (taller than wide, 3:4), never landscape. Compose for a tall page: "
    "the characters are large and fill the middle, with more sky or wall above them and more ground or floor below them."
)

# ---------- Image generation defaults (change model names here when providers update them) ----------
PROVIDERS = {
    "gemini": {"model": "gemini-2.5-flash-image", "env_key": "GEMINI_API_KEY"},
    "openai": {"model": "gpt-image-2", "env_key": "OPENAI_API_KEY", "size": "1024x1536", "quality": "medium"},
}
DEFAULT_PROVIDER = "gemini"
