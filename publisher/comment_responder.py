"""Topic-Aware Human-Like Multilingual Comment Responder (prompts/multilang_reply.md).

Features:
- Fetches new viewer comments across published channel videos via YouTube Data API v3
- Filters spam, links, crypto/Telegram scams, sub4sub, and bot noise
- Auto-approves legitimate viewer comments via `comments().setModerationStatus` so YouTube
  never hides real engagement in 'Held for review'
- Resolves every video's actual topic record from `state.db` (`topics.payload_json` +
  `videos.titles_json`) including title, primary_keyword, key_facts, and debate_hook
- Detects viewer language (EN, TR, ES, DE, FR, etc.) and classifies intent (picked
  option_a vs option_b, question, disbelief, short reaction, or general comment)
- Crafts authentic, varied, topic-grounded human replies with zero em-dashes and zero
  hardcoded cross-video leakage
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote

import requests
from langdetect import DetectorFactory, detect

from core.config import (
    ephemeral_youtube_credentials,
    get_logger,
    has_youtube_credentials,
    load_prompt,
)
from core.llm_client import ZeroCostLLMClient
from core.state_db import StateDB, utc_now_iso
from engine.idea_engine import CURATED_BLUEPRINTS
from publisher.youtube_uploader import build_youtube_service

WIKI_HARVEST_UA = "VelumBroadcastEngine/4.2 (https://github.com/MFTTT11/velum-studio; educational)"
VIEWER_IDEAS_MAX_QUEUE = 10

IDEA_REQUEST_PATTERNS = [
    re.compile(r"(?:next\s+video|topic\s+idea|video\s+idea|suggestion|idea|s[ıi]radaki|öneri)\s*[:\-]\s*([A-Za-zÀ-ÿğüşöçıİĞÜŞÖÇ0-9\s,'\-]{4,70}?)(?:[.!?]|$)", re.IGNORECASE),
    re.compile(r"(?:make\s+a\s+video\s+(?:about|on)|do\s+(?:a\s+video\s+(?:about|on)\s+)?|explain|break\s+down|cover|talk\s+about)\s+([A-Za-z0-9\s,'\-]{4,70}?)(?:\s+next|\s+please|\s+pls|[.!?]|$)", re.IGNORECASE),
    re.compile(r"(?:you\s+should\s+(?:do|cover|explain|try)|can\s+you\s+(?:do|explain|cover))\s+([A-Za-z0-9\s,'\-]{4,70}?)(?:\s+next|\s+please|\s+pls|[.!?]|$)", re.IGNORECASE),
    re.compile(r"(?:what\s+(?:if|about)|how\s+(?:does|do|much|fast|deep|long|big)|why\s+(?:does|do|is|are|can'?t))\s+([A-Za-z0-9\s,'\-]{5,75}?)(?:[.!?]|$)", re.IGNORECASE),
    re.compile(r"([A-Za-zÀ-ÿğüşöçıİĞÜŞÖÇ0-9\s,'\-]{4,65}?)\s+(?:hakkında\s+video|anlat(?:ır\s*mısın|sana|ın)?|konusunu\s+işle|videosu\s+yap)", re.IGNORECASE),
    re.compile(r"(?:peki|acaba)\s+([A-Za-zÀ-ÿğüşöçıİĞÜŞÖÇ0-9\s,'\-]{5,70}?)(?:\s+ne\s+olur|\s+nasıl|\s+neden|[.!?]|$)", re.IGNORECASE),
]

NON_IDEA_NOISE = {
    "this", "that", "it", "more", "next", "part 2", "part two", "video", "short", "shorts",
    "this video", "something", "anything", "everything", "nothing", "true", "false", "fake",
    "real", "good", "great", "nice", "cool", "wow", "lol", "bro", "first", "yes", "no",
    "amazing", "awesome", "incredible", "interesting", "fascinating", "thanks", "thank",
    "please", "really", "actually", "literally", "someone", "everyone", "people", "watching",
    "channel", "subscribe", "subscribed", "comment", "comments", "explain", "better", "crazy",
    "insane", "unreal", "wild", "mind", "blown", "awesome", "fantastic", "perfect",
    "bunu", "şunu", "böyle", "devam", "harika", "süper", "efsane", "muhteşem", "teşekkür",
    "teşekkürler", "gerçekten", "inanılmaz", "izledim", "abone", "güzel", "müthiş",
}

LEADING_IDEA_FILLERS = re.compile(
    r"^(?:abi|hocam|kanka|lütfen|bir\s+de|bence|acaba|peki|hey|yo|bro|please|pls|the|a|an)\s+",
    re.IGNORECASE,
)

PILLAR_KEYWORDS = {
    "money_scale": ("money", "dollar", "billion", "trillion", "gold", "bank", "debt", "economy", "wealth", "tax", "market", "inflation", "bitcoin", "crypto", "stock", "currency", "price", "cost", "rich", "coin"),
    "hidden_tech": ("internet", "cable", "satellite", "chip", "processor", "airplane", "plane", "rocket", "engine", "battery", "grid", "nuclear", "submarine", "ship", "bridge", "tunnel", "skyscraper", "computer", "ai", "algorithm", "radar", "gps", "laser", "reactor"),
    "mind_glitches": ("brain", "psychology", "bias", "illusion", "memory", "dopamine", "casino", "sleep", "dream", "fear", "habit", "attention", "decision", "perception", "placebo", "effect", "paradox", "trapped", "addiction"),
    "science_anomalies": ("space", "planet", "star", "black hole", "sun", "moon", "mars", "venus", "jupiter", "earth", "ocean", "trench", "volcano", "radiation", "quantum", "atom", "gravity", "speed", "light", "pressure", "temperature", "ice", "earthquake", "tsunami", "virus", "dna", "human body"),
}

DetectorFactory.seed = 42
logger = get_logger("comment_responder")

SPAM_PATTERNS = [
    re.compile(r"https?://|www\.|t\.me/|wa\.me/|bit\.ly/|tinyurl", re.IGNORECASE),
    re.compile(
        r"\b(whatsapp|telegram|crypto\s*signal|forex|airdrop|free\s*robux|sub4sub|check\s*my\s*channel)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\+\d{1,3}[\s\-]?\d{3,4}[\s\-]?\d{4,}"),
    re.compile(r"(.)\1{7,}"),
]

TURKISH_HINTS = (
    "çok", "gerçek", "harika", "müthiş", "inanılmaz", "şok", "güzel", "bence",
    "nasıl", "değil", "abi", "süper", "beyin", "oha", "yuh", "efsane", "kanka",
    "iyi", "asla", "kesinlikle", "bilmiyordum", "biliyordum", "ciddi", "yalan",
    "uçak", "altın", "ekonomi", "çöker", "hayır", "evet", "acaba", "neden",
)
SPANISH_HINTS = (
    "increíble", "gracias", "impresionante", "nunca", "pensé", "qué", "locura",
    "buen", "imposible", "sabía", "cómo", "por qué", "mentira", "jamás", "avión",
)
GERMAN_HINTS = (
    "krass", "unglaublich", "wahnsinn", "danke", "genial", "nicht", "wie", "echt",
    "niemals", "warum", "wirklich", "flugzeug", "wusste", "irre", "verrückt",
)
FRENCH_HINTS = (
    "incroyable", "merci", "jamais", "dingue", "génial", "vraiment", "fou",
    "pourquoi", "comment", "impossible", "avion", "savais", "carrément", "truc",
)

UPPERCASE_ACRONYMS = {"NASA", "ISS", "GPS", "DNA", "US", "UK", "AI", "DNS", "EUV", "ASML", "ATM", "ETF", "USD", "TEU"}

MULTILANG_STANCE_SYNONYMS: Dict[str, Tuple[str, ...]] = {
    "crash": ("crash", "collapse", "wreck", "ruin", "worthless", "çöker", "çökert", "batar", "colaps", "stürz", "effondr"),
    "save": ("save", "rich", "help", "fix", "kurtar", "zengin", "salv", "rett", "sauv"),
    "no": ("no chance", "never", "nope", "not a chance", "asla", "hayır", "imkansız", "nunca", "jamás", "nie", "niemals", "jamais"),
    "yes": ("yes", "definitely", "sign me up", "once", "evet", "kesinlikle", "giderim", "sí", "claro", "ja", "oui", "carrément"),
    "idea": ("no idea", "didn't know", "didnt know", "never knew", "bilmiyordum", "fikrim yok", "haberim yok", "ni idea", "no sabía", "keine ahnung", "wusste nicht", "aucune idée", "savais pas"),
    "knew": ("knew it", "already knew", "i knew", "biliyordum", "bildiğim", "ya lo sabía", "wusste ich", "je savais"),
    "gold": ("gold", "altın", "oro", "or "),
    "bitcoin": ("bitcoin", "btc", "kripto", "crypto"),
    "mars": ("mars", "marte"),
    "mantle": ("mantle", "manto", "manto", "mantel", "manteau", "yerin altı"),
    "earth": ("earth", "stay", "dünya", "tierra", "erde", "terre"),
    "ban": ("ban", "illegal", "yasak", "prohib", "verbiet", "interdir"),
    "legal": ("keep legal", "legal", "serbest", "yasal", "erlaubt"),
    "tailgaters": ("tailgat", "yakın takip", "dibine", "pegado", "drängler", "colle"),
    "slow": ("slow", "left lane", "yavaş", "sol şerit", "lento", "langsam", "lent"),
    "myth": ("myth", "fake", "efsane", "yalan", "mito", "mythos", "mythe"),
    "real": ("real", "true", "gerçek", "verdad", "echt", "vrai"),
    "guilty": ("guilty", "under my pillow", "every night", "suçluyum", "ben de", "culpable", "schuldig", "coupable"),
}

QUESTION_WORDS = (
    "how", "why", "what if", "what about", "wait how", "is it true", "does it", "can you",
    "nasıl", "neden", "niye", "peki", "acaba", "hangi", "kaç",
    "cómo", "por qué", "qué pasa", "cuánto",
    "wie", "warum", "was wäre", "stimmt es",
    "pourquoi", "comment", "est-ce que", "combien",
)

DISBELIEF_WORDS = (
    "no way", "fake", "cap", "impossible", "unreal", "insane", "crazy", "wild", "mind blown",
    "melted", "bs", "lie", "can't believe", "cant believe", "ain't no way", "aint no way",
    "inanılmaz", "imkansız", "yalan", "oha", "yuh", "şaka", "ciddi mi", "gerçek mi", "aklım almıyor",
    "increíble", "imposible", "mentira", "locura", "no puede ser",
    "unglaublich", "krass", "wahnsinn", "unmöglich", "echt jetzt", "lüge",
    "incroyable", "dingue", "fou", "impossible", "n'importe quoi", "vraiment",
)


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
    if any(ch in low for ch in ("¿", "¡", "ñ")) or any(w in low for w in SPANISH_HINTS):
        return "es"
    if any(ch in low for ch in ("ß", "ä")) or any(w in low for w in GERMAN_HINTS):
        return "de"
    if any(w in low for w in FRENCH_HINTS):
        return "fr"
    try:
        code = detect(text)
        return code[:2].lower()
    except Exception:
        return "en"


def _sanitize_human_reply(text: str) -> str:
    """Strip em-dashes and extra whitespace so replies read like natural human comments."""
    cleaned = text.replace(" — ", ", ").replace("—", ", ").replace(" – ", ", ")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned[:240]


def _humanize_phrase(raw: str) -> str:
    """Convert shouty ALL-CAPS labels/values into clean conversational casing."""
    text = re.sub(r"\s+", " ", (raw or "").strip())
    if not text:
        return ""
    tokens = text.split(" ")
    out: List[str] = []
    for tok in tokens:
        bare = re.sub(r"[^A-Za-z0-9]", "", tok)
        if bare.upper() in UPPERCASE_ACRONYMS:
            out.append(tok.upper())
        elif tok.upper() == "MILLISEC":
            out.append("ms")
        elif tok.upper() == "CELSIUS":
            out.append("°C")
        elif tok.upper() == "KM/H":
            out.append("km/h")
        elif tok.upper() == "KM/S":
            out.append("km/s")
        elif tok.upper() == "G/CM3":
            out.append("g/cm³")
        elif tok.isupper() and sum(ch.isalpha() for ch in bare) > 1:
            out.append(tok.lower())
        else:
            out.append(tok)
    joined = " ".join(out)
    joined = re.sub(r"\s+°C", "°C", joined)
    return joined


def _clean_topic_subject(topic_title: str, primary_keyword: str = "") -> str:
    """Extract a crisp, readable topic subject without slug hyphens or clickbait brackets."""
    src = (primary_keyword or "").strip() or (topic_title or "").strip()
    if not src:
        return "this one"
    # If src looks like a slug (e.g. 'asteroid-psyche'), turn hyphens into spaces
    if "-" in src and " " not in src:
        src = src.replace("-", " ")
    src = re.sub(r"\([^)]*\)", "", src).strip()
    if ":" in src and len(src) > 42:
        src = src.split(":", 1)[0].strip()
    src = re.sub(r"\s+", " ", src).strip(" -.,!?")
    if len(src) > 48:
        words = src.split()
        trimmed: List[str] = []
        for w in words:
            if len(" ".join(trimmed + [w])) <= 46:
                trimmed.append(w)
            else:
                break
        src = " ".join(trimmed)
    return src or "this breakdown"


def _match_blueprint_for_title(topic_title: str) -> Optional[Dict[str, Any]]:
    """Best-effort lookup of a curated blueprint when topic_context wasn't passed explicitly."""
    needle = (topic_title or "").strip().lower()
    if not needle:
        return None

    needle_slug = re.sub(r"[^a-z0-9]+", "-", needle).strip("-")
    needle_tokens = {tok for tok in re.findall(r"[a-z0-9]+", needle) if len(tok) >= 3}

    best_bp: Optional[Dict[str, Any]] = None
    best_score = 0

    for bp in CURATED_BLUEPRINTS:
        tid = bp["topic_id"].lower()
        if needle == tid or needle_slug == tid:
            return bp
        for tv in bp.get("title_variants", []):
            if needle == tv.lower():
                return bp

        bp_tokens = set(re.findall(r"[a-z0-9]+", tid)) | set(
            re.findall(r"[a-z0-9]+", bp.get("primary_keyword", "").lower())
        )
        bp_tokens = {tok for tok in bp_tokens if len(tok) >= 3}
        if not needle_tokens:
            continue
        overlap = needle_tokens & bp_tokens
        # Require strong match: all tokens of a short query (e.g. 'gold-cube', 'asteroid-psyche')
        # or at least 3 meaningful overlapping tokens for full titles
        if (len(needle_tokens) >= 2 and overlap == needle_tokens) or len(overlap) >= 3:
            score = len(overlap) * 10 + (5 if needle_slug and needle_slug in tid else 0)
            if score > best_score:
                best_score = score
                best_bp = bp

    return best_bp


def _resolve_topic_context(
    topic_title: str,
    topic_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build an idempotent, normalized topic context with title, keyword, facts, and debate."""
    ctx: Dict[str, Any] = dict(topic_context) if isinstance(topic_context, dict) else {}
    is_already_normalized = "facts" in ctx and "debate" in ctx and "subject" in ctx

    existing_facts = (
        ctx.get("key_facts")
        if isinstance(ctx.get("key_facts"), list) and ctx.get("key_facts")
        else (ctx.get("facts") if isinstance(ctx.get("facts"), list) else [])
    )
    existing_debate = (
        ctx.get("debate_hook")
        if isinstance(ctx.get("debate_hook"), dict) and any(str(v).strip() for v in ctx["debate_hook"].values())
        else (ctx.get("debate") if isinstance(ctx.get("debate"), dict) else {})
    )
    has_debate = any(str(existing_debate.get(k, "")).strip() for k in ("question", "option_a", "option_b"))

    if not is_already_normalized and not existing_facts and not has_debate:
        matched = _match_blueprint_for_title(topic_title)
        if matched:
            for k in ("topic_id", "primary_keyword", "key_facts", "debate_hook", "shock_hook_stat", "pillar"):
                ctx.setdefault(k, matched.get(k))
            if not ctx.get("title") and matched.get("title_variants"):
                ctx["title"] = matched["title_variants"][0]
            existing_facts = ctx.get("key_facts") if isinstance(ctx.get("key_facts"), list) else []
            existing_debate = ctx.get("debate_hook") if isinstance(ctx.get("debate_hook"), dict) else {}

    title = str(ctx.get("title") or topic_title or "").strip()
    primary_kw = str(ctx.get("primary_keyword") or "").strip()
    facts: List[Dict[str, str]] = []
    for f in existing_facts[:4]:
        if isinstance(f, dict) and f.get("value"):
            facts.append(
                {
                    "label": _humanize_phrase(str(f.get("label", ""))),
                    "value": _humanize_phrase(str(f.get("value", ""))),
                }
            )

    debate = {
        "question": str(existing_debate.get("question", "")).strip(),
        "option_a": _humanize_phrase(str(existing_debate.get("option_a", ""))),
        "option_b": _humanize_phrase(str(existing_debate.get("option_b", ""))),
    }

    subject = str(ctx.get("subject") or "").strip() or _clean_topic_subject(title, primary_kw)
    return {
        "topic_id": str(ctx.get("topic_id", "")),
        "title": title,
        "subject": subject,
        "primary_keyword": primary_kw,
        "facts": facts,
        "debate": debate,
    }


def _load_topic_context(state_db: StateDB, video_row: Dict[str, Any]) -> Dict[str, Any]:
    """Load the video's actual topic record from state_db (topics.payload_json + videos.titles_json)."""
    titles: List[str] = []
    try:
        parsed_titles = json.loads(video_row.get("titles_json", "[]"))
        if isinstance(parsed_titles, list):
            titles = [str(t) for t in parsed_titles if t]
    except json.JSONDecodeError:
        titles = []

    active_idx = int(video_row.get("active_variant", 0))
    live_title = (
        titles[active_idx]
        if 0 <= active_idx < len(titles)
        else (titles[0] if titles else str(video_row.get("topic_id", "")))
    )

    topic_payload: Dict[str, Any] = {}
    topic_id = str(video_row.get("topic_id", ""))
    if topic_id:
        with state_db._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM topics WHERE topic_id = ?",
                (topic_id,),
            ).fetchone()
        if row:
            try:
                topic_payload = json.loads(row["payload_json"])
            except json.JSONDecodeError:
                topic_payload = {}

    topic_payload["title"] = live_title
    return _resolve_topic_context(live_title, topic_payload)


