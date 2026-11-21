"""Netflix/Vox Editorial Data Plates, 0-2s Shock Hook, and Live Telemetry HUD Renderer.

Renders:
- 5 animated Vox-grade data plate types (comparison_bars, metric_hero,
  system_nodes, timeline_scale, radar_alert) with smooth ease-out cubic motion
- 0-2.0s high-contrast Shock Hook stat explosion banner (zero-latency eye capture)
- Live top/bottom HUD telemetry overlay (progress rail, beat counter, live metric
  pill, timecode, and SCALE // ZERO watermark)
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

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


def ease_out_back(t: float) -> float:
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    c3 = c1 + 1.0
    return 1.0 + c3 * ((t - 1.0) ** 3) + c1 * ((t - 1.0) ** 2)


def _accent_rgb(name: str, palette: Dict[str, str]) -> Tuple[int, int, int]:
    mapping = {
        "cyan": palette["accent_cyan"],
        "amber": palette["accent_amber"],
        "crimson": palette["accent_crimson"],
        "emerald": palette["accent_emerald"],
    }
    return _hex(mapping.get(name, palette["accent_cyan"]))


def _create_plate_backdrop(w: int, h: int, palette: Dict[str, str], accent_rgb: Tuple[int, int, int]) -> Image.Image:
    """Create dark Vox-terminal editorial canvas with subtle radial illumination & precision grid."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = xx / max(w - 1, 1)
    ny = yy / max(h - 1, 1)

    base = np.array(_hex(palette["bg_obsidian"]), dtype=np.float32)
    acc = np.array(accent_rgb, dtype=np.float32)
    cyan = np.array(_hex(palette["accent_cyan"]), dtype=np.float32)

    glow = np.exp(-(((nx - 0.5) * 1.15) ** 2 + ((ny - 0.44) * 1.15) ** 2) / 0.18) * 0.24
    glow2 = np.exp(-(((nx - 0.85) * 1.3) ** 2 + ((ny - 0.85) * 1.3) ** 2) / 0.16) * 0.11

    arr = np.zeros((h, w, 3), dtype=np.float32)
    for c in range(3):
        arr[:, :, c] = np.clip(base[c] + acc[c] * glow + cyan[c] * glow2, 0, 255)

    canvas = Image.fromarray(arr.astype(np.uint8), mode="RGB").convert("RGBA")

    # Subtle architectural data grid
    grid = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grid)
    step = 60 if w <= 1080 else 72
    for x in range(0, w, step):
        gdraw.line([(x, 0), (x, h)], fill=(45, 65, 100, 42), width=1)
    for y in range(0, h, step):
        gdraw.line([(0, y), (w, y)], fill=(45, 65, 100, 42), width=1)
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
        cur_y += int(th * 1.24)
    return cur_y


