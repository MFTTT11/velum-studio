"""Netflix/Vox Retention Script Architect (prompts/retention_script.md).

Generates scene-by-scene documentary scripts for:
- Shorts (9:16, ~40-48s, seamless infinite loop)
- Long-form (16:9, ~180-240s, multi-chapter deep breakdown)

Enforces:
- 0-2s high-contrast shock hook (zero banned AI-slop phrases)
- Primary keyword spoken within first 15s (VSEO)
- Visual beat durations strictly <= 2.5s
- Live HUD telemetry counters and alternating photo_grade / data_plate visuals
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from core.config import get_logger, load_prompt
from core.llm_client import ZeroCostLLMClient

logger = get_logger("script_engine")

BANNED_SLOP_PHRASES = (
    "in today's video",
    "welcome back",
    "hey guys",
    "mind-blowing",
    "buckle up",
    "let's dive in",
    "in conclusion",
    "don't forget to like",
    "delve into",
    "tapestry",
)


def _topic_specific_beats(topic: Dict[str, Any], fmt: str) -> List[Dict[str, Any]]:
    """Build hyper-dense, zero-fluff documentary beats tailored to the topic's real numbers."""
    tid = topic["topic_id"]
    facts = topic["key_facts"]
    queries = topic.get("visual_queries", ["dark technology infrastructure", "data visualization grid"])

    def q(idx: int) -> str:
        return queries[idx % len(queries)]

    if tid.startswith("one-million-vs-one-billion"):
        shorts_beats = [
            {
                "narration": "One million seconds is just eleven and a half days.",
                "visual_type": "data_plate",
                "plate_mode": "comparison_bars",
                "plate_data": {
                    "title": "THE TIME SCALE SHOCK",
                    "left_label": "1 MILLION SEC",
                    "left_value": 11.5,
                    "left_display": "11.5 DAYS",
                    "right_label": "1 BILLION SEC",
                    "right_value": 11574,
                    "right_display": "31.7 YEARS",
                    "ratio_badge": "1,000x GAP",
                },
                "visual_query": q(3),
                "hud_tag": "HOOK // SCALE 01",
                "hud_metric": "11.5 DAYS",
                "hud_delta": "10^6 SEC",
                "sfx": "sub_boom",
                "camera_motion": "zoom_in",
            },
            {
                "narration": "One billion seconds is thirty one point seven years.",
                "visual_type": "data_plate",
                "plate_mode": "metric_hero",
                "plate_data": {
                    "title": "ONE BILLION SECONDS",
                    "hero_value": "31.7 YRS",
                    "subtitle": "NEARLY HALF A HUMAN LIFETIME",
                    "accent": "amber",
                },
                "visual_query": q(3),
                "hud_tag": "RATIO // 1000X",
                "hud_metric": "31.7 YEARS",
                "hud_delta": "+99,900%",
                "sfx": "whoosh",
                "camera_motion": "zoom_out",
            },
            {
                "narration": "That single million vs billion scale comparison exposes a massive glitch in human perception.",
                "visual_type": "photo_grade",
                "visual_query": q(0),
                "hud_tag": "VSEO // PERCEPTION",
                "hud_metric": "0.1% GAP",
                "hud_delta": "COGNITIVE BIAS",
                "sfx": "tick",
                "camera_motion": "pan_right",
            },
            {
                "narration": "Your brain hears both words and treats them like close neighbors.",
                "visual_type": "photo_grade",
                "visual_query": q(2),
                "hud_tag": "NEURAL // SCALE",
                "hud_metric": "LOG ERROR",
                "hud_delta": "LINEAR BRAIN",
                "sfx": "none",
                "camera_motion": "zoom_in",
            },
            {
                "narration": "In reality, one million is literally zero point one percent of a billion.",
                "visual_type": "data_plate",
                "plate_mode": "comparison_bars",
                "plate_data": {
                    "title": "REAL PROPORTION",
                    "left_label": "$1,000,000",
                    "left_value": 1,
                    "left_display": "0.1%",
                    "right_label": "$1,000,000,000",
                    "right_value": 1000,
                    "right_display": "100%",
                    "ratio_badge": "1 : 1000",
                },
                "visual_query": q(1),
                "hud_tag": "RATIO // EXACT",
                "hud_metric": "0.10%",
                "hud_delta": "1 IN 1,000",
                "sfx": "sonar",
                "camera_motion": "zoom_in",
            },
            {
                "narration": "Now test this with real money.",
                "visual_type": "photo_grade",
                "visual_query": q(1),
                "hud_tag": "SIM // BURN RATE",
                "hud_metric": "$10,000/D",
                "hud_delta": "STRESS TEST",
                "sfx": "whoosh",
                "camera_motion": "pan_left",
            },
            {
                "narration": "Spend ten thousand dollars every single day starting tonight.",
                "visual_type": "data_plate",
                "plate_mode": "metric_hero",
                "plate_data": {
                    "title": "DAILY SPENDING RATE",
                    "hero_value": "$10,000",
                    "subtitle": "EVERY 24 HOURS WITHOUT STOPPING",
                    "accent": "cyan",
                },
                "visual_query": q(1),
                "hud_tag": "BURN // DAILY",
                "hud_metric": "$10,000",
                "hud_delta": "-10K / 24H",
                "sfx": "tick",
                "camera_motion": "zoom_in",
            },
            {
                "narration": "A millionaire goes completely broke in one hundred days.",
                "visual_type": "data_plate",
                "plate_mode": "timeline_scale",
                "plate_data": {
                    "title": "RUNWAY AT $10K / DAY",
                    "markers": [
                        {"label": "$1M", "value": "100 DAYS", "pct": 0.08, "color": "cyan"},
                        {"label": "$10M", "value": "2.7 YRS", "pct": 0.25, "color": "cyan"},
                        {"label": "$1B", "value": "273 YRS", "pct": 0.96, "color": "amber"},
                    ],
                },
                "visual_query": q(0),
                "hud_tag": "MILLIONAIRE",
                "hud_metric": "100 DAYS",
                "hud_delta": "EMPTY",
                "sfx": "glitch",
                "camera_motion": "pan_right",
            },
            {
                "narration": "A billionaire keeps spending for two hundred and seventy three years.",
                "visual_type": "photo_grade",
                "visual_query": q(0),
                "hud_tag": "BILLIONAIRE",
                "hud_metric": "273 YEARS",
                "hud_delta": "3.5 LIFETIMES",
                "sfx": "sub_boom",
                "camera_motion": "zoom_out",
            },
            {
                "narration": "Even weirder: stack one million dollars in hundred dollar bills.",
                "visual_type": "photo_grade",
                "visual_query": q(1),
                "hud_tag": "PHYSICAL // HEIGHT",
                "hud_metric": "1.09 M",
                "hud_delta": "WAIST HIGH",
                "sfx": "whoosh",
                "camera_motion": "drift_up",
            },
            {
                "narration": "The stack barely reaches waist height at one meter tall.",
                "visual_type": "data_plate",
                "plate_mode": "comparison_bars",
                "plate_data": {
                    "title": "CASH STACK HEIGHT ($100 BILLS)",
                    "left_label": "$1 MILLION",
                    "left_value": 1.09,
                    "left_display": "1.09 M",
                    "right_label": "$1 BILLION",
                    "right_value": 1092,
                    "right_display": "1,092 M",
                    "ratio_badge": "TALLER THAN BURJ KHALIFA",
                },
                "visual_query": q(0),
                "hud_tag": "STACK // $1M",
                "hud_metric": "1.09 M",
                "hud_delta": "10,000 BILLS",
                "sfx": "tick",
                "camera_motion": "zoom_in",
            },
            {
                "narration": "One billion dollars towers past one kilometer straight into the clouds.",
                "visual_type": "photo_grade",
                "visual_query": q(4),
                "hud_tag": "STACK // $1B",
                "hud_metric": "1,092 M",
                "hud_delta": "1.3x BURJ KHALIFA",
                "sfx": "riser",
                "camera_motion": "drift_up",
            },
            {
                "narration": "Now jump just one more word to one trillion seconds.",
                "visual_type": "data_plate",
                "plate_mode": "radar_alert",
                "plate_data": {
                    "title": "SCALE ANOMALY DETECTED",
                    "metric": "31,709 YEARS",
                    "subtitle": "ONE TRILLION SECONDS BACK TO THE ICE AGE",
                    "severity": "EXTREME",
                },
                "visual_query": q(4),
                "hud_tag": "ANOMALY // 10^12",
                "hud_metric": "31,709 YRS",
                "hud_delta": "ICE AGE ERA",
                "sfx": "sub_boom",
                "camera_motion": "zoom_in",
            },
            {
                "narration": "That stretches back thirty one thousand years to the Ice Age.",
                "visual_type": "photo_grade",
                "visual_query": q(4),
                "hud_tag": "TIMELINE // DEEP",
                "hud_metric": "-29,700 BC",
                "hud_delta": "HUMAN PREHISTORY",
                "sfx": "sonar",
                "camera_motion": "zoom_out",
            },
            {
                "narration": "Every extra zero does not add scale, it multiplies worlds apart.",
                "visual_type": "data_plate",
                "plate_mode": "system_nodes",
                "plate_data": {
                    "title": "EXPONENTIAL ARCHITECTURE",
                    "nodes": ["10^6 // 11.5D", "10^9 // 31.7Y", "10^12 // 31.7KY"],
                    "caption": "HUMAN INTUITION BREAKS ABOVE 10^6",
                },
                "visual_query": q(2),
                "hud_tag": "SYSTEM // RULE",
                "hud_metric": "10^3 STEP",
                "hud_delta": "NON-LINEAR",
                "sfx": "whoosh",
                "camera_motion": "pan_left",
            },
            {
                "narration": "Which is the exact blind spot that makes it so shocking when you remember—",
                "visual_type": "photo_grade",
                "visual_query": q(3),
                "hud_tag": "LOOP // REPLAY",
                "hud_metric": "RE-INDEXING",
                "hud_delta": "SEAMLESS",
                "sfx": "tick",
                "camera_motion": "zoom_in",
            },
        ]
    else:
        # Dynamic high-retention blueprint builder for any other pillar/topic
        f0, f1, f2, f3 = facts[0], facts[1], facts[2], facts[3]
        shorts_beats = [
            {
                "narration": f"Look at this single number: {f0['value']}.",
                "visual_type": "data_plate",
                "plate_mode": "metric_hero",
                "plate_data": {
                    "title": f0["label"],
                    "hero_value": f0["value"],
                    "subtitle": topic.get("hook_subtext", "HIDDEN SYSTEM METRIC"),
                    "accent": "crimson",
                },
                "visual_query": q(0),
                "hud_tag": "HOOK // 01",
                "hud_metric": f0["value"],
                "hud_delta": "ANOMALY",
                "sfx": "sub_boom",
                "camera_motion": "zoom_in",
            },
            {
                "narration": f"Almost nobody realizes how {topic['primary_keyword']} quietly runs modern reality.",
                "visual_type": "photo_grade",
                "visual_query": q(0),
                "hud_tag": "VSEO // CORE",
                "hud_metric": f1["value"],
                "hud_delta": "ACTIVE",
                "sfx": "whoosh",
                "camera_motion": "pan_right",
            },
            {
                "narration": f"Right now, the real bottleneck measures just {f1['value']}.",
                "visual_type": "data_plate",
                "plate_mode": "comparison_bars",
                "plate_data": {
                    "title": "CRITICAL THRESHOLD",
                    "left_label": f0["label"],
                    "left_value": float(abs(f0["numeric"])) or 10.0,
                    "left_display": f0["value"],
                    "right_label": f1["label"],
                    "right_value": float(abs(f1["numeric"])) or 100.0,
                    "right_display": f1["value"],
                    "ratio_badge": "LIVE RATIO",
                },
                "visual_query": q(1),
                "hud_tag": "SCALE // 02",
                "hud_metric": f1["value"],
                "hud_delta": "BOTTLENECK",
                "sfx": "sonar",
                "camera_motion": "zoom_in",
            },
            {
                "narration": "Most people picture something massive, indestructible, and invisible in the cloud.",
                "visual_type": "photo_grade",
                "visual_query": q(1),
                "hud_tag": "ILLUSION",
                "hud_metric": "99% HIDDEN",
                "hud_delta": "OFF-RADAR",
                "sfx": "tick",
                "camera_motion": "zoom_out",
            },
            {
                "narration": f"Yet the verified measurement hits an extreme {f2['value']}.",
                "visual_type": "data_plate",
                "plate_mode": "radar_alert",
                "plate_data": {
                    "title": f2["label"],
                    "metric": f2["value"],
                    "subtitle": "VERIFIED PHYSICAL LIMIT",
                    "severity": "CRITICAL",
                },
                "visual_query": q(2),
                "hud_tag": "LIMIT // 03",
                "hud_metric": f2["value"],
                "hud_delta": "EXTREME",
                "sfx": "glitch",
                "camera_motion": "pan_left",
            },
            {
                "narration": "Here is the catch almost nobody calculates.",
                "visual_type": "photo_grade",
                "visual_query": q(2),
                "hud_tag": "RE-HOOK",
                "hud_metric": "SYSTEM RISK",
                "hud_delta": "SINGLE POINT",
                "sfx": "whoosh",
                "camera_motion": "zoom_in",
            },
            {
                "narration": f"Every single cycle moves an astonishing {f3['value']} across the system.",
                "visual_type": "data_plate",
                "plate_mode": "system_nodes",
                "plate_data": {
                    "title": "HIDDEN SYSTEM TOPOLOGY",
                    "nodes": [f0["value"], f1["value"], f3["value"]],
                    "caption": topic["primary_keyword"].upper(),
                },
                "visual_query": q(3),
                "hud_tag": "FLOW // 04",
                "hud_metric": f3["value"],
                "hud_delta": "CONTINUOUS",
                "sfx": "sub_boom",
                "camera_motion": "zoom_in",
            },
            {
                "narration": "One tiny disruption at this exact layer cascades worldwide in seconds.",
                "visual_type": "photo_grade",
                "visual_query": q(3),
                "hud_tag": "CASCADE",
                "hud_metric": "< 1 SEC",
                "hud_delta": "GLOBAL",
                "sfx": "riser",
                "camera_motion": "drift_up",
            },
            {
                "narration": "Now compare every metric side by side on one scale.",
                "visual_type": "data_plate",
                "plate_mode": "timeline_scale",
                "plate_data": {
                    "title": "SYSTEM TELEMETRY SUMMARY",
                    "markers": [
                        {"label": f0["label"][:12], "value": f0["value"], "pct": 0.25, "color": "cyan"},
                        {"label": f1["label"][:12], "value": f1["value"], "pct": 0.55, "color": "amber"},
                        {"label": f3["label"][:12], "value": f3["value"], "pct": 0.90, "color": "crimson"},
                    ],
                },
                "visual_query": q(4),
                "hud_tag": "SYNTHESIS",
                "hud_metric": "4/4 VERIFIED",
                "hud_delta": "100%",
                "sfx": "sonar",
                "camera_motion": "pan_right",
            },
            {
                "narration": "Once you see the real machinery behind the curtain, you cannot unsee it.",
                "visual_type": "photo_grade",
                "visual_query": q(4),
                "hud_tag": "INSIGHT",
                "hud_metric": "DECODED",
                "hud_delta": "SIGNAL",
                "sfx": "tick",
                "camera_motion": "zoom_out",
            },
            {
                "narration": "And everything starts to make terrifying sense the moment you—",
                "visual_type": "photo_grade",
                "visual_query": q(0),
                "hud_tag": "LOOP // NEXT",
                "hud_metric": "REPLAY",
                "hud_delta": "SEAMLESS",
                "sfx": "whoosh",
                "camera_motion": "zoom_in",
            },
        ]

    if fmt == "longform":
        # Expand into a 3-chapter deep-dive breakdown for 16:9 long-form documentary mode
        expanded: List[Dict[str, Any]] = []
        chapters = [
            ("CH.01 // THE SCALE ILLUSION", shorts_beats),
            (
                "CH.02 // WHY HUMAN INTUITION FAILS",
                [
                    {
                        **b,
                        "hud_tag": f"DEEP // {i + 1:02d}",
                        "narration": (
                            f"Zooming deeper into the mechanics: {b['narration'][0].lower()}{b['narration'][1:]}"
                            if i % 3 == 0
                            else b["narration"]
                        ),
                    }
                    for i, b in enumerate(shorts_beats[:-1])
                ],
            ),
            (
                "CH.03 // REAL-WORLD CONSEQUENCES",
                [
                    {
                        **b,
                        "hud_tag": f"IMPACT // {i + 1:02d}",
                    }
                    for i, b in enumerate(shorts_beats[:-1])
                ],
            ),
        ]
        for _, ch_beats in chapters:
            expanded.extend(ch_beats)
        expanded.append(
            {
                "narration": "Drop your best guess in the comments: which invisible scale shocks you more, time or money?",
                "visual_type": "data_plate",
                "plate_mode": "metric_hero",
                "plate_data": {
                    "title": "JOIN THE DEBATE",
                    "hero_value": "TIME vs MONEY",
                    "subtitle": "WHICH SCALE BREAKS YOUR BRAIN MORE?",
                    "accent": "cyan",
                },
                "visual_query": q(0),
                "hud_tag": "DEBATE // OPEN",
                "hud_metric": "YOUR CALL",
                "hud_delta": "COMMENTS",
                "sfx": "sonar",
                "camera_motion": "zoom_in",
            }
        )
        return expanded

    return shorts_beats


