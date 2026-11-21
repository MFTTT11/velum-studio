"""High-Contrast A/B/C Thumbnail Engine (1280x720, max 3 bold words per hook).

Generates 3 distinct visual angles for YouTube A/B testing and automatic
growth_mutator.py swapping if CTR falls below 5%:
- thumb_A.png: Split Scale Contrast (Signal Amber + Electric Cyan comparison bars)
- thumb_B.png: Crimson Anomaly Spotlight (High-urgency redline framing + stark white)
- thumb_C.png: Minimalist Vox Data Card (Ultra-clean Bloomberg telemetry stat shock)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from core.config import get_logger, load_brand_config
from engine.hud_renderer import get_font
from engine.media_fetcher import MediaFetcher

logger = get_logger("thumbnail_engine")


def _hex(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _enforce_max_three_words(lines: List[str]) -> List[str]:
    """Strictly cap total thumbnail headline to <= 3 bold words without ever leaving dangling filler."""
    joined = " ".join(lines).strip()
    tokens = joined.split()
    filler = {"A", "AN", "THE", "OF", "TO", "IN", "ON", "VS"}
    while len(tokens) > 3:
        # Prefer dropping weak filler words first so meaning stays punchy
        dropped = False
        for idx, tok in enumerate(tokens):
            if tok.upper() in filler:
                tokens.pop(idx)
                dropped = True
                break
        if not dropped:
            tokens.pop()
    if len(tokens) <= 1:
        return [tokens[0].upper()] if tokens else ["SCALE SHOCK"]
    if len(tokens) == 2:
        return [tokens[0].upper(), tokens[1].upper()]
    # Keep natural 2-line split (e.g. ["11 DAYS", "vs 31Y"] or ["$1B IS", "BROKEN"])
    if len(lines) == 2 and len(lines[0].split()) + len(lines[1].split()) <= 3:
        return [lines[0].upper(), lines[1].upper()]
    return [f"{tokens[0]} {tokens[1]}".upper(), tokens[2].upper()]


def _draw_stroked_text(
    draw: ImageDraw.ImageDraw,
    pos: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: Tuple[int, int, int, int],
    stroke_fill: Tuple[int, int, int, int] = (5, 7, 12, 255),
    stroke_width: int = 10,
) -> None:
    x, y = pos
    # Drop shadow
    draw.text((x + 6, y + 8), text, font=font, fill=(0, 0, 0, 195), stroke_width=stroke_width, stroke_fill=(0, 0, 0, 195))
    # Crisp main letters
    draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)


def _prepare_bg_photo(photo_path: Path, w: int = 1280, h: int = 720, tint: Tuple[int, int, int] = (0, 229, 255)) -> Image.Image:
    img = Image.open(photo_path).convert("RGB").resize((w, h), Image.Resampling.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.25)
    img = ImageEnhance.Brightness(img).enhance(0.58)
    arr = np.asarray(img, dtype=np.float32)

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = xx / max(w - 1, 1)
    ny = yy / max(h - 1, 1)
    # Dark left-side gradient scrim for extreme text readability
    scrim = np.clip(0.22 + 0.78 * (nx**0.85), 0.22, 1.0)[:, :, None]
    glow = np.exp(-(((nx - 0.78) ** 2) / 0.16 + ((ny - 0.45) ** 2) / 0.22)) * 0.28
    tint_arr = np.array(tint, dtype=np.float32)

    out = arr * scrim
    for c in range(3):
        out[:, :, c] = np.clip(out[:, :, c] + tint_arr[c] * glow, 0, 255)
    return Image.fromarray(out.astype(np.uint8), mode="RGB").convert("RGBA")


def generate_ab_thumbnails(
    topic: Dict[str, Any],
    out_dir: Path,
    media_cache_dir: Path,
) -> List[str]:
    """Render 3 distinct high-contrast 1280x720 A/B/C thumbnails."""
    brand = load_brand_config()
    palette = brand["palette"]
    cyan = _hex(palette["accent_cyan"])
    amber = _hex(palette["accent_amber"])
    crimson = _hex(palette["accent_crimson"])
    white = _hex(palette["text_primary"])
    obsidian = _hex(palette["bg_obsidian"])

    w, h = 1280, 720
    out_dir.mkdir(parents=True, exist_ok=True)
    fetcher = MediaFetcher(media_cache_dir)
    queries = topic.get("visual_queries", [topic["primary_keyword"]])

    raw_hooks = topic.get(
        "thumbnail_hooks",
        [
            [topic["shock_hook_stat"]],
            ["HIDDEN", "SYSTEM"],
            ["1,000X", "GAP"],
        ],
    )
    hooks = [_enforce_max_three_words(h_lines) for h_lines in raw_hooks[:3]]
    while len(hooks) < 3:
        hooks.append(["SCALE", "SHOCK"])

    facts = topic.get("key_facts", [])
    left_stat = facts[0]["value"] if len(facts) > 0 else "1X"
    right_stat = facts[1]["value"] if len(facts) > 1 else "1,000X"

    saved_paths: List[str] = []

    # --- VARIANT A: SPLIT SCALE CONTRAST (Amber + Cyan Dramatic Data Bar) ---
    bg_a_path = fetcher.fetch_photo_plate(queries[0], (w, h), variant_index=0)
    canvas_a = _prepare_bg_photo(bg_a_path, w, h, tint=amber)
    ov_a = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    da = ImageDraw.Draw(ov_a)

    # Diagonal power accent slash + comparison bars on right half
    da.polygon([(720, 0), (w, 0), (w, h), (620, h)], fill=(*obsidian, 215))
    da.line([(720, 0), (620, h)], fill=(*amber, 255), width=8)

    # Dramatic short vs towering comparison bars on right
    da.rounded_rectangle([770, 515, 920, 610], radius=10, fill=(*cyan, 245), outline=(*white, 220), width=3)
    da.rounded_rectangle([985, 115, 1155, 610], radius=12, fill=(*amber, 250), outline=(*white, 230), width=4)
    stat_f = get_font("headline", 44)
    _draw_stroked_text(da, (760, 452), left_stat[:10], stat_f, (*cyan, 255), stroke_width=6)
    _draw_stroked_text(da, (965, 52), right_stat[:10], stat_f, (*amber, 255), stroke_width=6)

    # Giant left-side max-3-word hook
    f_huge = get_font("headline", 136)
    y_txt = 155
    for idx, line in enumerate(hooks[0]):
        col = amber if idx == 0 else white
        _draw_stroked_text(da, (62, y_txt), line, f_huge, (*col, 255), stroke_width=12)
        y_txt += 155

    # Crisp corner channel pill
    pill_f = get_font("mono", 28)
    da.rounded_rectangle([62, 595, 345, 650], radius=10, fill=(*crimson, 245))
    da.text((84, 608), "SCALE // ZERO", font=pill_f, fill=(*white, 255))

    canvas_a.alpha_composite(ov_a)
    path_a = out_dir / "thumbnail_A_scale_contrast.png"
    canvas_a.convert("RGB").save(path_a, format="PNG", optimize=True)
    saved_paths.append(str(path_a))

    # --- VARIANT B: CRIMSON ANOMALY ALERT (High-Urgency Editorial Frame) ---
    bg_b_path = fetcher.fetch_photo_plate(queries[min(1, len(queries) - 1)], (w, h), variant_index=1)
    canvas_b = _prepare_bg_photo(bg_b_path, w, h, tint=crimson)
    ov_b = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    db = ImageDraw.Draw(ov_b)

    # Bold outer crimson telemetry border + dark glass central slab
    db.rectangle([18, 18, w - 18, h - 18], outline=(*crimson, 245), width=8)
    db.rounded_rectangle([54, 105, 860, 615], radius=24, fill=(8, 10, 18, 222), outline=(*crimson, 210), width=4)

    # Top warning badge
    db.rounded_rectangle([88, 138, 435, 198], radius=8, fill=(*crimson, 255))
    db.text((108, 152), "SYSTEM ANOMALY", font=get_font("mono", 30), fill=(*white, 255))

    y_txt = 232
    for idx, line in enumerate(hooks[1]):
        col = white if idx == 0 else amber
        _draw_stroked_text(db, (88, y_txt), line, get_font("headline", 142), (*col, 255), stroke_width=12)
        y_txt += 162

    # Right-side circular glowing anomaly reticle (auto-fit stat cleanly, zero clipping)
    rcx, rcy = 1065, 360
    db.ellipse([rcx - 148, rcy - 148, rcx + 148, rcy + 148], outline=(*crimson, 235), width=8)
    db.ellipse([rcx - 108, rcy - 108, rcx + 108, rcy + 108], fill=(*obsidian, 215), outline=(*amber, 240), width=5)
    stat_text = right_stat.upper()
    rf_size = 48 if len(stat_text) <= 8 else 38
    rf = get_font("headline", rf_size)
    rb = db.textbbox((0, 0), stat_text, font=rf)
    _draw_stroked_text(
        db,
        (rcx - (rb[2] - rb[0]) // 2, rcy - (rb[3] - rb[1]) // 2 - 4),
        stat_text,
        rf,
        (*amber, 255),
        stroke_width=5,
    )

    canvas_b.alpha_composite(ov_b)
    path_b = out_dir / "thumbnail_B_crimson_anomaly.png"
    canvas_b.convert("RGB").save(path_b, format="PNG", optimize=True)
    saved_paths.append(str(path_b))

    # --- VARIANT C: MINIMALIST VOX DATA (Clean Cyan Editorial Shock) ---
    canvas_c = Image.new("RGBA", (w, h), (*obsidian, 255))
    ov_c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dc = ImageDraw.Draw(ov_c)

    # Editorial grid
    for gx in range(0, w, 64):
        dc.line([(gx, 0), (gx, h)], fill=(30, 45, 72, 95), width=1)
    for gy in range(0, h, 64):
        dc.line([(0, gy), (w, gy)], fill=(30, 45, 72, 95), width=1)

    # Top glowing electric cyan bar
    dc.rectangle([0, 0, w, 16], fill=(*cyan, 255))

    # Huge centered typography + sleek horizontal ratio gauge below
    f_vox = get_font("headline", 158)
    y_txt = 96
    for idx, line in enumerate(hooks[2]):
        col = cyan if idx == 0 else white
        bb = dc.textbbox((0, 0), line, font=f_vox)
        lw = bb[2] - bb[0]
        _draw_stroked_text(dc, ((w - lw) // 2, y_txt), line, f_vox, (*col, 255), stroke_width=12)
        y_txt += 172

    # High-contrast bottom data comparison gauge
    dc.rounded_rectangle([120, 495, w - 120, 625], radius=18, fill=(14, 21, 36, 240), outline=(*cyan, 220), width=4)
    dc.rounded_rectangle([144, 520, 235, 600], radius=10, fill=(*cyan, 255))
    dc.rounded_rectangle([258, 520, w - 144, 600], radius=10, fill=(*amber, 255))
    cmp_txt = f"{left_stat}   VS   {right_stat}"
    cmp_f = get_font("headline", 54)
    cb = dc.textbbox((0, 0), cmp_txt, font=cmp_f)
    bar_cx = (258 + (w - 144)) // 2
    dc.text((bar_cx - (cb[2] - cb[0]) // 2, 533), cmp_txt, font=cmp_f, fill=(*obsidian, 255))

    canvas_c.alpha_composite(ov_c)
    path_c = out_dir / "thumbnail_C_vox_data.png"
    canvas_c.convert("RGB").save(path_c, format="PNG", optimize=True)
    saved_paths.append(str(path_c))

    logger.info("Rendered 3 A/B/C high-contrast thumbnails (1280x720) in %s", out_dir.name)
    return saved_paths
