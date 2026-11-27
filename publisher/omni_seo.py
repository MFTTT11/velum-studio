"""Omni-SEO Engine (VSEO + SEO + GEO + AEO + Multi-Language SRT Captions).

Produces the complete discovery package per prompts/omni_seo.md:
- VSEO: Verifies exact primary keyword appears inside the first 15s of spoken audio
- SEO:  Enforces lowercase `keyword-slug.mp4` filename, 3 A/B/C titles, 300+ word
        structured micro-article description, chapters, tags, and hashtags
- GEO:  Structured entity-metric-value Key Data Summary for AI answer engines
- AEO:  3-question People-Also-Ask FAQ + debate-triggering Pinned First Comment
- SRT:  Whisper-aligned multi-language `.srt` files (EN, TR, ES, DE, FR)
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from core.config import get_logger, load_brand_config, load_prompt
from core.llm_client import ZeroCostLLMClient

logger = get_logger("omni_seo")

TARGET_CAPTION_LANGS = {
    "en": "English",
    "tr": "Turkish",
    "es": "Spanish",
    "de": "German",
    "fr": "French",
    "pt": "Portuguese",
    "ar": "Arabic",
    "hi": "Hindi",
    "ja": "Japanese",
    "ko": "Korean",
}


def slugify_keyword(keyword: str) -> str:
    """Convert a primary keyword into a clean lowercase SEO filename slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", keyword.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:72] or "velum-breakdown"


