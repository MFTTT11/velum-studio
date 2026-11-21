"""High-resolution brand identity renderer for VELUM (@VelumArchive).

Generates supersampled anti-aliased editorial visual identity assets:
- brand_kit/profile_800x800.png   (800x800 channel emblem, legible down to 32px)
- brand_kit/banner_2560x1440.png  (2560x1440 multi-device YouTube banner with 1546x423 safe area)
- brand_kit/watermark_150x150.png (150x150 RGBA broadcast video watermark)
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from core.config import BRAND_DIR, get_logger, load_brand_config, resolve_font

logger = get_logger("brand_kit")


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _load_font(role: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_path = resolve_font(role)
    if font_path:
        try:
            return ImageFont.truetype(font_path, size=size)
        except OSError as exc:
            logger.debug("Font load fallback (%s): %s", font_path, exc)
    return ImageFont.load_default()


def _create_atmospheric_backdrop(
    width: int,
    height: int,
    bg_hex: str,
    cyan_hex: str,
    amber_hex: str,
    crimson_hex: str,
    center_glow: Tuple[float, float] = (0.5, 0.5),
) -> Image.Image:
    """Create a deep obsidian studio backdrop with subtle volumetric lighting."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    nx = xx / max(width - 1, 1)
    ny = yy / max(height - 1, 1)

    base = np.array(hex_to_rgb(bg_hex), dtype=np.float32)
    cyan = np.array(hex_to_rgb(cyan_hex), dtype=np.float32)
    amber = np.array(hex_to_rgb(amber_hex), dtype=np.float32)
    crimson = np.array(hex_to_rgb(crimson_hex), dtype=np.float32)

    cx, cy = center_glow
    d_center = np.sqrt(((nx - cx) * 1.1) ** 2 + ((ny - cy) * 1.1) ** 2)
    glow_cyan = np.exp(-(d_center**2) / 0.16) * 0.20

    d_amber = np.sqrt(((nx - 0.80) * 1.3) ** 2 + ((ny - 0.26) * 1.5) ** 2)
    glow_amber = np.exp(-(d_amber**2) / 0.14) * 0.14

    d_crim = np.sqrt(((nx - 0.18) * 1.4) ** 2 + ((ny - 0.78) * 1.5) ** 2)
    glow_crim = np.exp(-(d_crim**2) / 0.12) * 0.08

    d_edge = np.sqrt((nx - 0.5) ** 2 + (ny - 0.5) ** 2)
    vignette = np.clip(1.0 - 0.45 * (d_edge**1.8), 0.55, 1.0)

    img = np.zeros((height, width, 3), dtype=np.float32)
    for c in range(3):
        channel = (
            base[c]
            + cyan[c] * glow_cyan
            + amber[c] * glow_amber
            + crimson[c] * glow_crim
        ) * vignette
        img[:, :, c] = np.clip(channel, 0, 255)

    rng = np.random.default_rng(77)
    noise = rng.normal(0.0, 1.7, size=(height, width, 1)).astype(np.float32)
    img = np.clip(img + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(img, mode="RGB").convert("RGBA")


def _draw_precision_grid(
    canvas: Image.Image, step: int, line_rgba: Tuple[int, int, int, int]
) -> None:
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = canvas.size
    for x in range(0, w, step):
        draw.line([(x, 0), (x, h)], fill=line_rgba, width=1)
    for y in range(0, h, step):
        draw.line([(0, y), (w, y)], fill=line_rgba, width=1)
    cross_rgba = (line_rgba[0], line_rgba[1], line_rgba[2], min(255, line_rgba[3] * 3))
    for x in range(0, w, step * 4):
        for y in range(0, h, step * 4):
            draw.line([(x - 6, y), (x + 6, y)], fill=cross_rgba, width=2)
            draw.line([(x, y - 6), (x, y + 6)], fill=cross_rgba, width=2)
    canvas.alpha_composite(overlay)


def _draw_velum_emblem(
    canvas: Image.Image,
    cx: int,
    cy: int,
    radius: int,
    palette: Dict[str, str],
) -> None:
    """Draw the iconic VELUM architectural split-aperture 'V' monogram inside a telemetry ring."""
    cyan = hex_to_rgb(palette["accent_cyan"])
    amber = hex_to_rgb(palette["accent_amber"])
    crimson = hex_to_rgb(palette["accent_crimson"])
    white = hex_to_rgb(palette["text_primary"])

    # Geometric V coordinates (parting the veil toward a focal apex)
    top_y = cy - int(radius * 0.56)
    bot_y = cy + int(radius * 0.64)
    left_x = cx - int(radius * 0.56)
    right_x = cx + int(radius * 0.56)
    arm_w = max(5, int(radius * 0.155))

    # 1. Atmospheric bloom behind the monogram
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
    gdraw.arc(bbox, start=130, end=255, fill=(*cyan, 180), width=max(8, int(radius * 0.08)))
    gdraw.arc(bbox, start=-75, end=50, fill=(*amber, 165), width=max(8, int(radius * 0.08)))
    gdraw.line([(left_x, top_y), (cx, bot_y)], fill=(*cyan, 210), width=arm_w + 10)
    gdraw.line([(right_x, top_y), (cx, bot_y)], fill=(*amber, 210), width=arm_w + 10)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(6, radius // 8)))
    canvas.alpha_composite(glow)

    # 2. Razor-sharp geometric foreground
    fg = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(fg)

    # Precision orbital tick ring
    dial_r = int(radius * 1.22)
    for deg in range(0, 360, 6):
        rad = math.radians(deg)
        is_major = deg % 30 == 0
        in_r = dial_r - (int(radius * 0.085) if is_major else int(radius * 0.04))
        x1 = cx + int(math.cos(rad) * in_r)
        y1 = cy + int(math.sin(rad) * in_r)
        x2 = cx + int(math.cos(rad) * dial_r)
        y2 = cy + int(math.sin(rad) * dial_r)
        alpha = 150 if is_major else 55
        draw.line([(x1, y1), (x2, y2)], fill=(*cyan, alpha), width=max(2, radius // 95))

    # Outer split precision arcs (evoking parted veil)
    ring_w = max(4, int(radius * 0.068))
    draw.arc(bbox, start=125, end=255, fill=(*white, 235), width=ring_w)
    draw.arc(bbox, start=-75, end=55, fill=(*white, 235), width=ring_w)

    # Inner hairline circle
    thin_r = int(radius * 1.09)
    draw.ellipse([cx - thin_r, cy - thin_r, cx + thin_r, cy + thin_r], outline=(*white, 42), width=max(2, radius // 115))

    # Architectural split VELUM 'V' polygons (crisp beveled studio mark)
    # Left veil blade (Titanium White + Cyan inner bevel)
    left_poly = [
        (left_x - int(arm_w * 0.55), top_y),
        (left_x + int(arm_w * 0.55), top_y),
        (cx - int(arm_w * 0.10), bot_y - int(arm_w * 0.45)),
        (cx - int(arm_w * 0.62), bot_y - int(arm_w * 0.15)),
    ]
    draw.polygon(left_poly, fill=(*white, 255))

    # Right veil blade (Signal Amber gold -> radiant architectural contrast)
    right_poly = [
        (right_x - int(arm_w * 0.55), top_y),
        (right_x + int(arm_w * 0.55), top_y),
        (cx + int(arm_w * 0.12), bot_y),
        (cx - int(arm_w * 0.36), bot_y - int(arm_w * 0.32)),
    ]
    draw.polygon(right_poly, fill=(*amber, 255))

    # Cyan veil-parting light beam slicing cleanly along the left inner edge
    beam_w = max(3, int(radius * 0.045))
    draw.line(
        [(left_x + int(arm_w * 0.62), top_y), (cx - int(arm_w * 0.06), bot_y - int(arm_w * 0.45))],
        fill=(*cyan, 255),
        width=beam_w,
    )

    # Crimson focal apex diamond hovering in the upper aperture of the V
    apex_y = cy - int(radius * 0.34)
    d = max(5, int(radius * 0.115))
    draw.polygon(
        [(cx, apex_y - d), (cx + d, apex_y), (cx, apex_y + d), (cx - d, apex_y)],
        fill=(*crimson, 255),
    )
    pin = max(2, d // 3)
    draw.polygon(
        [(cx, apex_y - pin), (cx + pin, apex_y), (cx, apex_y + pin), (cx - pin, apex_y)],
        fill=(255, 255, 255, 235),
    )

    canvas.alpha_composite(fg)


def render_profile_avatar(output_path: Path, brand: Dict) -> Path:
    """Render 800x800 high-resolution minimalist VELUM profile emblem (2x supersampled)."""
    palette = brand["palette"]
    ss = 2
    size = 800 * ss
    canvas = _create_atmospheric_backdrop(
        size,
        size,
        palette["bg_obsidian"],
        palette["accent_cyan"],
        palette["accent_amber"],
        palette["accent_crimson"],
        center_glow=(0.5, 0.46),
    )
    _draw_precision_grid(canvas, step=80, line_rgba=(30, 41, 66, 60))

    _draw_velum_emblem(canvas, size // 2, int(size * 0.45), int(size * 0.275), palette)

    fg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(fg)
    font = _load_font("mono", int(size * 0.056))
    label = "V E L U M"
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((size - tw) // 2, int(size * 0.805)), label, font=font, fill=(*hex_to_rgb(palette["text_primary"]), 240))

    cyan = hex_to_rgb(palette["accent_cyan"])
    pad, arm, bw = 90, 54, 5
    for (x0, y0, sx, sy) in [
        (pad, pad, 1, 1),
        (size - pad, pad, -1, 1),
        (pad, size - pad, 1, -1),
        (size - pad, size - pad, -1, -1),
    ]:
        draw.line([(x0, y0), (x0 + sx * arm, y0)], fill=(*cyan, 110), width=bw)
        draw.line([(x0, y0), (x0, y0 + sy * arm)], fill=(*cyan, 110), width=bw)

    canvas.alpha_composite(fg)
    final = canvas.convert("RGB").resize((800, 800), Image.Resampling.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(output_path, format="PNG", optimize=True)
    logger.info("Rendered VELUM profile emblem: %s (800x800)", output_path.name)
    return output_path


def render_banner(output_path: Path, brand: Dict) -> Path:
    """Render 2560x1440 multi-device YouTube banner (all branding inside 1546x423 safe zone)."""
    palette = brand["palette"]
    w, h = 2560, 1440
    canvas = _create_atmospheric_backdrop(
        w,
        h,
        palette["bg_obsidian"],
        palette["accent_cyan"],
        palette["accent_amber"],
        palette["accent_crimson"],
        center_glow=(0.35, 0.50),
    )
    _draw_precision_grid(canvas, step=64, line_rgba=(30, 41, 66, 70))

    cyan = hex_to_rgb(palette["accent_cyan"])
    amber = hex_to_rgb(palette["accent_amber"])
    crimson = hex_to_rgb(palette["accent_crimson"])
    emerald = hex_to_rgb(palette["accent_emerald"])
    white = hex_to_rgb(palette["text_primary"])
    muted = hex_to_rgb(palette["text_secondary"])

    bg_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(bg_overlay)

    pts_curve1, pts_curve2 = [], []
    for x in range(0, w + 16, 16):
        t = x / w
        y1 = int(h * 0.78 - (h * 0.54) * (t**2.2) + math.sin(t * 14.0) * 18)
        y2 = int(h * 0.72 - (h * 0.34) * (t**1.6) + math.cos(t * 10.0) * 14)
        pts_curve1.append((x, y1))
        pts_curve2.append((x, y2))
    bdraw.line(pts_curve1, fill=(*cyan, 68), width=4)
    bdraw.line(pts_curve2, fill=(*amber, 52), width=3)

    for idx, bh in enumerate([90, 150, 220, 310, 180, 260, 420]):
        bx = 90 + idx * 52
        bdraw.rectangle([bx, 930 - bh, bx + 28, 930], fill=(*cyan, 26), outline=(*cyan, 68), width=1)
    for idx, bh in enumerate([140, 240, 190, 340, 480, 620, 760]):
        bx = 2110 + idx * 54
        col = amber if idx >= 5 else cyan
        bdraw.rectangle([bx, 1040 - bh, bx + 30, 1040], fill=(*col, 30), outline=(*col, 78), width=1)

    bdraw.line([(0, 508), (w, 508)], fill=(*cyan, 50), width=2)
    bdraw.line([(0, 932), (w, 932)], fill=(*cyan, 50), width=2)

    mono_sm = _load_font("mono", 22)
    bdraw.text((100, 110), "VELUM ARCHIVE // VISUAL DOCUMENTARY TELEMETRY", fill=(*muted, 110), font=mono_sm)
    bdraw.text((1995, 110), "60FPS MASTER  |  EMPIRICAL DATA", fill=(*muted, 110), font=mono_sm)
    bdraw.text((100, 1300), "VISUAL COMPARISONS • HIDDEN INFRASTRUCTURE • EXTREME REALITY", fill=(*muted, 95), font=mono_sm)
    canvas.alpha_composite(bg_overlay)

    # Universal safe-area frosted studio panel (x=535..2025, y=534..906)
    panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(panel)
    pdraw.rounded_rectangle(
        [535, 534, 2025, 906],
        radius=26,
        fill=(10, 14, 24, 212),
        outline=(*cyan, 115),
        width=2,
    )
    pdraw.rounded_rectangle([551, 560, 561, 880], radius=5, fill=(*amber, 240))
    canvas.alpha_composite(panel)

    _draw_velum_emblem(canvas, cx=735, cy=720, radius=118, palette=palette)

    fg_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(fg_layer)
    font_title = _load_font("headline", 122)
    font_sub_badge = _load_font("mono", 30)
    font_tag = _load_font("body", 31)
    font_pill = _load_font("mono", 22)
    font_handle = _load_font("mono", 26)

    tx = 925
    ty = 562

    draw.text((tx, ty), "VELUM", font=font_title, fill=(*white, 255))
    w1 = draw.textbbox((tx, ty), "VELUM", font=font_title)[2]
    draw.text((w1 + 22, ty + 46), "// ARCHIVE", font=font_sub_badge, fill=(*amber, 245))

    div_y = ty + 136
    draw.line([(tx, div_y), (1965, div_y)], fill=(*white, 55), width=2)
    draw.line([(tx, div_y), (tx + 260, div_y)], fill=(*cyan, 255), width=3)

    tagline = "VISUAL COMPARISONS  •  HIDDEN SYSTEMS  •  EXTREME REALITY"
    draw.text((tx, div_y + 22), tagline, font=font_tag, fill=(*white, 235))

    pills = [
        ("CAPITAL & POWER", amber),
        ("INFRASTRUCTURE", cyan),
        ("COGNITION", crimson),
        ("PHYSICS", emerald),
    ]
    px = tx
    py = div_y + 82
    for label, col in pills:
        tb = draw.textbbox((0, 0), label, font=font_pill)
        pw = (tb[2] - tb[0]) + 34
        ph = 44
        draw.rounded_rectangle(
            [px, py, px + pw, py + ph],
            radius=8,
            fill=(col[0], col[1], col[2], 38),
            outline=(*col, 225),
            width=2,
        )
        draw.text((px + 17, py + 10), label, font=font_pill, fill=(*white, 255))
        px += pw + 16

    handle_text = brand["handle"].upper()
    hb = draw.textbbox((0, 0), handle_text, font=font_handle)
    draw.text((1965 - (hb[2] - hb[0]), 566), handle_text, font=font_handle, fill=(*cyan, 235))

    canvas.alpha_composite(fg_layer)
    final = canvas.convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(output_path, format="PNG", optimize=True)
    logger.info("Rendered VELUM banner: %s (2560x1440)", output_path.name)
    return output_path


def render_watermark(output_path: Path, brand: Dict) -> Path:
    """Render 150x150 RGBA VELUM broadcast video watermark."""
    palette = brand["palette"]
    ss = 2
    size = 150 * ss
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    bg = hex_to_rgb(palette["bg_obsidian"])
    amber = hex_to_rgb(palette["accent_amber"])

    margin = 14
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=44,
        fill=(*bg, 225),
        outline=(*amber, 215),
        width=6,
    )
    _draw_velum_emblem(canvas, size // 2, size // 2, int(size * 0.28), palette)

    final = canvas.resize((150, 150), Image.Resampling.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(output_path, format="PNG", optimize=True)
    logger.info("Rendered VELUM watermark: %s (150x150 RGBA)", output_path.name)
    return output_path


def ensure_brand_kit(force: bool = False) -> Dict[str, Path]:
    """Ensure all brand kit assets exist on disk; generate missing or when forced."""
    brand = load_brand_config()
    profile_path = BRAND_DIR / "profile_800x800.png"
    banner_path = BRAND_DIR / "banner_2560x1440.png"
    watermark_path = BRAND_DIR / "watermark_150x150.png"

    if force or not profile_path.exists():
        render_profile_avatar(profile_path, brand)
    if force or not banner_path.exists():
        render_banner(banner_path, brand)
    if force or not watermark_path.exists():
        render_watermark(watermark_path, brand)

    return {
        "profile": profile_path,
        "banner": banner_path,
        "watermark": watermark_path,
        "brand_json": BRAND_DIR / "brand.json",
    }


if __name__ == "__main__":
    ensure_brand_kit(force=True)