def _match_option_score(comment_low: str, option_text: str) -> int:
    """Score how strongly a viewer comment aligns with one of the video's debate options."""
    opt_low = option_text.strip().lower()
    if not opt_low:
        return 0
    score = 0
    if opt_low in comment_low:
        score += 5

    opt_tokens: Set[str] = {tok for tok in re.findall(r"[a-z0-9]+", opt_low) if len(tok) >= 2}
    comment_tokens: Set[str] = set(re.findall(r"[a-z0-9ğüşöçı]+", comment_low))
    for tok in opt_tokens:
        if len(tok) >= 3 and tok in comment_tokens:
            score += 3
        elif tok in ("no", "yes") and tok in comment_tokens:
            score += 2

    # Check multilingual synonym cues linked to this option's concepts
    for key, synonyms in MULTILANG_STANCE_SYNONYMS.items():
        if key in opt_low:
            if any(syn in comment_low for syn in synonyms):
                score += 4
    return score


def _classify_comment_intent(comment_text: str, ctx: Dict[str, Any]) -> str:
    """Classify viewer comment against the actual video's debate options and tone."""
    low = comment_text.lower().strip()
    opt_a = ctx["debate"].get("option_a", "")
    opt_b = ctx["debate"].get("option_b", "")

    score_a = _match_option_score(low, opt_a)
    score_b = _match_option_score(low, opt_b)
    if score_a > score_b and score_a >= 3:
        return "picked_a"
    if score_b > score_a and score_b >= 3:
        return "picked_b"

    if "?" in comment_text or any(w in low for w in QUESTION_WORDS):
        return "question"
    if any(w in low for w in DISBELIEF_WORDS):
        return "disbelief"
    if len(comment_text.strip()) <= 24:
        return "short_reaction"
    return "general"


