"""Built-in SLH Spark social creatives, generated on demand by SLH OS.

The library is fully self-contained: no user upload or external image URL is
required. PNG bytes are rendered with Pillow and can be served by the WebApp
or sent directly through the Telegram Bot API.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from typing import Any
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1200
HEIGHT = 630

_ASSETS: dict[str, dict[str, Any]] = {
    "brand": {
        "title": "SLH SPARK",
        "subtitle": "SMART LEARNING HUB",
        "kicker": "LEARN  •  BUILD  •  CONNECT",
        "caption": (
            "✨ SLH Spark — Smart Learning Hub\n"
            "לומדים, יוצרים ומתקדמים עם AI וקהילה.\n"
            "בלי הבטחות לרווח מהיר — ידע שהופכים לפעולה."
        ),
        "accent": (80, 220, 210),
        "glow": (40, 92, 202),
    },
    "academy": {
        "title": "LEARN. BUILD. REPEAT.",
        "subtitle": "SLH SPARK ACADEMY",
        "kicker": "PRACTICAL LEARNING  •  AI SUPPORT",
        "caption": (
            "🎓 SLH Spark Academy\n"
            "למידה מעשית, קורסים וכלים להתקדמות בקצב שלך.\n"
            "מתחילים בידע — ממשיכים בעשייה."
        ),
        "accent": (105, 235, 170),
        "glow": (22, 125, 108),
    },
    "agents": {
        "title": "YOUR AI WORKSPACE",
        "subtitle": "PLAN  •  CREATE  •  IMPROVE",
        "kicker": "AI TOOLS FOR YOUR WORKFLOW",
        "caption": (
            "🤖 מרחב העבודה של SLH Spark\n"
            "ארגנו רעיונות, תכננו צעדים והפכו משימות לתהליך ברור.\n"
            "AI הוא כלי לעבודה חכמה — לא תחליף לשיקול דעת."
        ),
        "accent": (190, 145, 255),
        "glow": (105, 52, 184),
    },
    "community": {
        "title": "GROW WITH THE COMMUNITY",
        "subtitle": "LEARNING  •  CREATIVITY  •  PROGRESS",
        "kicker": "SMALL STEPS. REAL SKILLS.",
        "caption": (
            "🌱 מתקדמים יחד ב־SLH Spark\n"
            "למידה, יצירה וקהילה — צעד אחד בכל פעם.\n"
            "אין הבטחת רווח; כל החלטה כלכלית כוללת סיכון."
        ),
        "accent": (255, 190, 100),
        "glow": (158, 76, 30),
    },
    "ecosystem": {
        "title": "ONE HUB. MORE POSSIBILITIES.",
        "subtitle": "SMART LAYER HUB  •  SLH OS",
        "kicker": "LEARNING  /  AI  /  COMMUNITY",
        "caption": (
            "🚀 הכירו את SLH OS\n"
            "מרכז אחד ללמידה, כלי AI ופעילות קהילתית.\n"
            "הכירו את הכלים ובחרו את הצעד הבא שלכם."
        ),
        "accent": (90, 190, 255),
        "glow": (25, 92, 180),
    },
}


def asset_ids() -> tuple[str, ...]:
    """Return stable identifiers for the built-in brand gallery."""
    return tuple(_ASSETS)


def get_asset(asset_id: str) -> dict[str, Any]:
    """Return a copy of one curated asset entry."""
    key = str(asset_id or "").strip().lower()
    item = _ASSETS.get(key)
    if item is None:
        raise KeyError("SOCIAL_ASSET_NOT_FOUND")
    return {
        "id": key,
        "title": item["title"],
        "subtitle": item["subtitle"],
        "kicker": item["kicker"],
        "caption": item["caption"],
        "content_type": "image/png",
        "width": WIDTH,
        "height": HEIGHT,
    }


def list_assets(base_url: str) -> list[dict[str, Any]]:
    """Return public card metadata and direct image URLs for the gallery."""
    base = str(base_url or "").strip().rstrip("/")
    output = []
    for key in _ASSETS:
        item = get_asset(key)
        safe_id = quote(key, safe="")
        item["image_url"] = f"{base}/api/v1/social/assets/{safe_id}.png"
        item["share_url"] = f"{base}/share/{safe_id}"
        output.append(item)
    return output


def _font(size: int, *, bold: bool = False):
    candidates = (
        ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        if bold else
        ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _centered(draw, text: str, y: int, font, fill, *, max_width: int = 1000):
    value = str(text)
    # All creative headlines are authored locally and contain at most one line.
    box = draw.textbbox((0, 0), value, font=font)
    width = box[2] - box[0]
    if width > max_width:
        base_size = int(getattr(font, "size", 18) or 18)
        scale = max(12, int(base_size * max_width / max(width, 1)))
        font = _font(scale, bold=base_size >= 40)
        box = draw.textbbox((0, 0), value, font=font)
        width = box[2] - box[0]
    draw.text(((WIDTH - width) / 2, y), value, font=font, fill=fill)


@lru_cache(maxsize=len(_ASSETS))
def render_social_asset(asset_id: str) -> bytes:
    """Render a branded 1200×630 PNG in memory; never writes state or files."""
    key = str(asset_id or "").strip().lower()
    item = _ASSETS.get(key)
    if item is None:
        raise KeyError("SOCIAL_ASSET_NOT_FOUND")

    accent = item["accent"]
    glow = item["glow"]
    image = Image.new("RGB", (WIDTH, HEIGHT), (8, 13, 33))
    pixels = image.load()
    # Subtle horizontal/vertical gradient with no external artwork dependency.
    for y in range(HEIGHT):
        for x in range(WIDTH):
            t = x / max(1, WIDTH - 1)
            v = y / max(1, HEIGHT - 1)
            base = (
                int(8 + 12 * t),
                int(13 + 8 * v),
                int(33 + 20 * t),
            )
            pixels[x, y] = base

    draw = ImageDraw.Draw(image, "RGBA")
    draw.ellipse((760, -190, 1370, 420), fill=(*glow, 66), outline=(*accent, 90), width=3)
    draw.ellipse((-170, 330, 360, 860), fill=(*accent, 24), outline=(*accent, 50), width=2)
    draw.rounded_rectangle((52, 52, WIDTH - 52, HEIGHT - 52), radius=34,
                           outline=(255, 255, 255, 44), width=2)
    draw.rounded_rectangle((84, 88, 104, HEIGHT - 88), radius=10, fill=(*accent, 220))
    draw.rounded_rectangle((150, 104, 342, 145), radius=18, fill=(*accent, 32),
                           outline=(*accent, 120), width=1)
    draw.text((171, 112), "SLH  /  SPARK", font=_font(19, bold=True), fill=(235, 247, 255, 255))

    title = item["title"]
    _centered(draw, title, 214, _font(62, bold=True), (249, 251, 255, 255), max_width=990)
    _centered(draw, item["subtitle"], 320, _font(27, bold=True), (*accent, 255), max_width=990)
    draw.line((280, 390, 920, 390), fill=(*accent, 150), width=2)
    _centered(draw, item["kicker"], 421, _font(21, bold=True), (211, 222, 243, 255), max_width=980)
    _centered(draw, "slh-nft.com", 520, _font(20, bold=True), (157, 178, 210, 255), max_width=600)

    target = BytesIO()
    image.save(target, format="PNG", optimize=True)
    return target.getvalue()