class ScriptEngine:
    """Produces retention-locked, VSEO-verified scripts ready for audio & visual synthesis."""

    def __init__(self, llm: Optional[ZeroCostLLMClient] = None) -> None:
        self.llm = llm or ZeroCostLLMClient()

    def _sanitize_anti_slop(self, text: str) -> str:
        cleaned = text.strip()
        for phrase in BANNED_SLOP_PHRASES:
            cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)
        return re.sub(r"\s{2,}", " ", cleaned).strip()

    def _verify_vseo_first_15s(self, beats: List[Dict[str, Any]], primary_keyword: str) -> bool:
        """Ensure primary keyword appears in the opening ~38 spoken words (~15 seconds)."""
        opening_words: List[str] = []
        for b in beats:
            opening_words.extend(b["narration"].split())
            if len(opening_words) >= 42:
                break
        opening_text = " ".join(opening_words).lower()
        kw_tokens = [tok for tok in re.findall(r"[a-z0-9]+", primary_keyword.lower()) if len(tok) > 2]
        matched = sum(1 for tok in kw_tokens if tok in opening_text)
        return matched >= max(1, len(kw_tokens) - 1)

    def generate_script(self, topic: Dict[str, Any], fmt: str = "shorts") -> Dict[str, Any]:
        """Generate a validated scene-by-scene script for 'shorts' (9:16) or 'longform' (16:9)."""
        beats: Optional[List[Dict[str, Any]]] = None

        if self.llm.is_available:
            system_prompt = load_prompt("retention_script.md")
            user_prompt = (
                f"Format: {fmt}\n"
                f"Target beats: {'14 to 18 tight beats (~40-48s total)' if fmt == 'shorts' else '40 to 55 beats (~3 min)'}.\n"
                f"Primary keyword (MUST be spoken within first 15 seconds): {topic['primary_keyword']}\n"
                f"Topic Blueprint:\n{json.dumps(topic, ensure_ascii=False)}"
            )
            llm_script = self.llm.complete_json(system_prompt, user_prompt, temperature=0.6)
            if llm_script and isinstance(llm_script.get("beats"), list) and len(llm_script["beats"]) >= 8:
                beats = llm_script["beats"]

        if not beats:
            beats = _topic_specific_beats(topic, fmt)

        # Normalize, index, and scrub banned phrases across every beat
        normalized_beats: List[Dict[str, Any]] = []
        total_beats = len(beats)
        for idx, raw in enumerate(beats):
            narration = self._sanitize_anti_slop(str(raw.get("narration", "")))
            if not narration:
                continue
            # Estimate target duration (~2.6 words/sec energetic documentary delivery), capped at <=2.5s rhythm
            words = max(1, len(narration.split()))
            est_dur = max(1.6, min(2.5, round(words / 3.1, 2)))
            normalized_beats.append(
                {
                    "index": idx + 1,
                    "target_duration": est_dur,
                    "narration": narration,
                    "visual_type": raw.get("visual_type", "data_plate" if idx % 2 == 0 else "photo_grade"),
                    "plate_mode": raw.get("plate_mode", "metric_hero"),
                    "plate_data": raw.get("plate_data", {}),
                    "visual_query": raw.get("visual_query", topic["primary_keyword"]),
                    "hud_tag": str(raw.get("hud_tag", f"DATA // {idx + 1:02d}")).upper(),
                    "hud_metric": str(raw.get("hud_metric", topic["shock_hook_stat"])).upper(),
                    "hud_delta": str(raw.get("hud_delta", f"{int((idx + 1) / total_beats * 100)}%")).upper(),
                    "hud_progress": round((idx + 1) / max(total_beats, 1), 3),
                    "sfx": raw.get("sfx", "sub_boom" if idx == 0 else ("whoosh" if idx % 3 == 0 else "tick")),
                    "camera_motion": raw.get(
                        "camera_motion",
                        ["zoom_in", "pan_right", "zoom_out", "pan_left", "drift_up"][idx % 5],
                    ),
                }
            )

        vseo_ok = self._verify_vseo_first_15s(normalized_beats, topic["primary_keyword"])
        if not vseo_ok and len(normalized_beats) >= 3:
            # Force-anchor primary keyword cleanly into beat 3 (around ~5-8s mark)
            normalized_beats[2]["narration"] = (
                f"This exact {topic['primary_keyword']} proves how distorted our intuition really is."
            )
            vseo_ok = True

        full_narration = " ".join(b["narration"] for b in normalized_beats)
        script_payload = {
            "format": fmt,
            "topic_id": topic["topic_id"],
            "pillar": topic["pillar"],
            "primary_keyword": topic["primary_keyword"],
            "hook_stat_text": topic["shock_hook_stat"],
            "hook_subtext": topic.get("hook_subtext", "VELUM ARCHIVE TELEMETRY"),
            "vseo_verified_under_15s": vseo_ok,
            "full_narration": full_narration,
            "word_count": len(full_narration.split()),
            "beats": normalized_beats,
        }
        logger.info(
            "Script generated: %s | format=%s | beats=%d | words=%d | VSEO<15s=%s",
            topic["topic_id"],
            fmt,
            len(normalized_beats),
            script_payload["word_count"],
            vseo_ok,
        )
        return script_payload
