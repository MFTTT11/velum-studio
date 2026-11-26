"""VELUM V6 — Programmatic 2D Technical Vector & Physics Schematic Animation Engine.

Renders original, museum-grade 2D blueprint & engineering explainer animations
in pure Python (Pillow + NumPy) at 1080x1920 -> 4K 60fps with zero paid AI video APIs:
- Persistent VELUM V6 Editorial Chrome:
    * Top @VelumDispatch handle + EPISODE XX identifier
    * 6-node geometric phase progress rail (Zeigarnik completion pull)
    * Numbered chapter pill + colossal 2-line left-aligned editorial headline
    * Quiet schematic simulation & authoritative scientific source footer
- 10 Living Animated Schematic Renderers:
    1. layered_cutaway          (multi-pane / structural cross-section + animated force/gap flow)
    2. depth_pressure_cutaway   (calibrated depth column + radial hull compression + ATM meters)
    3. orbital_relativity_sim   (wireframe Earth + animated satellite/asteroid orbit + vector beam)
    4. signal_flow_pipeline     (3-step live checklist + glowing data/laser conduit + choke ring)
    5. waveform_stability_meter (live sweeping oscilloscope wave + threshold breach + dual meters)
    6. exponential_scale_curve  (calibrated axes + intuition vs exponential reality spike)
    7. proportional_volume_scale(3D isometric wireframe cube / caliper scale ruler + dimensions)
    8. step_sequence_blueprint  (3-stage animated checklist + glowing schematic focal zone)
    9. split_blueprint_duel     (hairline blueprint head-to-head comparison + live gauges)
   10. verdict_poll_blueprint   (clean closing poll blueprint + subtle community prompt)
"""

from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from core.config import resolve_font

# VELUM V6 Original Editorial Blueprint Palette
BG_TOP = (7, 12, 20)
BG_BOT = (10, 17, 29)
CYAN = (34, 211, 238)
AMBER = (245, 158, 11)
CORAL = (244, 63, 94)
MINT = (16, 185, 129)
WHITE = (245, 247, 250)
MUTED = (138, 158, 184)
GRID_DIM = (36, 56, 82)
SURFACE = (13, 22, 36)


@lru_cache(maxsize=64)
def _font(role: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = resolve_font(role)
    if path:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            return ImageFont.load_default()
    return ImageFont.load_default()


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    role: str,
    max_size: int,
    max_width: int,
    min_size: int = 20,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = max_size
    while size > min_size:
        f = _font(role, size)
        bb = draw.textbbox((0, 0), text, font=f)
        if (bb[2] - bb[0]) <= max_width:
            return f
        size = max(min_size, int(size * 0.91))
    return _font(role, min_size)


def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _accent_color(name: str) -> Tuple[int, int, int]:
    return {
        "cyan": CYAN,
        "amber": AMBER,
        "coral": CORAL,
        "crimson": CORAL,
        "mint": MINT,
        "emerald": MINT,
    }.get((name or "amber").lower(), AMBER)


def _roll_number(raw: str, progress: float) -> str:
    """Smoothly roll the first numeric token inside a label while preserving calendar years."""
    p = max(0.15, min(1.0, _ease_out(progress)))
    if p >= 0.99:
        return raw

    def _rep(m: re.Match[str]) -> str:
        tok = m.group(0)
        has_comma = "," in tok
        has_dot = "." in tok
        clean = tok.replace(",", "")
        try:
            val = float(clean)
        except ValueError:
            return tok
        if not has_dot and not has_comma and 1800 <= val <= 2100:
            return tok
        cur = val * p
        if has_dot:
            dec = len(clean.split(".")[1])
            return f"{cur:,.{dec}f}" if has_comma else f"{cur:.{dec}f}"
        iv = max(1 if val >= 1 else 0, int(round(cur)))
        return f"{iv:,}" if has_comma else str(iv)

    return re.sub(r"\d[\d,]*(?:\.\d+)?", _rep, raw, count=1)


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    fill: Tuple[int, int, int, int],
    width: int = 2,
    dash: int = 12,
    gap: int = 8,
) -> None:
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    dist = math.hypot(dx, dy)
    if dist < 1.0:
        return
    ux, uy = dx / dist, dy / dist
    pos = 0.0
    step = float(dash + gap)
    while pos < dist:
        end_p = min(dist, pos + dash)
        draw.line(
            [(p0[0] + ux * pos, p0[1] + uy * pos), (p0[0] + ux * end_p, p0[1] + uy * end_p)],
            fill=fill,
            width=width,
        )
        pos += step


def _draw_dashed_ellipse(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    fill: Tuple[int, int, int, int],
    width: int = 3,
    segments: int = 36,
    phase: float = 0.0,
) -> None:
    for i in range(segments):
        if i % 2 == 1:
            continue
        a0 = (i / segments + phase * 0.08) * math.tau
        a1 = ((i + 0.72) / segments + phase * 0.08) * math.tau
        pts = []
        for s in range(5):
            ang = a0 + (a1 - a0) * (s / 4.0)
            pts.append((cx + math.cos(ang) * rx, cy + math.sin(ang) * ry))
        draw.line(pts, fill=fill, width=width)


def _draw_arrow(
    draw: ImageDraw.ImageDraw,
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    fill: Tuple[int, int, int, int],
    width: int = 4,
    head_len: float = 16.0,
) -> None:
    draw.line([p0, p1], fill=fill, width=width)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    left = (
        p1[0] - head_len * math.cos(ang - 0.45),
        p1[1] - head_len * math.sin(ang - 0.45),
    )
    right = (
        p1[0] - head_len * math.cos(ang + 0.45),
        p1[1] - head_len * math.sin(ang + 0.45),
    )
    draw.polygon([p1, left, right], fill=fill)