def _native_multilang_reply(
    comment_text: str,
    lang: str,
    topic_title: str,
    topic_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Craft a natural, varied, topic-aware human reply grounded in the video's actual facts."""
    ctx = _resolve_topic_context(topic_title, topic_context)
    intent = _classify_comment_intent(comment_text, ctx)
    seed_input = f"{ctx.get('topic_id') or topic_title}|{comment_text}"
    seed = int(hashlib.md5(seed_input.encode("utf-8")).hexdigest()[:6], 16)

    subject = ctx["subject"]
    facts = ctx["facts"]
    f0_val = facts[0]["value"] if len(facts) > 0 else ""
    f0_lbl = facts[0]["label"] if len(facts) > 0 else ""
    f1_val = facts[1]["value"] if len(facts) > 1 else ""
    f1_lbl = facts[1]["label"] if len(facts) > 1 else ""
    f2_val = facts[2]["value"] if len(facts) > 2 else ""

    opt_a = ctx["debate"].get("option_a", "")
    opt_b = ctx["debate"].get("option_b", "")
    has_facts = bool(f0_val and f1_val)
    has_debate = bool(opt_a and opt_b)

    if lang == "tr":
        if intent == "picked_a" and has_debate:
            choices = [
                f"Açıkçası ben de '{opt_a}' tarafındayım, {f0_val} ile {f1_val} yan yana gelince '{opt_b}' pek gerçekçi durmuyor."
                if has_facts
                else f"Ben de '{opt_a}' seçeneğine daha yakınım açıkçası. Çoğu kişi tersini bekliyor ama mantıklı olan bu.",
                f"'{opt_a}' diyenler genelde haklı çıkıyor burada. {f0_val} detayı tüm hesabı değiştiriyor."
                if f0_val
                else f"'{opt_a}' seçimi bence de en mantıklısı, {subject} konusunda tablo çok net.",
            ]
        elif intent == "picked_b" and has_debate:
            choices = [
                f"'{opt_b}' tarafını seçen çok kişi var, özellikle {f1_val} kısmını düşününce kulağa mantıklı geliyor."
                if f1_val
                else f"'{opt_b}' bayağı güçlü bir görüş, yorumlarda iki taraf da bayağı bölündü.",
                f"Güzel bakış açısı, '{opt_a}' ile '{opt_b}' arasında herkes ikiye ayrılmış durumda. Sence en belirleyici detay hangisi?",
            ]
        elif intent == "question":
            choices = [
                f"Güzel soru, olayın özü {f0_val} ile {f1_val} arasındaki farkta gizli. İkisini yan yana koyunca bütün sistem netleşiyor."
                if has_facts
                else f"Güzel soru, {subject} konusunda bütün olay aslında gözle görülmeyen bu oran farkından kaynaklanıyor.",
                f"Kısaca şöyle: burada kritik sınır {f0_val} noktası, onu aştığında her şey bambaşka çalışıyor. Aklına takılan başka bir konu var mı?"
                if f0_val
                else f"Kısaca işin sırrı {subject} içindeki fiziksel sınırlar. Bunu ayrı bir videoda daha derin açalım mı?",
            ]
        elif intent == "disbelief":
            choices = [
                f"İlk araştırırken ben de gerçek olamaz dedim, {f0_val} ile {f1_val} farkını iki kez kontrol ettim."
                if has_facts
                else f"İlk gördüğümde benim de tepkim aynıydı, {subject} gerçekten insanın aklını zorluyor.",
                f"Kulağa şaka gibi geliyor ama {f0_val} rakamı tamamen gerçek. {f2_val} detayı işin tuzu biberi."
                if f0_val and f2_val
                else f"Gerçekten kulağa imkansız gibi geliyor değil mi, rakamları yan yana görmeden inanmak zor.",
            ]
        elif intent == "short_reaction":
            choices = [
                f"Vallahi {f0_val} detayını ilk hesapladığımda benim de tepkim birebir aynıydı."
                if f0_val
                else f"Vallahi {subject} konusunu hazırlarken ben de aynı şaşkınlığı yaşadım.",
                f"{f0_val} ve {f1_val} yan yana gelince insanın algısı şaşıyor gerçekten. Sırada neyi inceleyelim?"
                if has_facts
                else f"Gerçekten çok acayip bir detay değil mi? Sıradaki videoda ne görmek istersin?",
                f"Bunu duyunca insanın tekrar bakası geliyor. Sence {opt_a} mı yoksa {opt_b} mı?"
                if has_debate
                else f"Rakamları yan yana koyunca bambaşka bir tablo çıkıyor ortaya.",
            ]
        else:
            choices = [
                f"Aynen öyle, {f0_val} ile {f1_val} arasındaki farkı görünce bakış açısı tamamen değişiyor."
                if has_facts
                else f"Aynen öyle, {subject} konusundaki gerçek rakamlar insanı hep şaşırtıyor.",
                f"Yorumun için sağ ol! {f0_val} kısmını araştırırken ben de bayağı şaşırmıştım. Sırada hangi konuyu açalım?"
                if f0_val
                else f"Yorumun için sağ ol! Bir sonraki bölümde hangi gizli sistemi inceleyelim?",
                f"Kesinlikle katılıyorum, {subject} konusunda çoğu kişi bu detayı hiç fark etmiyor.",
            ]
    elif lang == "es":
        if intent == "picked_a" and has_debate:
            choices = [
                f"Yo también me inclino por '{opt_a}', viendo {f0_val} frente a {f1_val} cuesta defender la otra opción."
                if has_facts
                else f"También votaría por '{opt_a}', los comentarios están súper divididos con esto.",
            ]
        elif intent == "picked_b" and has_debate:
            choices = [
                f"Tiene bastante sentido elegir '{opt_b}', sobre todo por ese dato de {f1_val}."
                if f1_val
                else f"Buen punto con '{opt_b}', aquí nadie se pone de acuerdo.",
            ]
        elif intent == "question":
            choices = [
                f"Buena pregunta, todo se explica al comparar {f0_val} con {f1_val} en {subject}."
                if has_facts
                else f"Buena pregunta, en {subject} todo cambia por la escala real que casi nunca vemos.",
            ]
        elif intent == "disbelief":
            choices = [
                f"Parece mentira, ¿verdad? Tuve que verificar ese dato de {f0_val} dos veces antes de subirlo."
                if f0_val
                else f"Suena irreal al principio, {subject} siempre deja a todos dudando.",
            ]
        elif intent == "short_reaction":
            choices = [
                f"Literalmente tuve la misma reacción cuando vi lo de {f0_val}."
                if f0_val
                else f"Tuve exactamente la misma reacción preparando este video sobre {subject}.",
                f"Cuesta asimilar {f0_val} contra {f1_val} hasta que lo ves así. ¿Qué tema analizamos luego?"
                if has_facts
                else "Cuando ves los datos lado a lado cambia todo. ¿Qué deberíamos analizar después?",
            ]
        else:
            choices = [
                f"Totalmente, ver {f0_val} junto a {f1_val} hace que todo encaje al instante."
                if has_facts
                else f"Totalmente, {subject} tiene cifras que nadie imagina hasta verlas comparadas.",
                f"Me alegra que te haya gustado! ¿Qué otro tema de este estilo te gustaría ver?",
            ]
    elif lang == "de":
        if intent == "picked_a" and has_debate:
            choices = [
                f"Ich tendiere auch klar zu '{opt_a}', bei {f0_val} gegen {f1_val} ist der Unterschied einfach riesig."
                if has_facts
                else f"Bin da auch eher bei '{opt_a}', die Kommentare sind komplett gespalten.",
            ]
        elif intent == "picked_b" and has_debate:
            choices = [
                f"Kann man gut vertreten mit '{opt_b}', gerade wegen der {f1_val}."
                if f1_val
                else f"Guter Punkt für '{opt_b}', die Meinungen gehen hier echt weit auseinander.",
            ]
        elif intent == "question":
            choices = [
                f"Gute Frage, entscheidend ist hier das Verhältnis zwischen {f0_val} und {f1_val}."
                if has_facts
                else f"Gute Frage, bei {subject} liegt der Kern genau in dieser extremen Größenordnung.",
            ]
        elif intent == "disbelief":
            choices = [
                f"Klingt echt verrückt, oder? Ich musste die {f0_val} selbst zweimal nachrechnen."
                if f0_val
                else f"Klingt erstmal komplett unrealistisch, bei {subject} staunt man echt.",
            ]
        elif intent == "short_reaction":
            choices = [
                f"Genau so habe ich auch geschaut, als ich das mit {f0_val} gesehen habe."
                if f0_val
                else f"Ging mir beim Recherchieren zu {subject} genauso.",
                f"{f0_val} neben {f1_val} lässt einen echt kurz stutzen. Welches Thema soll als Nächstes kommen?"
                if has_facts
                else "Im direkten Vergleich wirken solche Zahlen einfach komplett anders.",
            ]
        else:
            choices = [
                f"Absolut, erst wenn man {f0_val} und {f1_val} direkt nebeneinander sieht, macht es klick."
                if has_facts
                else f"Absolut, bei {subject} unterschätzt man die echten Zahlen fast immer.",
                "Freut mich, dass der Vergleich hängen geblieben ist! Welches Thema sollen wir als Nächstes knacken?",
            ]
    elif lang == "fr":
        if intent == "picked_a" and has_debate:
            choices = [
                f"Je penche aussi pour '{opt_a}', quand on met {f0_val} face à {f1_val} ça change tout."
                if has_facts
                else f"Je suis plutôt du côté '{opt_a}' aussi, les avis sont très partagés ici.",
            ]
        elif intent == "picked_b" and has_debate:
            choices = [
                f"C'est un vrai argument pour '{opt_b}', surtout avec ce chiffre de {f1_val}."
                if f1_val
                else f"Bien vu pour '{opt_b}', le débat dans les commentaires est serré.",
            ]
        elif intent == "question":
            choices = [
                f"Bonne question, tout repose sur l'écart entre {f0_val} et {f1_val} dans ce cas précis."
                if has_facts
                else f"Bonne question, sur {subject} tout vient de cet ordre de grandeur qu'on imagine mal.",
            ]
        elif intent == "disbelief":
            choices = [
                f"Ça paraît fou hein ? J'ai vérifié ce chiffre de {f0_val} deux fois avant de monter la vidéo."
                if f0_val
                else f"Ça a l'air totalement irréel au premier abord, {subject} surprend tout le monde.",
            ]
        elif intent == "short_reaction":
            choices = [
                f"J'ai eu exactement la même réaction en tombant sur le chiffre de {f0_val}."
                if f0_val
                else f"Même réaction ici en préparant cet épisode sur {subject}.",
                f"Voir {f0_val} à côté de {f1_val} remet vite les idées en place. Quel sujet tu veux ensuite ?"
                if has_facts
                else "En comparant les vrais chiffres côte à côte, ça saute tout de suite aux yeux.",
            ]
        else:
            choices = [
                f"Carrément, poser {f0_val} face à {f1_val} rend le phénomène beaucoup plus concret."
                if has_facts
                else f"Carrément, sur {subject} on réalise rarement l'échelle réelle sans comparaison visuelle.",
                "Merci pour ton retour ! Quel système caché tu aimerais qu'on décortique demain ?",
            ]
    else:
        # English (primary global language)
        if intent == "picked_a" and has_debate:
            choices = [
                f"Honestly leaning toward '{opt_a}' too. Looking at {f0_val} next to {f1_val}, '{opt_b}' feels like a tough sell."
                if has_facts
                else f"Honestly leaning toward '{opt_a}' too. Comments are split right down the middle on this one.",
                f"Hard to argue with '{opt_a}' once you see {f0_lbl} sitting at {f0_val}. What made you pick that side?"
                if f0_lbl and f0_val
                else f"Hard to argue with '{opt_a}' on {subject}. Most people guess the opposite at first.",
            ]
        elif intent == "picked_b" and has_debate:
            choices = [
                f"You might be onto something with '{opt_b}', especially once {f1_lbl} hits {f1_val}."
                if f1_lbl and f1_val
                else f"Fair take on '{opt_b}', this one has people debating hard in the comments.",
                f"Respect for backing '{opt_b}' over '{opt_a}'. Once you factor in {f1_val}, it's closer than people think."
                if f1_val
                else f"Interesting call picking '{opt_b}' over '{opt_a}'. Think most people would agree with you?",
            ]
        elif intent == "question":
            choices = [
                f"Good question, the short version comes down to {f0_lbl} ({f0_val}) versus {f1_lbl} ({f1_val}). Put those side by side and the whole thing clicks."
                if has_facts and f0_lbl and f1_lbl
                else f"Good question, on {subject} it all comes down to the physical margin nobody notices until you zoom in.",
                f"That's the wild part: once {f0_lbl} reaches {f0_val}, normal everyday intuition stops applying. Want a deeper follow-up on this?"
                if f0_lbl and f0_val
                else f"Basically our everyday intuition flattens the real numbers behind {subject}. Want us to go deeper on a part two?",
            ]
        elif intent == "disbelief":
            choices = [
                f"Felt fake to me too when I first looked it up. Double checked {f0_val} against {f1_val} twice before rendering this."
                if has_facts
                else f"Felt completely unreal when I first researched {subject} too. The real physics gets weird fast.",
                f"Sounds made up, right? That {f0_val} number is 100% real, and {f2_val} makes it even crazier."
                if f0_val and f2_val
                else f"I had the exact same reaction verifying {subject}. Real-world scale gets absurd fast.",
            ]
        elif intent == "short_reaction":
            choices = [
                f"Had the exact same reaction when I first saw the {f0_val} number."
                if f0_val
                else f"Had the exact same reaction putting {subject} together.",
                f"Seeing {f0_val} right next to {f1_val} really breaks your brain for a second."
                if has_facts
                else f"{subject.capitalize()} hits way differently once you see it side by side.",
                f"Right? Curious where you land on it: '{opt_a}' or '{opt_b}'?"
                if has_debate
                else "Wait till you see the next one we're rendering, the scale gap gets even wilder.",
            ]
        else:
            choices = [
                f"Glad this one clicked! Putting {f0_val} beside {f1_val} is the only way {subject} actually makes sense visually."
                if has_facts
                else f"Glad this one clicked! {subject.capitalize()} looks totally different once you map out the real numbers.",
                f"Appreciate you dropping a comment! That {f0_val} detail was the part that blew me away while researching. What should we break down next?"
                if f0_val
                else "Appreciate you dropping a comment! What hidden system or crazy scale should we break down next?",
                f"Exactly, most people never realize {f1_lbl} hits {f1_val} until they see the numbers stacked together."
                if f1_lbl and f1_val
                else f"Exactly, the real numbers behind {subject} hide in plain sight until you visualize them.",
            ]

    picked = choices[seed % len(choices)]
    return _sanitize_human_reply(picked)


def _translate_to_english_free(text: str, source_lang: str = "auto") -> str:
    """Zero-key translation from any viewer language into English for Wikipedia verification."""
    sl = source_lang if source_lang and source_lang != "en" else "auto"
    try:
        resp = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": sl, "tl": "en", "dt": "t", "q": text},
            timeout=7,
        )
        if resp.status_code == 200:
            payload = resp.json()
            translated = "".join(seg[0] for seg in payload[0] if seg and seg[0]).strip()
            if translated:
                return translated
    except Exception as exc:
        logger.debug("GTX to-English translation fallback (%s)", type(exc).__name__)
    try:
        mm_resp = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text[:200], "langpair": f"{sl if sl != 'auto' else 'tr'}|en"},
            timeout=7,
        )
        if mm_resp.status_code == 200:
            tr_txt = str(mm_resp.json().get("responseData", {}).get("translatedText", "")).strip()
            if tr_txt:
                return tr_txt
    except Exception as exc:
        logger.debug("MyMemory to-English translation fallback (%s)", type(exc).__name__)
    return text


