"""Context-Aware Human-Like Multilingual Comment Responder (prompts/multilang_reply.md).

Features:
- Fetches new viewer comments across published channel videos via YouTube Data API v3
- Filters spam, links, crypto/Telegram scams, sub4sub, and bot noise
- Auto-approves legitimate viewer comments via `comments().setModerationStatus` so YouTube
  never hides real engagement in 'Held for review'
- Detects viewer language (TR, EN, ES, DE, FR, PT, etc.) and analyzes the exact topic/intent
  mentioned in the comment (money/spending, time/years, physical stack, shock, question, praise)
- Crafts authentic, human-sounding replies (zero robotic em-dashes or repetitive templates)
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from langdetect import DetectorFactory, detect

from core.config import (
    ephemeral_youtube_credentials,
    get_logger,
    has_youtube_credentials,
    load_prompt,
)
from core.llm_client import ZeroCostLLMClient
from core.state_db import StateDB, utc_now_iso
from publisher.youtube_uploader import build_youtube_service

DetectorFactory.seed = 42
logger = get_logger("comment_responder")

SPAM_PATTERNS = [
    re.compile(r"https?://|www\.|t\.me/|wa\.me/|bit\.ly/|tinyurl", re.IGNORECASE),
    re.compile(r"\b(whatsapp|telegram|crypto\s*signal|forex|airdrop|free\s*robux|sub4sub|check\s*my\s*channel)\b", re.IGNORECASE),
    re.compile(r"\+\d{1,3}[\s\-]?\d{3,4}[\s\-]?\d{4,}"),
    re.compile(r"(.)\1{7,}"),
]

TURKISH_HINTS = (
    "çok", "gerçek", "harika", "müthiş", "inanılmaz", "şok", "milyar", "milyon",
    "güzel", "bence", "nasıl", "değil", "abi", "süper", "beyin", "oha", "yuh", "efsane", "kanka", "iyi"
)
SPANISH_HINTS = ("increíble", "gracias", "millones", "mil millones", "impresionante", "nunca", "pensé", "qué", "locura", "buen")
GERMAN_HINTS = ("krass", "unglaublich", "wahnsinn", "milliarde", "danke", "genial", "nicht", "wie", "echt")
FRENCH_HINTS = ("incroyable", "merci", "milliard", "jamais", "dingue", "génial", "vraiment", "fou")


def is_spam_comment(text: str) -> bool:
    """Return True if comment matches bot, link, scam, or empty spam heuristics."""
    cleaned = (text or "").strip()
    if len(cleaned) < 2:
        return True
    if not re.search(r"[A-Za-zÀ-ÿğüşöçıİĞÜŞÖÇ0-9]", cleaned):
        return True
    for pat in SPAM_PATTERNS:
        if pat.search(cleaned):
            return True
    return False


def detect_comment_language(text: str) -> str:
    """Accurately detect viewer comment language, even on short informal comments."""
    low = text.lower()
    if any(ch in low for ch in ("ğ", "ş", "ı")) or any(w in low for w in TURKISH_HINTS):
        return "tr"
    if any(w in low for w in SPANISH_HINTS):
        return "es"
    if any(w in low for w in GERMAN_HINTS):
        return "de"
    if any(w in low for w in FRENCH_HINTS):
        return "fr"
    try:
        code = detect(text)
        return code[:2].lower()
    except Exception:
        return "en"


def _classify_comment_angle(comment_text: str) -> str:
    """Detect what specific aspect of the video the viewer is reacting to."""
    low = comment_text.lower()
    if any(k in low for k in ("273", "10,000", "10k", "10.000", "spend", "harca", "broke", "100 day", "100 gün")):
        return "spending"
    if any(k in low for k in ("31", "11", "second", "saniye", "year", "yıl", "day", "gün", "time", "zaman", "ice age")):
        return "time_scale"
    if any(k in low for k in ("stack", "meter", "km", "kilometer", "burj", "height", "tall", "boy", "kule")):
        return "height_stack"
    if "?" in comment_text or any(k in low for k in ("how", "why", "what if", "nasıl", "neden", "peki")):
        return "question"
    if len(comment_text.strip()) <= 22:
        return "short_reaction"
    return "general"


def _native_multilang_reply(comment_text: str, lang: str, topic_title: str) -> str:
    """Craft a natural, varied, human-sounding reply tailored to what the viewer actually said."""
    angle = _classify_comment_angle(comment_text)
    # Deterministic pick based on comment text hash so different viewers get different phrasing
    seed = int(hashlib.md5(comment_text.encode("utf-8")).hexdigest()[:6], 16)

    en_Pool: Dict[str, List[str]] = {
        "spending": [
            "The $10k a day part broke my head too when I first ran the numbers. 273 years without earning a single cent of interest is wild.",
            "Right? And that's assuming zero investment return. With even 4% interest a billionaire could spend $100k a day and still get richer.",
            "100 days vs 273 years is the one comparison that finally made a billion click for me.",
        ],
        "time_scale": [
            "11 days vs 31.7 years really shows how badly our brains flatten big numbers just because the words sound alike.",
            "Crazy part is jumping one more step to a trillion seconds takes you back 31,700 years to the last Ice Age.",
            "Wild how 'million' and 'billion' only differ by one letter, yet in time it's a two-week vacation vs half a lifetime.",
        ],
        "height_stack": [
            "Visualizing the $100 bills stacked past the Burj Khalifa is still the wildest part to me.",
            "One meter waist-high vs over a kilometer into the clouds really puts that extra three zeros in perspective.",
        ],
        "question": [
            "Good question: our brains evolved to judge linear everyday counts, so exponential 1,000x jumps all blur together in our heads.",
            "It comes down to logarithmic perception. Once a number passes a few thousand, we stop picturing it and just hear 'a lot'.",
            "Basically every extra zero multiplies the whole stack by 10, so three extra zeros is a 1,000x leap.",
        ],
        "short_reaction": [
            "Honestly had the exact same reaction when I first calculated the 31.7 years part.",
            "Our brains really weren't built for three extra zeros.",
            "Wait until you see tomorrow's breakdown, the scale gap gets even crazier.",
            "It really messes with your sense of scale once you see it side by side.",
        ],
        "general": [
            "Glad this one clicked! Putting the numbers side by side is the only way my brain can actually picture the gap.",
            "Appreciate you watching! Always crazy how different huge numbers look once you turn them into time or height.",
            "That gap between a million and a billion hides in plain sight until you map it to real time. What topic should we break down next?",
            "Thanks for dropping a comment! We're building a whole series on hidden scales like this, let me know what you want to see next.",
        ],
    }

    tr_Pool: Dict[str, List[str]] = {
        "spending": [
            "Günde 10 bin dolar harcayıp 273 yıl bitmemesi hesabını ilk yaptığımda ben de inanamadım, üstelik sıfır faizle.",
            "100 gün nerede 273 yıl nerede... Milyon ile milyarın aslında bambaşka gezegenler olduğunu en iyi bu örnek anlatıyor.",
        ],
        "time_scale": [
            "11 gün ile 31.7 yıl farkını görünce insan kelimelerin birbirine bu kadar benzemesine şaşırıyor gerçekten.",
            "İşin daha çılgın kısmı 1 trilyon saniyeye çıkınca tam 31.700 yıl geriye, Buzul Çağı'na gidiyoruz.",
        ],
        "height_stack": [
            "1 milyon doların bel hizasında kalıp 1 milyarın Burj Khalifa'yı geçmesi aradaki 1000 katı en net gösteren detay.",
        ],
        "question": [
            "Çok iyi soru: insan beyni günlük hayatta doğrusal sayılara evrimleştiği için üç sıfır eklendiğinde aradaki 1000 katlık uçurumu sezgiyle hissedemiyor.",
            "Sebebi tamamen beynin büyük sayıları tek bir 'çok büyük' kutusunda sıkıştırması, ta ki zamana veya boyuta çevirene kadar.",
        ],
        "short_reaction": [
            "Vallahi sayıları ilk hesapladığımda benim de tepkim birebir aynıydı :)",
            "İki harf fark var gibi duruyor ama arada koca bir ömür var.",
            "Yarınki bölümde bu ölçek farkının daha da uçuk bir örneği geliyor, takipte kal!",
        ],
        "general": [
            "Çok teşekkürler! Sayıları zamana ve fiziksel boyuta dökünce tablo bir anda bambaşka görünüyor. Sıradaki videoda neyi kıyaslayalım?",
            "Beğenmene çok sevindim, bu tarz görünmeyen sistemleri ve ölçek farklarını her gün seriye devam ettireceğiz.",
            "Kesinlikle, soyut rakamları yan yana koymadan beynimiz aradaki uçurumu tam canlandıramıyor. Yorumun için teşekkürler!",
        ],
    }

    es_Pool = [
        "La diferencia entre 11 días y 31 años es de esas cosas que te cambian la perspectiva por completo.",
        "Tal cual, como las palabras suenan parecido nuestro cerebro no dimensiona que hay un abismo de 1.000x entre ambas.",
        "Gracias por pasarte! Mañana sale otro análisis visual todavía más extremo.",
    ]
    de_Pool = [
        "11 Tage gegen fast 32 Jahre zeigt einfach perfekt, wie sehr unser Gehirn große Zahlen unterschätzt.",
        "Absolut, erst wenn man das in echte Lebenszeit umrechnet, merkt man wie gewaltig drei Nullen mehr sind.",
        "Danke dir! Morgen kommt direkt der nächste visuelle Vergleich.",
    ]
    fr_Pool = [
        "11 jours contre 31 ans, c'est vraiment le comparatif qui fait réaliser l'écart colossal entre les deux.",
        "Carrément, notre cerveau entend deux mots proches alors qu'il y a un facteur 1000 entre les deux.",
        "Merci pour ton commentaire ! La suite arrive dès demain.",
    ]

    if lang == "tr":
        choices = tr_Pool.get(angle, tr_Pool["general"])
    elif lang == "es":
        choices = es_Pool
    elif lang == "de":
        choices = de_Pool
    elif lang == "fr":
        choices = fr_Pool
    else:
        choices = en_Pool.get(angle, en_Pool["general"])

    return choices[seed % len(choices)]


def craft_reply(
    comment_text: str,
    topic_title: str,
    llm: Optional[ZeroCostLLMClient] = None,
) -> Dict[str, Any]:
    """Classify spam, detect exact language, and draft an authentic human creator reply."""
    if is_spam_comment(comment_text):
        return {
            "is_spam": True,
            "detected_lang": "spam",
            "reply_text": "",
        }

    lang = detect_comment_language(comment_text)
    if llm and llm.is_available:
        system_prompt = load_prompt("multilang_reply.md")
        user_prompt = (
            f"Video title: {topic_title}\n"
            f"Detected language hint: {lang}\n"
            f"Viewer comment: {comment_text}"
        )
        res = llm.complete_json(system_prompt, user_prompt, temperature=0.75)
        if res and isinstance(res.get("is_spam"), bool):
            if res["is_spam"]:
                return {"is_spam": True, "detected_lang": "spam", "reply_text": ""}
            reply = str(res.get("reply_text", "")).strip().replace(" — ", ", ").replace("—", ", ")
            if reply:
                return {
                    "is_spam": False,
                    "detected_lang": str(res.get("detected_language", lang))[:5],
                    "reply_text": reply[:240],
                }

    return {
        "is_spam": False,
        "detected_lang": lang,
        "reply_text": _native_multilang_reply(comment_text, lang, topic_title),
    }


def run_comment_cycle(
    state_db: StateDB,
    out_dir: Optional[Path] = None,
    llm: Optional[ZeroCostLLMClient] = None,
) -> Dict[str, Any]:
    """Fetch new comments, approve visibility, and reply naturally in the viewer's language."""
    llm = llm or ZeroCostLLMClient()
    summary: Dict[str, Any] = {
        "mode": "live" if has_youtube_credentials() else "verification_preview",
        "fetched": 0,
        "spam_filtered": 0,
        "queued": 0,
        "sent_now": 0,
        "samples": [],
    }

    if not has_youtube_credentials():
        sample_comments = [
            ("demo_tr_01", "İnanılmaz bir görsel karşılaştırma olmuş, 1 milyar saniyenin 31 yıl ettiğini hiç böyle düşünmemiştim!"),
            ("demo_en_02", "Wait spending $10,000 a day takes 273 YEARS for a billion?? My brain just melted."),
            ("demo_es_03", "Increíble explicación visual, nunca había entendido la diferencia real entre millón y mil millones."),
            ("demo_de_04", "Krass, diese visuelle Darstellung macht den Unterschied sofort klar!"),
            ("demo_spam_05", "FREE CRYPTO SIGNALS join https://t.me/scamchannel123 check my channel sub4sub!!!"),
        ]
        now = datetime.now(timezone.utc)
        for cid, text in sample_comments:
            decision = craft_reply(text, "VELUM Visual Breakdown", llm=llm)
            sched_iso = now.replace(microsecond=0).isoformat()
            summary["fetched"] += 1
            if decision["is_spam"]:
                summary["spam_filtered"] += 1
            else:
                summary["queued"] += 1
            if not state_db.is_comment_processed(cid):
                state_db.record_comment_reply(
                    youtube_comment_id=cid,
                    video_ref="local_verification",
                    detected_lang=decision["detected_lang"],
                    reply_text=decision["reply_text"],
                    is_spam=decision["is_spam"],
                    scheduled_at=sched_iso,
                    status="filtered_spam" if decision["is_spam"] else "scheduled_preview",
                )
            summary["samples"].append(
                {
                    "comment_id": cid,
                    "input_excerpt": text[:90],
                    "is_spam": decision["is_spam"],
                    "detected_lang": decision["detected_lang"],
                    "reply_text": decision["reply_text"],
                }
            )
        if out_dir is not None:
            (out_dir / "comment_bot_report.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return summary

    videos = [v for v in state_db.get_all_videos() if v.get("youtube_id")]
    with ephemeral_youtube_credentials() as (_, token_path):
        if token_path is None:
            return summary
        youtube = build_youtube_service(token_path)

        my_channel_id = ""
        try:
            me_resp = youtube.channels().list(part="id", mine=True).execute()
            me_items = me_resp.get("items", [])
            if me_items:
                my_channel_id = me_items[0]["id"]
        except Exception as exc:
            logger.debug("Could not resolve own channel ID (%s)", type(exc).__name__)

        now = datetime.now(timezone.utc)
        for vid in videos[:10]:
            yt_id = vid["youtube_id"]
            titles = json.loads(vid.get("titles_json", '["VELUM"]'))
            title = titles[0] if titles else "VELUM"

            try:
                st_resp = youtube.videos().list(part="statistics", id=yt_id).execute()
                st_items = st_resp.get("items", [])
                if st_items:
                    stats = st_items[0].get("statistics", {})
                    v_cnt = int(stats.get("viewCount", 0))
                    l_cnt = int(stats.get("likeCount", 0))
                    c_cnt = int(stats.get("commentCount", 0))
                    logger.info(
                        "LIVE STATS [%s] -> views=%d | likes=%d | comments=%d",
                        yt_id,
                        v_cnt,
                        l_cnt,
                        c_cnt,
                    )
                    if v_cnt > 0:
                        state_db.update_video_metrics(
                            vid["video_uid"], v_cnt, float(vid.get("avg_view_pct", 0.0)), float(vid.get("ctr", 0.0))
                        )
            except Exception as exc:
                logger.debug("Stats check skipped for %s (%s)", yt_id, type(exc).__name__)

            try:
                resp = youtube.commentThreads().list(
                    part="snippet",
                    videoId=yt_id,
                    maxResults=25,
                    order="time",
                    textFormat="plainText",
                ).execute()
            except Exception as exc:
                logger.warning("Could not fetch comments for %s (%s)", yt_id, type(exc).__name__)
                continue

            for item in resp.get("items", []):
                top = item["snippet"]["topLevelComment"]
                cid = top["id"]
                author_ch = top["snippet"].get("authorChannelId", {}).get("value", "")
                if my_channel_id and author_ch == my_channel_id:
                    continue
                if state_db.is_comment_processed(cid):
                    continue
                summary["fetched"] += 1
                text = top["snippet"].get("textDisplay", "")
                decision = craft_reply(text, title, llm=llm)
                sched_iso = now.replace(microsecond=0).isoformat()
                if decision["is_spam"]:
                    summary["spam_filtered"] += 1
                    state_db.record_comment_reply(cid, yt_id, "spam", "", True, sched_iso, status="filtered_spam")
                else:
                    # Approve comment visibility on channel via official API
                    try:
                        youtube.comments().setModerationStatus(
                            id=cid, moderationStatus="published"
                        ).execute()
                    except Exception as exc:
                        logger.debug("Moderation publish skipped (%s)", type(exc).__name__)

                    sent_ok = False
                    try:
                        youtube.comments().insert(
                            part="snippet",
                            body={
                                "snippet": {
                                    "parentId": cid,
                                    "textOriginal": decision["reply_text"],
                                }
                            },
                        ).execute()
                        sent_ok = True
                        summary["sent_now"] += 1
                        logger.info(
                            "Replied to viewer comment (%s) on %s -> %s",
                            decision["detected_lang"],
                            yt_id,
                            decision["reply_text"],
                        )
                    except Exception as exc:
                        summary["queued"] += 1
                        logger.warning("Immediate reply deferred to queue (%s)", type(exc).__name__)

                    state_db.record_comment_reply(
                        cid,
                        yt_id,
                        decision["detected_lang"],
                        decision["reply_text"],
                        False,
                        sched_iso,
                        status="sent" if sent_ok else "scheduled",
                        replied_at=sched_iso if sent_ok else None,
                    )

        due = state_db.get_due_comment_replies(utc_now_iso())
        for row in due[:15]:
            try:
                youtube.comments().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "parentId": row["youtube_comment_id"],
                            "textOriginal": row["reply_text"],
                        }
                    },
                ).execute()
                state_db.mark_comment_replied(row["comment_hash"])
                summary["sent_now"] += 1
            except Exception as exc:
                logger.warning("Reply send error for %s (%s)", row["comment_hash"], type(exc).__name__)

    logger.info(
        "Live comment cycle done | fetched=%d | spam=%d | queued=%d | sent=%d",
        summary["fetched"],
        summary["spam_filtered"],
        summary["queued"],
        summary["sent_now"],
    )
    return summary