def _draw_diamond(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    r: float,
    fill: Optional[Tuple[int, int, int, int]],
    outline: Tuple[int, int, int, int],
    width: int = 2,
) -> None:
    pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    draw.polygon(pts, fill=fill, outline=outline)
    if width > 1:
        draw.line(pts + [pts[0]], fill=outline, width=width)


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    cx: int,
    y: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: Tuple[int, int, int, int],
    max_width: Optional[int] = None,
) -> int:
    if not max_width:
        bb = draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.text((cx - tw // 2, y - bb[1]), text, font=font, fill=fill)
        return y + th
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w_tok in words:
        trial = f"{cur} {w_tok}".strip()
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w_tok
    if cur:
        lines.append(cur)
    cy = y
    for ln in lines:
        bb = draw.textbbox((0, 0), ln, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.text((cx - tw // 2, cy - bb[1]), ln, font=font, fill=fill)
        cy += int(th * 1.24)
    return cy


def _clean_lbl(text: str, max_chars: int) -> str:
    """Trim a label cleanly at a word boundary so no word is ever chopped mid-letter."""
    s = re.sub(r"\s+", " ", str(text or "").strip()).upper()
    if len(s) <= max_chars:
        return s
    parts: List[str] = []
    for tok in s.split():
        cand = " ".join(parts + [tok])
        if len(cand) <= max_chars:
            parts.append(tok)
        else:
            break
    return " ".join(parts) if parts else s[:max_chars]


def _draw_check_icon(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    color: Tuple[int, int, int, int],
) -> None:
    """Draw a crisp 2-segment vector checkmark (zero Unicode font dependency across OSes)."""
    draw.line([(cx - 8, cy), (cx - 2, cy + 6), (cx + 8, cy - 6)], fill=color, width=3)


def _draw_meter_bar(
    draw: ImageDraw.ImageDraw,
    x0: int,
    y0: int,
    width: int,
    height: int,
    label: str,
    value_text: str,
    fill_frac: float,
    color: Tuple[int, int, int],
) -> None:
    lbl_f = _font("mono", 22)
    val_f = _font("headline", 28)
    draw.text((x0, y0), _clean_lbl(label, 24), font=lbl_f, fill=(*MUTED, 235))
    vbb = draw.textbbox((0, 0), value_text, font=val_f)
    draw.text((x0 + width - (vbb[2] - vbb[0]), y0 - 4), value_text, font=val_f, fill=(*color, 255))
    by = y0 + 34
    draw.rounded_rectangle(
        [x0, by, x0 + width, by + height],
        radius=height // 2,
        fill=(18, 30, 48, 220),
        outline=(*GRID_DIM, 180),
        width=1,
    )
    fw = max(height, int(width * max(0.05, min(1.0, fill_frac))))
    draw.rounded_rectangle(
        [x0, by, x0 + fw, by + height],
        radius=height // 2,
        fill=(*color, 240),
    )


@lru_cache(maxsize=8)
def _base_canvas_array(w: int, h: int, accent: Tuple[int, int, int]) -> np.ndarray:
    """Precompute silky radial blueprint slate backdrop + architectural dot-matrix grid once per (size, accent)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = xx / max(w - 1, 1)
    ny = yy / max(h - 1, 1)
    arr = np.zeros((h, w, 3), dtype=np.float32)
    radial = np.exp(-(((nx - 0.50) * 1.15) ** 2 + ((ny - 0.44) * 1.25) ** 2) / 0.24) * 0.14
    glow_cyan = np.exp(-(((nx - 0.50) * 1.25) ** 2 + ((ny - 0.48) * 1.45) ** 2) / 0.16) * 0.11
    for c in range(3):
        grad = BG_TOP[c] * (1.0 - ny) + BG_BOT[c] * ny
        arr[:, :, c] = np.clip(grad + accent[c] * radial + CYAN[c] * glow_cyan, 0, 255)
    # Bake subtle architectural dot-matrix micro-grid directly via NumPy slicing (eliminates 600 Python draws/frame)
    dot_alpha = 72.0 / 255.0
    dot_rgb = np.array([72.0, 102.0, 138.0], dtype=np.float32)
    ys = np.arange(140, max(141, h - 180), 54)
    xs = np.arange(27, w, 54)
    grid_patch = arr[np.ix_(ys, xs)]
    arr[np.ix_(ys, xs)] = np.clip(grid_patch * (1.0 - dot_alpha) + dot_rgb * dot_alpha, 0, 255)
    return arr.astype(np.uint8)


def _draw_living_backdrop_streams(
    draw: ImageDraw.ImageDraw,
    w: int,
    stream_t: float,
) -> None:
    """Draw continuous living horizontal stream particles driven by unbroken timeline time."""
    for i in range(16):
        speed = 115.0 + (i % 4) * 52.0
        px = int((w - ((i * 173.0 + stream_t * speed) % (w + 160.0))) + 40.0)
        py = 440 + ((i * 97) % 780)
        slen = 36 + (i % 3) * 28
        draw.line([(px, py), (px + slen, py)], fill=(*CYAN, 26 + (i % 3) * 10), width=2)


def _create_v6_backdrop(w: int, h: int, accent: Tuple[int, int, int], phase_t: float) -> Image.Image:
    base = _base_canvas_array(w, h, accent)
    canvas = Image.fromarray(base, mode="RGB")
    draw = ImageDraw.Draw(canvas, "RGBA")
    _draw_living_backdrop_streams(draw, w, phase_t * 2.4)
    return canvas


def _compose_reality_backdrop(
    real_rgb: Image.Image,
    w: int,
    h: int,
    accent_col: Tuple[int, int, int],
    full_hook: bool,
) -> Image.Image:
    """Blend a real-world cinema photo cleanly into the VELUM V8 blueprint frame."""
    photo = real_rgb.convert("RGB")
    if photo.size != (w, h):
        photo = photo.resize((w, h), Image.Resampling.LANCZOS)
    p_arr = np.asarray(photo, dtype=np.float32)
    base_arr = _base_canvas_array(w, h, accent_col).astype(np.float32)

    if not full_hook:
        # Mid-video pattern interrupt (Ch 4): sleek 18% atmospheric real-world depth layer behind CAD
        blended = np.clip(base_arr * 0.82 + p_arr * 0.18, 0, 255).astype(np.uint8)
        return Image.fromarray(blended, mode="RGB")

    # Chapter 1 Scroll-Stopper Hook: vivid real subject in center viewport (y=428..1246)
    # with deep editorial vignette top (headline) & bottom (captions) for razor-sharp contrast
    yy = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None, None]
    # Center band (0.22..0.67) showcases vibrant reality at ~82% visibility; top/bottom fade to dark slate
    top_fade = np.clip((yy - 0.17) / 0.10, 0.0, 1.0)
    bot_fade = np.clip((0.72 - yy) / 0.11, 0.0, 1.0)
    window_vis = (top_fade * bot_fade) * 0.84 + 0.14
    blended = np.clip(base_arr * (1.0 - window_vis) + p_arr * window_vis, 0, 255).astype(np.uint8)
    return Image.fromarray(blended, mode="RGB")


def _draw_reality_xray_scanner(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent_col: Tuple[int, int, int],
) -> None:
    """VELUM V8 Chapter-1 live 60fps X-Ray target reticle & cyan laser scanner over real-world footage."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    eased = _ease_out(anim_t)

    # Crisp corner viewport brackets framing the real-world subject
    b_len = 52
    b_col = (*CYAN, 235)
    corners = [
        [(x0, y0 + b_len), (x0, y0), (x0 + b_len, y0)],
        [(x1 - b_len, y0), (x1, y0), (x1, y0 + b_len)],
        [(x0, y1 - b_len), (x0, y1), (x0 + b_len, y1)],
        [(x1 - b_len, y1), (x1, y1), (x1, y1 - b_len)],
    ]
    for c_pts in corners:
        draw.line(c_pts, fill=b_col, width=4)

    # Sweeping vertical X-Ray cyan laser beam + glowing trail
    scan_prog = (phase_t * 1.15) % 1.0
    scan_y = int(y0 + 18 + (y1 - y0 - 36) * scan_prog)
    trail_top = max(y0 + 6, scan_y - 68)
    draw.rectangle([x0 + 6, trail_top, x1 - 6, scan_y], fill=(CYAN[0], CYAN[1], CYAN[2], 32))
    draw.line([(x0 + 4, scan_y), (x1 - 4, scan_y)], fill=(*CYAN, 250), width=4)
    draw.line([(x0 + 4, scan_y - 3), (x1 - 4, scan_y - 3)], fill=(*WHITE, 195), width=2)

    # Pulsing central target lock reticle over real subject
    pulse = 0.5 + 0.5 * math.sin(phase_t * math.tau * 3.0)
    r_outer = int(112 + 12 * pulse)
    _draw_dashed_ellipse(draw, cx, cy, r_outer, r_outer, (*accent_col, 235), width=3, segments=24, phase=phase_t * 2.5)
    r_inner = int(64 * max(0.35, eased))
    draw.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], outline=(*WHITE, 215), width=2)
    draw.line([(cx - 24, cy), (cx + 24, cy)], fill=(*accent_col, 240), width=2)
    draw.line([(cx, cy - 24), (cx, cy + 24)], fill=(*accent_col, 240), width=2)

    # Top-left live X-Ray scan status pill + bottom-right key metric badge
    pill_f = _font("mono", 21)
    scan_pct = min(99, int(phase_t * 100))
    status_txt = f"X-RAY LOCK · {scan_pct:02d}%"
    sbb = draw.textbbox((0, 0), status_txt, font=pill_f)
    pw = (sbb[2] - sbb[0]) + 46
    draw.rounded_rectangle(
        [x0 + 18, y0 + 18, x0 + 18 + pw, y0 + 58],
        radius=8,
        fill=(7, 14, 24, 215),
        outline=(*CYAN, 210),
        width=2,
    )
    draw.ellipse([x0 + 30, y0 + 32, x0 + 42, y0 + 44], fill=(*CORAL, int(170 + 85 * pulse)))
    draw.text((x0 + 50, y0 + 27 - sbb[1]), status_txt, font=pill_f, fill=(*WHITE, 245))

    m_val = _clean_lbl(str(data.get("metric_value") or ""), 22)
    if m_val:
        mf = _font("headline", 32)
        mbb = draw.textbbox((0, 0), m_val, font=mf)
        mw = (mbb[2] - mbb[0]) + 36
        draw.rounded_rectangle(
            [x1 - 18 - mw, y1 - 74, x1 - 18, y1 - 18],
            radius=10,
            fill=(7, 14, 24, 222),
            outline=(*accent_col, 230),
            width=2,
        )
        draw.text((x1 - 18 - mw + 18, y1 - 62 - mbb[1]), m_val, font=mf, fill=(*accent_col, 255))


def prepare_v6_chapter_context(
    schematic_mode: str,
    schematic_data: Dict[str, Any],
    size: Tuple[int, int] = (1080, 1920),
    chapter_num: int = 1,
    total_chapters: int = 6,
    chapter_tag: str = "THE MECHANISM",
    headline_line1: str = "HIDDEN SCALE",
    headline_line2: str = "EXPOSED BY PHYSICS",
    accent_word: str = "",
    episode_num: int = 1,
    source_credit: str = "VELUM RESEARCH",
    real_backdrop_rgb: Optional[Image.Image] = None,
    hook_reality_mode: bool = False,
    show_subscribe_cta: bool = False,
) -> Dict[str, Any]:
    """Pre-bake static per-chapter chrome & settled typography ONCE for butter-smooth native 60fps streaming."""
    w, h = size
    pad = 60
    accent_col = _accent_color(str(schematic_data.get("accent", "amber")))
    if real_backdrop_rgb is not None:
        base_bg = _compose_reality_backdrop(real_backdrop_rgb, w, h, accent_col, full_hook=hook_reality_mode)
    else:
        base_bg = Image.fromarray(_base_canvas_array(w, h, accent_col).copy(), mode="RGB")
    draw = ImageDraw.Draw(base_bg, "RGBA")

    # 1. Top Editorial Header: @VelumDispatch  |  EPISODE XX
    hdr_f = _font("mono", 25)
    draw.text((pad, 48), "@VelumDispatch", font=hdr_f, fill=(*WHITE, 232))
    ep_txt = f"EPISODE {episode_num:02d}"
    ebb = draw.textbbox((0, 0), ep_txt, font=hdr_f)
    draw.text((w - pad - (ebb[2] - ebb[0]), 48), ep_txt, font=hdr_f, fill=(*MUTED, 220))

    # 2. Static parts of 6-Node VELUM Geometric Phase Progress Rail (y=108)
    rail_y = 108
    rail_f = _font("mono", 20)
    draw.text((pad, rail_y - 12), "START", font=rail_f, fill=(*MUTED, 200))
    end_txt = "RESULT"
    eb = draw.textbbox((0, 0), end_txt, font=rail_f)
    draw.text((w - pad - (eb[2] - eb[0]), rail_y - 12), end_txt, font=rail_f, fill=(*MUTED, 200))

    rx0, rx1 = pad + 96, w - pad - 116
    n_steps = max(2, min(8, total_chapters))
    cur_idx = max(0, min(n_steps - 1, chapter_num - 1))
    xs = [rx0 + i * ((rx1 - rx0) / max(1, n_steps - 1)) for i in range(n_steps)]

    draw.line([(rx0, rail_y), (rx1, rail_y)], fill=(*GRID_DIM, 200), width=3)
    if cur_idx > 0:
        draw.line([(rx0, rail_y), (xs[cur_idx], rail_y)], fill=(*AMBER, 240), width=4)
    for i, nx in enumerate(xs):
        if i < cur_idx:
            _draw_diamond(draw, nx, rail_y, 9, (*AMBER, 255), (*AMBER, 255), width=2)
        elif i > cur_idx:
            _draw_diamond(draw, nx, rail_y, 8, (*BG_TOP, 255), (*MUTED, 165), width=2)

    # 3. Chapter Pill Badge (y=154..198)
    pill_f = _font("mono", 22)
    pill_txt = f"{chapter_num}  ·  {chapter_tag.upper()[:24]}"
    pbb = draw.textbbox((0, 0), pill_txt, font=pill_f)
    pw = (pbb[2] - pbb[0]) + 40
    ph = 44
    draw.rounded_rectangle(
        [pad, 154, pad + pw, 154 + ph],
        radius=10,
        fill=(accent_col[0], accent_col[1], accent_col[2], 32),
        outline=(*accent_col, 165),
        width=2,
    )
    draw.text((pad + 20, 154 + 10 - pbb[1]), pill_txt, font=pill_f, fill=(*accent_col, 250))

    # 4. Pre-fit Colossal 2-Line Editorial Headline ONCE (avoids 10+ textbbox lookups per frame)
    max_hw = w - pad * 2
    l1 = headline_line1.upper().strip()
    l2 = headline_line2.upper().strip()
    f1 = _fit_font(draw, l1, "headline", 86, max_hw, min_size=46)
    f2 = _fit_font(draw, l2, "headline", 86, max_hw, min_size=46)
    uni_size = min(getattr(f1, "size", 76), getattr(f2, "size", 76))
    head_f = _font("headline", uni_size)
    bb1 = draw.textbbox((0, 0), l1, font=head_f)
    y_l2_offset = (bb1[3] - bb1[1]) + 22

    acc_target = (accent_word or "").upper().strip()
    words_l2 = l2.split()
    l2_layout: List[Tuple[int, str, Tuple[int, int, int]]] = []
    cur_x = pad
    for idx_w, tok in enumerate(words_l2):
        is_acc = (acc_target and acc_target in tok) or (not acc_target and idx_w == len(words_l2) - 1)
        col = accent_col if is_acc else WHITE
        l2_layout.append((cur_x, tok, col))
        cur_x += draw.textbbox((0, 0), tok + " ", font=head_f)[2]

    # 5. Subtle Schematic Attribution Strip (y=1278) right above editorial captions
    foot_y = 1278
    foot_f = _font("mono", 20)
    draw.ellipse([pad, foot_y + 6, pad + 10, foot_y + 16], fill=(*CYAN, 220))
    draw.text((pad + 20, foot_y), "SCHEMATIC SIMULATION · VELUM", font=foot_f, fill=(*MUTED, 195))
    if source_credit:
        src_txt = f"SOURCE: {source_credit.upper()[:28]}"
        sbb = draw.textbbox((0, 0), src_txt, font=foot_f)
        draw.text((w - pad - (sbb[2] - sbb[0]), foot_y), src_txt, font=foot_f, fill=(*MUTED, 185))

    # Pre-bake settled headline backdrop used for ~76% of frames once intro slide finishes
    settled_bg = base_bg.copy()
    sdraw = ImageDraw.Draw(settled_bg, "RGBA")
    y_l1_settled = 218
    sdraw.text((pad, y_l1_settled), l1, font=head_f, fill=(*WHITE, 255))
    y_l2_settled = y_l1_settled + y_l2_offset
    for tx, tok, col in l2_layout:
        sdraw.text((tx, y_l2_settled), tok, font=head_f, fill=(*col, 255))

    # Resolve renderer callable once per chapter (V8 Chapter-1 Reality Hook uses X-Ray scanner overlay!)
    if hook_reality_mode and real_backdrop_rgb is not None:
        renderer = _draw_reality_xray_scanner
    else:
        renderer = _RENDERERS.get(schematic_mode)
        if renderer is None and schematic_mode.startswith("mech_"):
            from engine.v7_mechanisms import V7_MECHANISM_RENDERERS
            renderer = V7_MECHANISM_RENDERERS.get(schematic_mode)
        if renderer is None:
            renderer = _render_step_sequence_blueprint

    return {
        "size": (w, h),
        "pad": pad,
        "base_bg": base_bg,
        "settled_bg": settled_bg,
        "accent_col": accent_col,
        "schematic_mode": schematic_mode,
        "schematic_data": schematic_data,
        "renderer": renderer,
        "chapter_num": chapter_num,
        "n_steps": n_steps,
        "cur_idx": cur_idx,
        "xs": xs,
        "rail_y": rail_y,
        "head_f": head_f,
        "l1": l1,
        "y_l2_offset": y_l2_offset,
        "l2_layout": l2_layout,
        "hook_reality_mode": bool(hook_reality_mode and real_backdrop_rgb is not None),
        "show_subscribe_cta": bool(show_subscribe_cta),
    }


def _draw_v6_dynamic_frame(
    ctx: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    global_t_sec: Optional[float] = None,
    local_t: Optional[float] = None,
) -> Image.Image:
    """Render one silky V8 frame onto cached chapter chrome (zero full-frame alpha_composite overhead)."""
    w, h = ctx["size"]
    pad = ctx["pad"]
    settled = anim_t >= 0.56
    canvas = ctx["settled_bg"].copy() if settled else ctx["base_bg"].copy()
    draw = ImageDraw.Draw(canvas, "RGBA")

    # 1. Unbroken continuous background telemetry flow streaks (skip over bright reality hook center)
    stream_t = global_t_sec if global_t_sec is not None else (phase_t * 4.5)
    if not ctx.get("hook_reality_mode"):
        _draw_living_backdrop_streams(draw, w, stream_t)

    # 2. Smooth fractional progress beam + pulsing active diamond node
    cur_idx = ctx["cur_idx"]
    n_steps = ctx["n_steps"]
    xs = ctx["xs"]
    rail_y = ctx["rail_y"]
    if cur_idx + 1 < n_steps:
        frac_x = xs[cur_idx] + (xs[cur_idx + 1] - xs[cur_idx]) * min(0.92, phase_t * 0.92)
        draw.line([(xs[cur_idx], rail_y), (frac_x, rail_y)], fill=(*CYAN, 215), width=3)

    pulse_phase = global_t_sec * 1.15 if global_t_sec is not None else (phase_t * 2.0)
    pulse = 0.5 + 0.5 * math.sin(pulse_phase * math.tau)
    nx = xs[cur_idx]
    glow_r = 15.0 + 3.5 * pulse
    draw.ellipse(
        [nx - glow_r, rail_y - glow_r, nx + glow_r, rail_y + glow_r],
        fill=(*CYAN, int(45 + 42 * pulse)),
    )
    _draw_diamond(draw, nx, rail_y, 11, (*CYAN, 255), (*WHITE, 255), width=2)

    # 3. Animated cubic-eased headline glide during chapter entrance only (0.0ms once settled!)
    if not settled:
        e_head = _ease_out(min(1.0, anim_t * 1.8))
        alpha_h = int(255 * min(1.0, 0.30 + 0.70 * e_head))
        slide_y = int(round((1.0 - _ease_out(min(1.0, anim_t * 2.0))) * 16.0))
        y_l1 = 218 + slide_y
        head_f = ctx["head_f"]
        draw.text((pad, y_l1), ctx["l1"], font=head_f, fill=(*WHITE, alpha_h))
        y_l2 = y_l1 + ctx["y_l2_offset"]
        for tx, tok, col in ctx["l2_layout"]:
            draw.text((tx, y_l2), tok, font=head_f, fill=(*col, alpha_h))

    # 4. Tactile damped mechanical recoil on climax chapters (Ch 3 rupture / Ch 5 twist)
    jitter_x = 0
    jitter_y = 0
    lt = phase_t if local_t is None else local_t
    if ctx["chapter_num"] in (3, 5) and 0.0 <= lt <= 0.18:
        decay = (1.0 - lt / 0.18) ** 2
        jitter_x = int(round(math.sin(lt * 92.0) * 5.0 * decay))
        jitter_y = int(round(math.cos(lt * 74.0) * 3.5 * decay))

    stage_box = (60 + jitter_x, 428 + jitter_y, w - 60 + jitter_x, 1246 + jitter_y)
    ctx["renderer"](draw, stage_box, ctx["schematic_data"], anim_t, phase_t, ctx["accent_col"])

    # 5. V8 Climax-Moment Subscriber Micro-Pill (Ch 5 & 6 dopamine peak — ZERO extra outro seconds!)
    if ctx.get("show_subscribe_cta"):
        cta_f = _font("mono", 20)
        cta_txt = "+ SUBSCRIBE  ·  DAILY 60FPS X-RAY MECHANICS"
        cbb = draw.textbbox((0, 0), cta_txt, font=cta_f)
        cw = (cbb[2] - cbb[0]) + 56
        cx0 = (w - cw) // 2
        cy0 = 1218
        draw.rounded_rectangle(
            [cx0, cy0, cx0 + cw, cy0 + 40],
            radius=20,
            fill=(16, 24, 38, 232),
            outline=(*CORAL, int(175 + 75 * pulse)),
            width=2,
        )
        draw.ellipse([cx0 + 18, cy0 + 14, cx0 + 30, cy0 + 26], fill=(*CORAL, int(190 + 65 * pulse)))
        draw.text((cx0 + 40, cy0 + 10 - cbb[1]), cta_txt, font=cta_f, fill=(*WHITE, 248))

    return canvas


def render_v6_stream_frame_bgr(
    ctx: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    global_t_sec: float,
    local_t: float,
) -> np.ndarray:
    """Stream one ready-to-pipe OpenCV BGR uint8 frame directly from cached chapter context."""
    pil_rgb = _draw_v6_dynamic_frame(
        ctx=ctx,
        anim_t=anim_t,
        phase_t=phase_t,
        global_t_sec=global_t_sec,
        local_t=local_t,
    )
    arr_rgb = np.asarray(pil_rgb)
    return np.ascontiguousarray(arr_rgb[:, :, ::-1])


# ==============================================================================
# 10 LIVING 2D TECHNICAL SCHEMATIC STAGE RENDERERS (Stage box: x=60..1020, y=428..1246)
# ==============================================================================

def _render_layered_cutaway(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Multi-layer engineering cutaway (3-pane window, battery separator, 2nm gate, ship hull)."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    eased = _ease_out(anim_t)

    layers = data.get("layers") or ["OUTER SHIELD", "ACTIVE CORE", "INNER BARRIER"]
    metric_lbl = str(data.get("metric_label", "LOAD TRANSFER"))
    metric_val = _roll_number(str(data.get("metric_value", "100%")), anim_t)
    sub_lbl = str(data.get("sub_label", "FORCE ROUTING"))
    sub_val = _roll_number(str(data.get("sub_value", "VERIFIED")), anim_t)
    callout = str(data.get("callout", "CRITICAL MARGIN"))

    # Top sequence pills if provided
    stages = data.get("stages") or ["LOAD", "VALVE", "SHIELD"]
    _draw_stage_strip(draw, x0 + 20, y0 + 18, (x1 - x0) - 40, stages, anim_t, accent)

    # 3 vertical engineering cutaway panes in center
    pane_top = y0 + 135
    pane_bot = y1 - 215
    pane_xs = [cx - 210, cx, cx + 210]
    pane_colors = [CORAL, CYAN, MINT]
    mono_f = _font("mono", 20)
    bold_f = _font("headline", 26)

    # Dashed safety / danger envelope around middle layer
    _draw_dashed_ellipse(draw, cx, (pane_top + pane_bot) // 2, 340, 175, (*accent, 155), width=2, phase=phase_t)

    for i, px in enumerate(pane_xs):
        col = pane_colors[i % 3]
        pw = 34 if i != 1 else 26
        # Slide layers cleanly into place
        offset = int((1.0 - eased) * (i - 1) * 40)
        lx = px + offset
        draw.rounded_rectangle(
            [lx - pw // 2, pane_top, lx + pw // 2, pane_bot],
            radius=8,
            fill=(col[0], col[1], col[2], 52),
            outline=(*col, 240),
            width=3,
        )
        # Micro bleed gap / gate aperture in middle layer
        if i == 1:
            gy = (pane_top + pane_bot) // 2
            draw.rectangle([lx - pw // 2 - 2, gy - 14, lx + pw // 2 + 2, gy + 14], fill=(*BG_TOP, 255))
            r_glow = 18 + int(6 * math.sin(phase_t * math.tau * 2))
            draw.ellipse([lx - r_glow, gy - r_glow, lx + r_glow, gy + r_glow], outline=(*AMBER, 240), width=3)
            _draw_centered(draw, _clean_lbl(callout, 24), lx, pane_bot + 16, mono_f, (*AMBER, 250))

        lbl = _clean_lbl(str(layers[i % len(layers)]), 16)
        _draw_centered(draw, lbl, lx, pane_top - 34, mono_f, (*col, 235))

    # Animated force / particle arrows streaming left -> right across aperture
    for row_i in range(4):
        ay = pane_top + 70 + row_i * ((pane_bot - pane_top - 140) // 3)
        travel = (phase_t * 1.4 + row_i * 0.25) % 1.0
        ax0 = x0 + 55 + travel * 110
        _draw_arrow(draw, (ax0, ay), (ax0 + 78, ay), (*AMBER, 235), width=4, head_len=14)
        bx0 = cx + 35 + travel * 100
        _draw_arrow(draw, (bx0, ay), (bx0 + 68, ay), (*CYAN, 220), width=3, head_len=12)

    # Bottom dual live telemetry bars
    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(draw, x0 + 25, y1 - 125, bar_w, 16, metric_lbl, metric_val, 0.88 * eased, CORAL)
    _draw_meter_bar(draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16, sub_lbl, sub_val, 0.68 * eased, CYAN)


def _render_depth_pressure_cutaway(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Calibrated vertical depth shaft + inward-crushing hull cross-section + live pressure bars."""
    x0, y0, x1, y1 = box
    eased = _ease_out(anim_t)
    mono_f = _font("mono", 20)
    hero_f = _font("headline", 48)

    # Left: Calibrated depth ruler (x0+30 .. x0+290)
    axis_x = x0 + 135
    top_y, bot_y = y0 + 55, y1 - 190
    draw.line([(axis_x, top_y), (axis_x, bot_y)], fill=(*CYAN, 200), width=3)

    markers = data.get("depth_markers") or [
        ("SURFACE", "0 M", 0.0),
        ("SUNLIGHT ENDS", "1,000 M", 0.28),
        ("EVEREST PEAK", "8,848 M", 0.72),
        ("FLOOR LIMIT", str(data.get("primary_value", "10,984 M")), 0.96),
    ]
    for lbl, val, frac in markers:
        my = int(top_y + (bot_y - top_y) * frac)
        col = CORAL if frac > 0.85 else (AMBER if frac > 0.5 else CYAN)
        draw.line([(axis_x - 16, my), (axis_x + 16, my)], fill=(*col, 235), width=3)
        draw.text((axis_x + 26, my - 20), f"{val}", font=_font("headline", 25), fill=(*col, 250))
        draw.text((axis_x + 26, my + 8), str(lbl).upper()[:18], font=mono_f, fill=(*MUTED, 210))

    # Sliding live depth probe beacon along ruler
    probe_y = int(top_y + (bot_y - top_y) * (0.12 + 0.84 * eased))
    draw.ellipse([axis_x - 12, probe_y - 12, axis_x + 12, probe_y + 12], fill=(*AMBER, 255), outline=(*WHITE, 255), width=2)

    # Right: Radial crushing hull cross-section schematic
    hcx = x0 + int((x1 - x0) * 0.69)
    hcy = (top_y + bot_y) // 2
    pulse = math.sin(phase_t * math.tau * 2.5)
    hull_r = int(115 - 8 * eased + 3 * pulse)

    _draw_dashed_ellipse(draw, hcx, hcy, 195, 195, (*CORAL, 145), width=2, phase=phase_t)
    draw.ellipse([hcx - hull_r, hcy - hull_r, hcx + hull_r, hcy + hull_r], fill=(16, 28, 44, 210), outline=(*CYAN, 245), width=5)
    draw.ellipse([hcx - hull_r + 18, hcy - hull_r + 18, hcx + hull_r - 18, hcy + hull_r - 18], outline=(*CYAN, 110), width=2)

    # 8 inward crushing crimson force arrows pulsing inward
    for k in range(8):
        ang = k * (math.tau / 8.0) + phase_t * 0.15
        outer_r = 215 - 24 * ((phase_t * 1.6 + k * 0.12) % 1.0)
        inner_r = hull_r + 16
        p0 = (hcx + math.cos(ang) * outer_r, hcy + math.sin(ang) * outer_r)
        p1 = (hcx + math.cos(ang) * inner_r, hcy + math.sin(ang) * inner_r)
        _draw_arrow(draw, p0, p1, (*CORAL, 240), width=4, head_len=14)

    center_val = _roll_number(str(data.get("center_metric", "1,086 ATM")), anim_t)
    cf = _fit_font(draw, center_val, "headline", 44, hull_r * 2 - 28, 22)
    _draw_centered(draw, center_val, hcx, hcy - 22, cf, (*AMBER, 255))
    _draw_centered(draw, str(data.get("center_label", "FORCE")).upper()[:14], hcx, hcy + 26, mono_f, (*WHITE, 210))

    # Bottom dual gauges
    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(
        draw, x0 + 25, y1 - 125, bar_w, 16,
        str(data.get("metric_label", "PRESSURE")),
        _roll_number(str(data.get("metric_value", "1,086 ATM")), anim_t),
        0.92 * eased, CORAL,
    )
    _draw_meter_bar(
        draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16,
        str(data.get("sub_label", "SCALE RATIO")),
        _roll_number(str(data.get("sub_value", "10.9 KM")), anim_t),
        0.78 * eased, CYAN,
    )


def _render_orbital_relativity_sim(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Wireframe Earth/Planet + animated orbital track + gliding satellite/body + live telemetry."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, y0 + 335
    eased = _ease_out(anim_t)
    mono_f = _font("mono", 20)

    # Outer dashed orbital ellipse + glowing wireframe Earth at center
    orb_rx, orb_ry = 390, 210
    _draw_dashed_ellipse(draw, cx, cy, orb_rx, orb_ry, (*CYAN, 175), width=3, segments=48, phase=phase_t * 0.5)
    _draw_dashed_ellipse(draw, cx, cy, orb_rx * 0.68, orb_ry * 0.68, (*GRID_DIM, 140), width=2, segments=32)

    earth_r = 104
    draw.ellipse([cx - earth_r - 14, cy - earth_r - 14, cx + earth_r + 14, cy + earth_r + 14], fill=(*CYAN, 28))
    draw.ellipse([cx - earth_r, cy - earth_r, cx + earth_r, cy + earth_r], fill=(12, 26, 44, 235), outline=(*CYAN, 245), width=4)
    # Wireframe latitude/longitude arcs
    for rx_f in (0.35, 0.72):
        draw.ellipse([cx - int(earth_r * rx_f), cy - earth_r, cx + int(earth_r * rx_f), cy + earth_r], outline=(*CYAN, 95), width=2)
    for ry_f in (0.35, 0.72):
        draw.ellipse([cx - earth_r, cy - int(earth_r * ry_f), cx + earth_r, cy + int(earth_r * ry_f)], outline=(*CYAN, 95), width=2)
    _draw_centered(draw, _clean_lbl(str(data.get("planet_label", "EARTH")), 12), cx, cy - 12, _font("mono", 22), (*WHITE, 235))

    # Moving orbiting satellite / spacecraft / asteroid
    ang = -0.85 + phase_t * 1.45
    sx = cx + math.cos(ang) * orb_rx
    sy = cy + math.sin(ang) * orb_ry

    # Pulsing signal beam from orbiting body straight to Earth surface
    _draw_dashed_line(draw, (sx, sy), (cx, cy), (*AMBER, 200), width=3, dash=10, gap=8)
    pkt_t = (phase_t * 2.2) % 1.0
    px = sx + (cx - sx) * pkt_t
    py = sy + (cy - sy) * pkt_t
    draw.ellipse([px - 7, py - 7, px + 7, py + 7], fill=(*AMBER, 255))

    # Crisp vector satellite / body icon
    draw.rounded_rectangle([sx - 28, sy - 9, sx + 28, sy + 9], radius=4, fill=(*CYAN, 90), outline=(*CYAN, 250), width=2)
    draw.ellipse([sx - 12, sy - 12, sx + 12, sy + 12], fill=(*AMBER, 255), outline=(*WHITE, 255), width=2)
    sat_lbl = _clean_lbl(str(data.get("orbiter_label", "ORBITAL VECTOR")), 18)
    draw.text((int(sx) - 85, int(sy) - 42), sat_lbl, font=mono_f, fill=(*AMBER, 250))

    # Velocity / distance callout pill right under orbit
    badge_txt = _roll_number(str(data.get("callout", "20,200 KM ALTITUDE")), anim_t).upper()
    bf = _fit_font(draw, badge_txt, "headline", 36, (x1 - x0) - 120, 22)
    bb = draw.textbbox((0, 0), badge_txt, font=bf)
    bw = (bb[2] - bb[0]) + 56
    draw.rounded_rectangle([cx - bw // 2, cy + 236, cx + bw // 2, cy + 298], radius=14, fill=(*SURFACE, 230), outline=(*accent, 210), width=2)
    _draw_centered(draw, badge_txt, cx, cy + 248, bf, (*accent, 255))

    # Bottom dual telemetry bars
    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(
        draw, x0 + 25, y1 - 125, bar_w, 16,
        str(data.get("metric_label", "PRIMARY VELOCITY")),
        _roll_number(str(data.get("metric_value", "14,000 KM/H")), anim_t),
        0.86 * eased, CYAN,
    )
    _draw_meter_bar(
        draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16,
        str(data.get("sub_label", "NET DRIFT")),
        _roll_number(str(data.get("sub_value", "+38 µS/DAY")), anim_t),
        0.74 * eased, AMBER,
    )


def _draw_stage_strip(
    draw: ImageDraw.ImageDraw,
    x0: int,
    y0: int,
    width: int,
    stages: List[str],
    anim_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Draw a 3-box live engineering sequence checklist with crisp vector checkmarks."""
    n = min(3, max(2, len(stages)))
    gap = 46
    bw = (width - gap * (n - 1)) // n
    bh = 62
    f = _font("mono", 22)
    for i in range(n):
        bx = x0 + i * (bw + gap)
        done = anim_t >= (i * 0.34 + 0.15)
        is_last = i == n - 1
        show_check = done and not is_last
        col = MINT if show_check else (accent if done else MUTED)
        txt = _clean_lbl(str(stages[i]), 13)
        draw.rounded_rectangle(
            [bx, y0, bx + bw, y0 + bh],
            radius=10,
            fill=(col[0], col[1], col[2], 32 if done else 14),
            outline=(*col, 235 if done else 120),
            width=2,
        )
        tbb = draw.textbbox((0, 0), txt, font=f)
        tw = tbb[2] - tbb[0]
        if show_check:
            total_w = 24 + tw
            sx = bx + (bw - total_w) // 2
            _draw_check_icon(draw, sx + 8, y0 + bh // 2, (*col, 255))
            draw.text((sx + 24, y0 + 18 - tbb[1]), txt, font=f, fill=(*col, 255))
        else:
            _draw_centered(draw, txt, bx + bw // 2, y0 + 18, f, (*col, 255 if done else 160))
        if i + 1 < n:
            _draw_arrow(draw, (bx + bw + 6, y0 + bh // 2), (bx + bw + gap - 6, y0 + bh // 2), (*MUTED, 210), width=3, head_len=11)


def _render_signal_flow_pipeline(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """3-stage live checklist + glowing vector network conduit with racing laser/data packets."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, y0 + 380
    eased = _ease_out(anim_t)

    stages = data.get("stages") or ["ORIGIN", "CONDUIT", "DELIVERY"]
    _draw_stage_strip(draw, x0 + 20, y0 + 22, (x1 - x0) - 40, stages, anim_t, accent)

    # Schematic horizontal architecture conduit with 3 glowing technical nodes
    nodes = data.get("nodes") or [
        (str(data.get("metric_label", "NODE A")), str(data.get("metric_value", "99%"))),
        ("BOTTLENECK", str(data.get("callout", "17 MM"))),
        (str(data.get("sub_label", "OUTPUT")), str(data.get("sub_value", "$10T"))),
    ]
    n_xs = [x0 + 150, cx, x1 - 150]
    node_cols = [CYAN, CORAL, AMBER]

    # Dashed choke-point highlight ring around middle node
    _draw_dashed_ellipse(draw, cx, cy, 148, 148, (*CORAL, 165), width=3, phase=phase_t)

    # Conduit lines + multiple animated glowing signal packets racing across
    draw.line([(n_xs[0], cy), (n_xs[2], cy)], fill=(*CYAN, 110), width=10)
    draw.line([(n_xs[0], cy), (n_xs[2], cy)], fill=(*CYAN, 235), width=3)
    for k in range(5):
        t_pkt = (phase_t * 1.4 + k * 0.2) % 1.0
        px = n_xs[0] + (n_xs[2] - n_xs[0]) * t_pkt
        p_col = AMBER if t_pkt > 0.5 else CYAN
        draw.ellipse([px - 11, cy - 11, px + 11, cy + 11], fill=(*p_col, 255), outline=(*WHITE, 220), width=2)

    lbl_f = _font("mono", 20)
    for i, (nx, (nlbl, nval)) in enumerate(zip(n_xs, nodes[:3])):
        col = node_cols[i % 3]
        r = 82 if i == 1 else 74
        draw.ellipse([nx - r, cy - r, nx + r, cy + r], fill=(*SURFACE, 245), outline=(*col, 245), width=4)
        val_s = _roll_number(str(nval).upper(), anim_t)
        vf = _fit_font(draw, val_s, "headline", 34, r * 2 - 22, 18)
        _draw_centered(draw, val_s, nx, cy - 18, vf, (*col, 255))
        _draw_centered(draw, _clean_lbl(str(nlbl), 16), nx, cy + r + 18, lbl_f, (*WHITE, 220))

    # Bottom dual telemetry bars
    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(
        draw, x0 + 25, y1 - 125, bar_w, 16,
        str(data.get("metric_label", "THROUGHPUT")),
        _roll_number(str(data.get("metric_value", "99%")), anim_t),
        0.94 * eased, CYAN,
    )
    _draw_meter_bar(
        draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16,
        str(data.get("sub_label", "RISK MARGIN")),
        _roll_number(str(data.get("sub_value", "CRITICAL")), anim_t),
        0.72 * eased, CORAL,
    )


def _render_waveform_stability_meter(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Live animated oscilloscope waveform with critical threshold breach & dual telemetry meters."""
    x0, y0, x1, y1 = box
    eased = _ease_out(anim_t)
    mono_f = _font("mono", 20)

    # Calibrated oscilloscope viewport
    ox0, oy0, ox1, oy1 = x0 + 25, y0 + 35, x1 - 25, y1 - 220
    ocy = (oy0 + oy1) // 2
    draw.rounded_rectangle([ox0, oy0, ox1, oy1], radius=16, fill=(*SURFACE, 220), outline=(*GRID_DIM, 210), width=2)

    # Subtle internal oscilloscope grid
    for gx in range(ox0 + 70, ox1, 90):
        draw.line([(gx, oy0 + 12), (gx, oy1 - 12)], fill=(*GRID_DIM, 85), width=1)
    for gy in range(oy0 + 60, oy1, 70):
        draw.line([(ox0 + 12, gy), (ox1 - 12, gy)], fill=(*GRID_DIM, 85), width=1)

    # Red critical threshold dashed horizon
    thresh_y = oy0 + int((oy1 - oy0) * 0.24)
    _draw_dashed_line(draw, (ox0 + 18, thresh_y), (ox1 - 18, thresh_y), (*CORAL, 215), width=3, dash=14, gap=8)
    draw.text((ox0 + 28, thresh_y - 30), f"LIMIT // {str(data.get('callout', 'THRESHOLD')).upper()[:22]}", font=mono_f, fill=(*CORAL, 240))

    # Sweeping live waveform (cyan stable -> amber/coral spike on right!)
    pts: List[Tuple[float, float]] = []
    span_w = ox1 - ox0 - 40
    n_pts = 120
    amp_base = (oy1 - oy0) * 0.23
    for i in range(n_pts):
        u = i / float(n_pts - 1)
        px = ox0 + 20 + u * span_w
        spike = 1.0 + 0.65 * max(0.0, (u - 0.55) / 0.45) * eased
        y_off = math.sin(u * math.tau * 3.5 - phase_t * math.tau * 2.4) * amp_base * spike
        y_off += 0.18 * math.sin(u * math.tau * 9.0 + phase_t * math.tau * 3.0) * amp_base * eased
        py = max(oy0 + 22, min(oy1 - 22, ocy - y_off))
        pts.append((px, py))

    split_i = int(n_pts * 0.62)
    draw.line(pts[: split_i + 1], fill=(*CYAN, 245), width=5)
    draw.line(pts[split_i:], fill=(*CORAL, 255), width=6)
    # Glowing live scanner dot at waveform tip
    tip_x, tip_y = pts[-1]
    draw.ellipse([tip_x - 11, tip_y - 11, tip_x + 11, tip_y + 11], fill=(*AMBER, 255), outline=(*WHITE, 255), width=2)

    # Live readout badge inside top-right of scope
    hero_s = _roll_number(str(data.get("center_metric", data.get("metric_value", "50.0 HZ"))).upper(), anim_t)
    hf = _fit_font(draw, hero_s, "headline", 44, 340, 24)
    hbb = draw.textbbox((0, 0), hero_s, font=hf)
    draw.text((ox1 - 28 - (hbb[2] - hbb[0]), oy0 + 22), hero_s, font=hf, fill=(*AMBER, 255))

    # Bottom dual telemetry bars
    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(
        draw, x0 + 25, y1 - 125, bar_w, 16,
        str(data.get("metric_label", "SIGNAL PEAK")),
        _roll_number(str(data.get("metric_value", "100%")), anim_t),
        0.91 * eased, CORAL,
    )
    _draw_meter_bar(
        draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16,
        str(data.get("sub_label", "BUFFER")),
        _roll_number(str(data.get("sub_value", "< 2%")), anim_t),
        0.35 * eased, CYAN,
    )


def _render_exponential_scale_curve(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Calibrated coordinate blueprint comparing linear human intuition vs vertical reality spike."""
    x0, y0, x1, y1 = box
    eased = _ease_out(anim_t)
    mono_f = _font("mono", 20)

    gx0, gy0, gx1, gy1 = x0 + 55, y0 + 50, x1 - 45, y1 - 210
    draw.line([(gx0, gy0), (gx0, gy1)], fill=(*MUTED, 210), width=3)
    draw.line([(gx0, gy1), (gx1, gy1)], fill=(*MUTED, 210), width=3)

    # Dashed linear expectation line
    lin_end_y = gy1 - int((gy1 - gy0) * 0.24)
    _draw_dashed_line(draw, (gx0, gy1), (gx1, lin_end_y), (*MUTED, 175), width=3, dash=12, gap=8)
    draw.text((gx0 + 30, lin_end_y - 34), "HUMAN INTUITION (LINEAR)", font=mono_f, fill=(*MUTED, 210))

    # Exponential reality curve drawing live from left -> right
    max_u = max(0.08, eased)
    pts: List[Tuple[float, float]] = []
    n_pts = 90
    for i in range(n_pts + 1):
        u = (i / float(n_pts)) * max_u
        px = gx0 + u * (gx1 - gx0)
        py = gy1 - (u ** 3.6) * (gy1 - gy0 - 20)
        pts.append((px, py))

    if len(pts) >= 2:
        draw.line(pts, fill=(*AMBER, 255), width=7)
        tx, ty = pts[-1]
        pulse = 10 + int(5 * math.sin(phase_t * math.tau * 2.5))
        draw.ellipse([tx - pulse - 6, ty - pulse - 6, tx + pulse + 6, ty + pulse + 6], fill=(*AMBER, 65))
        draw.ellipse([tx - 11, ty - 11, tx + 11, ty + 11], fill=(*AMBER, 255), outline=(*WHITE, 255), width=3)

    # Big floating hero comparison callout top-left inside chart
    hero_val = _roll_number(str(data.get("metric_value", "1,000X")).upper(), anim_t)
    hf = _fit_font(draw, hero_val, "headline", 82, 460, 40)
    draw.text((gx0 + 34, gy0 + 18), hero_val, font=hf, fill=(*AMBER, 255))
    draw.text((gx0 + 36, gy0 + 116), str(data.get("metric_label", "ACTUAL SCALE")).upper()[:26], font=mono_f, fill=(*CYAN, 240))

    # Bottom dual comparison bars
    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(
        draw, x0 + 25, y1 - 125, bar_w, 16,
        str(data.get("left_label", "BASELINE")),
        _roll_number(str(data.get("left_value", "1X")), anim_t),
        0.18 * eased, CYAN,
    )
    _draw_meter_bar(
        draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16,
        str(data.get("right_label", "REALITY")),
        _roll_number(str(data.get("right_value", "1,000X")), anim_t),
        0.95 * eased, AMBER,
    )


def _render_proportional_volume_scale(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """3D isometric architectural wireframe cube + precision dimension calipers & reference scale."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, y0 + 350
    eased = _ease_out(anim_t)
    mono_f = _font("mono", 22)

    # Crisp 3D isometric glowing wireframe cube (left-center) + tiny/giant reference comparison
    s = int((145 + 32 * eased) * (1.0 + 0.015 * math.sin(phase_t * math.tau * 2)))
    iso_x = int(s * 0.86)
    iso_y = int(s * 0.44)

    # Cube vertices centered at (cx, cy)
    top_v = (cx, cy - s - iso_y)
    r_top = (cx + iso_x, cy - s)
    mid_v = (cx, cy - s + iso_y)
    l_top = (cx - iso_x, cy - s)
    r_bot = (cx + iso_x, cy + iso_y)
    bot_v = (cx, cy + iso_y * 2)
    l_bot = (cx - iso_x, cy + iso_y)

    # Subtle filled translucent faces + crisp luminous wireframe edges
    draw.polygon([top_v, r_top, mid_v, l_top], fill=(accent[0], accent[1], accent[2], 58), outline=(*accent, 250))
    draw.polygon([l_top, mid_v, bot_v, l_bot], fill=(accent[0], accent[1], accent[2], 32), outline=(*accent, 215))
    draw.polygon([mid_v, r_top, r_bot, bot_v], fill=(accent[0], accent[1], accent[2], 20), outline=(*accent, 190))
    for edge in [(top_v, r_top), (r_top, mid_v), (mid_v, l_top), (l_top, top_v), (l_top, l_bot), (mid_v, bot_v), (r_top, r_bot), (l_bot, bot_v), (bot_v, r_bot)]:
        draw.line(edge, fill=(*accent, 245), width=3)

    # Architectural dimension caliper line below cube
    dim_y = bot_y = bot_v[1] + 42
    _draw_arrow(draw, (cx, dim_y), (cx - iso_x, dim_y), (*CYAN, 235), width=3, head_len=12)
    _draw_arrow(draw, (cx, dim_y), (cx + iso_x, dim_y), (*CYAN, 235), width=3, head_len=12)
    dim_txt = _roll_number(str(data.get("callout", data.get("metric_value", "22 METERS"))).upper(), anim_t)
    df = _fit_font(draw, dim_txt, "headline", 42, 460, 24)
    _draw_centered(draw, dim_txt, cx, bot_y + 18, df, (*WHITE, 255))
    _draw_centered(draw, str(data.get("metric_label", "TOTAL PHYSICAL VOLUME")).upper()[:28], cx, bot_y + 72, mono_f, (*CYAN, 230))

    # Bottom comparison bars
    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(
        draw, x0 + 25, y1 - 125, bar_w, 16,
        str(data.get("left_label", "VOLUME")),
        _roll_number(str(data.get("left_value", "22 M")), anim_t),
        0.55 * eased, CYAN,
    )
    _draw_meter_bar(
        draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16,
        str(data.get("right_label", "TOTAL VALUE")),
        _roll_number(str(data.get("right_value", "$16T")), anim_t),
        0.92 * eased, AMBER,
    )


def _render_step_sequence_blueprint(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """3-stage live checklist + central glowing focal schematic dial with key metric & annotations."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, y0 + 390
    eased = _ease_out(anim_t)
    mono_f = _font("mono", 21)

    stages = data.get("stages") or ["DETECT", "MEASURE", "VERIFY"]
    _draw_stage_strip(draw, x0 + 20, y0 + 24, (x1 - x0) - 40, stages, anim_t, accent)

    # Central precision targeting dial + animated orbital ticks
    r_out = 185
    r_in = 132
    _draw_dashed_ellipse(draw, cx, cy, r_out + 24, r_out + 24, (*CYAN, 150), width=2, segments=40, phase=phase_t)
    draw.ellipse([cx - r_out, cy - r_out, cx + r_out, cy + r_out], outline=(*GRID_DIM, 220), width=3)
    # Active animated progress arc
    sweep_deg = int(290 * eased)
    draw.arc([cx - r_out, cy - r_out, cx + r_out, cy + r_out], start=-90, end=-90 + sweep_deg, fill=(*accent, 255), width=8)
    draw.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], fill=(*SURFACE, 235), outline=(*CYAN, 165), width=2)

    # Rotating scanner ticks
    ang = phase_t * math.tau
    tx = cx + math.cos(ang) * r_out
    ty = cy + math.sin(ang) * r_out
    draw.ellipse([tx - 8, ty - 8, tx + 8, ty + 8], fill=(*CYAN, 255))

    hero = _roll_number(str(data.get("metric_value", "100%")).upper(), anim_t)
    hf = _fit_font(draw, hero, "headline", 64, r_in * 2 - 28, 28)
    _draw_centered(draw, hero, cx, cy - 36, hf, (*accent, 255))
    _draw_centered(draw, str(data.get("metric_label", "CORE FACTOR")).upper()[:18], cx, cy + 38, mono_f, (*WHITE, 225))

    # Bottom dual telemetry bars
    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(
        draw, x0 + 25, y1 - 125, bar_w, 16,
        str(data.get("left_label", "BASELINE")),
        _roll_number(str(data.get("left_value", "NORMAL")), anim_t),
        0.48 * eased, CYAN,
    )
    _draw_meter_bar(
        draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16,
        str(data.get("right_label", "EXTREME")),
        _roll_number(str(data.get("right_value", "PEAK")), anim_t),
        0.92 * eased, accent,
    )


def _render_split_blueprint_duel(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Clean hairline blueprint head-to-head split (zero heavy dark dashboard boxes)."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2 - 15
    eased = _ease_out(anim_t)
    mono_f = _font("mono", 22)

    # Central hairline axis + VS diamond
    draw.line([(cx, y0 + 55), (cx, y1 - 135)], fill=(*GRID_DIM, 210), width=2)
    _draw_diamond(draw, cx, cy, 34, (*SURFACE, 255), (*AMBER, 245), width=3)
    _draw_centered(draw, "VS", cx, cy - 14, _font("headline", 28), (*AMBER, 255))

    l_cx = x0 + (cx - x0) // 2
    r_cx = cx + (x1 - cx) // 2

    l_lbl = str(data.get("left_label", "BASELINE")).upper()[:18]
    r_lbl = str(data.get("right_label", "EXTREME")).upper()[:18]
    l_val = _roll_number(str(data.get("left_value", "11.5 DAYS")).upper(), anim_t)
    r_val = _roll_number(str(data.get("right_value", "31.7 YRS")).upper(), anim_t)

    # Left Blueprint Column (Cyan)
    _draw_centered(draw, l_lbl, l_cx, y0 + 75, mono_f, (*CYAN, 235))
    lf = _fit_font(draw, l_val, "headline", 64, (cx - x0) - 56, 28)
    _draw_centered(draw, l_val, l_cx, cy - 42, lf, (*WHITE, 255))
    # Subtle animated gauge bar under left value
    gw = (cx - x0) - 96
    draw.rounded_rectangle([l_cx - gw // 2, cy + 70, l_cx + gw // 2, cy + 88], radius=9, fill=(*SURFACE, 230), outline=(*GRID_DIM, 180))
    draw.rounded_rectangle([l_cx - gw // 2, cy + 70, l_cx - gw // 2 + max(18, int(gw * 0.34 * eased)), cy + 88], radius=9, fill=(*CYAN, 240))

    # Right Blueprint Column (Amber/Coral)
    _draw_centered(draw, r_lbl, r_cx, y0 + 75, mono_f, (*accent, 245))
    rf = _fit_font(draw, r_val, "headline", 64, (x1 - cx) - 56, 28)
    _draw_centered(draw, r_val, r_cx, cy - 42, rf, (*accent, 255))
    draw.rounded_rectangle([r_cx - gw // 2, cy + 70, r_cx + gw // 2, cy + 88], radius=9, fill=(*SURFACE, 230), outline=(*GRID_DIM, 180))
    draw.rounded_rectangle([r_cx - gw // 2, cy + 70, r_cx - gw // 2 + max(18, int(gw * 0.94 * eased)), cy + 88], radius=9, fill=(*accent, 245))

    # Bottom ratio callout strip
    ratio_s = str(data.get("callout", "VERIFIED SCALE GAP")).upper()[:34]
    rbf = _fit_font(draw, ratio_s, "headline", 34, (x1 - x0) - 100, 22)
    rbb = draw.textbbox((0, 0), ratio_s, font=rbf)
    rw = (rbb[2] - rbb[0]) + 64
    draw.rounded_rectangle([cx - rw // 2, y1 - 105, cx + rw // 2, y1 - 42], radius=14, fill=(accent[0], accent[1], accent[2], 32), outline=(*accent, 220), width=2)
    _draw_centered(draw, ratio_s, cx, y1 - 92, rbf, (*WHITE, 255))


def _render_verdict_poll_blueprint(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Clean V6 closing blueprint poll card matching the exact editorial aesthetic."""
    x0, y0, x1, y1 = box
    cx = (x0 + x1) // 2
    eased = _ease_out(anim_t)
    pulse = 0.5 + 0.5 * math.sin(phase_t * math.tau * 2.5)

    q_txt = str(data.get("question", "WHICH SIDE ARE YOU ON?")).upper()
    opt_a = str(data.get("option_a", "OPTION A")).upper()[:18]
    opt_b = str(data.get("option_b", "OPTION B")).upper()[:18]

    # Clean bordered blueprint container
    draw.rounded_rectangle(
        [x0 + 18, y0 + 55, x1 - 18, y1 - 65],
        radius=22,
        fill=(*SURFACE, 210),
        outline=(*CYAN, int(130 + 60 * pulse)),
        width=2,
    )

    _draw_centered(draw, "OPEN VERDICT // YOUR CALL", cx, y0 + 98, _font("mono", 23), (*AMBER, 240))
    qf = _font("headline", 52 if len(q_txt) <= 44 else 44)
    q_bot = _draw_centered(draw, q_txt, cx, y0 + 162, qf, (*WHITE, 255), max_width=(x1 - x0) - 130)

    # Two refined architectural option buttons
    btn_y = max(q_bot + 56, y0 + 340)
    btn_h = 112
    btn_w = ((x1 - x0) - 140) // 2
    bx_a = x0 + 52
    bx_b = cx + 18

    draw.rounded_rectangle(
        [bx_a, btn_y, bx_a + btn_w, btn_y + btn_h],
        radius=16,
        fill=(CYAN[0], CYAN[1], CYAN[2], int(34 * eased)),
        outline=(*CYAN, 235),
        width=3,
    )
    af = _fit_font(draw, opt_a, "headline", 36, btn_w - 32, 22)
    _draw_centered(draw, opt_a, bx_a + btn_w // 2, btn_y + 36, af, (*CYAN, 255))

    draw.rounded_rectangle(
        [bx_b, btn_y, bx_b + btn_w, btn_y + btn_h],
        radius=16,
        fill=(AMBER[0], AMBER[1], AMBER[2], int(34 * eased)),
        outline=(*AMBER, 235),
        width=3,
    )
    bf = _fit_font(draw, opt_b, "headline", 36, btn_w - 32, 22)
    _draw_centered(draw, opt_b, bx_b + btn_w // 2, btn_y + 36, bf, (*AMBER, 255))

    # Quiet editorial community footer
    sub_y = btn_y + btn_h + 62
    _draw_centered(draw, "COMMENT YOUR PICK BELOW", cx, sub_y, _font("mono", 24), (*WHITE, 230))
    _draw_centered(draw, "+ SUBSCRIBE TO @VELUMDISPATCH", cx, sub_y + 42, _font("mono", 22), (*AMBER, int(200 + 55 * pulse)))


_RENDERERS = {
    "layered_cutaway": _render_layered_cutaway,
    "depth_pressure_cutaway": _render_depth_pressure_cutaway,
    "orbital_relativity_sim": _render_orbital_relativity_sim,
    "signal_flow_pipeline": _render_signal_flow_pipeline,
    "waveform_stability_meter": _render_waveform_stability_meter,
    "exponential_scale_curve": _render_exponential_scale_curve,
    "proportional_volume_scale": _render_proportional_volume_scale,
    "step_sequence_blueprint": _render_step_sequence_blueprint,
    "split_blueprint_duel": _render_split_blueprint_duel,
    "verdict_poll_blueprint": _render_verdict_poll_blueprint,
}


def render_v6_schematic_frame(
    schematic_mode: str,
    schematic_data: Dict[str, Any],
    size: Tuple[int, int] = (1080, 1920),
    anim_t: float = 1.0,
    phase_t: float = 0.0,
    chapter_num: int = 1,
    total_chapters: int = 6,
    chapter_tag: str = "THE MECHANISM",
    headline_line1: str = "HIDDEN SCALE",
    headline_line2: str = "EXPOSED BY PHYSICS",
    accent_word: str = "",
    episode_num: int = 1,
    source_credit: str = "VELUM RESEARCH",
) -> Image.Image:
    """Render one crisp RGB frame of a VELUM V6/V7 2D technical schematic animation."""
    ctx = prepare_v6_chapter_context(
        schematic_mode=schematic_mode,
        schematic_data=schematic_data,
        size=size,
        chapter_num=chapter_num,
        total_chapters=total_chapters,
        chapter_tag=chapter_tag,
        headline_line1=headline_line1,
        headline_line2=headline_line2,
        accent_word=accent_word,
        episode_num=episode_num,
        source_credit=source_credit,
    )
    return _draw_v6_dynamic_frame(ctx=ctx, anim_t=anim_t, phase_t=phase_t)
