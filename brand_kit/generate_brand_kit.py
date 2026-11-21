"""High-resolution brand kit renderer for SCALE // ZERO.

Generates supersampled anti-aliased Netflix/Vox-grade visual identity assets:
- brand_kit/profile_800x800.png   (800x800 channel avatar, readable down to 32px)
- brand_kit/banner_2560x1440.png  (2560x1440 multi-device YouTube banner with 1546x423 safe zone)
- brand_kit/watermark_150x150.png (150x150 RGBA video branding watermark)
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
    """Create a deep obsidian editorial backdrop with subtle dual-tone volumetric lighting."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    nx = xx / max(width - 1, 1)
    ny = yy / max(height - 1, 1)

    base = np.array(hex_to_rgb(bg_hex), dtype=np.float32)
    cyan = np.array(hex_to_rgb(cyan_hex), dtype=np.float32)
    amber = np.array(hex_to_rgb(amber_hex), dtype=np.float32)
    crimson = np.array(hex_to_rgb(crimson_hex), dtype=np.float32)

    cx, cy = center_glow
    d_center = np.sqrt(((nx - cx) * 1.1) ** 2 + ((ny - cy) * 1.1) ** 2)
    glow_cyan = np.exp(-(d_center**2) / 0.16) * 0.22

    d_amber = np.sqrt(((nx - 0.82) * 1.3) ** 2 + ((ny - 0.25) * 1.5) ** 2)
    glow_amber = np.exp(-(d_amber**2) / 0.14) * 0.14

    d_crim = np.sqrt(((nx - 0.16) * 1.4) ** 2 + ((ny - 0.78) * 1.5) ** 2)
    glow_crim = np.exp(-(d_crim**2) / 0.12) * 0.08

    # Edge vignette
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

    # Subtle deterministic editorial micro-grain (anti-banding)
    rng = np.random.default_rng(42)
    noise = rng.normal(0.0, 1.8, size=(height, width, 1)).astype(np.float32)
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
    # Crosshair intersections every 4th cell
    cross_rgba = (line_rgba[0], line_rgba[1], line_rgba[2], min(255, line_rgba[3] * 3))
    for x in range(0, w, step * 4):
        for y in range(0, h, step * 4):
            draw.line([(x - 6, y), (x + 6, y)], fill=cross_rgba, width=2)
            draw.line([(x, y - 6), (x, y + 6)], fill=cross_rgba, width=2)
    canvas.alpha_composite(overlay)


