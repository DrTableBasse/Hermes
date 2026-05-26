"""Generate achievement unlock banner images using Pillow."""
import io
from PIL import Image, ImageDraw, ImageFont


def _tier_color(points: int) -> tuple:
    if points >= 100:
        return (255, 215, 0)    # Gold
    if points >= 50:
        return (192, 192, 192)  # Silver
    if points >= 25:
        return (205, 127, 50)   # Bronze
    return (100, 149, 237)      # Blue (common)


def generate_achievement_image(
    achievement_name: str,
    achievement_desc: str,
    achievement_icon: str,
    points: int,
    username: str,
) -> io.BytesIO:
    """Return a BytesIO PNG image for the achievement unlock."""
    W, H = 700, 220
    tier_color = _tier_color(points)

    img = Image.new('RGBA', (W, H), (30, 30, 40, 255))
    draw = ImageDraw.Draw(img)

    # Gradient border
    for i in range(4):
        draw.rectangle([i, i, W - 1 - i, H - 1 - i], outline=(*tier_color, 255 - i * 40))

    # Left colored accent bar
    draw.rectangle([0, 0, 8, H], fill=(*tier_color, 255))

    # Load fonts with fallback to default
    try:
        font_big = ImageFont.truetype("arial.ttf", 60)
        font_title = ImageFont.truetype("arial.ttf", 26)
        font_body = ImageFont.truetype("arial.ttf", 18)
        font_small = ImageFont.truetype("arial.ttf", 14)
    except Exception:
        font_big = font_title = font_body = font_small = ImageFont.load_default()

    # Icon
    draw.text((30, H // 2 - 40), achievement_icon, font=font_big, fill=(255, 255, 255, 255))

    # "Achievement débloqué !"
    draw.text((140, 25), "Achievement débloqué !", font=font_small, fill=(*tier_color, 255))

    # Achievement name
    draw.text((140, 50), achievement_name, font=font_title, fill=(255, 255, 255, 255))

    # Description
    draw.text((140, 90), achievement_desc[:80], font=font_body, fill=(200, 200, 200, 255))

    # Points
    pts_text = f"+{points} pts"
    draw.text((140, 125), pts_text, font=font_body, fill=(*tier_color, 255))

    # Username at bottom right
    draw.text((W - 200, H - 30), f"@{username}", font=font_small, fill=(150, 150, 150, 255))

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf
