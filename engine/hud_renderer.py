"""VELUM V3 Zero-Freeze 60fps Cinema Motion Graphics & Sleek Telemetry HUD Renderer.

Features:
- Continuous full-beat living animation (`anim_t` entrance + `phase_t` non-stop motion)
  so NO visual element ever animates fast and then freezes mid-shot.
- Live rolling numeric counters (numbers dynamically roll up to target value).
- 8 high-contrast documentary & viral visual modes:
    * split_vs_clash       (Frame-0 scroll-stopper high-voltage VS clash)
    * visual_scale_blocks  (3D extruded isometric proportional scale comparison)
    * debate_cta_plate     (Closing polarizing comment-trigger poll card)
    * comparison_bars      (Animated racing bars with moving sheen highlight)
    * metric_hero          (Rotating orbital gauge + rolling hero figure)
    * timeline_scale       (Live progressing timeline with pulsing beacons)
    * system_nodes         (Animated signal pulse flowing across architecture nodes)
    * radar_alert          (Continuous sweeping radar beam + expanding pulse rings)
- Minimalist floating glass HUD + Open-Loop Retention Tease badge + mobile Shorts safe zones.
"""

from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from core.config import BRAND_DIR, load_brand_config, resolve_font


def _hex(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


@lru_cache(maxsize=64)
def get_font(role: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = resolve_font(role)
    if path:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            return ImageFont.load_default()
    return ImageFont.load_default()


def fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    role: str,
    max_size: int,
    max_width: int,
    min_size: int = 22,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Dynamically scale font down until text fits comfortably inside max_width (Windows & Linux safe)."""
    size = max_size
    while size > min_size:
        font = get_font(role, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            return font
        size = max(min_size, int(size * 0.90))
    return get_font(role, min_size)


@lru_cache(maxsize=8)
def _load_watermark(target_size: int) -> Optional[Image.Image]:
    wm_path = BRAND_DIR / "watermark_150x150.png"
    if not wm_path.exists():
        return None
    img = Image.open(wm_path).convert("RGBA")
    return img.resize((target_size, target_size), Image.Resampling.LANCZOS)


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def ease_out_quart(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 4


def _accent_rgb(name: str, palette: Dict[str, str]) -> Tuple[int, int, int]:
    mapping = {
        "cyan": palette["accent_cyan"],
        "amber": palette["accent_amber"],
        "crimson": palette["accent_crimson"],
        "emerald": palette["accent_emerald"],
    }
    return _hex(mapping.get(name, palette["accent_cyan"]))


def _interpolate_metric_text(raw_text: str, progress: float) -> str:
    """Smoothly roll the primary numeric value inside a metric label from ~12% to 100%."""
    p = max(0.12, min(1.0, ease_out_cubic(progress)))
    if p >= 0.995:
        return raw_text

    def _repl(match: re.Match[str]) -> str:
        tok = match.group(0)
        has_comma = "," in tok
        has_dot = "." in tok
        clean = tok.replace(",", "")
        try:
            target = float(clean)
        except ValueError:
            return tok
        # Avoid rolling calendar years like 1927 or 2026 weirdly
        if not has_dot and 1800 <= target <= 2100 and not has_comma:
            return tok
        cur = target * p
        if has_dot:
            decimals = len(clean.split(".")[1])
            return f"{cur:,.{decimals}f}" if has_comma else f"{cur:.{decimals}f}"
        val_i = max(1 if target >= 1 else 0, int(round(cur)))
        return f"{val_i:,}" if has_comma else str(val_i)

    return re.sub(r"\d[\d,]*(?:\.\d+)?", _repl, raw_text, count=1)


@lru_cache(maxsize=8)
def _get_norm_grid(h: int, w: int) -> Tuple[np.ndarray, np.ndarray]:
    """Cache normalized (nx, ny) coordinate grids to avoid per-frame mgrid overhead."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = xx / max(w - 1, 1)
    ny = yy / max(h - 1, 1)
    return nx, ny


def _create_plate_backdrop(
    w: int,
    h: int,
    palette: Dict[str, str],
    accent_rgb: Tuple[int, int, int],
    phase_t: float = 0.0,
) -> Image.Image:
    """Create living dark Vox-cinema backdrop with slowly drifting grid & breathing glow."""
    nx, ny = _get_norm_grid(h, w)

    base = np.array(_hex(palette["bg_obsidian"]), dtype=np.float32)
    acc = np.array(accent_rgb, dtype=np.float32)
    cyan = np.array(_hex(palette["accent_cyan"]), dtype=np.float32)

    # Subtle continuous drift of atmospheric focal glow so background stays alive 100% of beat
    gx = 0.50 + 0.08 * math.sin(phase_t * math.pi * 1.5)
    gy = 0.42 + 0.05 * math.cos(phase_t * math.pi * 1.2)
    glow = np.exp(-(((nx - gx) * 1.15) ** 2 + ((ny - gy) * 1.15) ** 2) / 0.19) * 0.27
    glow2 = np.exp(-(((nx - (0.85 - 0.12 * phase_t)) * 1.25) ** 2 + ((ny - 0.82) * 1.25) ** 2) / 0.17) * 0.14

    arr = np.zeros((h, w, 3), dtype=np.float32)
    for c in range(3):
        arr[:, :, c] = np.clip(base[c] + acc[c] * glow + cyan[c] * glow2, 0, 255)

    canvas = Image.fromarray(arr.astype(np.uint8), mode="RGB").convert("RGBA")

    # Continuously drifting precision architectural grid
    grid = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grid)
    step = 64 if w <= 1080 else 76
    drift_x = int(phase_t * step * 0.55) % step
    drift_y = int(phase_t * step * 0.85) % step
    for x in range(-step + drift_x, w + step, step):
        gdraw.line([(x, 0), (x, h)], fill=(48, 72, 112, 40), width=1)
    for y in range(-step + drift_y, h + step, step):
        gdraw.line([(0, y), (w, y)], fill=(48, 72, 112, 40), width=1)

    # Subtle floating depth particles drifting smoothly upward
    for p_i in range(14):
        px = int(((p_i * 197 + 83) % w))
        py = int(((p_i * 313 + 140) - phase_t * (110 + (p_i % 4) * 35)) % h)
        pr = 2 + (p_i % 3)
        p_col = acc if p_i % 2 == 0 else cyan
        gdraw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=(int(p_col[0]), int(p_col[1]), int(p_col[2]), 95))

    canvas.alpha_composite(grid)
    return canvas


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    cx: int,
    y: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: Tuple[int, int, int, int],
    max_width: Optional[int] = None,
) -> int:
    """Draw horizontally centered text with automatic line wrapping if needed; returns bottom y."""
    if not max_width:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((cx - tw // 2, y), text, font=font, fill=fill)
        return y + th

    words = text.split()
    lines: List[str] = []
    cur = ""
    for word in words:
        trial = f"{cur} {word}".strip()
        tw = draw.textbbox((0, 0), trial, font=font)[2]
        if tw <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)

    cur_y = y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((cx - tw // 2, cur_y), line, font=font, fill=fill)
        cur_y += int(th * 1.22)
    return cur_y


def _draw_3d_cube(
    draw: ImageDraw.ImageDraw,
    cx: int,
    bottom_y: int,
    side: int,
    base_col: Tuple[int, int, int],
    alpha: int = 235,
    sheen_phase: float = 0.0,
) -> Tuple[int, int]:
    """Draw a crisp 3D isometric extruded glowing cube/block; returns top apex (cx, top_y)."""
    half_w = max(14, int(side * 0.56))
    iso_h = max(8, int(side * 0.26))
    body_h = max(18, int(side * 0.84))

    top_center_y = bottom_y - body_h - iso_h
    # Top diamond face (brightest)
    top_face = [
        (cx, top_center_y - iso_h),
        (cx + half_w, top_center_y),
        (cx, top_center_y + iso_h),
        (cx - half_w, top_center_y),
    ]
    # Left face (mid tone)
    left_face = [
        (cx - half_w, top_center_y),
        (cx, top_center_y + iso_h),
        (cx, bottom_y),
        (cx - half_w, bottom_y - iso_h),
    ]
    # Right face (deep shade)
    right_face = [
        (cx + half_w, top_center_y),
        (cx, top_center_y + iso_h),
        (cx, bottom_y),
        (cx + half_w, bottom_y - iso_h),
    ]

    pulse = 1.0 + 0.14 * math.sin(sheen_phase * math.pi * 2.0)
    c_top = tuple(min(255, int(c * 1.15 * pulse)) for c in base_col)
    c_left = tuple(min(255, int(c * 0.82)) for c in base_col)
    c_right = tuple(min(255, int(c * 0.52)) for c in base_col)

    draw.polygon(left_face, fill=(*c_left, alpha), outline=(255, 255, 255, 130))
    draw.polygon(right_face, fill=(*c_right, alpha), outline=(255, 255, 255, 100))
    draw.polygon(top_face, fill=(*c_top, alpha), outline=(255, 255, 255, 210))
    return cx, top_center_y - iso_h


def render_data_plate(
    plate_mode: str,
    plate_data: Dict[str, Any],
    size: Tuple[int, int],
    anim_t: float = 1.0,
    phase_t: Optional[float] = None,
    bg_image: Optional[Image.Image] = None,
) -> Image.Image:
    """Render a fluid, zero-freeze 60fps Netflix/Vox/Viral cinema visual plate."""
    brand = load_brand_config()
    palette = brand["palette"]
    w, h = size
    is_vertical = h > w
    live_p = anim_t if phase_t is None else max(0.0, min(1.0, phase_t))

    cyan = _hex(palette["accent_cyan"])
    amber = _hex(palette["accent_amber"])
    crimson = _hex(palette["accent_crimson"])
    emerald = _hex(palette["accent_emerald"])
    white = _hex(palette["text_primary"])

    accent_name = plate_data.get("accent", "amber" if plate_mode in ("comparison_bars", "visual_scale_blocks") else "cyan")
    if plate_mode in ("radar_alert", "debate_cta_plate"):
        accent_name = "crimson"
    accent = _accent_rgb(accent_name, palette)

    if bg_image is not None:
        bg_resized = bg_image.convert("RGB")
        if bg_resized.size != (w, h):
            bg_resized = bg_resized.resize((w, h), Image.Resampling.BILINEAR)
        canvas = bg_resized.convert("RGBA")
        scrim = Image.new("RGBA", (w, h), (6, 10, 18, 128))
        canvas.alpha_composite(scrim)
    else:
        canvas = _create_plate_backdrop(w, h, palette, accent, phase_t=live_p)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    eased = ease_out_quart(anim_t)
    # Gentle continuous breathing growth across the entire beat so visuals NEVER freeze
    living_growth = 0.90 * eased + 0.10 * live_p

    # Focal zone sits cleanly below the 0-2s Shock Hook (y=112..282) and above mobile captions (y=1330+)
    if is_vertical:
        box_l, box_r = 56, w - 56
        box_t, box_b = 310, 1265
    else:
        box_l, box_r = 150, w - 150
        box_t, box_b = 148, h - 185

    box_w = box_r - box_l
    box_h = box_b - box_t
    cx = (box_l + box_r) // 2
    cy = (box_t + box_b) // 2

    # --- MODE 1: HIGH-VOLTAGE SPLIT VS CLASH (Frame-0 Scroll-Stopper & Auto-Thumbnail Hero!) ---
    if plate_mode == "split_vs_clash":
        left_lbl = str(plate_data.get("left_label", "BASELINE")).upper()
        right_lbl = str(plate_data.get("right_label", "EXTREME")).upper()
        left_disp = _interpolate_metric_text(str(plate_data.get("left_display", "1x")).upper(), anim_t * 1.25)
        right_disp = _interpolate_metric_text(str(plate_data.get("right_display", "1,000x")).upper(), anim_t * 1.1)
        badge = str(plate_data.get("ratio_badge", "EXTREME GAP")).upper()

        mid_y = cy
        card_alpha = 186 if bg_image is not None else 228
        # Top Cyan Clash Card
        top_h = int((mid_y - box_t - 34) * (0.94 + 0.06 * eased))
        t_y0 = mid_y - 34 - top_h
        draw.rounded_rectangle(
            [box_l, t_y0, box_r, mid_y - 34],
            radius=26,
            fill=(7, 20, 36, card_alpha),
            outline=(*cyan, 240),
            width=4,
        )
        # Moving shimmer accent line inside top panel
        shimmer_x = box_l + 30 + int((box_w - 180) * ((live_p * 1.3) % 1.0))
        draw.rectangle([shimmer_x, t_y0 + 3, shimmer_x + 120, t_y0 + 9], fill=(*cyan, 255))

        # Bottom Amber/Crimson Clash Card
        bot_h = int((box_b - mid_y - 34) * (0.94 + 0.06 * eased))
        b_y1 = mid_y + 34 + bot_h
        draw.rounded_rectangle(
            [box_l, mid_y + 34, box_r, b_y1],
            radius=26,
            fill=(28, 12, 16, card_alpha + 8),
            outline=(*amber, 245),
            width=4,
        )
        shimmer_x2 = box_r - 150 - int((box_w - 180) * ((live_p * 1.3) % 1.0))
        draw.rectangle([shimmer_x2, mid_y + 37, shimmer_x2 + 120, mid_y + 43], fill=(*amber, 255))

        lbl_f_l = fit_font(draw, left_lbl, "mono", 34 if is_vertical else 28, box_w - 80, 18)
        lbl_f_r = fit_font(draw, right_lbl, "mono", 34 if is_vertical else 28, box_w - 80, 18)
        val_f_l = fit_font(draw, left_disp, "headline", 118 if is_vertical else 96, box_w - 72, 40)
        val_f_r = fit_font(draw, right_disp, "headline", 126 if is_vertical else 102, box_w - 72, 40)

        _draw_centered_text(draw, left_lbl, cx, t_y0 + 46, lbl_f_l, (*white, 220))
        _draw_centered_text(draw, left_disp, cx, t_y0 + 112, val_f_l, (*cyan, 255))

        # Proportional live racing progress bars inside each clash half
        l_val = max(0.01, float(plate_data.get("left_value", 1)))
        r_val = max(0.01, float(plate_data.get("right_value", 100)))
        max_v = max(l_val, r_val)
        l_frac = max(0.10, (l_val / max_v) ** 0.35) * living_growth
        r_frac = max(0.14, (r_val / max_v) ** 0.35) * living_growth
        bar_l, bar_r = box_l + 64, box_r - 64
        bar_span = bar_r - bar_l
        draw.rounded_rectangle([bar_l, mid_y - 90, bar_r, mid_y - 68], radius=10, fill=(255, 255, 255, 28))
        draw.rounded_rectangle([bar_l, mid_y - 90, bar_l + max(22, int(bar_span * l_frac)), mid_y - 68], radius=10, fill=(*cyan, 245))

        _draw_centered_text(draw, right_lbl, cx, mid_y + 72, lbl_f_r, (*white, 225))
        _draw_centered_text(draw, right_disp, cx, mid_y + 136, val_f_r, (*amber, 255))
        draw.rounded_rectangle([bar_l, b_y1 - 86, bar_r, b_y1 - 64], radius=10, fill=(255, 255, 255, 28))
        draw.rounded_rectangle([bar_l, b_y1 - 86, bar_l + max(26, int(bar_span * r_frac)), b_y1 - 64], radius=10, fill=(*amber, 250))

        # Glowing VS badge pulsating right in the center seam
        vs_r = int(56 + 6 * math.sin(live_p * math.pi * 3.0))
        draw.ellipse([cx - vs_r - 10, mid_y - vs_r - 10, cx + vs_r + 10, mid_y + vs_r + 10], fill=(*crimson, 90))
        draw.ellipse([cx - vs_r, mid_y - vs_r, cx + vs_r, mid_y + vs_r], fill=(*crimson, 250), outline=(*white, 240), width=4)
        vs_f = get_font("headline", 54 if is_vertical else 46)
        _draw_centered_text(draw, "VS", cx, mid_y - 30, vs_f, (*white, 255))

        # Ratio shock pill bottom
        if is_vertical:
            bf = fit_font(draw, badge, "headline", 36, box_w - 80, 18)
            bb = draw.textbbox((0, 0), badge, font=bf)
            bw = (bb[2] - bb[0]) + 50
            draw.rounded_rectangle([cx - bw // 2, box_b - 28, cx + bw // 2, box_b + 30], radius=14, fill=(*crimson, 240))
            _draw_centered_text(draw, badge, cx, box_b - 18, bf, (*white, 255))

        canvas.alpha_composite(layer)
        return canvas.convert("RGB")

    # --- MODE 2: 3D PROPORTIONAL SCALE BLOCKS (Isometric Cube Size Contrast!) ---
    if plate_mode == "visual_scale_blocks":
        draw.rounded_rectangle(
            [box_l, box_t, box_r, box_b],
            radius=28,
            fill=(10, 15, 26, 220),
            outline=(*accent, 175),
            width=3,
        )
        title = str(plate_data.get("title", "TRUE PHYSICAL SCALE")).upper()
        title_str = f"// {title}"
        title_font = fit_font(draw, title_str, "mono", 32 if is_vertical else 28, box_w - 80, 18)
        _draw_centered_text(draw, title_str, cx, box_t + 36, title_font, (*cyan, 240), max_width=box_w - 80)

        left_lbl = str(plate_data.get("left_label", "HUMAN SCALE")).upper()
        right_lbl = str(plate_data.get("right_label", "EXTREME SCALE")).upper()
        left_disp = _interpolate_metric_text(str(plate_data.get("left_display", "1x")).upper(), anim_t * 1.2)
        right_disp = _interpolate_metric_text(str(plate_data.get("right_display", "1,000x")).upper(), anim_t * 1.05)

        l_val = max(0.01, float(plate_data.get("left_value", 1)))
        r_val = max(0.01, float(plate_data.get("right_value", 100)))
        ratio_pow = (min(l_val, r_val) / max(l_val, r_val)) ** 0.30
        max_side = 320 if is_vertical else 255
        small_side = max(56, int(max_side * max(0.20, ratio_pow)))

        s_left = int((small_side if l_val <= r_val else max_side) * (0.35 + 0.65 * living_growth))
        s_right = int((max_side if r_val >= l_val else small_side) * (0.30 + 0.70 * living_growth))

        floor_y = box_b - 195
        x_l = cx - (220 if is_vertical else 310)
        x_r = cx + (190 if is_vertical else 270)

        # Perspective floor plane line
        draw.line([(box_l + 54, floor_y + 10), (box_r - 54, floor_y + 10)], fill=(*white, 95), width=3)

        _, top_l = _draw_3d_cube(draw, x_l, floor_y, s_left, cyan, alpha=235, sheen_phase=live_p)
        _, top_r = _draw_3d_cube(draw, x_r, floor_y, s_right, amber, alpha=245, sheen_phase=live_p + 0.35)

        # Animated laser measurement line comparing heights
        meas_x = x_l + int(s_left * 0.56) + 22
        draw.line([(meas_x, top_r), (x_r - int(s_right * 0.56) - 10, top_r)], fill=(*crimson, 210), width=3)
        draw.line([(meas_x, top_r), (meas_x, top_l)], fill=(*crimson, 180), width=3)

        vf_l = fit_font(draw, left_disp, "headline", 54 if is_vertical else 48, 360, 26)
        vf_r = fit_font(draw, right_disp, "headline", 60 if is_vertical else 52, 420, 28)
        lbl_max_w = 370 if is_vertical else 500
        lf_l = fit_font(draw, left_lbl, "mono", 26 if is_vertical else 24, lbl_max_w, 16)
        lf_r = fit_font(draw, right_lbl, "mono", 26 if is_vertical else 24, lbl_max_w, 16)

        _draw_centered_text(draw, left_disp, x_l, max(box_t + 115, top_l - 78), vf_l, (*cyan, 255))
        _draw_centered_text(draw, right_disp, x_r, max(box_t + 115, top_r - 82), vf_r, (*amber, 255))
        _draw_centered_text(draw, left_lbl, x_l, floor_y + 34, lf_l, (*white, 235), max_width=lbl_max_w)
        _draw_centered_text(draw, right_lbl, x_r, floor_y + 34, lf_r, (*white, 235), max_width=lbl_max_w)

        badge = str(plate_data.get("ratio_badge", "REAL PROPORTION")).upper()
        bf = fit_font(draw, badge, "headline", 38 if is_vertical else 34, box_w - 90, 18)
        bb = draw.textbbox((0, 0), badge, font=bf)
        bw = (bb[2] - bb[0]) + 54
        by = box_b - 96
        draw.rounded_rectangle([cx - bw // 2, by, cx + bw // 2, by + 62], radius=14, fill=(*crimson, 235))
        _draw_centered_text(draw, badge, cx, by + 11, bf, (*white, 255))

        canvas.alpha_composite(layer)
        return canvas.convert("RGB")

    # --- MODE 2B: DUAL FACT SPOTLIGHT (Zero apples-vs-oranges bar height distortions!) ---
    if plate_mode == "dual_fact_spotlight":
        left_lbl = str(plate_data.get("left_label", "FACT 01")).upper()
        right_lbl = str(plate_data.get("right_label", "FACT 02")).upper()
        left_disp = _interpolate_metric_text(str(plate_data.get("left_display", "VERIFIED")).upper(), anim_t * 1.2)
        right_disp = _interpolate_metric_text(str(plate_data.get("right_display", "EXTREME")).upper(), anim_t * 1.08)
        badge = str(plate_data.get("ratio_badge", "VERIFIED TELEMETRY")).upper()

        card_gap = 34
        card_h = (box_h - 170 - card_gap) // 2
        y_top0 = box_t + 76
        y_top1 = y_top0 + card_h
        y_bot0 = y_top1 + card_gap
        y_bot1 = y_bot0 + card_h
        glass_a = 192 if bg_image is not None else 224

        title = str(plate_data.get("title", "KEY TELEMETRY")).upper()
        t_str = f"// {title}"
        t_font = fit_font(draw, t_str, "mono", 30 if is_vertical else 26, box_w - 60, 18)
        _draw_centered_text(draw, t_str, cx, box_t + 20, t_font, (*cyan, 245))

        # Top Spotlight Card (Electric Cyan)
        draw.rounded_rectangle(
            [box_l, y_top0, box_r, y_top1],
            radius=24,
            fill=(8, 22, 38, glass_a),
            outline=(*cyan, 235),
            width=4,
        )
        sh_x1 = box_l + 28 + int((box_w - 170) * ((live_p * 1.35) % 1.0))
        draw.rectangle([sh_x1, y_top0 + 3, sh_x1 + 115, y_top0 + 9], fill=(*cyan, 255))

        # Bottom Spotlight Card (Signal Amber)
        draw.rounded_rectangle(
            [box_l, y_bot0, box_r, y_bot1],
            radius=24,
            fill=(28, 16, 12, glass_a + 6),
            outline=(*amber, 240),
            width=4,
        )
        sh_x2 = box_r - 143 - int((box_w - 170) * ((live_p * 1.35) % 1.0))
        draw.rectangle([sh_x2, y_bot0 + 3, sh_x2 + 115, y_bot0 + 9], fill=(*amber, 255))

        lf1 = fit_font(draw, left_lbl, "mono", 32 if is_vertical else 26, box_w - 84, 18)
        lf2 = fit_font(draw, right_lbl, "mono", 32 if is_vertical else 26, box_w - 84, 18)
        vf1 = fit_font(draw, left_disp, "headline", 112 if is_vertical else 92, box_w - 76, 44)
        vf2 = fit_font(draw, right_disp, "headline", 112 if is_vertical else 92, box_w - 76, 44)

        _draw_centered_text(draw, left_lbl, cx, y_top0 + 44, lf1, (*white, 225))
        _draw_centered_text(draw, left_disp, cx, y_top0 + 118, vf1, (*cyan, 255))
        _draw_centered_text(draw, right_lbl, cx, y_bot0 + 44, lf2, (*white, 225))
        _draw_centered_text(draw, right_disp, cx, y_bot0 + 118, vf2, (*amber, 255))

        bf = fit_font(draw, badge, "headline", 34 if is_vertical else 30, box_w - 80, 18)
        bb = draw.textbbox((0, 0), badge, font=bf)
        bw = (bb[2] - bb[0]) + 50
        by = box_b - 68
        draw.rounded_rectangle([cx - bw // 2, by, cx + bw // 2, by + 58], radius=14, fill=(*crimson, 235))
        _draw_centered_text(draw, badge, cx, by + 10, bf, (*white, 255))

        canvas.alpha_composite(layer)
        return canvas.convert("RGB")

    # --- MODE 3: CLOSING DEBATE / COMMENT + SUBSCRIBE CONVERSION CARD ---
    if plate_mode == "debate_cta_plate":
        card_a = 198 if bg_image is not None else 232
        draw.rounded_rectangle(
            [box_l, box_t, box_r, box_b],
            radius=28,
            fill=(14, 10, 22, card_a),
            outline=(*crimson, 235),
            width=4,
        )
        badge_f = get_font("mono", 29 if is_vertical else 25)
        _draw_centered_text(draw, "LIVE DEBATE // DROP YOUR CALL", cx, box_t + 36, badge_f, (*amber, 255))

        q_text = str(plate_data.get("question", "WOULD YOU GUESS HIGHER OR LOWER?")).upper()
        q_font = fit_font(draw, q_text[:28], "headline", 64 if is_vertical else 54, box_w - 84, 34)
        _draw_centered_text(draw, q_text, cx, box_t + 108, q_font, (*white, 255), max_width=box_w - 90)

        opt_a = str(plate_data.get("option_a", "HIGHER")).upper()
        opt_b = str(plate_data.get("option_b", "LOWER")).upper()
        card_w = int((box_w - 130) // 2)
        card_y0 = cy - 10
        card_y1 = cy + 150
        pulse_a = int(6 * math.sin(live_p * math.pi * 3.0))
        pulse_b = int(6 * math.cos(live_p * math.pi * 3.0))

        draw.rounded_rectangle(
            [box_l + 44, card_y0 - pulse_a, box_l + 44 + card_w, card_y1 - pulse_a],
            radius=20,
            fill=(0, 229, 255, 52),
            outline=(*cyan, 250),
            width=4,
        )
        draw.rounded_rectangle(
            [box_r - 44 - card_w, card_y0 - pulse_b, box_r - 44, card_y1 - pulse_b],
            radius=20,
            fill=(255, 184, 0, 56),
            outline=(*amber, 250),
            width=4,
        )
        of_a = fit_font(draw, opt_a, "headline", 46, card_w - 30, 24)
        of_b = fit_font(draw, opt_b, "headline", 46, card_w - 30, 24)
        _draw_centered_text(draw, opt_a, box_l + 44 + card_w // 2, card_y0 + 48 - pulse_a, of_a, (*cyan, 255))
        _draw_centered_text(draw, opt_b, box_r - 44 - card_w // 2, card_y0 + 48 - pulse_b, of_b, (*amber, 255))

        # Pulsing comment CTA pill + animated downward chevron
        cta_y = box_b - 235
        cta_txt = "COMMENT YOUR ANSWER BELOW"
        cta_f = fit_font(draw, cta_txt, "headline", 35 if is_vertical else 30, box_w - 100, 22)
        cb = draw.textbbox((0, 0), cta_txt, font=cta_f)
        cw = (cb[2] - cb[0]) + 56
        draw.rounded_rectangle([cx - cw // 2, cta_y, cx + cw // 2, cta_y + 62], radius=16, fill=(*crimson, 242))
        _draw_centered_text(draw, cta_txt, cx, cta_y + 12, cta_f, (*white, 255))

        bounce = int(12 * abs(math.sin(live_p * math.pi * 3.0)))
        arr_y = cta_y + 74 + bounce
        draw.line([(cx - 20, arr_y), (cx, arr_y + 16), (cx + 20, arr_y)], fill=(*amber, 255), width=6)

        # High-converting pulsing YouTube-red Subscribe pill (drives repeat viewers -> subscribers!)
        sub_y = box_b - 104
        sub_txt = "+ SUBSCRIBE FOR TOMORROW'S SCALE"
        sub_f = fit_font(draw, sub_txt, "headline", 31 if is_vertical else 27, box_w - 90, 20)
        sb = draw.textbbox((0, 0), sub_txt, font=sub_f)
        sw = (sb[2] - sb[0]) + 56
        sub_pulse = int(4 * abs(math.sin(live_p * math.pi * 4.0)))
        draw.rounded_rectangle(
            [cx - sw // 2 - sub_pulse, sub_y - sub_pulse // 2, cx + sw // 2 + sub_pulse, sub_y + 60 + sub_pulse // 2],
            radius=30,
            fill=(230, 25, 45, 248),
            outline=(*white, 235),
            width=3,
        )
        _draw_centered_text(draw, sub_txt, cx, sub_y + 12, sub_f, (*white, 255))

        canvas.alpha_composite(layer)
        return canvas.convert("RGB")

    # --- STANDARD FROSTED EDITORIAL CONTAINER FOR REMAINING 5 LIVING MODES ---
    draw.rounded_rectangle(
        [box_l, box_t, box_r, box_b],
        radius=28,
        fill=(10, 15, 26, 220),
        outline=(*accent, 165),
        width=3,
    )
    # Continuous travelling energy bar along card top edge
    scan_w = int(box_w * 0.34)
    scan_x = box_l + 24 + int((box_w - 48 - scan_w) * live_p)
    draw.rectangle([box_l + 24, box_t + 2, box_r - 24, box_t + 7], fill=(*accent, 65))
    draw.rectangle([scan_x, box_t + 2, scan_x + scan_w, box_t + 8], fill=(*accent, 255))

    title = str(plate_data.get("title", "SCALE TELEMETRY")).upper()
    title_str = f"// {title}"
    title_font = fit_font(draw, title_str, "mono", 32 if is_vertical else 28, box_w - 80, 18)
    _draw_centered_text(draw, title_str, cx, box_t + 38, title_font, (*cyan, 240), max_width=box_w - 80)

    if plate_mode == "comparison_bars":
        left_lbl = str(plate_data.get("left_label", "BASELINE")).upper()
        right_lbl = str(plate_data.get("right_label", "EXTREME")).upper()
        left_disp = _interpolate_metric_text(str(plate_data.get("left_display", "1x")).upper(), anim_t * 1.2)
        right_disp = _interpolate_metric_text(str(plate_data.get("right_display", "1,000x")).upper(), anim_t * 1.05)
        l_val = max(0.01, float(plate_data.get("left_value", 1)))
        r_val = max(0.01, float(plate_data.get("right_value", 100)))
        max_v = max(l_val, r_val)
        l_frac = max(0.08, (l_val / max_v) ** 0.35)
        r_frac = max(0.08, (r_val / max_v) ** 0.35)

        bar_area_top = box_t + 165
        bar_area_bot = box_b - 190
        max_bar_h = max(140, bar_area_bot - bar_area_top)

        bar_w_px = 195 if is_vertical else 250
        gap_px = 120 if is_vertical else 220
        x_left = cx - gap_px // 2 - bar_w_px
        x_right = cx + gap_px // 2

        h_left = max(28, int(max_bar_h * l_frac * living_growth))
        h_right = max(28, int(max_bar_h * r_frac * living_growth))

        draw.line([(box_l + 56, bar_area_bot), (box_r - 56, bar_area_bot)], fill=(*white, 100), width=3)

        draw.rounded_rectangle(
            [x_left, bar_area_bot - h_left, x_left + bar_w_px, bar_area_bot],
            radius=14,
            fill=(*cyan, 220),
            outline=(*white, 180),
            width=2,
        )
        draw.rounded_rectangle(
            [x_right, bar_area_bot - h_right, x_right + bar_w_px, bar_area_bot],
            radius=14,
            fill=(*amber, 238),
            outline=(*white, 200),
            width=2,
        )
        # Travelling highlight sheen gliding up the taller bar across the entire shot
        sheen_y = bar_area_bot - int(h_right * ((live_p * 1.5) % 1.0))
        if bar_area_bot - h_right + 12 < sheen_y < bar_area_bot - 12:
            draw.rectangle([x_right + 6, sheen_y - 6, x_right + bar_w_px - 6, sheen_y + 6], fill=(255, 255, 255, 115))

        val_font_l = fit_font(draw, left_disp, "headline", 54 if is_vertical else 50, bar_w_px + 90, 26)
        val_font_r = fit_font(draw, right_disp, "headline", 54 if is_vertical else 50, bar_w_px + 90, 26)
        lbl_max_w = (bar_w_px + gap_px - 36) if is_vertical else (bar_w_px + gap_px - 44)
        lbl_font_l = fit_font(draw, left_lbl, "mono", 27 if is_vertical else 25, lbl_max_w, 16)
        lbl_font_r = fit_font(draw, right_lbl, "mono", 27 if is_vertical else 25, lbl_max_w, 16)
        _draw_centered_text(draw, left_disp, x_left + bar_w_px // 2, bar_area_bot - h_left - 72, val_font_l, (*cyan, 255))
        _draw_centered_text(draw, right_disp, x_right + bar_w_px // 2, bar_area_bot - h_right - 72, val_font_r, (*amber, 255))
        _draw_centered_text(draw, left_lbl, x_left + bar_w_px // 2, bar_area_bot + 26, lbl_font_l, (*white, 235), max_width=lbl_max_w)
        _draw_centered_text(draw, right_lbl, x_right + bar_w_px // 2, bar_area_bot + 26, lbl_font_r, (*white, 235), max_width=lbl_max_w)

        badge = str(plate_data.get("ratio_badge", "EXTREME CONTRAST")).upper()
        badge_font = fit_font(draw, badge, "headline", 36 if is_vertical else 34, box_w - 80, 18)
        bb = draw.textbbox((0, 0), badge, font=badge_font)
        bw = (bb[2] - bb[0]) + 54
        by = box_b - 96
        draw.rounded_rectangle([cx - bw // 2, by, cx + bw // 2, by + 62], radius=14, fill=(*crimson, 235))
        _draw_centered_text(draw, badge, cx, by + 11, badge_font, (*white, 255))

    elif plate_mode == "metric_hero":
        raw_hero = str(plate_data.get("hero_value", "1,000x")).upper()
        hero_val = _interpolate_metric_text(raw_hero, anim_t * 1.15)
        sub = str(plate_data.get("subtitle", "VERIFIED TELEMETRY")).upper()

        ring_r = int(min(box_w, box_h) * 0.34)
        rot_deg = int(live_p * 115)
        draw.ellipse([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r], outline=(*white, 38), width=12)
        sweep = int(285 * living_growth)
        draw.arc(
            [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
            start=-90 + rot_deg,
            end=-90 + rot_deg + sweep,
            fill=(*accent, 248),
            width=14,
        )
        # Secondary counter-rotating inner orbital arc for continuous living telemetry feel
        in_r = int(ring_r * 0.82)
        draw.arc(
            [cx - in_r, cy - in_r, cx + in_r, cy + in_r],
            start=180 - rot_deg * 2,
            end=270 - rot_deg * 2,
            fill=(*cyan, 165),
            width=5,
        )

        hero_font = fit_font(draw, hero_val, "headline", 132 if is_vertical else 112, box_w - 110, 52)
        sub_font = get_font("body", 34 if is_vertical else 30)
        _draw_centered_text(draw, hero_val, cx, cy - 66, hero_font, (*white, 255), max_width=box_w - 80)
        _draw_centered_text(draw, sub, cx, box_b - 135, sub_font, (*accent, 248), max_width=box_w - 100)

    elif plate_mode == "timeline_scale":
        markers = plate_data.get("markers", [])
        rail_l = box_l + 76
        rail_r = box_r - 76
        rail_y = cy + 28
        rail_w = rail_r - rail_l

        draw.line([(rail_l, rail_y), (rail_r, rail_y)], fill=(*white, 75), width=8)
        head_x = rail_l + int(rail_w * living_growth)
        draw.line([(rail_l, rail_y), (head_x, rail_y)], fill=(*cyan, 245), width=8)
        draw.ellipse([head_x - 10, rail_y - 10, head_x + 10, rail_y + 10], fill=(*amber, 255))

        for idx, m in enumerate(markers[:3]):
            pct = float(m.get("pct", (idx + 1) / 4.0))
            mx = rail_l + int(rail_w * pct)
            mcol = _accent_rgb(str(m.get("color", "cyan")), palette)
            shown = living_growth >= pct * 0.72
            alpha = 255 if shown else 70
            stem_dir = -1 if idx % 2 == 0 else 1
            stem_end = rail_y + stem_dir * 140
            draw.line([(mx, rail_y), (mx, stem_end)], fill=(*mcol, alpha), width=4)
            pulse_r = 14 + (int(4 * abs(math.sin(live_p * math.pi * 3.0 + idx))) if shown else 0)
            draw.ellipse([mx - pulse_r, rail_y - pulse_r, mx + pulse_r, rail_y + pulse_r], fill=(*mcol, alpha), outline=(*white, alpha), width=3)

            m_val = str(m.get("value", "")).upper()
            m_lbl = str(m.get("label", "")).upper()
            col_w = max(210, int(rail_w // max(1, min(3, len(markers)))) - 20)
            mv_f = fit_font(draw, m_val, "headline", 42 if is_vertical else 40, col_w, 22)
            ml_f = fit_font(draw, m_lbl, "mono", 27, col_w, 15)
            text_y = stem_end - 90 if stem_dir < 0 else stem_end + 16
            _draw_centered_text(draw, m_val, mx, text_y, mv_f, (*mcol, alpha))
            _draw_centered_text(draw, m_lbl, mx, text_y + 52, ml_f, (*white, alpha), max_width=col_w)

    elif plate_mode == "system_nodes":
        nodes = plate_data.get("nodes", ["NODE 01", "NODE 02", "NODE 03"])
        caption = str(plate_data.get("caption", "HIDDEN SYSTEM ARCHITECTURE")).upper()
        n_nodes = max(1, min(3, len(nodes)))
        node_f = get_font("headline", 42 if is_vertical else 38)
        cap_f = get_font("mono", 28)

        if is_vertical:
            ys = [box_t + 215 + i * 205 for i in range(n_nodes)]
            for i in range(n_nodes - 1):
                draw.line([(cx, ys[i] + 54), (cx, ys[i + 1] - 54)], fill=(*cyan, 195), width=6)
                # Animated glowing data packet travelling down connector wire
                pkt_y = int(ys[i] + 54 + (ys[i + 1] - ys[i] - 108) * ((live_p * 1.8 + i * 0.4) % 1.0))
                draw.ellipse([cx - 9, pkt_y - 9, cx + 9, pkt_y + 9], fill=(*amber, 255))
            for i, node in enumerate(nodes[:3]):
                col = amber if i == n_nodes - 1 else cyan
                nw = int((box_w - 135) * (0.88 + 0.12 * eased))
                draw.rounded_rectangle(
                    [cx - nw // 2, ys[i] - 54, cx + nw // 2, ys[i] + 54],
                    radius=16,
                    fill=(col[0], col[1], col[2], 42),
                    outline=(*col, 245),
                    width=3,
                )
                _draw_centered_text(draw, str(node).upper(), cx, ys[i] - 24, node_f, (*white, 255))
        else:
            xs = [box_l + 240 + i * ((box_w - 480) // max(1, n_nodes - 1)) for i in range(n_nodes)]
            for i in range(n_nodes - 1):
                draw.line([(xs[i] + 155, cy), (xs[i + 1] - 155, cy)], fill=(*cyan, 195), width=6)
                pkt_x = int(xs[i] + 155 + (xs[i + 1] - xs[i] - 310) * ((live_p * 1.8 + i * 0.4) % 1.0))
                draw.ellipse([pkt_x - 9, cy - 9, pkt_x + 9, cy + 9], fill=(*amber, 255))
            for i, node in enumerate(nodes[:3]):
                col = amber if i == n_nodes - 1 else cyan
                draw.rounded_rectangle(
                    [xs[i] - 155, cy - 75, xs[i] + 155, cy + 75],
                    radius=16,
                    fill=(col[0], col[1], col[2], 42),
                    outline=(*col, 245),
                    width=3,
                )
                _draw_centered_text(draw, str(node).upper(), xs[i], cy - 22, node_f, (*white, 255))

        _draw_centered_text(draw, caption, cx, box_b - 102, cap_f, (*amber, 245), max_width=box_w - 90)

    else:  # radar_alert (continuous rotating sweep beam + expanding rings)
        raw_m = str(plate_data.get("metric", "ANOMALY")).upper()
        metric = _interpolate_metric_text(raw_m, anim_t * 1.15)
        sub = str(plate_data.get("subtitle", "THRESHOLD EXCEEDED")).upper()
        sev = str(plate_data.get("severity", "EXTREME")).upper()

        max_r = int(min(box_w, box_h) * 0.36)
        for ring_idx in range(3):
            ring_prog = (live_p + ring_idx / 3.0) % 1.0
            rr = int(55 + (max_r - 55) * ring_prog)
            r_alpha = int(190 * (1.0 - ring_prog))
            draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(*crimson, max(25, r_alpha)), width=4)

        # Rotating radar scanner arm
        ang = live_p * math.pi * 2.5
        rx = cx + int(math.cos(ang) * max_r)
        ry = cy + int(math.sin(ang) * max_r)
        draw.line([(cx, cy), (rx, ry)], fill=(*crimson, 175), width=4)

        pill_f = get_font("mono", 28)
        pill_txt = f"ALERT // {sev}"
        pb = draw.textbbox((0, 0), pill_txt, font=pill_f)
        pw = (pb[2] - pb[0]) + 48
        draw.rounded_rectangle([cx - pw // 2, box_t + 125, cx + pw // 2, box_t + 180], radius=10, fill=(*crimson, 235))
        _draw_centered_text(draw, pill_txt, cx, box_t + 138, pill_f, (*white, 255))

        m_font = fit_font(draw, metric, "headline", 104 if is_vertical else 92, box_w - 90, 44)
        s_font = get_font("body", 34)
        _draw_centered_text(draw, metric, cx, cy - 58, m_font, (*amber, 255), max_width=box_w - 84)
        _draw_centered_text(draw, sub, cx, box_b - 134, s_font, (*white, 245), max_width=box_w - 100)

    canvas.alpha_composite(layer)
    return canvas.convert("RGB")


def render_hud_overlay(
    size: Tuple[int, int],
    global_progress: float,
    hud_tag: str,
    hud_metric: str,
    hud_delta: str,
    time_sec: float,
    shock_hook_text: Optional[str] = None,
    shock_hook_sub: Optional[str] = None,
    shock_progress: float = 0.0,
    total_duration: Optional[float] = None,
) -> Image.Image:
    """Render sleek minimalist cinema HUD, open-loop retention badge & 0-2.1s Frame-0 Hook."""
    brand = load_brand_config()
    palette = brand["palette"]
    w, h = size
    is_vertical = h > w

    cyan = _hex(palette["accent_cyan"])
    amber = _hex(palette["accent_amber"])
    crimson = _hex(palette["accent_crimson"])
    white = _hex(palette["text_primary"])

    hud = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(hud)

    # --- 1. RAZOR-THIN FULL-WIDTH CINEMA PROGRESS RAIL (y=0..8) ---
    rail_h = 8 if is_vertical else 6
    draw.rectangle([0, 0, w, rail_h], fill=(255, 255, 255, 34))
    prog_x = max(12, int(w * max(0.0, min(1.0, global_progress))))
    draw.rectangle([0, 0, prog_x, rail_h], fill=(*cyan, 245))
    draw.rectangle([max(0, prog_x - 36), 0, prog_x, rail_h], fill=(*amber, 255))

    # --- 2. MINIMALIST FLOATING GLASS TELEMETRY PILLS (Hidden during 0.0-1.85s V5 Clean Cover Hook) ---
    shock_active = bool(shock_hook_text) and (0.0 <= shock_progress <= 1.0)
    pad_x = 38 if is_vertical else 52
    pill_y = 30 if is_vertical else 24
    pill_h = 54 if is_vertical else 48
    mono_sm = get_font("mono", 24 if is_vertical else 21)
    bold_sm = get_font("headline", 29 if is_vertical else 25)

    if not shock_active:
        # Left glass pill: pulsing REC dot + beat tag
        left_txt = hud_tag[:16]
        lb = draw.textbbox((0, 0), left_txt, font=mono_sm)
        lw = (lb[2] - lb[0]) + 68
        draw.rounded_rectangle(
            [pad_x, pill_y, pad_x + lw, pill_y + pill_h],
            radius=14,
            fill=(7, 10, 18, 175),
            outline=(*cyan, 130),
            width=2,
        )
        dot_alpha = 255 if int(time_sec * 3.5) % 2 == 0 else 110
        draw.ellipse([pad_x + 18, pill_y + pill_h // 2 - 7, pad_x + 32, pill_y + pill_h // 2 + 7], fill=(*crimson, dot_alpha))
        draw.text((pad_x + 44, pill_y + 13), left_txt, font=mono_sm, fill=(*white, 240))

        # Right glass pill: live highlighted metric
        right_txt = hud_metric[:18]
        rb = draw.textbbox((0, 0), right_txt, font=bold_sm)
        rw = (rb[2] - rb[0]) + 40
        rx0 = w - pad_x - rw
        draw.rounded_rectangle(
            [rx0, pill_y, w - pad_x, pill_y + pill_h],
            radius=14,
            fill=(7, 10, 18, 185),
            outline=(*amber, 165),
            width=2,
        )
        draw.text((rx0 + 20, pill_y + 10), right_txt, font=bold_sm, fill=(*amber, 255))

    # --- 3. SUBTLE BRAND WATERMARK (Tucked cleanly outside Shorts UI buttons & captions) ---
    wm_size = 62 if is_vertical else 72
    wm = _load_watermark(wm_size)
    if wm is not None:
        wm_x = pad_x
        wm_y = (h - 190) if is_vertical else (h - 104)
        hud.alpha_composite(wm, dest=(wm_x, wm_y))
        draw.text((wm_x + wm_size + 12, wm_y + 18), "VELUM", font=mono_sm, fill=(*white, 155))

    # --- 4. V5 FULL-BLEED CINEMA SCROLL-STOPPER HOOK COVER (0.0-1.85s, instant Frame-0 punch!) ---
    if shock_active:
        if shock_progress > 0.84:
            alpha_mult = max(0.0, 1.0 - (shock_progress - 0.84) / 0.16)
        else:
            alpha_mult = 1.0

        if alpha_mult > 0.02:
            hook_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            hdraw = ImageDraw.Draw(hook_layer)

            # Pixel-smooth top cinema gradient scrim (zero horizontal banding lines!)
            scrim_h = int(h * (0.42 if is_vertical else 0.36))
            grad_y = np.linspace(1.0, 0.0, scrim_h, dtype=np.float32) ** 1.45
            scrim_alpha = np.clip(np.rint(grad_y * 210.0 * alpha_mult), 0, 255).astype(np.uint8)
            scrim_arr = np.zeros((scrim_h, w, 4), dtype=np.uint8)
            scrim_arr[:, :, 0] = 5
            scrim_arr[:, :, 1] = 8
            scrim_arr[:, :, 2] = 16
            scrim_arr[:, :, 3] = scrim_alpha[:, None]
            hook_layer.alpha_composite(Image.fromarray(scrim_arr, mode="RGBA"), dest=(0, 0))

            # Subtle live rolling shock number during first 0.55s (100% locked at Frame 0 thumbnail? Keep full value at Frame 0, subtle glow pulse!)
            htext = (
                shock_hook_text.upper()
                if shock_progress < 0.04
                else _interpolate_metric_text(shock_hook_text.upper(), min(1.0, shock_progress * 2.6))
            )
            max_tw = w - (96 if is_vertical else 280)
            hook_font = fit_font(
                hdraw,
                htext,
                "headline",
                max_size=108 if is_vertical else 98,
                max_width=max_tw,
                min_size=46,
            )

            # Crisp obsidian drop-shadow + luminous Signal Amber viral cover headline
            title_y = 185 if is_vertical else 118
            for ox, oy in ((0, 7), (4, 5), (-4, 5), (0, -3)):
                _draw_centered_text(
                    hdraw,
                    htext,
                    w // 2 + ox,
                    title_y + oy,
                    hook_font,
                    (4, 6, 12, int(235 * alpha_mult)),
                    max_width=max_tw,
                )
            title_bottom = _draw_centered_text(
                hdraw,
                htext,
                w // 2,
                title_y,
                hook_font,
                (*amber, int(255 * alpha_mult)),
                max_width=max_tw,
            )

            # Sleek floating accent pill right below headline (clean poster typography, zero big red boxes)
            if shock_hook_sub:
                sub_str = shock_hook_sub.upper().strip("[] ")
                sub_font = fit_font(
                    hdraw,
                    sub_str,
                    "mono",
                    max_size=28 if is_vertical else 24,
                    max_width=max_tw - 48,
                    min_size=18,
                )
                sb = hdraw.textbbox((0, 0), sub_str, font=sub_font)
                sw = (sb[2] - sb[0]) + 56
                sh = (sb[3] - sb[1]) + 24
                pill_top = title_bottom + 24
                hdraw.rounded_rectangle(
                    [w // 2 - sw // 2, pill_top, w // 2 + sw // 2, pill_top + sh],
                    radius=sh // 2,
                    fill=(7, 11, 22, int(218 * alpha_mult)),
                    outline=(*cyan, int(235 * alpha_mult)),
                    width=3,
                )
                hdraw.text(
                    (w // 2 - (sb[2] - sb[0]) // 2, pill_top + 10 - sb[1]),
                    sub_str,
                    font=sub_font,
                    fill=(*white, int(250 * alpha_mult)),
                )

            hud.alpha_composite(hook_layer)

    # --- 5. OPEN-LOOP RETENTION TEASE BADGE (Vertical Shorts only, y=96..144 safe band) ---
    # Strictly positioned below top pills (y=30..84), above focal card (y=310..1265),
    # above captions (y=1340..1440), and never active during the 0-2.1s Shock Hook.
    if is_vertical and not shock_active and time_sec > 1.9 and (0.10 <= global_progress < 0.90):
        tease_y = 96
        if global_progress <= 0.72:
            fade = ease_out_cubic((global_progress - 0.12) / 0.04) if global_progress < 0.16 else 1.0
            pulse = 0.5 + 0.5 * math.sin(time_sec * 4.2)

            est_total = (
                float(total_duration)
                if (total_duration is not None and total_duration > 0.0)
                else (time_sec / max(global_progress, 1e-4))
            )
            rem_sec = int(math.ceil(max(0.0, 0.72 - global_progress) * est_total))
            show_countdown = 1 <= rem_sec <= 45

            tease_font = get_font("mono", 22)
            main_txt = "WAIT FOR THE TWIST"
            mb = draw.textbbox((0, 0), main_txt, font=tease_font)
            main_w, main_h = mb[2] - mb[0], mb[3] - mb[1]

            count_txt = f"CLIMAX IN {rem_sec:02d}S" if show_countdown else ""
            if show_countdown:
                cb = draw.textbbox((0, 0), count_txt, font=tease_font)
                count_w, count_h = cb[2] - cb[0], cb[3] - cb[1]
                pw = 44 + main_w + 26 + count_w + 24
            else:
                count_w, count_h = 0, 0
                pw = 44 + main_w + 26

            tease_h = 44
            pad = 8
            surf_w, surf_h = pw + pad * 2, tease_h + pad * 2
            glow_surf = Image.new("RGBA", (surf_w, surf_h), (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(glow_surf)
            gdraw.rounded_rectangle(
                [pad - 3, pad - 3, pad + pw + 3, pad + tease_h + 3],
                radius=24,
                fill=(*cyan, int((28 + 26 * pulse) * fade)),
            )

            pill_surf = Image.new("RGBA", (surf_w, surf_h), (0, 0, 0, 0))
            pdraw = ImageDraw.Draw(pill_surf)
            pdraw.rounded_rectangle(
                [pad, pad, pad + pw, pad + tease_h],
                radius=22,
                fill=(8, 13, 24, int(196 * fade)),
                outline=(*cyan, int((135 + 75 * pulse) * fade)),
                width=2,
            )
            dot_cx = pad + 22
            dot_cy = pad + tease_h // 2
            pdraw.ellipse(
                [dot_cx - 5, dot_cy - 5, dot_cx + 5, dot_cy + 5],
                fill=(*cyan, int((170 + 85 * pulse) * fade)),
            )

            text_x = pad + 40
            main_y = pad + (tease_h - main_h) // 2 - mb[1]
            pdraw.text((text_x, main_y), main_txt, font=tease_font, fill=(*white, int(238 * fade)))

            if show_countdown:
                div_x = text_x + main_w + 13
                pdraw.line(
                    [(div_x, pad + 11), (div_x, pad + tease_h - 11)],
                    fill=(*white, int(85 * fade)),
                    width=2,
                )
                count_y = pad + (tease_h - count_h) // 2 - cb[1]
                pdraw.text(
                    (div_x + 13, count_y),
                    count_txt,
                    font=tease_font,
                    fill=(*amber, int(250 * fade)),
                )

            dest = (w // 2 - surf_w // 2, tease_y - pad)
            hud.alpha_composite(glow_surf, dest=dest)
            hud.alpha_composite(pill_surf, dest=dest)
        else:
            if global_progress < 0.74:
                fade = ease_out_cubic((global_progress - 0.72) / 0.02)
            elif global_progress > 0.86:
                fade = max(0.0, 1.0 - (global_progress - 0.86) / 0.04)
            else:
                fade = 1.0

            if fade > 0.02:
                pulse = 0.5 + 0.5 * math.sin(time_sec * 10.5)
                twist_font = get_font("headline", 28)
                twist_txt = "THE TWIST"
                tb = draw.textbbox((0, 0), twist_txt, font=twist_font)
                tw, th = tb[2] - tb[0], tb[3] - tb[1]
                pw = tw + 88
                tease_h = 48
                pad = 10
                surf_w, surf_h = pw + pad * 2, tease_h + pad * 2

                glow_surf = Image.new("RGBA", (surf_w, surf_h), (0, 0, 0, 0))
                gdraw = ImageDraw.Draw(glow_surf)
                gdraw.rounded_rectangle(
                    [pad - 5, pad - 4, pad + pw + 5, pad + tease_h + 4],
                    radius=26,
                    fill=(*crimson, int((78 + 64 * pulse) * fade)),
                )

                pill_surf = Image.new("RGBA", (surf_w, surf_h), (0, 0, 0, 0))
                pdraw = ImageDraw.Draw(pill_surf)
                pdraw.rounded_rectangle(
                    [pad, pad, pad + pw, pad + tease_h],
                    radius=24,
                    fill=(*crimson, int(236 * fade)),
                    outline=(*amber, int((195 + 60 * pulse) * fade)),
                    width=3,
                )
                pdraw.rectangle(
                    [pad + 26, pad + 3, pad + pw - 26, pad + 6],
                    fill=(*amber, int((160 + 95 * pulse) * fade)),
                )

                dot_y = pad + tease_h // 2
                for dx in (pad + 22, pad + pw - 22):
                    pdraw.ellipse(
                        [dx - 5, dot_y - 5, dx + 5, dot_y + 5],
                        fill=(*amber, int((190 + 65 * pulse) * fade)),
                    )

                text_x = pad + (pw - tw) // 2 - tb[0]
                text_y = pad + (tease_h - th) // 2 - tb[1]
                pdraw.text((text_x, text_y), twist_txt, font=twist_font, fill=(*white, int(255 * fade)))

                dest = (w // 2 - surf_w // 2, tease_y - pad)
                hud.alpha_composite(glow_surf, dest=dest)
                hud.alpha_composite(pill_surf, dest=dest)

    return hud