def render_data_plate(
    plate_mode: str,
    plate_data: Dict[str, Any],
    size: Tuple[int, int],
    anim_t: float = 1.0,
) -> Image.Image:
    """Render a crisp, animated Netflix/Vox data visualization plate at `anim_t` (0..1)."""
    brand = load_brand_config()
    palette = brand["palette"]
    w, h = size
    is_vertical = h > w

    cyan = _hex(palette["accent_cyan"])
    amber = _hex(palette["accent_amber"])
    crimson = _hex(palette["accent_crimson"])
    emerald = _hex(palette["accent_emerald"])
    white = _hex(palette["text_primary"])
    muted = _hex(palette["text_secondary"])

    accent_name = plate_data.get("accent", "amber" if plate_mode == "comparison_bars" else "cyan")
    if plate_mode == "radar_alert":
        accent_name = "crimson"
    accent = _accent_rgb(accent_name, palette)

    canvas = _create_plate_backdrop(w, h, palette, accent)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    eased = ease_out_cubic(anim_t)

    # Safe focal zone (keeps clear of top HUD & bottom kinetic captions!)
    if is_vertical:
        box_l, box_r = 76, w - 76
        box_t, box_b = 330, 1260
    else:
        box_l, box_r = 160, w - 160
        box_t, box_b = 175, h - 220

    box_w = box_r - box_l
    box_h = box_b - box_t
    cx = (box_l + box_r) // 2
    cy = (box_t + box_b) // 2

    # Frosted dark editorial frame
    draw.rounded_rectangle(
        [box_l, box_t, box_r, box_b],
        radius=28,
        fill=(11, 16, 28, 215),
        outline=(*accent, 150),
        width=3,
    )
    # Top glowing hairline bar inside card
    bar_w = int(box_w * max(0.15, eased))
    draw.rectangle([box_l + 28, box_t + 2, box_l + 28 + min(bar_w, box_w - 56), box_t + 8], fill=(*accent, 255))

    title_font = get_font("mono", 34 if is_vertical else 30)
    title = str(plate_data.get("title", "SCALE TELEMETRY")).upper()
    _draw_centered_text(draw, f"// {title}", cx, box_t + 44, title_font, (*cyan, 235), max_width=box_w - 80)

    if plate_mode == "comparison_bars":
        left_lbl = str(plate_data.get("left_label", "BASELINE")).upper()
        right_lbl = str(plate_data.get("right_label", "EXTREME")).upper()
        left_disp = str(plate_data.get("left_display", "1x")).upper()
        right_disp = str(plate_data.get("right_display", "1,000x")).upper()
        l_val = max(0.01, float(plate_data.get("left_value", 1)))
        r_val = max(0.01, float(plate_data.get("right_value", 100)))
        max_v = max(l_val, r_val)
        # Visual log/hybrid scaling so tiny bar is visible while contrast stays jaw-dropping
        l_frac = max(0.06, (l_val / max_v) ** 0.35)
        r_frac = max(0.06, (r_val / max_v) ** 0.35)

        bar_area_top = box_t + 165
        bar_area_bot = box_b - 190
        max_bar_h = max(140, bar_area_bot - bar_area_top)

        bar_w_px = 180 if is_vertical else 240
        gap_px = 120 if is_vertical else 220
        x_left = cx - gap_px // 2 - bar_w_px
        x_right = cx + gap_px // 2

        h_left = max(24, int(max_bar_h * l_frac * eased))
        h_right = max(24, int(max_bar_h * r_frac * eased))

        # Baseline rail
        draw.line([(box_l + 60, bar_area_bot), (box_r - 60, bar_area_bot)], fill=(*white, 90), width=3)

        # Left bar (Electric Cyan)
        draw.rounded_rectangle(
            [x_left, bar_area_bot - h_left, x_left + bar_w_px, bar_area_bot],
            radius=12,
            fill=(*cyan, 215),
            outline=(*white, 170),
            width=2,
        )
        # Right bar (Signal Amber)
        draw.rounded_rectangle(
            [x_right, bar_area_bot - h_right, x_right + bar_w_px, bar_area_bot],
            radius=12,
            fill=(*amber, 235),
            outline=(*white, 190),
            width=2,
        )

        val_font = get_font("headline", 54 if is_vertical else 52)
        lbl_font = get_font("mono", 28 if is_vertical else 26)
        _draw_centered_text(draw, left_disp, x_left + bar_w_px // 2, bar_area_bot - h_left - 72, val_font, (*cyan, 255))
        _draw_centered_text(draw, right_disp, x_right + bar_w_px // 2, bar_area_bot - h_right - 72, val_font, (*amber, 255))

        _draw_centered_text(draw, left_lbl, x_left + bar_w_px // 2, bar_area_bot + 26, lbl_font, (*white, 235))
        _draw_centered_text(draw, right_lbl, x_right + bar_w_px // 2, bar_area_bot + 26, lbl_font, (*white, 235))

        badge = str(plate_data.get("ratio_badge", "EXTREME CONTRAST")).upper()
        badge_font = get_font("headline", 36 if is_vertical else 34)
        bb = draw.textbbox((0, 0), badge, font=badge_font)
        bw = (bb[2] - bb[0]) + 54
        by = box_b - 96
        draw.rounded_rectangle(
            [cx - bw // 2, by, cx + bw // 2, by + 62],
            radius=12,
            fill=(*crimson, 225),
        )
        _draw_centered_text(draw, badge, cx, by + 11, badge_font, (*white, 255))

    elif plate_mode == "metric_hero":
        hero_val = str(plate_data.get("hero_value", "1,000x")).upper()
        sub = str(plate_data.get("subtitle", "VERIFIED TELEMETRY")).upper()

        # Animated radial gauge ring around hero figure
        ring_r = int(min(box_w, box_h) * 0.34)
        draw.ellipse(
            [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
            outline=(*white, 38),
            width=12,
        )
        sweep = int(310 * eased)
        draw.arc(
            [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
            start=-90,
            end=-90 + sweep,
            fill=(*accent, 245),
            width=14,
        )

        hero_size = 128 if len(hero_val) <= 9 else 88
        hero_font = get_font("headline", hero_size if is_vertical else int(hero_size * 0.92))
        sub_font = get_font("body", 34 if is_vertical else 30)

        _draw_centered_text(draw, hero_val, cx, cy - int(hero_size * 0.56), hero_font, (*white, 255), max_width=box_w - 80)
        _draw_centered_text(draw, sub, cx, box_b - 135, sub_font, (*accent, 245), max_width=box_w - 110)

    elif plate_mode == "timeline_scale":
        markers = plate_data.get("markers", [])
        rail_l = box_l + 80
        rail_r = box_r - 80
        rail_y = cy + 30
        rail_w = rail_r - rail_l

        draw.line([(rail_l, rail_y), (rail_r, rail_y)], fill=(*white, 75), width=8)
        draw.line([(rail_l, rail_y), (rail_l + int(rail_w * eased), rail_y)], fill=(*cyan, 245), width=8)

        lbl_f = get_font("mono", 28)
        val_f = get_font("headline", 44 if is_vertical else 42)
        for idx, m in enumerate(markers[:3]):
            pct = float(m.get("pct", (idx + 1) / 4.0))
            mx = rail_l + int(rail_w * pct)
            mcol = _accent_rgb(str(m.get("color", "cyan")), palette)
            shown = eased >= pct * 0.75
            alpha = 255 if shown else 60
            # Vertical drop stem
            stem_dir = -1 if idx % 2 == 0 else 1
            stem_end = rail_y + stem_dir * 135
            draw.line([(mx, rail_y), (mx, stem_end)], fill=(*mcol, alpha), width=4)
            draw.ellipse([mx - 14, rail_y - 14, mx + 14, rail_y + 14], fill=(*mcol, alpha), outline=(*white, alpha), width=3)

            text_y = stem_end - 88 if stem_dir < 0 else stem_end + 16
            _draw_centered_text(draw, str(m.get("value", "")).upper(), mx, text_y, val_f, (*mcol, alpha))
            _draw_centered_text(draw, str(m.get("label", "")).upper(), mx, text_y + 52, lbl_f, (*white, alpha))

    elif plate_mode == "system_nodes":
        nodes = plate_data.get("nodes", ["NODE 01", "NODE 02", "NODE 03"])
        caption = str(plate_data.get("caption", "HIDDEN SYSTEM ARCHITECTURE")).upper()
        n_nodes = max(1, min(3, len(nodes)))
        node_f = get_font("headline", 42 if is_vertical else 38)
        cap_f = get_font("mono", 28)

        if is_vertical:
            ys = [box_t + 220 + i * 200 for i in range(n_nodes)]
            for i in range(n_nodes - 1):
                draw.line([(cx, ys[i] + 54), (cx, ys[i + 1] - 54)], fill=(*cyan, int(220 * eased)), width=6)
            for i, node in enumerate(nodes[:3]):
                col = amber if i == n_nodes - 1 else cyan
                nw = int((box_w - 150) * (0.85 + 0.15 * eased))
                draw.rounded_rectangle(
                    [cx - nw // 2, ys[i] - 54, cx + nw // 2, ys[i] + 54],
                    radius=16,
                    fill=(col[0], col[1], col[2], 36),
                    outline=(*col, 240),
                    width=3,
                )
                _draw_centered_text(draw, str(node).upper(), cx, ys[i] - 24, node_f, (*white, 255))
        else:
            xs = [box_l + 240 + i * ((box_w - 480) // max(1, n_nodes - 1)) for i in range(n_nodes)]
            for i in range(n_nodes - 1):
                draw.line([(xs[i] + 155, cy), (xs[i + 1] - 155, cy)], fill=(*cyan, int(220 * eased)), width=6)
            for i, node in enumerate(nodes[:3]):
                col = amber if i == n_nodes - 1 else cyan
                draw.rounded_rectangle(
                    [xs[i] - 155, cy - 75, xs[i] + 155, cy + 75],
                    radius=16,
                    fill=(col[0], col[1], col[2], 38),
                    outline=(*col, 240),
                    width=3,
                )
                _draw_centered_text(draw, str(node).upper(), xs[i], cy - 22, node_f, (*white, 255))

        _draw_centered_text(draw, caption, cx, box_b - 105, cap_f, (*amber, 240), max_width=box_w - 100)

    else:  # radar_alert
        metric = str(plate_data.get("metric", "ANOMALY")).upper()
        sub = str(plate_data.get("subtitle", "THRESHOLD EXCEEDED")).upper()
        sev = str(plate_data.get("severity", "EXTREME")).upper()

        # Concentric expanding radar rings
        for ring_idx in range(1, 4):
            rr = int((75 * ring_idx + 45 * eased) * (1.0 if is_vertical else 0.9))
            draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(*crimson, max(35, 160 - ring_idx * 40)), width=3)

        # Alert pill
        pill_f = get_font("mono", 28)
        pill_txt = f"ALERT // {sev}"
        pb = draw.textbbox((0, 0), pill_txt, font=pill_f)
        pw = (pb[2] - pb[0]) + 48
        draw.rounded_rectangle([cx - pw // 2, box_t + 135, cx + pw // 2, box_t + 190], radius=10, fill=(*crimson, 230))
        _draw_centered_text(draw, pill_txt, cx, box_t + 148, pill_f, (*white, 255))

        m_font = get_font("headline", 96 if len(metric) <= 12 else 72)
        s_font = get_font("body", 34)
        _draw_centered_text(draw, metric, cx, cy - 55, m_font, (*amber, 255), max_width=box_w - 90)
        _draw_centered_text(draw, sub, cx, box_b - 138, s_font, (*white, 240), max_width=box_w - 110)

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
) -> Image.Image:
    """Render transparent RGBA telemetry HUD + optional 0-2.0s Shock Hook kinetic explosion."""
    brand = load_brand_config()
    palette = brand["palette"]
    w, h = size
    is_vertical = h > w

    cyan = _hex(palette["accent_cyan"])
    amber = _hex(palette["accent_amber"])
    crimson = _hex(palette["accent_crimson"])
    white = _hex(palette["text_primary"])
    muted = _hex(palette["text_secondary"])

    hud = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(hud)

    # --- 1. TOP TELEMETRY BAR (Sleek Bloomberg / Documentary HUD) ---
    pad_x = 46 if is_vertical else 58
    top_y = 66 if is_vertical else 34
    bar_h = 92 if is_vertical else 72

    draw.rounded_rectangle(
        [pad_x, top_y, w - pad_x, top_y + bar_h],
        radius=16,
        fill=(7, 10, 18, 195),
        outline=(*cyan, 115),
        width=2,
    )

    # Live smooth progress rail along top inside HUD
    rail_l = pad_x + 20
    rail_r = w - pad_x - 20
    rail_y = top_y + bar_h - 15
    draw.rounded_rectangle([rail_l, rail_y, rail_r, rail_y + 7], radius=4, fill=(255, 255, 255, 35))
    fill_r = rail_l + max(10, int((rail_r - rail_l) * max(0.0, min(1.0, global_progress))))
    draw.rounded_rectangle([rail_l, rail_y, fill_r, rail_y + 7], radius=4, fill=(*cyan, 245))
    # Glowing progress tip
    draw.ellipse([fill_r - 6, rail_y - 3, fill_r + 6, rail_y + 10], fill=(*amber, 255))

    mono_sm = get_font("mono", 24 if is_vertical else 21)
    mono_md = get_font("mono", 28 if is_vertical else 24)
    bold_md = get_font("headline", 34 if is_vertical else 28)

    # Left: pulsing red REC dot + beat tag
    dot_alpha = 255 if int(time_sec * 3) % 2 == 0 else 120
    draw.ellipse([pad_x + 22, top_y + 22, pad_x + 38, top_y + 38], fill=(*crimson, dot_alpha))
    draw.text((pad_x + 50, top_y + 16), hud_tag[:22], font=mono_sm, fill=(*white, 235))

    # Center: live metric value
    mb = draw.textbbox((0, 0), hud_metric[:18], font=bold_md)
    mw = mb[2] - mb[0]
    draw.text((w // 2 - mw // 2, top_y + 13), hud_metric[:18], font=bold_md, fill=(*amber, 255))

    # Right: clean non-clipped delta badge + live timecode
    mm = int(time_sec // 60)
    ss = time_sec % 60
    tc = f"{mm:02d}:{ss:05.2f}"
    clean_delta = hud_delta.strip()
    if len(clean_delta) > 12:
        # Cleanly shorten at word boundary instead of chopping mid-word
        words = clean_delta.split()
        short = ""
        for w_tok in words:
            trial = f"{short} {w_tok}".strip()
            if len(trial) <= 12:
                short = trial
            else:
                break
        clean_delta = short or clean_delta[:10]
    right_txt = f"{clean_delta}  |  {tc}"
    rb = draw.textbbox((0, 0), right_txt, font=mono_sm)
    rw = rb[2] - rb[0]
    draw.text((w - pad_x - 20 - rw, top_y + 18), right_txt, font=mono_sm, fill=(*cyan, 235))

    # --- 2. BRAND WATERMARK (Crisp corner placement outside Shorts right-side buttons) ---
    wm_size = 76 if is_vertical else 84
    wm = _load_watermark(wm_size)
    if wm is not None:
        wm_x = pad_x
        wm_y = (h - 215) if is_vertical else (h - 118)
        hud.alpha_composite(wm, dest=(wm_x, wm_y))
        draw.text((wm_x + wm_size + 14, wm_y + 22), "SCALE // ZERO", font=mono_md, fill=(*white, 175))

    # --- 3. 0.0-2.0s SHOCK HOOK EXPLOSION (Frame-0 high-contrast thumb-stopper) ---
    if shock_hook_text and 0.0 <= shock_progress <= 1.0:
        # Spring entrance (0..0.18) -> hold -> rapid exit (0.85..1.0)
        if shock_progress < 0.18:
            alpha_mult = ease_out_cubic(shock_progress / 0.18)
        elif shock_progress > 0.84:
            alpha_mult = max(0.0, 1.0 - (shock_progress - 0.84) / 0.16)
        else:
            alpha_mult = 1.0

        if alpha_mult > 0.02:
            hook_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            hdraw = ImageDraw.Draw(hook_layer)

            banner_y = int(h * 0.34) if is_vertical else int(h * 0.28)
            banner_h = 265 if is_vertical else 225
            bx0, bx1 = (44, w - 44) if is_vertical else (180, w - 180)

            # High-contrast crimson/obsidian shock impact slab
            hdraw.rounded_rectangle(
                [bx0, banner_y, bx1, banner_y + banner_h],
                radius=22,
                fill=(10, 12, 20, int(238 * alpha_mult)),
                outline=(*crimson, int(255 * alpha_mult)),
                width=5,
            )
            # Top warning bar
            hdraw.rectangle(
                [bx0 + 4, banner_y + 4, bx1 - 4, banner_y + 18],
                fill=(*amber, int(255 * alpha_mult)),
            )

            hook_font = get_font("headline", 94 if is_vertical else 104)
            sub_font = get_font("mono", 32 if is_vertical else 30)

            # Fit giant text cleanly inside shock slab
            htext = shock_hook_text.upper()
            hb = hdraw.textbbox((0, 0), htext, font=hook_font)
            if (hb[2] - hb[0]) > (bx1 - bx0 - 60):
                hook_font = get_font("headline", 72 if is_vertical else 82)

            _draw_centered_text(
                hdraw,
                htext,
                w // 2,
                banner_y + 46,
                hook_font,
                (*amber, int(255 * alpha_mult)),
                max_width=(bx1 - bx0 - 50),
            )
            if shock_hook_sub:
                _draw_centered_text(
                    hdraw,
                    f"[ {shock_hook_sub.upper()} ]",
                    w // 2,
                    banner_y + banner_h - 62,
                    sub_font,
                    (*white, int(245 * alpha_mult)),
                    max_width=(bx1 - bx0 - 60),
                )
            hud.alpha_composite(hook_layer)

    return hud
