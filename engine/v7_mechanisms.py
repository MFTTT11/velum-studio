"""VELUM V7 — Bespoke Physically-Animated 2D CAD/Vector Mechanism Renderers.

Ten unmistakable, physically-moving engineering & physics silhouettes built in pure Python
(Pillow + NumPy, zero paid AI video APIs, zero external stock mismatches):
1. mech_elevator_brake  (snapping cable, spinning governor, steel wedges slamming onto rails)
2. mech_sr71_blackbird  (SR-71 wireframe, runway fuel drips -> Mach 3.2 315C sealed panels)
3. mech_train_wheel_cone(tapered conical wheels on I-beam rails self-steering on a curve)
4. mech_airplane_window (3-pane fuselage window, 1.5mm bleed hole, outer crack vs middle shield)
5. mech_volcano_eruption(crater cutaway, falling bundle piercing lava crust -> steam eruption)
6. mech_bridge_teeth    (interlocking steel expansion fingers closing as deck heats -10C->+45C)
7. mech_nuclear_sub     (submarine CAD profile: 25yr reactor, O2 electrolysis, 90-day food limit)
8. mech_diver_oxygen    (scuba diver descending past 6m O2 toxicity barrier + 1.6 ATM alarm)
9. mech_cargo_ship      (container ship hull cutaway in waves: hollow air volume vs buoyancy)
10. mech_spacesuit_layers(astronaut CAD torso in vacuum + magnified 14-layer restraint mesh)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from PIL import ImageDraw

from engine.schematic_engine import (
    AMBER,
    BG_TOP,
    CORAL,
    CYAN,
    GRID_DIM,
    MINT,
    MUTED,
    SURFACE,
    WHITE,
    _clean_lbl,
    _draw_arrow,
    _draw_centered,
    _draw_dashed_ellipse,
    _draw_dashed_line,
    _draw_meter_bar,
    _draw_stage_strip,
    _ease_out,
    _fit_font,
    _font,
    _roll_number,
)


def _mech_elevator_brake(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Elevator cab in shaft, snapping cable, overspeed governor wheel, wedge brakes clamping rails."""
    x0, y0, x1, y1 = box
    cx = (x0 + x1) // 2
    eased = _ease_out(anim_t)
    mono = _font("mono", 20)

    stages = data.get("stages") or ["CABLE SNAP", "GOVERNOR", "WEDGE LOCK"]
    _draw_stage_strip(draw, x0 + 20, y0 + 14, (x1 - x0) - 40, stages, anim_t, accent)

    shaft_top = y0 + 108
    shaft_bot = y1 - 165
    rail_l = cx - 155
    rail_r = cx + 155

    # Twin steel guide rails + wall brackets
    for rx in (rail_l, rail_r):
        draw.rectangle([rx - 10, shaft_top, rx + 10, shaft_bot], fill=(24, 38, 56, 235), outline=(*CYAN, 185), width=2)
        for by in range(shaft_top + 28, shaft_bot - 16, 68):
            side = -24 if rx == rail_l else 24
            draw.line([(rx, by), (rx + side, by)], fill=(*GRID_DIM, 220), width=4)

    # Overhead governor pulley wheel (turns crimson when overspeed triggers)
    pulley_y = shaft_top + 38
    pulley_r = 34
    overspeed = phase_t > 0.32
    p_col = CORAL if overspeed else CYAN
    draw.ellipse([cx - pulley_r, pulley_y - pulley_r, cx + pulley_r, pulley_y + pulley_r], fill=(*SURFACE, 240), outline=(*p_col, 245), width=4)
    for sp in range(6):
        ang = sp * (math.tau / 6.0) + phase_t * (14.0 if overspeed else 4.0)
        draw.line([(cx, pulley_y), (cx + math.cos(ang) * (pulley_r - 4), pulley_y + math.sin(ang) * (pulley_r - 4))], fill=(*p_col, 210), width=2)
    draw.text((rail_r + 22, pulley_y - 14), "GOVERNOR WHEEL", font=mono, fill=(*p_col, 240))

    # Elevator cab drops briefly during 0.25..0.52 then locks HARD at locked_y!
    drop_t = min(1.0, max(0.0, (phase_t - 0.18) / 0.34))
    locked = phase_t >= 0.52
    cab_y = int(shaft_top + 135 + 88 * _ease_out(drop_t))
    cab_w, cab_h = 230, 210
    cab_l, cab_r = cx - cab_w // 2, cx + cab_w // 2

    # Steel hoist cable (intact before 0.20, physically snapped with sparks after!)
    if phase_t < 0.20:
        draw.line([(cx, pulley_y + pulley_r), (cx, cab_y)], fill=(*WHITE, 220), width=4)
    else:
        snap_y = pulley_y + pulley_r + 36
        draw.line([(cx, pulley_y + pulley_r), (cx - 12, snap_y)], fill=(*CORAL, 235), width=4)
        draw.line([(cx + 14, snap_y + 30), (cx, cab_y)], fill=(*CORAL, 210), width=4)
        # Snap spark burst
        for k in range(6):
            sa = k * (math.tau / 6.0) + phase_t * 6.0
            sr = 12 + int(16 * ((phase_t * 3.0) % 1.0))
            draw.line([(cx, snap_y + 14), (cx + math.cos(sa) * sr, snap_y + 14 + math.sin(sa) * sr)], fill=(*AMBER, 245), width=3)
        draw.text((cx + 28, snap_y - 2), "CABLE SEVERED", font=mono, fill=(*CORAL, 250))

    # Detailed elevator cab wireframe + split doors + glowing safety frame
    cab_col = MINT if locked else CYAN
    draw.rounded_rectangle([cab_l, cab_y, cab_r, cab_y + cab_h], radius=12, fill=(14, 26, 42, 240), outline=(*cab_col, 245), width=4)
    # Interior door seam & glass window
    draw.rectangle([cab_l + 24, cab_y + 24, cab_r - 24, cab_y + cab_h - 14], outline=(*cab_col, 150), width=2)
    draw.line([(cx, cab_y + 24), (cx, cab_y + cab_h - 14)], fill=(*cab_col, 195), width=2)
    # Floor indicator LED inside cab
    draw.rounded_rectangle([cx - 46, cab_y + 38, cx + 46, cab_y + 68], radius=6, fill=(*SURFACE, 255), outline=(*AMBER, 220), width=2)
    _draw_centered(draw, "LOCKED" if locked else "FALL!", cx, cab_y + 44, _font("mono", 18), (*(MINT if locked else CORAL), 255))

    # Spring-loaded triangular steel wedge clamps underneath cab slamming into rails!
    clamp_t = _ease_out(min(1.0, max(0.0, (phase_t - 0.38) / 0.22)))
    wedge_y = cab_y + cab_h - 24
    for side in (-1, 1):
        wx_inner = cx + side * int(cab_w // 2 - 22 + clamp_t * 28)
        wx_rail = rail_l + 11 if side == -1 else rail_r - 11
        w_col = MINT if locked else AMBER
        pts = [
            (wx_inner, wedge_y - 18),
            (wx_rail if locked else (wx_inner + side * 20), wedge_y + 24),
            (wx_inner, wedge_y + 32),
        ]
        draw.polygon(pts, fill=(w_col[0], w_col[1], w_col[2], 145), outline=(*w_col, 255))
        if locked:
            # Clamp engagement glow sparks
            _draw_dashed_ellipse(draw, wx_rail, wedge_y + 18, 28, 28, (*MINT, 210), width=2, segments=12, phase=phase_t)

    # Callout annotation pointing right at wedge brake
    if locked:
        _draw_arrow(draw, (x1 - 36, wedge_y + 10), (rail_r + 22, wedge_y + 14), (*MINT, 240), width=3, head_len=12)
        draw.text((rail_r + 36, wedge_y - 26), "STEEL WEDGES", font=mono, fill=(*MINT, 250))
        draw.text((rail_r + 36, wedge_y - 2), "CLAMP RAIL", font=mono, fill=(*WHITE, 225))
    else:
        _draw_arrow(draw, (cx, cab_y + cab_h + 10), (cx, cab_y + cab_h + 52), (*CORAL, 235), width=4, head_len=14)

    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(draw, x0 + 25, y1 - 125, bar_w, 16, str(data.get("metric_label", "CABLE SAFETY")), _roll_number(str(data.get("metric_value", "8X RATED")), anim_t), 0.92 * eased, CYAN)
    _draw_meter_bar(draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16, str(data.get("sub_label", "BRAKE STOP")), _roll_number(str(data.get("sub_value", "0.12 SEC")), anim_t), (0.96 if locked else 0.45) * eased, MINT if locked else AMBER)


def _mech_sr71_blackbird(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Unmistakable SR-71 Blackbird CAD wireframe: cold fuel drips -> Mach 3.2 315C sealed panels."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, y0 + 375
    eased = _ease_out(anim_t)
    mono = _font("mono", 20)

    stages = data.get("stages") or ["COLD GAP", "MACH 3.2", "HEAT SEAL"]
    _draw_stage_strip(draw, x0 + 20, y0 + 14, (x1 - x0) - 40, stages, anim_t, accent)

    hot_phase = phase_t > 0.48
    skin_col = CORAL if hot_phase else CYAN

    # Supersonic Mach shock cone V-lines streaming from needle nose (x=cx, y=cy-240)
    nose_y = cy - 235
    if hot_phase:
        for k in range(3):
            spread = 230 + k * 55
            alpha = 180 - k * 45
            _draw_dashed_line(draw, (cx, nose_y - 18), (cx - spread, cy + 210), (*AMBER, alpha), width=3, dash=16, gap=10)
            _draw_dashed_line(draw, (cx, nose_y - 18), (cx + spread, cy + 210), (*AMBER, alpha), width=3, dash=16, gap=10)

    # Top-down SR-71 Blackbird CAD silhouette polygon (symmetric blended chine + delta wings)
    right_half = [
        (0, -235), (14, -185), (34, -135), (42, -75), (34, -20),
        (78, 35), (185, 130), (225, 175), (185, 195), (122, 180),
        (108, 205), (72, 205), (60, 170), (24, 185), (14, 215), (0, 215),
    ]
    poly = [(cx + dx, cy + dy) for dx, dy in right_half] + [(cx - dx, cy + dy) for dx, dy in reversed(right_half[:-1])]
    fill_a = 65 if hot_phase else 42
    draw.polygon(poly, fill=(skin_col[0], skin_col[1], skin_col[2], fill_a), outline=(*skin_col, 250))
    draw.line(poly + [poly[0]], fill=(*skin_col, 250), width=3)

    # Twin J58 cylindrical engine nacelles + intake spikes
    for side in (-1, 1):
        nx = cx + side * 90
        draw.rounded_rectangle([nx - 22, cy + 12, nx + 22, cy + 198], radius=10, fill=(*SURFACE, 240), outline=(*skin_col, 245), width=3)
        # Intake spike cone
        draw.polygon([(nx, cy - 24), (nx - 14, cy + 14), (nx + 14, cy + 14)], fill=(*AMBER, 220))
        # Afterburner shock diamonds during Mach 3.2
        if hot_phase:
            flame_len = 52 + int(18 * math.sin(phase_t * 28.0))
            draw.polygon([(nx - 15, cy + 198), (nx + 15, cy + 198), (nx, cy + 198 + flame_len)], fill=(*AMBER, 225))
            draw.polygon([(nx - 8, cy + 198), (nx + 8, cy + 198), (nx, cy + 198 + int(flame_len * 0.65))], fill=(*WHITE, 240))

    # Glowing cockpit canopy
    draw.polygon([(cx, cy - 165), (cx + 14, cy - 125), (cx, cy - 96), (cx - 14, cy - 125)], fill=(*CYAN, 180), outline=(*WHITE, 230))

    # Animated titanium skin expansion seams (open & dripping fuel cold -> sealed tight hot!)
    gap_w = 2 if hot_phase else 7
    for seam_y in (cy + 58, cy + 115):
        draw.line([(cx - 125, seam_y), (cx + 125, seam_y)], fill=(*(MINT if hot_phase else AMBER), 240), width=gap_w)

    if not hot_phase:
        # Dripping JP-7 amber fuel droplets falling off wing joints
        for d in range(5):
            drop_t = (phase_t * 2.4 + d * 0.2) % 1.0
            dx = cx - 120 + d * 60
            dy = cy + 125 + drop_t * 105
            draw.ellipse([dx - 5, dy - 7, dx + 5, dy + 7], fill=(*AMBER, int(255 * (1.0 - drop_t))))
        _draw_centered(draw, "COLD RUNWAY // TITANIUM GAPS OPEN", cx, cy + 235, mono, (*AMBER, 245))
    else:
        _draw_centered(draw, "MACH 3.2 // 315°C THERMAL SEAL LOCKED", cx, cy + 276, mono, (*MINT, 250))

    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(draw, x0 + 25, y1 - 125, bar_w, 16, str(data.get("metric_label", "TOP SPEED")), _roll_number(str(data.get("metric_value", "MACH 3.2")), anim_t), (0.95 if hot_phase else 0.12) * eased, AMBER)
    _draw_meter_bar(draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16, str(data.get("sub_label", "SKIN TEMP")), _roll_number(str(data.get("sub_value", "315 °C")), anim_t), (0.92 if hot_phase else 0.15) * eased, CORAL if hot_phase else CYAN)


def _mech_train_wheel_cone(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Front cross-section of tapered conical train wheels on steel I-beam rails self-steering."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, y0 + 380
    eased = _ease_out(anim_t)
    mono = _font("mono", 20)

    stages = data.get("stages") or ["CURVE SHIFT", "CONE RADIUS", "AUTO-CENTER"]
    _draw_stage_strip(draw, x0 + 20, y0 + 14, (x1 - x0) - 40, stages, anim_t, accent)

    # Wooden/concrete sleeper beam & twin steel I-beam rails
    rail_y = cy + 120
    draw.rectangle([x0 + 65, rail_y + 52, x1 - 65, rail_y + 82], fill=(20, 32, 48, 220), outline=(*GRID_DIM, 200), width=2)
    rail_lx, rail_rx = cx - 220, cx + 220
    for rx in (rail_lx, rail_rx):
        # I-beam rail profile
        draw.rectangle([rx - 26, rail_y, rx + 26, rail_y + 14], fill=(*MUTED, 230), outline=(*WHITE, 210), width=2)
        draw.rectangle([rx - 10, rail_y + 14, rx + 10, rail_y + 42], fill=(*MUTED, 200))
        draw.rectangle([rx - 30, rail_y + 42, rx + 30, rail_y + 52], fill=(*MUTED, 230))

    # Oscillating lateral curve shift (wheelset slides right -> larger cone radius contacts right rail!)
    shift_x = int(34 * math.sin(phase_t * math.tau * 1.2) * eased)
    axle_y = cy + 12

    # Solid rigid steel axle connecting both wheels
    draw.rectangle([rail_lx - 85 + shift_x, axle_y - 16, rail_rx + 85 + shift_x, axle_y + 16], fill=(*SURFACE, 245), outline=(*CYAN, 235), width=3)

    # Left & Right CONICAL tapered wheels (visibly wider inner radius, smaller outer radius!)
    for side, base_rx in ((-1, rail_lx), (1, rail_rx)):
        wx = base_rx + shift_x
        col = AMBER if (side == 1 and shift_x > 8) or (side == -1 and shift_x < -8) else CYAN
        if side == -1:
            # Left wheel: flange on right (inside), cone tapers downward toward outside-left
            pts = [(wx + 52, axle_y - 122), (wx + 36, axle_y - 122), (wx - 58, axle_y - 82), (wx - 58, axle_y + 82), (wx + 36, axle_y + 114), (wx + 52, axle_y + 114)]
        else:
            # Right wheel: flange on left (inside), cone tapers downward toward outside-right
            pts = [(wx - 52, axle_y - 122), (wx - 36, axle_y - 122), (wx + 58, axle_y - 82), (wx + 58, axle_y + 82), (wx - 36, axle_y + 114), (wx - 52, axle_y + 114)]
        draw.polygon(pts, fill=(col[0], col[1], col[2], 62), outline=(*col, 250))
        draw.line(pts + [pts[0]], fill=(*col, 250), width=4)
        # Contact highlight dot on rail top
        draw.ellipse([base_rx - 10, rail_y - 10, base_rx + 10, rail_y + 10], fill=(*col, 255), outline=(*WHITE, 255), width=2)

    # Dynamic radius callouts showing R_OUTER > R_INNER
    _draw_centered(draw, "RIGID SOLID AXLE (NO STEERING WHEEL)", cx, axle_y - 54, mono, (*WHITE, 230))
    lbl_l = "SMALL RADIUS" if shift_x >= 0 else "LARGE RADIUS (FASTER)"
    lbl_r = "LARGE RADIUS (FASTER)" if shift_x >= 0 else "SMALL RADIUS"
    _draw_centered(draw, lbl_l, rail_lx, rail_y + 100, mono, (*(AMBER if shift_x < 0 else CYAN), 245))
    _draw_centered(draw, lbl_r, rail_rx, rail_y + 100, mono, (*(AMBER if shift_x >= 0 else CYAN), 245))

    # Self-steering corrective vector arrow above axle
    if abs(shift_x) > 5:
        _draw_arrow(draw, (cx + shift_x * 2, axle_y - 95), (cx - shift_x * 2, axle_y - 95), (*MINT, 245), width=5, head_len=16)
        _draw_centered(draw, "SELF-STEERING FORCE", cx, axle_y - 130, mono, (*MINT, 250))

    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(draw, x0 + 25, y1 - 125, bar_w, 16, str(data.get("metric_label", "CONE SLOPE")), _roll_number(str(data.get("metric_value", "1 : 20")), anim_t), 0.78 * eased, CYAN)
    _draw_meter_bar(draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16, str(data.get("sub_label", "TURNING SYSTEM")), _roll_number(str(data.get("sub_value", "PURE GEOMETRY")), anim_t), 0.94 * eased, AMBER)


def _mech_airplane_window(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Curved aircraft fuselage window cutaway: 3 panes, 1.5mm bleed hole, outer crack vs middle shield."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, y0 + 385
    eased = _ease_out(anim_t)
    mono = _font("mono", 20)

    stages = data.get("stages") or ["CABIN AIR", "1.5MM VALVE", "FAIL-SAFE"]
    _draw_stage_strip(draw, x0 + 20, y0 + 14, (x1 - x0) - 40, stages, anim_t, accent)

    crack_phase = phase_t > 0.52
    top_y, bot_y = y0 + 145, y1 - 210
    p_outer, p_mid, p_inner = cx - 195, cx, cx + 195

    # Curved aircraft fuselage wall caps top & bottom
    for cap_y in (top_y - 26, bot_y):
        draw.rounded_rectangle([p_outer - 50, cap_y, p_inner + 50, cap_y + 26], radius=8, fill=(28, 42, 62, 235), outline=(*MUTED, 185), width=2)

    # Labels left (OUTSIDE -56C) and right (CABIN 1 ATM)
    draw.text((x0 + 24, cy - 35), "OUTSIDE", font=mono, fill=(*CORAL, 240))
    draw.text((x0 + 24, cy - 8), "-56°C", font=_font("headline", 28), fill=(*CORAL, 255))
    draw.text((x1 - 145, cy - 35), "CABIN", font=mono, fill=(*CYAN, 240))
    draw.text((x1 - 145, cy - 8), "PRESSURE", font=mono, fill=(*WHITE, 220))

    # Pane 1 (Outer thick structural acrylic) — flashes crack lines during fail-safe test!
    o_col = CORAL if crack_phase else AMBER
    draw.rounded_rectangle([p_outer - 22, top_y, p_outer + 22, bot_y], radius=8, fill=(o_col[0], o_col[1], o_col[2], 62), outline=(*o_col, 250), width=4)
    if crack_phase:
        draw.line([(p_outer - 20, cy - 55), (p_outer + 12, cy - 15), (p_outer - 14, cy + 25), (p_outer + 20, cy + 65)], fill=(*WHITE, 250), width=4)
        _draw_centered(draw, "OUTER CRACKED", p_outer, bot_y + 34, mono, (*CORAL, 255))
    else:
        _draw_centered(draw, "OUTER PANE", p_outer, bot_y + 34, mono, (*AMBER, 240))

    # Pane 2 (Middle emergency fail-safe shield WITH glowing 1.5mm bleed hole!)
    m_col = MINT if crack_phase else CYAN
    draw.rounded_rectangle([p_mid - 16, top_y, p_mid + 16, bot_y], radius=6, fill=(m_col[0], m_col[1], m_col[2], 58), outline=(*m_col, 250), width=4)
    hole_y = bot_y - 68
    draw.rectangle([p_mid - 18, hole_y - 9, p_mid + 18, hole_y + 9], fill=(*BG_TOP, 255))
    hr = 16 + int(5 * math.sin(phase_t * math.tau * 3))
    draw.ellipse([p_mid - hr, hole_y - hr, p_mid + hr, hole_y + hr], outline=(*AMBER, 250), width=3)
    _draw_centered(draw, "1.5MM BLEED HOLE", p_mid, bot_y + 34, mono, (*AMBER, 255))

    # Pane 3 (Inner thin passenger scratch guard)
    draw.rounded_rectangle([p_inner - 9, top_y, p_inner + 9, bot_y], radius=4, fill=(*MUTED, 55), outline=(*MUTED, 215), width=2)
    _draw_centered(draw, "SCRATCH GUARD", p_inner, bot_y + 34, mono, (*MUTED, 225))

    # Animated cabin air pressure arrows routing right -> left through bleed hole onto outer pane!
    for k in range(3):
        t_flow = (phase_t * 1.5 + k * 0.33) % 1.0
        fx = p_inner - 24 - t_flow * (p_inner - p_outer - 75)
        fy = hole_y if abs(fx - p_mid) < 60 else (cy - 30 + k * 35)
        _draw_arrow(draw, (fx + 42, fy), (fx, fy), (*CYAN, 235), width=3, head_len=11)

    if crack_phase:
        _draw_centered(draw, "MIDDLE SHIELD HOLDS 100% PRESSURE", cx, top_y - 54, mono, (*MINT, 255))

    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(draw, x0 + 25, y1 - 125, bar_w, 16, str(data.get("metric_label", "BLEED HOLE")), _roll_number(str(data.get("metric_value", "1.5 MM")), anim_t), 0.85 * eased, AMBER)
    _draw_meter_bar(draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16, str(data.get("sub_label", "FAIL-SAFE")), _roll_number(str(data.get("sub_value", "3 PANES")), anim_t), 0.96 * eased, MINT)


def _mech_volcano_eruption(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Volcanic crater cross-section: 30kg bundle breaks lava crust -> steam chain eruption!"""
    x0, y0, x1, y1 = box
    cx = (x0 + x1) // 2
    eased = _ease_out(anim_t)
    mono = _font("mono", 20)

    stages = data.get("stages") or ["DROP 30KG", "CRUST BREAK", "STEAM BLAST"]
    _draw_stage_strip(draw, x0 + 20, y0 + 14, (x1 - x0) - 40, stages, anim_t, accent)

    base_y = y1 - 175
    rim_y = y0 + 265
    lava_y = rim_y + 110

    # Volcanic cone cutaway slopes (left & right basalt rock walls)
    left_rock = [(x0 + 40, base_y), (cx - 210, rim_y), (cx - 145, rim_y), (cx - 125, base_y)]
    right_rock = [(x1 - 40, base_y), (cx + 210, rim_y), (cx + 145, rim_y), (cx + 125, base_y)]
    draw.polygon(left_rock, fill=(22, 28, 38, 240), outline=(*MUTED, 200))
    draw.polygon(right_rock, fill=(22, 28, 38, 240), outline=(*MUTED, 200))

    # Glowing subterranean magma pool + dark cooled surface crust
    draw.polygon([(cx - 132, lava_y), (cx + 132, lava_y), (cx + 125, base_y), (cx - 125, base_y)], fill=(210, 58, 24, 155), outline=(*CORAL, 245))
    draw.line([(cx - 135, lava_y), (cx + 135, lava_y)], fill=(*AMBER, 255), width=6)

    erupt = phase_t >= 0.42
    if not erupt:
        # Falling 30kg waste bundle dropping toward crust
        drop_t = min(1.0, phase_t / 0.42)
        by = int(y0 + 125 + drop_t * (lava_y - y0 - 145))
        draw.rounded_rectangle([cx - 24, by - 18, cx + 24, by + 18], radius=6, fill=(*CYAN, 180), outline=(*WHITE, 245), width=3)
        _draw_arrow(draw, (cx, by - 45), (cx, by - 22), (*CYAN, 235), width=3, head_len=10)
        draw.text((cx + 36, by - 12), "30 KG WATER/TRASH", font=mono, fill=(*CYAN, 245))
    else:
        # Instant 1,100C steam flash bubble + violent upward magma chain eruption!
        bt = min(1.0, (phase_t - 0.42) / 0.58)
        bub_r = int(26 + 62 * _ease_out(bt))
        draw.ellipse([cx - bub_r, lava_y - bub_r // 2, cx + bub_r, lava_y + bub_r], fill=(*WHITE, int(190 * (1.0 - 0.4 * bt))), outline=(*CYAN, 255), width=4)
        # Rising magma plume & projectiles
        for k in range(9):
            ang = -math.pi * 0.5 + (k - 4) * 0.16
            dist = (80 + 195 * _ease_out(bt)) * (0.75 + 0.25 * (k % 3))
            px = cx + math.cos(ang) * dist
            py = lava_y + math.sin(ang) * dist
            col = AMBER if k % 2 == 0 else CORAL
            draw.line([(cx, lava_y - 10), (px, py)], fill=(*col, 225), width=4)
            draw.ellipse([px - 8, py - 8, px + 8, py + 8], fill=(*col, 255))
        _draw_centered(draw, "1,600X STEAM FLASH EXPLOSION", cx, y0 + 115, mono, (*CORAL, 255))

    _draw_centered(draw, "1,100°C MAGMA LAKE", cx, base_y - 42, _font("headline", 28), (*WHITE, 245))

    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(draw, x0 + 25, y1 - 125, bar_w, 16, str(data.get("metric_label", "LAVA TEMP")), _roll_number(str(data.get("metric_value", "1,100 °C")), anim_t), 0.90 * eased, CORAL)
    _draw_meter_bar(draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16, str(data.get("sub_label", "STEAM EXPANSION")), _roll_number(str(data.get("sub_value", "1,600X")), anim_t), (0.95 if erupt else 0.20) * eased, AMBER)


def _mech_bridge_teeth(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Interlocking steel bridge expansion finger joint closing dynamically as temperature rises."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, y0 + 380
    eased = _ease_out(anim_t)
    mono = _font("mono", 20)

    stages = data.get("stages") or ["HEAT +45°C", "STEEL EXPANDS", "TEETH MESH"]
    _draw_stage_strip(draw, x0 + 20, y0 + 14, (x1 - x0) - 40, stages, anim_t, accent)

    # Thermal oscillation: 0.0 = winter (-10C, gap wide), 1.0 = summer (+45C, teeth meshed tight!)
    heat_t = 0.5 + 0.5 * math.sin(phase_t * math.tau - math.pi * 0.5)
    gap_half = int(68 - 44 * heat_t)
    deck_top, deck_bot = cy - 120, cy + 120
    deck_col = CORAL if heat_t > 0.65 else CYAN

    # Left & Right bridge roadway slabs
    draw.rectangle([x0 + 40, deck_top, cx - gap_half, deck_bot], fill=(22, 34, 52, 235), outline=(*deck_col, 240), width=3)
    draw.rectangle([cx + gap_half, deck_top, x1 - 40, deck_bot], fill=(22, 34, 52, 235), outline=(*deck_col, 240), width=3)

    # Interlocking steel comb/finger teeth meshing smoothly across the expansion gap!
    n_teeth = 6
    tooth_h = (deck_bot - deck_top - 24) // (n_teeth * 2)
    tooth_len = 86
    for i in range(n_teeth):
        ty_l = deck_top + 14 + (i * 2) * tooth_h
        ty_r = deck_top + 14 + (i * 2 + 1) * tooth_h
        # Left slab finger pointing right
        draw.polygon([
            (cx - gap_half, ty_l),
            (cx - gap_half + tooth_len, ty_l + 4),
            (cx - gap_half + tooth_len, ty_l + tooth_h - 4),
            (cx - gap_half, ty_l + tooth_h),
        ], fill=(*AMBER, 195), outline=(*WHITE, 230))
        # Right slab finger pointing left
        draw.polygon([
            (cx + gap_half, ty_r),
            (cx + gap_half - tooth_len, ty_r + 4),
            (cx + gap_half - tooth_len, ty_r + tooth_h - 4),
            (cx + gap_half, ty_r + tooth_h),
        ], fill=(*CYAN, 195), outline=(*WHITE, 230))

    # Expansion force arrows pushing inward
    _draw_arrow(draw, (x0 + 80, cy), (cx - gap_half - 24, cy), (*deck_col, 245), width=5, head_len=15)
    _draw_arrow(draw, (x1 - 80, cy), (cx + gap_half + 24, cy), (*deck_col, 245), width=5, head_len=15)

    temp_c = int(round(-10 + 55 * heat_t))
    status_txt = f"DECK TEMP: {temp_c:+d}°C  //  {'SUMMER EXPANSION' if heat_t > 0.5 else 'WINTER CONTRACTION'}"
    _draw_centered(draw, status_txt, cx, deck_top - 48, mono, (*deck_col, 250))
    _draw_centered(draw, "INTERLOCKING STEEL FINGERS PREVENT BUCKLING", cx, deck_bot + 26, mono, (*MINT, 240))

    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(draw, x0 + 25, y1 - 125, bar_w, 16, str(data.get("metric_label", "LENGTH SWING")), _roll_number(str(data.get("metric_value", "40 CM")), anim_t), 0.30 + 0.65 * heat_t, AMBER)
    _draw_meter_bar(draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16, str(data.get("sub_label", "THERMAL STRESS")), _roll_number(str(data.get("sub_value", "ABSORBED")), anim_t), 0.90 * eased, MINT)


def _mech_nuclear_sub(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Nuclear submarine CAD profile: 25yr reactor, infinite O2 electrolysis, 90-day food limit."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, y0 + 385
    eased = _ease_out(anim_t)
    mono = _font("mono", 19)

    stages = data.get("stages") or ["FUEL 25 YRS", "O2 INFINITE", "FOOD 90D"]
    _draw_stage_strip(draw, x0 + 20, y0 + 14, (x1 - x0) - 40, stages, anim_t, accent)

    # Teardrop submarine CAD hull outline
    hull_l, hull_r = x0 + 85, x1 - 75
    hull_h = 84
    draw.rounded_rectangle([hull_l, cy - hull_h, hull_r, cy + hull_h], radius=hull_h, fill=(14, 28, 46, 235), outline=(*CYAN, 245), width=4)
    # Conning tower / sail + periscope
    sail_x = cx + 90
    draw.polygon([(sail_x - 52, cy - hull_h), (sail_x - 36, cy - hull_h - 84), (sail_x + 42, cy - hull_h - 84), (sail_x + 56, cy - hull_h)], fill=(18, 34, 54, 245), outline=(*CYAN, 245))
    draw.line([(sail_x + 6, cy - hull_h - 84), (sail_x + 6, cy - hull_h - 122), (sail_x + 28, cy - hull_h - 122)], fill=(*WHITE, 235), width=4)

    # Spinning stern propeller + cavitation bubble wake on left!
    prop_x = hull_l - 12
    blade_h = int(52 * abs(math.cos(phase_t * math.tau * 4.0)) + 16)
    draw.line([(prop_x, cy - blade_h), (prop_x, cy + blade_h)], fill=(*AMBER, 250), width=7)
    for b in range(6):
        bt = (phase_t * 1.8 + b * 0.16) % 1.0
        bx = prop_x - 12 - bt * 58
        by = cy + int(math.sin(b * 2.1 + phase_t * 8) * 26)
        draw.ellipse([bx - 5, by - 5, bx + 5, by + 5], outline=(*CYAN, int(210 * (1.0 - bt))), width=2)

    # 3 Internal CAD Sub-Compartments inside hull: REACTOR | ELECTROLYSIS O2 | FOOD BAY!
    # 1. Reactor Core (left-mid, pulsing cyan)
    rx = cx - 185
    rp = 26 + int(6 * math.sin(phase_t * math.tau * 3))
    draw.ellipse([rx - rp, cy - rp, rx + rp, cy + rp], fill=(*CYAN, 60), outline=(*CYAN, 255), width=3)
    _draw_centered(draw, "NUCLEAR", rx, cy - 10, _font("mono", 16), (*WHITE, 245))
    draw.line([(rx, cy + hull_h), (rx, cy + hull_h + 44)], fill=(*CYAN, 210), width=2)
    _draw_centered(draw, "25 YR FUEL", rx, cy + hull_h + 50, mono, (*CYAN, 250))

    # 2. Seawater Electrolysis (center, mint oxygen bubbles)
    ex = cx - 10
    draw.rounded_rectangle([ex - 54, cy - 38, ex + 54, cy + 38], radius=10, fill=(*MINT, 45), outline=(*MINT, 245), width=3)
    _draw_centered(draw, "H2O -> O2", ex, cy - 10, _font("mono", 17), (*MINT, 255))
    draw.line([(ex, cy + hull_h), (ex, cy + hull_h + 44)], fill=(*MINT, 210), width=2)
    _draw_centered(draw, "UNLIMITED AIR", ex, cy + hull_h + 50, mono, (*MINT, 250))

    # 3. Food Storage Bay (front-right, flashing coral bottleneck!)
    fx = cx + 185
    pulse_f = 0.5 + 0.5 * math.sin(phase_t * math.tau * 3.5)
    draw.rounded_rectangle([fx - 64, cy - 42, fx + 64, cy + 42], radius=10, fill=(*CORAL, int(55 + 45 * pulse_f)), outline=(*CORAL, 255), width=4)
    _draw_centered(draw, "FOOD BAY", fx, cy - 12, _font("mono", 17), (*WHITE, 255))
    draw.line([(fx, cy + hull_h), (fx, cy + hull_h + 44)], fill=(*CORAL, 240), width=3)
    _draw_centered(draw, "90-DAY LIMIT!", fx, cy + hull_h + 50, mono, (*CORAL, 255))

    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(draw, x0 + 25, y1 - 125, bar_w, 16, str(data.get("metric_label", "REACTOR LIFE")), _roll_number(str(data.get("metric_value", "25 YEARS")), anim_t), 0.96 * eased, CYAN)
    _draw_meter_bar(draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16, str(data.get("sub_label", "REAL LIMIT")), _roll_number(str(data.get("sub_value", "90 DAYS FOOD")), anim_t), 0.22 * eased, CORAL)


def _mech_diver_oxygen(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Scuba diver descending past the 6m pure-oxygen toxicity ceiling (1.6 ATM partial pressure)."""
    x0, y0, x1, y1 = box
    cx = (x0 + x1) // 2
    eased = _ease_out(anim_t)
    mono = _font("mono", 20)

    stages = data.get("stages") or ["100% O2 TANK", "6M DEPTH", "1.6 ATM TOXIC"]
    _draw_stage_strip(draw, x0 + 20, y0 + 14, (x1 - x0) - 40, stages, anim_t, accent)

    top_y, bot_y = y0 + 125, y1 - 185
    # Left calibrated depth gauge (0m -> 6m RED LINE -> 20m)
    ax = x0 + 110
    draw.line([(ax, top_y), (ax, bot_y)], fill=(*CYAN, 210), width=3)
    toxic_y = top_y + int((bot_y - top_y) * 0.44)
    _draw_dashed_line(draw, (ax - 18, toxic_y), (x1 - 45, toxic_y), (*CORAL, 235), width=3, dash=14, gap=8)
    draw.text((ax + 20, top_y - 10), "0 M  (1.0 ATM · SAFE)", font=mono, fill=(*MINT, 240))
    draw.text((x1 - 310, toxic_y - 32), "6 M  PURE O2 TOXIC LIMIT", font=mono, fill=(*CORAL, 255))
    draw.text((ax + 20, bot_y - 12), "20 M (3.0 ATM · SEIZURE)", font=mono, fill=(*CORAL, 230))

    # Animated scuba diver wireframe descending smoothly past 6m line
    dy = int(top_y + 52 + (bot_y - top_y - 115) * eased)
    dx = cx + 30
    danger = dy >= toxic_y
    d_col = CORAL if danger else CYAN

    # Helmet / mask
    draw.ellipse([dx + 68, dy - 26, dx + 114, dy + 20], fill=(*SURFACE, 245), outline=(*d_col, 250), width=4)
    # Torso & pressurized O2 tank on back
    draw.rounded_rectangle([dx - 54, dy - 18, dx + 68, dy + 24], radius=16, fill=(d_col[0], d_col[1], d_col[2], 65), outline=(*d_col, 250), width=3)
    draw.rounded_rectangle([dx - 38, dy - 42, dx + 42, dy - 20], radius=10, fill=(*AMBER, 165), outline=(*WHITE, 235), width=2)
    draw.text((dx - 24, dy - 40), "100% O2", font=_font("mono", 15), fill=(*BG_TOP, 255))
    # Fins
    draw.polygon([(dx - 54, dy - 8), (dx - 118, dy - 24), (dx - 118, dy - 2)], fill=(*d_col, 160))
    draw.polygon([(dx - 54, dy + 12), (dx - 118, dy + 4), (dx - 118, dy + 28)], fill=(*d_col, 160))

    # Exhaled bubbles rising smoothly from regulator
    for b in range(5):
        bt = (phase_t * 1.6 + b * 0.2) % 1.0
        bx = dx + 108 + int(math.sin(bt * 8 + b) * 14)
        by = dy - 28 - bt * 110
        if by > top_y:
            draw.ellipse([bx - 6, by - 6, bx + 6, by + 6], outline=(*CYAN, int(230 * (1.0 - bt))), width=2)

    if danger:
        _draw_dashed_ellipse(draw, dx + 91, dy - 3, 44, 44, (*CORAL, 240), width=3, segments=16, phase=phase_t)

    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(draw, x0 + 25, y1 - 125, bar_w, 16, str(data.get("metric_label", "O2 PARTIAL PRESSURE")), _roll_number(str(data.get("metric_value", "1.6 ATM")), anim_t), (0.94 if danger else 0.45) * eased, CORAL if danger else CYAN)
    _draw_meter_bar(draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16, str(data.get("sub_label", "SAFE CEILING")), _roll_number(str(data.get("sub_value", "6 METERS")), anim_t), 0.65 * eased, AMBER)


def _mech_cargo_ship(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """250,000-ton steel ship cross-section in waves showing hollow air cavity vs upward buoyancy."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, y0 + 395
    eased = _ease_out(anim_t)
    mono = _font("mono", 20)

    stages = data.get("stages") or ["250K TONS", "HOLLOW AIR", "BUOYANCY"]
    _draw_stage_strip(draw, x0 + 20, y0 + 14, (x1 - x0) - 40, stages, anim_t, accent)

    water_y = cy + 16
    bob = int(6 * math.sin(phase_t * math.tau * 1.5))

    # Animated ocean surface waves & submerged translucent cyan water zone
    draw.rectangle([x0 + 30, water_y, x1 - 30, y1 - 170], fill=(10, 48, 72, 130))
    wave_pts = [(wx, water_y + int(7 * math.sin((wx - x0) * 0.025 + phase_t * math.tau * 2))) for wx in range(x0 + 30, x1 - 24, 16)]
    draw.line(wave_pts, fill=(*CYAN, 240), width=4)

    # Massive steel V-hull cross-section with visible HOLLOW AIR CAVITY inside!
    hull_pts = [
        (cx - 210, cy - 35 + bob),
        (cx + 210, cy - 35 + bob),
        (cx + 175, cy + 125 + bob),
        (cx - 175, cy + 125 + bob),
    ]
    draw.polygon(hull_pts, fill=(22, 34, 52, 245), outline=(*WHITE, 245))
    draw.line(hull_pts + [hull_pts[0]], fill=(*WHITE, 245), width=4)
    # Inner hollow air chamber (dotted cyan zone — explains Archimedes low average density!)
    inner_pts = [
        (cx - 178, cy - 12 + bob),
        (cx + 178, cy - 12 + bob),
        (cx + 148, cy + 102 + bob),
        (cx - 148, cy + 102 + bob),
    ]
    draw.polygon(inner_pts, fill=(*CYAN, 36), outline=(*CYAN, 210))
    _draw_centered(draw, "85% HOLLOW AIR CAVITY", cx, cy + 32 + bob, _font("headline", 28), (*CYAN, 255))

    # Stacked colorful shipping containers on top deck
    cols_c = [CORAL, AMBER, MINT, CYAN]
    for row in range(3):
        for c_i in range(6):
            bx = cx - 186 + c_i * 62
            by = cy - 35 + bob - (row + 1) * 34
            cc = cols_c[(row + c_i) % len(cols_c)]
            draw.rectangle([bx + 2, by + 2, bx + 58, by + 32], fill=(cc[0], cc[1], cc[2], 145), outline=(*cc, 250), width=2)

    # Downward Gravity Force arrow vs 4 huge Upward Buoyancy Force arrows!
    _draw_arrow(draw, (cx, y0 + 115), (cx, cy - 146 + bob), (*CORAL, 250), width=6, head_len=16)
    _draw_centered(draw, "GRAVITY: 250,000 T", cx, y0 + 88, mono, (*CORAL, 255))
    for ux in (cx - 140, cx - 48, cx + 48, cx + 140):
        _draw_arrow(draw, (ux, y1 - 180), (ux, cy + 138 + bob), (*MINT, 245), width=5, head_len=15)
    _draw_centered(draw, "UPWARD DISPLACED WATER BUOYANCY", cx, y1 - 172, mono, (*MINT, 255))

    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(draw, x0 + 25, y1 - 125, bar_w, 16, str(data.get("metric_label", "STEEL DENSITY")), _roll_number(str(data.get("metric_value", "7.8 G/CM3")), anim_t), 0.92 * eased, CORAL)
    _draw_meter_bar(draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16, str(data.get("sub_label", "SHIP AVG DENSITY")), _roll_number(str(data.get("sub_value", "0.5 G/CM3")), anim_t), 0.34 * eased, MINT)


def _mech_spacesuit_layers(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    data: Dict[str, Any],
    anim_t: float,
    phase_t: float,
    accent: Tuple[int, int, int],
) -> None:
    """Astronaut helmet & torso in vacuum + magnified 14-layer pressure restraint weave."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, y0 + 385
    eased = _ease_out(anim_t)
    mono = _font("mono", 20)

    stages = data.get("stages") or ["0.0 ATM VACUUM", "0.3 ATM INSIDE", "MESH LOCK"]
    _draw_stage_strip(draw, x0 + 20, y0 + 14, (x1 - x0) - 40, stages, anim_t, accent)

    # Left: Astronaut helmet & torso CAD wireframe silhouette
    ax = x0 + 235
    # Helmet dome + reflective gold visor
    draw.ellipse([ax - 74, cy - 175, ax + 74, cy - 27], fill=(16, 28, 44, 240), outline=(*WHITE, 245), width=4)
    draw.ellipse([ax - 52, cy - 148, ax + 52, cy - 58], fill=(*AMBER, 130), outline=(*AMBER, 255), width=3)
    # Torso hard upper shell
    draw.rounded_rectangle([ax - 95, cy - 24, ax + 95, cy + 168], radius=38, fill=(18, 32, 50, 235), outline=(*CYAN, 245), width=4)
    # Chest DCM control module
    draw.rounded_rectangle([ax - 44, cy + 16, ax + 44, cy + 84], radius=10, fill=(*SURFACE, 255), outline=(*AMBER, 225), width=2)
    _draw_centered(draw, "0.3 ATM", ax, cy + 40, _font("mono", 18), (*AMBER, 255))

    # Outward pressure arrows attempting to inflate the suit like a balloon
    for ang_d in (-150, 150, -30, 30):
        ang = math.radians(ang_d)
        r0 = 104
        r1 = 138 + int(10 * math.sin(phase_t * math.tau * 2.5))
        _draw_arrow(draw, (ax + math.cos(ang) * r0, cy + 60 + math.sin(ang) * r0), (ax + math.cos(ang) * r1, cy + 60 + math.sin(ang) * r1), (*CORAL, 235), width=4, head_len=12)

    # Right: Magnified 14-layer cross-section lens showing restraint mesh!
    lx = x1 - 245
    lr = 165
    _draw_dashed_line(draw, (ax + 78, cy + 10), (lx - lr, cy), (*CYAN, 210), width=3, dash=10, gap=6)
    draw.ellipse([lx - lr, cy - lr, lx + lr, cy + lr], fill=(*SURFACE, 245), outline=(*CYAN, 250), width=4)

    # 4 nested curved pressure/restraint arcs inside lens
    layer_specs = [
        ("URETHANE BLADDER", AMBER, 44),
        ("DACRON RESTRAINT", MINT, 82),
        ("THERMAL FOIL x7", CYAN, 118),
        ("KEVLAR OUTER", WHITE, 148),
    ]
    for lname, lcol, rad in layer_specs:
        draw.arc([lx - rad, cy - rad, lx + rad, cy + rad], start=205, end=335, fill=(*lcol, 245), width=8)
    _draw_centered(draw, "14 LAYERS", lx, cy + 32, _font("headline", 38), (*WHITE, 255))
    _draw_centered(draw, "RESTRAINT MESH", lx, cy + 82, mono, (*MINT, 250))

    bar_w = (x1 - x0 - 90) // 2
    _draw_meter_bar(draw, x0 + 25, y1 - 125, bar_w, 16, str(data.get("metric_label", "SUIT LAYERS")), _roll_number(str(data.get("metric_value", "14 LAYERS")), anim_t), 0.92 * eased, CYAN)
    _draw_meter_bar(draw, x0 + 65 + bar_w, y1 - 125, bar_w, 16, str(data.get("sub_label", "SUIT PRESSURE")), _roll_number(str(data.get("sub_value", "0.3 ATM")), anim_t), 0.72 * eased, MINT)


V7_MECHANISM_RENDERERS = {
    "mech_elevator_brake": _mech_elevator_brake,
    "mech_sr71_blackbird": _mech_sr71_blackbird,
    "mech_train_wheel_cone": _mech_train_wheel_cone,
    "mech_airplane_window": _mech_airplane_window,
    "mech_volcano_eruption": _mech_volcano_eruption,
    "mech_bridge_teeth": _mech_bridge_teeth,
    "mech_nuclear_sub": _mech_nuclear_sub,
    "mech_diver_oxygen": _mech_diver_oxygen,
    "mech_cargo_ship": _mech_cargo_ship,
    "mech_spacesuit_layers": _mech_spacesuit_layers,
}