def _extract_viewer_idea_candidate(comment_text: str, lang: str) -> Optional[str]:
    """Extract a clean, non-trivial topic concept from a viewer comment (None if junk/reaction)."""
    cleaned = re.sub(r"@[A-Za-z0-9_.\-]+", "", comment_text or "").strip()
    if len(cleaned) < 12 or len(cleaned) > 320:
        return None
    if is_spam_comment(cleaned):
        return None

    candidate = ""
    for pat in IDEA_REQUEST_PATTERNS:
        m = pat.search(cleaned)
        if m:
            candidate = m.group(1).strip(" .,!?;:\"'()-")
            if len(candidate) >= 4:
                break

    if not candidate:
        return None

    # Strip leading informal greetings/fillers (e.g. "Abi ...", "Hey ...", "the ...")
    for _ in range(3):
        trimmed = LEADING_IDEA_FILLERS.sub("", candidate).strip(" .,!?;:\"'()-")
        if trimmed == candidate:
            break
        candidate = trimmed

    if len(candidate) < 4:
        return None

    # Translate non-English idea phrasing cleanly into English for Wikipedia verification
    if lang != "en":
        translated = _translate_to_english_free(candidate, source_lang=lang)
        if translated:
            candidate = translated

    candidate = re.sub(r"[^A-Za-z0-9\s\-']", " ", candidate)
    candidate = re.sub(r"\s{2,}", " ", candidate).strip()
    for _ in range(2):
        trimmed = LEADING_IDEA_FILLERS.sub("", candidate).strip()
        if trimmed == candidate:
            break
        candidate = trimmed

    words = [w for w in candidate.split() if len(w) >= 2]
    if not words or len(words) > 10:
        return None
    if len(words) == 1 and len(words[0]) < 6:
        return None
    low_cand = " ".join(words).lower()
    if low_cand in NON_IDEA_NOISE:
        return None
    meaningful = [w for w in words if w.lower() not in NON_IDEA_NOISE and len(w) >= 3]
    if not meaningful:
        return None
    return " ".join(words[:7])