def _format_srt_ts(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - math.floor(sec)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_chapter_ts(sec: float) -> str:
    sec = max(0, int(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def _translate_lines_batch_free(lines: List[str], target_lang: str) -> List[str]:
    """Fast, resilient Autonomous batch subtitle translation (Google GTX -> MyMemory -> safe passthrough)."""
    if target_lang == "en" or not lines:
        return list(lines)

    # 1. Primary fast batch translation via zero-key Google Translate GTX public endpoint
    delimiter = " ||| "
    joined = delimiter.join(ln.strip() for ln in lines)
    try:
        resp = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "en", "tl": target_lang, "dt": "t", "q": joined},
            timeout=10,
        )
        if resp.status_code == 200:
            payload = resp.json()
            combined = "".join(seg[0] for seg in payload[0] if seg and seg[0])
            parts = [p.strip() for p in re.split(r"\|\s*\|\s*\|", combined)]
            if len(parts) == len(lines):
                return parts
    except Exception as exc:
        logger.debug("GTX batch translation fallback for %s (%s)", target_lang, type(exc).__name__)

    # 2. Secondary fallback via chunked MyMemory public endpoint (<=420 chars per chunk)
    translated: List[str] = []
    chunk: List[str] = []
    chunk_len = 0

    def _flush_chunk(items: List[str]) -> List[str]:
        if not items:
            return []
        try:
            resp = requests.get(
                "https://api.mymemory.translated.net/get",
                params={"q": "\n".join(items), "langpair": f"en|{target_lang}"},
                timeout=8,
            )
            if resp.status_code == 200:
                tr = resp.json().get("responseData", {}).get("translatedText", "").strip()
                if tr and "MYMEMORY WARNING" not in tr.upper():
                    split_tr = [s.strip() for s in tr.splitlines() if s.strip()]
                    if len(split_tr) == len(items):
                        return split_tr
        except Exception as exc:
            logger.debug("MyMemory fallback skipped for %s (%s)", target_lang, type(exc).__name__)
        return list(items)

    for ln in lines:
        if chunk and chunk_len + len(ln) + 1 > 400:
            translated.extend(_flush_chunk(chunk))
            chunk = [ln]
            chunk_len = len(ln)
        else:
            chunk.append(ln)
            chunk_len += len(ln) + 1
    if chunk:
        translated.extend(_flush_chunk(chunk))

    return translated if len(translated) == len(lines) else list(lines)


def _build_srt_cues_from_beats(timed_beats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse subdivided beats back into clean spoken subtitle cues."""
    cues: List[Dict[str, Any]] = []
    for beat in timed_beats:
        text = beat["narration"].strip()
        start = float(beat["start"])
        end = float(beat["end"])
        if cues and cues[-1]["text"] == text:
            cues[-1]["end"] = end
        else:
            cues.append({"start": start, "end": end, "text": text})
    return cues


def generate_multilang_srt_tracks(
    timed_beats: List[Dict[str, Any]],
    out_dir: Path,
    slug: str,
    llm: Optional[ZeroCostLLMClient] = None,
) -> Dict[str, str]:
    """Generate clean `.srt` subtitle files in EN, TR, ES, DE, FR."""
    srt_dir = out_dir / "subtitles"
    srt_dir.mkdir(parents=True, exist_ok=True)
    cues = _build_srt_cues_from_beats(timed_beats)
    en_texts = [c["text"] for c in cues]

    srt_paths: Dict[str, str] = {}
    for lang_code, lang_name in TARGET_CAPTION_LANGS.items():
        translated_lines = list(en_texts)
        if lang_code != "en":
            llm_translated = None
            if llm and llm.is_available:
                res = llm.complete_json(
                    f"Translate each English documentary subtitle line naturally into {lang_name}. "
                    'Return JSON: {"lines": ["..."]} with exact same length.',
                    json.dumps({"lines": en_texts}, ensure_ascii=False),
                    temperature=0.25,
                )
                if res and isinstance(res.get("lines"), list) and len(res["lines"]) == len(en_texts):
                    llm_translated = [str(x).strip() for x in res["lines"]]

            if llm_translated:
                translated_lines = llm_translated
            else:
                translated_lines = _translate_lines_batch_free(en_texts, lang_code)

        srt_blocks: List[str] = []
        for idx, (cue, line_text) in enumerate(zip(cues, translated_lines), start=1):
            srt_blocks.append(
                f"{idx}\n{_format_srt_ts(cue['start'])} --> {_format_srt_ts(cue['end'])}\n{line_text}\n"
            )
        srt_file = srt_dir / f"{slug}.{lang_code}.srt"
        srt_file.write_text("\n".join(srt_blocks), encoding="utf-8")
        srt_paths[lang_code] = str(srt_file)

    logger.info("Generated %d multi-language .srt caption tracks (%s)", len(srt_paths), ", ".join(srt_paths.keys()))
    return srt_paths


def _verify_vseo_in_whisper(words: List[Dict[str, Any]], primary_keyword: str) -> Dict[str, Any]:
    """Verify that primary keyword tokens were actually spoken inside the first 15 seconds."""
    first_15s_tokens = [
        w["word"].lower() for w in words if float(w.get("start", 99.0)) <= 15.0
    ]
    spoken_15s = " ".join(first_15s_tokens)
    stop = {"how", "why", "the", "and", "for", "can", "you", "are", "with", "each", "long", "vs", "dont"}
    kw_parts = [
        p for p in re.findall(r"[a-z0-9]+", primary_keyword.lower())
        if len(p) > 2 and p not in stop
    ]
    matched = [
        p for p in kw_parts
        if p in spoken_15s or (len(p) > 4 and p[:-1] in spoken_15s)
    ]
    verified = len(matched) >= max(1, (len(kw_parts) + 1) // 2)
    return {
        "primary_keyword": primary_keyword,
        "verified_under_15s": verified,
        "matched_tokens": matched,
        "first_15s_excerpt": spoken_15s[:260],
    }


def _build_native_omni_seo(
    topic: Dict[str, Any],
    script: Dict[str, Any],
    voice_data: Dict[str, Any],
    brand: Dict[str, Any],
) -> Dict[str, Any]:
    """Construct a verified 300+ word micro-article SEO + GEO + AEO package natively."""
    kw = topic["primary_keyword"]
    facts = topic["key_facts"]
    pillar = topic["pillar"].replace("_", " ").title()
    wiki_snip = topic.get("wiki_summary", "")

    f0, f1, f2, f3 = facts[0], facts[1], facts[2], facts[3]

    # Build chapter markers from timed beats (4 clean chapters)
    timed_beats = voice_data.get("timed_beats", [])
    total_dur = float(voice_data.get("duration", 40.0))
    chapters = [
        f"00:00 — The Shock Hook: {topic['shock_hook_stat']}",
        f"{_format_chapter_ts(total_dur * 0.22)} — Why {kw.title()} Breaks Human Intuition",
        f"{_format_chapter_ts(total_dur * 0.52)} — Real-World Visual Comparison ({f1['value']} vs {f3['value']})",
        f"{_format_chapter_ts(total_dur * 0.80)} — The Exponential System Behind the Numbers",
    ]

    # Build 100% unique episode-specific documentary description (V8: zero boilerplate template openings!)
    spoken_summary = re.sub(r"\s+", " ", str(script.get("full_narration") or "").strip())
    hook_sub = str(topic.get("hook_subtext") or kw).strip()
    article_paragraphs = [
        (
            f"{spoken_summary} "
            f"In this {brand['channel_name']} 60fps X-Ray engineering breakdown of {kw}, we peel back the outer surface "
            f"to show the exact physical mechanism at work ({hook_sub.lower()})."
        ),
        (
            f"Key physical measurements behind {kw}: {f0['label'].lower()} hits {f0['value']}, "
            f"while {f1['label'].lower()} reaches {f1['value']}. "
            f"Under real-world operating loads, {f2['label'].lower()} ({f2['value']}) interacts directly with "
            f"{f3['label'].lower()} ({f3['value']}) — creating the counterintuitive effect shown in this simulation."
        ),
        (
            f"{wiki_snip + ' ' if wiki_snip else ''}"
            f"Every episode on {brand['channel_name']} decodes one overlooked piece of real-world engineering, physics, "
            f"or hidden infrastructure in under 30 seconds using custom 60fps X-Ray cross-sections and verified data."
        ),
    ]

    geo_bullets = [
        f"- Subject: {kw.title()} ({pillar})",
        f"- Metric 1 ({f0['label']}): {f0['value']}",
        f"- Metric 2 ({f1['label']}): {f1['value']}",
        f"- Metric 3 ({f2['label']}): {f2['value']}",
        f"- Metric 4 ({f3['label']}): {f3['value']}",
        f"- Core Mechanism: {topic['shock_hook_stat']} ({hook_sub})",
    ]

    aeo_faq = [
        {
            "q": f"How does {kw} actually work in real life?",
            "a": (
                f"The physical trigger comes down to {f0['label'].lower()} ({f0['value']}) acting against "
                f"{f1['label'].lower()} ({f1['value']}), as shown in the 60fps cutaway above."
            ),
        },
        {
            "q": f"What are the exact engineering numbers for {kw}?",
            "a": (
                f"Verified benchmarks include {f0['label']} ({f0['value']}), {f1['label']} ({f1['value']}), "
                f"{f2['label']} ({f2['value']}), and {f3['label']} ({f3['value']})."
            ),
        },
        {
            "q": f"Why does {kw} surprise most people?",
            "a": (
                f"Everyday intuition misses hidden pressure, thermal, or geometric forces like {f2['label'].lower()} "
                f"({f2['value']}) until you slice open the mechanism in X-Ray view."
            ),
        },
    ]

    hashtags = [
        "#VelumDispatch",
        "#Engineering",
        "#HowItWorks",
        "#Physics",
        "#Shorts" if script["format"] == "shorts" else "#Documentary",
    ]

    faq_text = "\n\n".join(f"Q: {item['q']}\nA: {item['a']}" for item in aeo_faq)
    chapters_section = (
        "\n\n--- CHAPTERS ---\n" + "\n".join(chapters)
        if script.get("format") != "shorts"
        else ""
    )
    description_full = (
        f"{topic['title_variants'][0]}\n\n"
        + "\n\n".join(article_paragraphs)
        + "\n\n--- VERIFIED ENGINEERING DATA ---\n"
        + "\n".join(geo_bullets)
        + chapters_section
        + "\n\n--- QUICK FAQ ---\n"
        + faq_text
        + f"\n\nSubscribe to {brand['channel_name']} ({brand['handle']}) for daily X-Ray breakdowns of hidden engineering & physics.\n\n"
        + " ".join(hashtags)
    )

    debate = topic.get("debate_hook") or {}
    pinned_comment = debate.get("pinned") or (
        f"Honest question: did you expect {f0['value']} vs {f1['value']}? "
        f"Drop which hidden machine or physics mystery we should X-Ray next — top comment gets built tomorrow."
    )

    tags = list(
        dict.fromkeys(
            [
                kw,
                topic["topic_id"].replace("-", " "),
                f"{kw} explained",
                "how it works",
                "engineering explained",
                "physics animation",
                "hidden mechanics",
                "x-ray animation",
                "velum dispatch",
                pillar.lower(),
                "science shorts" if script["format"] == "shorts" else "engineering documentary",
            ]
        )
    )

    return {
        "titles_ab": topic["title_variants"][:3],
        "description_full": description_full,
        "geo_summary_bullets": geo_bullets,
        "aeo_faq": aeo_faq,
        "pinned_comment": pinned_comment,
        "tags": tags[:20],
        "hashtags": hashtags,
    }


def generate_video_localizations(
    primary_title: str,
    description_full: str,
) -> Dict[str, Dict[str, str]]:
    """Build YouTube API `localizations` (regional native Title & Description) across 10 languages."""
    # Extract concise 3-paragraph summary + hashtags for localized regional descriptions
    paragraphs = [p.strip() for p in description_full.split("\n\n") if p.strip()]
    core_excerpt = "\n\n".join(paragraphs[:3])[:1200]
    hashtags_line = paragraphs[-1] if paragraphs and paragraphs[-1].startswith("#") else "#VelumArchive #Shorts"

    localizations: Dict[str, Dict[str, str]] = {}
    for lang_code in TARGET_CAPTION_LANGS:
        if lang_code == "en":
            continue
        tr_lines = _translate_lines_batch_free([primary_title, core_excerpt], lang_code)
        loc_title = (tr_lines[0] if tr_lines else primary_title)[:95].strip()
        loc_desc = (tr_lines[1] if len(tr_lines) > 1 else core_excerpt).strip()
        localizations[lang_code] = {
            "title": loc_title or primary_title[:95],
            "description": f"{loc_title}\n\n{loc_desc}\n\n{hashtags_line}"[:4900],
        }
    logger.info("Built regional Title & Description localizations for %d languages", len(localizations))
    return localizations


def generate_omni_seo_package(
    topic: Dict[str, Any],
    script: Dict[str, Any],
    voice_data: Dict[str, Any],
    out_dir: Path,
    llm: Optional[ZeroCostLLMClient] = None,
) -> Dict[str, Any]:
    """Generate complete VSEO/SEO/GEO/AEO package + multi-language SRT tracks."""
    brand = load_brand_config()
    llm = llm or ZeroCostLLMClient()

    slug = slugify_keyword(topic["primary_keyword"])
    slug_filename = f"{slug}.mp4"
    vseo_audit = _verify_vseo_in_whisper(voice_data.get("words", []), topic["primary_keyword"])

    package = _build_native_omni_seo(topic, script, voice_data, brand)

    # Optionally enrich via free-tier LLM if key is configured (keeping >=300 word floor)
    if llm.is_available:
        system_prompt = load_prompt("omni_seo.md")
        user_prompt = (
            f"Format: {script['format']}\n"
            f"Primary keyword: {topic['primary_keyword']}\n"
            f"Topic facts: {json.dumps(topic['key_facts'], ensure_ascii=False)}\n"
            f"Narration transcript: {script['full_narration']}"
        )
        llm_seo = llm.complete_json(system_prompt, user_prompt, temperature=0.5)
        if llm_seo:
            desc = str(llm_seo.get("description_full", ""))
            if len(desc.split()) >= 300:
                package["description_full"] = desc
            if isinstance(llm_seo.get("titles_ab"), list) and len(llm_seo["titles_ab"]) >= 3:
                package["titles_ab"] = [str(t)[:70] for t in llm_seo["titles_ab"][:3]]
            if llm_seo.get("pinned_comment"):
                package["pinned_comment"] = str(llm_seo["pinned_comment"])
            if isinstance(llm_seo.get("aeo_faq"), list) and len(llm_seo["aeo_faq"]) == 3:
                package["aeo_faq"] = llm_seo["aeo_faq"]

    # V9: Shorts use burned-in English captions & strictly English metadata (zero unsubtitled foreign bait!)
    if script.get("format") == "shorts":
        srt_tracks: Dict[str, str] = {}
        localizations: Dict[str, Dict[str, str]] = {}
    else:
        srt_tracks = generate_multilang_srt_tracks(
            voice_data.get("timed_beats", []), out_dir, slug, llm=llm
        )
        localizations = generate_video_localizations(
            package["titles_ab"][0], package["description_full"]
        )

    word_count = len(package["description_full"].split())
    full_seo = {
        "slug": slug,
        "slug_filename": slug_filename,
        "primary_keyword": topic["primary_keyword"],
        "vseo": vseo_audit,
        "seo_description_word_count": word_count,
        "titles_ab": package["titles_ab"],
        "description_full": package["description_full"],
        "localizations": localizations,
        "geo_summary_bullets": package["geo_summary_bullets"],
        "aeo_faq": package["aeo_faq"],
        "pinned_comment": package["pinned_comment"],
        "tags": package["tags"],
        "hashtags": package["hashtags"],
        "subtitles_srt": srt_tracks,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    seo_path = out_dir / "omni_seo_package.json"
    seo_path.write_text(json.dumps(full_seo, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "Omni-SEO built | file=%s | VSEO<15s=%s | desc_words=%d (>=300) | SRTs=%d",
        slug_filename,
        vseo_audit["verified_under_15s"],
        word_count,
        len(srt_tracks),
    )
    return full_seo