def _draw_emblem(
    canvas: Image.Image,
    cx: int,
    cy: int,
    radius: int,
    palette: Dict[str, str],
) -> None:
    """Draw the iconic SCALE // ZERO precision reticle emblem with bloom."""
    cyan = hex_to_rgb(palette["accent_cyan"])
    amber = hex_to_rgb(palette["accent_amber"])
    crimson = hex_to_rgb(palette["accent_crimson"])
    white = hex_to_rgb(palette["text_primary"])

    # 1. Glow layer (blurred behind crisp vector strokes)
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    stroke = max(4, int(radius * 0.105))

    # Outer cyan aura ring
    bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
    gdraw.arc(bbox, start=20, end=170, fill=(*cyan, 190), width=stroke + 8)
    gdraw.arc(bbox, start=200, end=350, fill=(*amber, 165), width=stroke + 8)

    # Diagonal slash glow
    s_dx = int(radius * 0.56)
    s_dy = int(radius * 0.78)
    gdraw.line(
        [(cx - s_dx, cy + s_dy), (cx + s_dx, cy - s_dy)],
        fill=(*cyan, 210),
        width=max(6, int(radius * 0.14)),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(6, radius // 8)))
    canvas.alpha_composite(glow)

    # 2. Sharp geometric foreground layer
    fg = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(fg)

    # Subtle outer telemetry dial ticks
    dial_r = int(radius * 1.24)
    for deg in range(0, 360, 6):
        rad = math.radians(deg)
        is_major = deg % 30 == 0
        inner_r = dial_r - (int(radius * 0.09) if is_major else int(radius * 0.045))
        x1 = cx + int(math.cos(rad) * inner_r)
        y1 = cy + int(math.sin(rad) * inner_r)
        x2 = cx + int(math.cos(rad) * dial_r)
        y2 = cy + int(math.sin(rad) * dial_r)
        alpha = 155 if is_major else 65
        draw.line([(x1, y1), (x2, y2)], fill=(*cyan, alpha), width=max(2, radius // 95))

    # Hairline precision ring
    thin_r = int(radius * 1.10)
    draw.ellipse(
        [cx - thin_r, cy - thin_r, cx + thin_r, cy + thin_r],
        outline=(*white, 45),
        width=max(2, radius // 110),
    )

    # Primary split zero ring (Titanium White + Electric Cyan & Amber accents)
    draw.arc(bbox, start=24, end=166, fill=(*white, 255), width=stroke)
    draw.arc(bbox, start=204, end=346, fill=(*white, 255), width=stroke)

    # Inner high-contrast accent arcs
    inner_r = int(radius * 0.78)
    ibbox = [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r]
    inner_w = max(3, int(radius * 0.045))
    draw.arc(ibbox, start=38, end=142, fill=(*cyan, 240), width=inner_w)
    draw.arc(ibbox, start=218, end=322, fill=(*amber, 240), width=inner_w)

    # Dual vector slashes ("//") ascending through the zero
    slash_w = max(4, int(radius * 0.085))
    gap = int(radius * 0.145)
    dx = int(radius * 0.44)
    dy = int(radius * 0.74)

    # Left slash (Electric Cyan)
    draw.line(
        [(cx - dx - gap, cy + dy), (cx + dx - gap, cy - dy)],
        fill=(*cyan, 255),
        width=slash_w,
    )
    # Right slash (Signal Amber)
    draw.line(
        [(cx - dx + gap, cy + dy), (cx + dx + gap, cy - dy)],
        fill=(*amber, 255),
        width=slash_w,
    )

    # Crimson anomaly telemetry dot (upper-right apex)
    dot_r = max(5, int(radius * 0.095))
    dot_x = cx + int(radius * 0.78)
    dot_y = cy - int(radius * 0.78)
    draw.ellipse(
        [dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r],
        fill=(*crimson, 255),
    )
    # Crisp white specular pinpoint inside anomaly dot
    pin_r = max(2, dot_r // 3)
    draw.ellipse(
        [dot_x - pin_r, dot_y - pin_r, dot_x + pin_r, dot_y + pin_r],
        fill=(255, 255, 255, 220),
    )

    canvas.alpha_composite(fg)


def render_profile_avatar(output_path: Path, brand: Dict) -> Path:
    """Render 800x800 high-resolution minimalist profile avatar (2x supersampled)."""
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
        center_glow=(0.5, 0.48),
    )
    _draw_precision_grid(canvas, step=80, line_rgba=(30, 41, 66, 65))

    # Central iconic emblem scaled for crisp 32px readability
    _draw_emblem(canvas, size // 2, int(size * 0.46), int(size * 0.27), palette)

    # Minimal bottom micro-wordmark inside safe circle
    draw = ImageDraw.Draw(canvas)
    font = _load_font("mono", int(size * 0.052))
    label = "SCALE // ZERO"
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    tx = (size - tw) // 2
    ty = int(size * 0.81)
    draw.text((tx, ty), label, font=font, fill=(*hex_to_rgb(palette["text_primary"]), 235))

    # Crisp corner brackets
    cyan = hex_to_rgb(palette["accent_cyan"])
    pad = 90
    arm = 54
    bw = 5
    for (x0, y0, sx, sy) in [
        (pad, pad, 1, 1),
        (size - pad, pad, -1, 1),
        (pad, size - pad, 1, -1),
        (size - pad, size - pad, -1, -1),
    ]:
        draw.line([(x0, y0), (x0 + sx * arm, y0)], fill=(*cyan, 110), width=bw)
        draw.line([(x0, y0), (x0, y0 + sy * arm)], fill=(*cyan, 110), width=bw)

    final = canvas.convert("RGB").resize((800, 800), Image.Resampling.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(output_path, format="PNG", optimize=True)
    logger.info("Rendered profile avatar: %s (800x800)", output_path.name)
    return output_path


def render_banner(output_path: Path, brand: Dict) -> Path:
    """Render 2560x1440 cinematic multi-device YouTube banner.

    All text and core branding sit strictly inside YouTube's universal safe area
    (1546x423 centered: x=507..2053, y=508..931) so Mobile, Desktop, and TV
    never clip a single character.
    """
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
    _draw_precision_grid(canvas, step=64, line_rgba=(30, 41, 66, 75))

    cyan = hex_to_rgb(palette["accent_cyan"])
    amber = hex_to_rgb(palette["accent_amber"])
    crimson = hex_to_rgb(palette["accent_crimson"])
    emerald = hex_to_rgb(palette["accent_emerald"])
    white = hex_to_rgb(palette["text_primary"])
    muted = hex_to_rgb(palette["text_secondary"])

    # --- Full-canvas cinematic background telemetry curves (TV + Desktop flanks) ---
    bg_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(bg_overlay)

    # Logarithmic ascending curve sweeping across entire 2560px canvas
    pts_curve1 = []
    pts_curve2 = []
    for x in range(0, w + 16, 16):
        t = x / w
        y1 = int(h * 0.78 - (h * 0.54) * (t**2.2) + math.sin(t * 14.0) * 18)
        y2 = int(h * 0.72 - (h * 0.34) * (t**1.6) + math.cos(t * 10.0) * 14)
        pts_curve1.append((x, y1))
        pts_curve2.append((x, y2))
    bdraw.line(pts_curve1, fill=(*cyan, 70), width=4)
    bdraw.line(pts_curve2, fill=(*amber, 55), width=3)

    # Subtle vertical comparison bar silhouettes on far left and far right (Desktop/TV wings)
    bar_heights_left = [90, 150, 220, 310, 180, 260, 420]
    for idx, bh in enumerate(bar_heights_left):
        bx = 90 + idx * 52
        by0 = 930 - bh
        bdraw.rectangle([bx, by0, bx + 28, 930], fill=(*cyan, 28), outline=(*cyan, 70), width=1)

    bar_heights_right = [140, 240, 190, 340, 480, 620, 760]
    for idx, bh in enumerate(bar_heights_right):
        bx = 2110 + idx * 54
        by0 = 1040 - bh
        col = amber if idx >= 5 else cyan
        bdraw.rectangle([bx, by0, bx + 30, 1040], fill=(*col, 32), outline=(*col, 80), width=1)

    # Horizontal cinematic scan framing rails framing the Desktop band (y=508..931)
    bdraw.line([(0, 508), (w, 508)], fill=(*cyan, 55), width=2)
    bdraw.line([(0, 932), (w, 932)], fill=(*cyan, 55), width=2)

    # Top/bottom TV telemetry watermarks (subtle, outside desktop band)
    mono_sm = _load_font("mono", 22)
    bdraw.text((100, 110), "SYS.TELEMETRY // GLOBAL SCALE INDEX [00.00 -> 10^12]", fill=(*muted, 110), font=mono_sm)
    bdraw.text((1960, 110), "4K HDR PIPELINE  |  VERIFIED DATA", fill=(*muted, 110), font=mono_sm)
    bdraw.text((100, 1300), "FORMAT LOCK: VISUAL COMPARISONS • HIDDEN SYSTEMS • EXTREME REALITY", fill=(*muted, 100), font=mono_sm)

    canvas.alpha_composite(bg_overlay)

    # --- UNIVERSAL SAFE AREA (x=507..2053, y=508..931) ---
    # Glass telemetry panel backing inside safe zone for supreme readability
    panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(panel)
    safe_box = [535, 534, 2025, 906]
    pdraw.rounded_rectangle(
        safe_box,
        radius=26,
        fill=(11, 16, 28, 205),
        outline=(*cyan, 110),
        width=2,
    )
    # Cyan accent pill cleanly inset inside the rounded panel
    pdraw.rounded_rectangle([551, 560, 561, 880], radius=5, fill=(*cyan, 240))
    canvas.alpha_composite(panel)

    # Emblem anchored cleanly on the left side of safe zone
    _draw_emblem(canvas, cx=735, cy=720, radius=118, palette=palette)

    # Main typography anchored cleanly right of emblem inside safe zone (x=925..1990)
    fg_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(fg_layer)
    font_title = _load_font("headline", 116)
    font_tag = _load_font("body", 31)
    font_pill = _load_font("mono", 23)
    font_handle = _load_font("mono", 26)

    tx = 925
    ty = 568

    # Multi-tone headline: "SCALE " (White) + "//" (Cyan) + " ZERO" (Amber)
    part1, part2, part3 = "SCALE ", "//", " ZERO"
    draw.text((tx, ty), part1, font=font_title, fill=(*white, 255))
    w1 = draw.textbbox((tx, ty), part1, font=font_title)[2]
    draw.text((w1, ty), part2, font=font_title, fill=(*cyan, 255))
    w2 = draw.textbbox((w1, ty), part2, font=font_title)[2]
    draw.text((w2, ty), part3, font=font_title, fill=(*amber, 255))

    # Crisp divider rule
    div_y = ty + 132
    draw.line([(tx, div_y), (1965, div_y)], fill=(*white, 55), width=2)
    draw.line([(tx, div_y), (tx + 240, div_y)], fill=(*cyan, 255), width=3)

    # Sub-tagline
    tagline = "VISUAL COMPARISONS  •  HIDDEN SYSTEMS  •  EXTREME FACTS"
    draw.text((tx, div_y + 22), tagline, font=font_tag, fill=(*white, 235))

    # Pillar telemetry pills (true alpha-composited dark glass fill + crisp glowing outline)
    pills = [
        ("MONEY SCALE", amber),
        ("HIDDEN TECH", cyan),
        ("PSYCHOLOGY", crimson),
        ("SCIENCE", emerald),
    ]
    px = tx
    py = div_y + 82
    for label, col in pills:
        tb = draw.textbbox((0, 0), label, font=font_pill)
        pw = (tb[2] - tb[0]) + 36
        ph = 44
        draw.rounded_rectangle(
            [px, py, px + pw, py + ph],
            radius=8,
            fill=(col[0], col[1], col[2], 38),
            outline=(*col, 225),
            width=2,
        )
        draw.text((px + 18, py + 10), label, font=font_pill, fill=(*white, 255))
        px += pw + 18

    # Handle badge top-right of safe panel
    handle_text = brand["handle"].upper()
    hb = draw.textbbox((0, 0), handle_text, font=font_handle)
    hw = hb[2] - hb[0]
    draw.text((1965 - hw, 566), handle_text, font=font_handle, fill=(*cyan, 235))

    canvas.alpha_composite(fg_layer)

    final = canvas.convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(output_path, format="PNG", optimize=True)
    logger.info("Rendered multi-device banner: %s (2560x1440)", output_path.name)
    return output_path


def render_watermark(output_path: Path, brand: Dict) -> Path:
    """Render 150x150 RGBA branding watermark for YouTube video overlay."""
    palette = brand["palette"]
    ss = 2
    size = 150 * ss
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    bg = hex_to_rgb(palette["bg_obsidian"])
    cyan = hex_to_rgb(palette["accent_cyan"])

    # Clean rounded dark telemetry badge with translucent perimeter
    margin = 14
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=44,
        fill=(*bg, 220),
        outline=(*cyan, 210),
        width=6,
    )
    _draw_emblem(canvas, size // 2, size // 2, int(size * 0.28), palette)

    final = canvas.resize((150, 150), Image.Resampling.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(output_path, format="PNG", optimize=True)
    logger.info("Rendered video watermark: %s (150x150 RGBA)", output_path.name)
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