def _infer_pillar_for_text(text: str) -> str:
    low = text.lower()
    best_pillar = "science_anomalies"
    best_hits = 0
    for pillar, kws in PILLAR_KEYWORDS.items():
        hits = sum(1 for kw in kws if kw in low)
        if hits > best_hits:
            best_hits = hits
            best_pillar = pillar
    return best_pillar


def evaluate_and_harvest_viewer_idea(
    comment_text: str,
    lang: str,
    state_db: StateDB,
    current_topic_ctx: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Evaluate a viewer comment for a novel, verifiable video topic; ignore junk, queue real gems."""
    phrase = _extract_viewer_idea_candidate(comment_text, lang)
    if not phrase:
        return None

    # Deduplicate against current video, curated library, produced topics, and existing viewer queue
    used_ids = set(state_db.get_used_topic_ids())
    raw_q = state_db.get_meta("viewer_ideas_queue_json")
    try:
        queue: List[Dict[str, Any]] = json.loads(raw_q) if raw_q else []
        if not isinstance(queue, list):
            queue = []
    except json.JSONDecodeError:
        queue = []

    if len(queue) >= VIEWER_IDEAS_MAX_QUEUE:
        return None

    phrase_tokens = {t for t in re.findall(r"[a-z0-9]+", phrase.lower()) if len(t) >= 4}
    if current_topic_ctx:
        cur_blob = f"{current_topic_ctx.get('topic_id', '')} {current_topic_ctx.get('title', '')} {current_topic_ctx.get('primary_keyword', '')}".lower()
        cur_tokens = {t for t in re.findall(r"[a-z0-9]+", cur_blob) if len(t) >= 4}
        if phrase_tokens and len(phrase_tokens & cur_tokens) >= len(phrase_tokens):
            return None

    curated_entities: Set[str] = set()
    for bp in CURATED_BLUEPRINTS:
        if bp.get("wiki_entity"):
            curated_entities.add(str(bp["wiki_entity"]).lower())
        bp_tokens = {
            t for t in re.findall(r"[a-z0-9]+", f"{bp['topic_id']} {bp['primary_keyword']}".lower())
            if len(t) >= 4
        }
        if phrase_tokens and len(phrase_tokens & bp_tokens) >= len(phrase_tokens):
            return None
    for q_item in queue:
        if q_item.get("query", "").lower() == phrase.lower():
            return None

    # Live Zero-Key Wikipedia verification: only accept real, factual, documentable phenomena
    try:
        search_resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            headers={"User-Agent": WIKI_HARVEST_UA},
            params={"action": "opensearch", "search": phrase, "limit": 3, "namespace": 0, "format": "json"},
            timeout=7,
        )
        if search_resp.status_code != 200:
            return None
        payload = search_resp.json()
        titles = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
        if not titles:
            return None

        chosen_title = ""
        chosen_extract = ""
        for title in titles[:3]:
            sum_resp = requests.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'))}",
                headers={"User-Agent": WIKI_HARVEST_UA},
                timeout=7,
            )
            if sum_resp.status_code != 200:
                continue
            sdata = sum_resp.json()
            if sdata.get("type") == "disambiguation":
                continue
            extract = str(sdata.get("extract") or "").strip().replace("\n", " ")
            if len(extract) < 140:
                continue
            chosen_title = str(sdata.get("title") or title).strip()
            chosen_extract = extract[:520]
            break

        if not chosen_title or not chosen_extract:
            return None
    except Exception as exc:
        logger.debug("Viewer idea Wikipedia check skipped (%s)", type(exc).__name__)
        return None

    resolved_entity = chosen_title.replace(" ", "_")
    if resolved_entity.lower() in curated_entities:
        return None

    entity_slug = re.sub(r"[^a-z0-9]+", "-", chosen_title.lower()).strip("-")[:48]
    topic_id = f"viewer-{entity_slug}"
    if (
        topic_id in used_ids
        or entity_slug in used_ids
        or any(item.get("topic_id") == topic_id or item.get("wiki_entity", "").lower() == resolved_entity.lower() for item in queue)
    ):
        return None

    # Score documentary worthiness (must contain concrete facts/numbers or strong domain fit)
    nums = re.findall(r"\b\d[\d,\.]*\s*(?:km|m|million|billion|trillion|%|percent|years|seconds|tons|degrees|meters|miles|hours|days)?", chosen_extract, re.I)
    pillar = _infer_pillar_for_text(f"{phrase} {chosen_title} {chosen_extract}")
    score = 68 + (10 if len(nums) >= 2 else (5 if len(nums) == 1 else 0)) + (8 if len(chosen_extract) >= 240 else 0)
    if score < 76:
        return None

    idea_entry = {
        "topic_id": topic_id,
        "wiki_entity": chosen_title.replace(" ", "_"),
        "title_clean": chosen_title,
        "query": phrase,
        "pillar": pillar,
        "wiki_summary": chosen_extract,
        "score": min(96, score),
        "harvested_at": utc_now_iso(),
    }
    queue.append(idea_entry)
    state_db.set_meta("viewer_ideas_queue_json", json.dumps(queue, ensure_ascii=False))
    logger.info(
        "VIEWER IDEA HARVESTED -> %s (%s | pillar=%s | score=%d)",
        chosen_title,
        topic_id,
        pillar,
        idea_entry["score"],
    )
    return idea_entry


def _build_idea_accepted_reply(topic_name: str, lang: str) -> str:
    """Craft a warm personal reply letting the viewer know their idea was added to production."""
    if lang == "tr":
        return _sanitize_human_reply(
            f"Harika fikir! {topic_name} konusunu hemen sıradaki video havuzuna aldım, yakında yayında olacak. Takipte kal!"
        )
    if lang == "es":
        return _sanitize_human_reply(
            f"Gran idea, acabo de añadir {topic_name} a la lista de próximos videos. Quédate pendiente!"
        )
    if lang == "de":
        return _sanitize_human_reply(
            f"Starke Idee! Ich habe {topic_name} direkt auf unsere Produktionsliste gesetzt, kommt bald!"
        )
    if lang == "fr":
        return _sanitize_human_reply(
            f"Super idée, je viens d'ajouter {topic_name} à notre liste des prochaines vidéos. Reste connecté !"
        )
    return _sanitize_human_reply(
        f"Love that idea, just added {topic_name} straight to our upcoming breakdown queue. Keep an eye out for it!"
    )


def craft_reply(
    comment_text: str,
    topic_title: str,
    llm: Optional[ZeroCostLLMClient] = None,
    topic_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Classify spam, detect exact language, and draft an authentic topic-aware human reply."""
    if is_spam_comment(comment_text):
        return {
            "is_spam": True,
            "detected_lang": "spam",
            "reply_text": "",
        }

    ctx = _resolve_topic_context(topic_title, topic_context)
    lang = detect_comment_language(comment_text)
    if llm and llm.is_available:
        system_prompt = load_prompt("multilang_reply.md")
        facts_str = ", ".join(f"{f['label']}: {f['value']}" for f in ctx["facts"])
        debate = ctx["debate"]
        debate_str = (
            f"Debate options: {debate['option_a']} vs {debate['option_b']}"
            if debate.get("option_a") and debate.get("option_b")
            else ""
        )
        user_prompt = (
            f"Video title: {ctx['title'] or topic_title}\n"
            f"Topic keyword: {ctx['primary_keyword'] or ctx['subject']}\n"
            f"Verified facts from this video ONLY: {facts_str or 'Use title context only'}\n"
            f"{debate_str}\n"
            f"Detected language hint: {lang}\n"
            f"Viewer comment: {comment_text}\n"
            "CRITICAL: Only reference facts from THIS video. Never use em-dashes."
        )
        res = llm.complete_json(system_prompt, user_prompt, temperature=0.75)
        if res and isinstance(res.get("is_spam"), bool):
            if res["is_spam"]:
                return {"is_spam": True, "detected_lang": "spam", "reply_text": ""}
            reply = _sanitize_human_reply(str(res.get("reply_text", "")))
            if reply:
                return {
                    "is_spam": False,
                    "detected_lang": str(res.get("detected_language", lang))[:5],
                    "reply_text": reply,
                }

    return {
        "is_spam": False,
        "detected_lang": lang,
        "reply_text": _native_multilang_reply(comment_text, lang, topic_title, topic_context=ctx),
    }


def run_comment_cycle(
    state_db: StateDB,
    out_dir: Optional[Path] = None,
    llm: Optional[ZeroCostLLMClient] = None,
) -> Dict[str, Any]:
    """Fetch new comments, approve visibility, and reply naturally with each video's real topic."""
    llm = llm or ZeroCostLLMClient()
    summary: Dict[str, Any] = {
        "mode": "live" if has_youtube_credentials() else "verification_preview",
        "fetched": 0,
        "spam_filtered": 0,
        "queued": 0,
        "sent_now": 0,
        "ideas_harvested": 0,
        "samples": [],
    }

    if not has_youtube_credentials():
        # Preview across actual recent video in state.db or diverse multi-topic blueprints
        all_vids = state_db.get_all_videos()
        if all_vids:
            preview_ctx = _load_topic_context(state_db, all_vids[0])
            preview_title = preview_ctx["title"]
        else:
            preview_ctx = _resolve_topic_context("asteroid-psyche")
            preview_title = preview_ctx["title"]

        sample_comments = [
            ("demo_tr_01", "İnanılmaz bir detay olmuş, bunu ilk kez duyuyorum, gerçek mi bu?"),
            ("demo_en_02", "No way this is real, it would definitely crash the whole market overnight!"),
            ("demo_es_03", "Increíble explicación visual, nunca lo había visto así de claro."),
            ("demo_de_04", "Krass, diese visuelle Darstellung macht es sofort verständlich!"),
            ("demo_spam_05", "FREE CRYPTO SIGNALS join https://t.me/scamchannel123 check my channel sub4sub!!!"),
        ]
        now = datetime.now(timezone.utc)
        for cid, text in sample_comments:
            decision = craft_reply(text, preview_title, llm=llm, topic_context=preview_ctx)
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

        # Batch statistics lookup (1 quota unit for up to 25 active videos so older hits are never missed!)
        active_videos = videos[:25]
        batch_ids = [str(v["youtube_id"]) for v in active_videos if v.get("youtube_id")]
        stats_map: Dict[str, Dict[str, Any]] = {}
        if batch_ids:
            try:
                st_resp = youtube.videos().list(part="statistics", id=",".join(batch_ids)).execute()
                for st_item in st_resp.get("items", []):
                    stats_map[st_item["id"]] = st_item.get("statistics", {})
            except Exception as exc:
                logger.debug("Batch stats check skipped (%s)", type(exc).__name__)

        now = datetime.now(timezone.utc)
        for vid in active_videos:
            yt_id = vid["youtube_id"]
            topic_ctx = _load_topic_context(state_db, vid)
            title = topic_ctx["title"] or "VELUM"

            if yt_id in stats_map:
                stats = stats_map[yt_id]
                v_cnt = int(stats.get("viewCount", 0) or 0)
                l_cnt = int(stats.get("likeCount", 0) or 0)
                c_cnt = int(stats.get("commentCount", 0) or 0)
                logger.info(
                    "LIVE STATS [%s] -> views=%d | likes=%d | comments=%d",
                    yt_id,
                    v_cnt,
                    l_cnt,
                    c_cnt,
                )
                if v_cnt > 0:
                    state_db.update_video_metrics(
                        vid["video_uid"],
                        v_cnt,
                        float(vid.get("avg_view_pct", 0.0)),
                        float(vid.get("ctr", 0.0)),
                    )

            try:
                # Include `replies` at 0 extra quota cost so replies to our pinned discussion comment are NEVER missed!
                resp = youtube.commentThreads().list(
                    part="snippet,replies",
                    videoId=yt_id,
                    maxResults=25,
                    order="time",
                    textFormat="plainText",
                ).execute()
            except Exception as exc:
                logger.warning("Could not fetch comments for %s (%s)", yt_id, type(exc).__name__)
                continue

            # Collect both top-level viewer comments AND viewer replies under existing threads
            incoming_entries: List[Tuple[str, str, str, bool]] = []
            for item in resp.get("items", []):
                top = item["snippet"]["topLevelComment"]
                top_id = top["id"]
                top_author = top["snippet"].get("authorChannelId", {}).get("value", "")
                if not (my_channel_id and top_author == my_channel_id):
                    incoming_entries.append((top_id, top_id, top["snippet"].get("textDisplay", ""), True))
                # Also inspect thread replies (e.g., viewers answering our pinned debate comment!)
                for rep in (item.get("replies") or {}).get("comments", []):
                    rep_id = rep.get("id", "")
                    rep_author = rep.get("snippet", {}).get("authorChannelId", {}).get("value", "")
                    if rep_id and not (my_channel_id and rep_author == my_channel_id):
                        incoming_entries.append((rep_id, top_id, rep.get("snippet", {}).get("textDisplay", ""), False))

            for cid, reply_parent_id, text, is_top_level in incoming_entries:
                if state_db.is_comment_processed(cid):
                    continue
                summary["fetched"] += 1
                decision = craft_reply(text, title, llm=llm, topic_context=topic_ctx)
                sched_iso = now.replace(microsecond=0).isoformat()
                if decision["is_spam"]:
                    summary["spam_filtered"] += 1
                    state_db.record_comment_reply(cid, yt_id, "spam", "", True, sched_iso, status="filtered_spam")
                    continue

                # Evaluate whether this viewer comment contains a genuinely useful, novel topic idea!
                harvested = evaluate_and_harvest_viewer_idea(
                    text,
                    decision["detected_lang"],
                    state_db,
                    current_topic_ctx=topic_ctx,
                )
                reply_text = decision["reply_text"]
                if harvested is not None:
                    summary["ideas_harvested"] += 1
                    reply_text = _build_idea_accepted_reply(harvested["title_clean"], decision["detected_lang"])

                if is_top_level:
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
                                "parentId": reply_parent_id,
                                "textOriginal": reply_text,
                            }
                        },
                    ).execute()
                    sent_ok = True
                    summary["sent_now"] += 1
                    logger.info(
                        "Replied to viewer %s (%s) on %s [%s]%s -> %s",
                        "comment" if is_top_level else "thread reply",
                        decision["detected_lang"],
                        yt_id,
                        topic_ctx.get("topic_id") or title[:24],
                        " [IDEA HARVESTED]" if harvested else "",
                        reply_text,
                    )
                except Exception as exc:
                    summary["queued"] += 1
                    logger.warning("Immediate reply deferred to queue (%s)", type(exc).__name__)

                state_db.record_comment_reply(
                    cid,
                    yt_id,
                    decision["detected_lang"],
                    reply_text,
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
                            "parentId": str(row["youtube_comment_id"]).split(".", 1)[0],
                            "textOriginal": row["reply_text"],
                        }
                    },
                ).execute()
                state_db.mark_comment_replied(row["comment_hash"])
                summary["sent_now"] += 1
            except Exception as exc:
                logger.warning("Reply send error for %s (%s)", row["comment_hash"], type(exc).__name__)

    logger.info(
        "Live comment cycle done | fetched=%d | spam=%d | queued=%d | sent=%d | ideas_harvested=%d",
        summary["fetched"],
        summary["spam_filtered"],
        summary["queued"],
        summary["sent_now"],
        summary["ideas_harvested"],
    )
    return summary
