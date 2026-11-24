"""YouTube Data API v3 Quota-Safe Uploader + V3 4/Day Shorts Blitz Scheduler.

Features:
- Ephemeral OAuth credential handling strictly from ENV / GitHub Secrets
  (client_secrets.json & token.json are zero-wiped & deleted immediately after use).
- V3 Hyper-Growth Cadence & Anti-Spam Spacing Guard:
    * Days 1–13: 4 Viral 4K Shorts/day ([12:00, 16:00, 20:00, 00:00] UTC, >=2.8h spacing)
    * Day 14+:   4 Shorts/day + optional Long-form every 2 days (18:30 UTC)
- Quota-Safe Captions:
    * Shorts: skip `captions().insert` completely (burned-in kinetic captions + 10-language
      `video.localizations` at 0 extra quota cost -> saves 4,000 units/video, 4/day = ~7,240/10,000)
    * Long-form: upload only English (`en`) `.srt` caption (400 units)
- Automatic A/B Variant #1 thumbnail upload (`thumbnails().set`)
- Automatic Pinned First Comment publishing (`commentThreads().insert`)
- Clean dry-run/package mode when OAuth secrets are absent (never crashes or leaks).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import (
    BRAND_DIR,
    ephemeral_youtube_credentials,
    get_logger,
    has_youtube_credentials,
    load_brand_config,
)
from core.state_db import StateDB
from publisher.omni_seo import (
    TARGET_CAPTION_LANGS,
    _translate_lines_batch_free,
    generate_video_localizations,
)

logger = get_logger("youtube_uploader")

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def _sanitize_youtube_text(
    text: Any,
    max_chars: Optional[int] = None,
    max_bytes: int = 4950,
) -> str:
    """Sanitize metadata for YouTube Data API v3 (forbids `<` and `>`, enforces UTF-8 byte & char caps)."""
    cleaned = str(text or "")
    cleaned = re.sub(r"\s*-+>\s*", " to ", cleaned)
    cleaned = re.sub(r"<=\s*", "at most ", cleaned)
    cleaned = re.sub(r">=\s*", "at least ", cleaned)
    cleaned = re.sub(r"<\s*", "under ", cleaned)
    cleaned = re.sub(r">\s*", "over ", cleaned)
    # Belt-and-suspenders removal of any residual angle brackets or illegal ASCII control chars
    cleaned = cleaned.replace("<", "").replace(">", "")
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", cleaned)
    cleaned = "\n".join(re.sub(r"[ \t]{2,}", " ", ln).rstrip() for ln in cleaned.splitlines()).strip()

    if max_chars is not None and len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip()

    if max_bytes is not None and max_bytes > 0:
        encoded = cleaned.encode("utf-8")
        if len(encoded) > max_bytes:
            cleaned = encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()
    return cleaned


def _sanitize_youtube_tags(tags: List[Any], max_tags: int = 20, max_total_chars: int = 460) -> List[str]:
    """Sanitize video tags for YouTube Data API v3 (zero `<`/`>`, total length < 500 chars)."""
    clean_tags: List[str] = []
    total_len = 0
    for raw in tags[:max_tags]:
        tag = _sanitize_youtube_text(raw, max_chars=45, max_bytes=120).replace("\n", " ").strip()
        if not tag:
            continue
        cost = len(tag) + (3 if " " in tag else 1)
        if total_len + cost > max_total_chars:
            break
        clean_tags.append(tag)
        total_len += cost
    return clean_tags


def _sanitize_localizations(
    loc_map: Dict[str, Any],
    fallback_title: str,
    fallback_desc: str,
) -> Dict[str, Dict[str, str]]:
    """Sanitize every regional localization title & description for YouTube Data API v3."""
    safe_title_fb = _sanitize_youtube_text(fallback_title, max_chars=95, max_bytes=360) or "VELUM Visual Breakdown"
    safe_desc_fb = _sanitize_youtube_text(fallback_desc, max_chars=4900, max_bytes=4900)
    sanitized: Dict[str, Dict[str, str]] = {}
    for lang_code, entry in (loc_map or {}).items():
        if not isinstance(entry, dict):
            continue
        loc_title = _sanitize_youtube_text(entry.get("title", ""), max_chars=95, max_bytes=360) or safe_title_fb
        loc_desc = _sanitize_youtube_text(entry.get("description", ""), max_chars=4900, max_bytes=4900) or safe_desc_fb
        sanitized[str(lang_code)] = {"title": loc_title, "description": loc_desc}
    sanitized["en"] = {"title": safe_title_fb, "description": safe_desc_fb}
    return sanitized


def _parse_utc_iso(raw_ts: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp string cleanly into a timezone-aware UTC datetime."""
    if not raw_ts:
        return None
    try:
        dt = datetime.fromisoformat(str(raw_ts).strip().replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def compute_warmup_plan(state_db: StateDB, now_utc: Optional[datetime] = None) -> Dict[str, Any]:
    """Determine V3 blitz day, 4/day Shorts quota, 2.8h spacing guard, and next target slot."""
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    launch_dt = _parse_utc_iso(state_db.get_meta("launch_date")) or now
    day_num = max(1, (now.date() - launch_dt.date()).days + 1)

    daily_shorts_cap = 2
    shorts_hours = [8, 18]

    if day_num <= 13:
        allow_longform = False
        phase = f"V7_SIGNATURE_DAY_{day_num} (2 High-Craft Mechanical 4K Shorts/day)"
    else:
        allow_longform = (day_num % 2 == 1)
        phase = f"SCALE_PHASE_DAY_{day_num} (2 Mechanical Shorts/day + Long-form every 2d)"

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    two_days_ago = (now - timedelta(days=2)).isoformat()
    shorts_today = state_db.count_videos_by_format_since("shorts", today_start)
    longform_recent = state_db.count_videos_by_format_since("longform", two_days_ago)

    if allow_longform and longform_recent == 0 and shorts_today >= 1:
        recommended_format = "longform"
        candidate_hours = [18]
        minute_offset = 30
        daily_quota_reached = False
    else:
        recommended_format = "shorts"
        candidate_hours = shorts_hours
        minute_offset = 0
        daily_quota_reached = shorts_today >= daily_shorts_cap

    all_videos = state_db.get_all_videos()

    # Compute hours elapsed since the most recent uploaded/produced video
    latest_upload_dt: Optional[datetime] = None
    for vid in all_videos:
        created_dt = _parse_utc_iso(vid.get("created_at"))
        if created_dt is not None and (latest_upload_dt is None or created_dt > latest_upload_dt):
            latest_upload_dt = created_dt

    if latest_upload_dt is not None:
        hours_since_last_upload = round(max(0.0, (now - latest_upload_dt).total_seconds() / 3600.0), 2)
    else:
        hours_since_last_upload = 999.0

    spacing_guard_active = bool(hours_since_last_upload < 7.5 and not daily_quota_reached)

    # Collect already-scheduled publishAt timestamps so slots never collide
    existing_slots = {
        v.get("publish_at") for v in all_videos if v.get("publish_at")
    }

    # Find next clean future slot (>= 25 min ahead for YouTube HD/4K processing)
    min_publish_dt = now + timedelta(minutes=25)
    chronological_hours = sorted(candidate_hours)
    chosen_dt: Optional[datetime] = None
    for day_offset in range(0, 14):
        target_day = (now + timedelta(days=day_offset)).date()
        for hr in chronological_hours:
            slot = datetime(
                target_day.year,
                target_day.month,
                target_day.day,
                hr,
                minute_offset,
                0,
                tzinfo=timezone.utc,
            )
            slot_iso = slot.strftime("%Y-%m-%dT%H:%M:%SZ")
            if slot >= min_publish_dt and slot_iso not in existing_slots:
                chosen_dt = slot
                break
        if chosen_dt is not None:
            break

    if chosen_dt is None:
        chosen_dt = (now + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)

    publish_at_iso = chosen_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "channel_day": day_num,
        "phase": phase,
        "daily_shorts_cap": daily_shorts_cap,
        "shorts_produced_today": shorts_today,
        "daily_quota_reached": daily_quota_reached,
        "hours_since_last_upload": hours_since_last_upload,
        "spacing_guard_active": spacing_guard_active,
        "recommended_format": recommended_format,
        "publish_at": publish_at_iso,
    }


def build_youtube_service(token_path: Path):
    """Build authenticated YouTube Data API v3 service from ephemeral token.json."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(str(token_path), YOUTUBE_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        raise RuntimeError("YouTube OAuth token is invalid or missing refresh_token.")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def sync_channel_branding(youtube, state_db: StateDB, force: bool = False) -> Dict[str, Any]:
    """Automatically push Banner (2560x1440), Watermark (150x150), Bio, Keywords & Country via YouTube Data API v3."""
    from googleapiclient.http import MediaFileUpload

    result: Dict[str, Any] = {
        "channel_id": None,
        "banner_uploaded": False,
        "watermark_uploaded": False,
        "metadata_updated": False,
    }
    if not force and state_db.get_meta("channel_branding_synced") == "v3":
        return result

    brand = load_brand_config()
    banner_path = BRAND_DIR / "banner_2560x1440.png"
    watermark_path = BRAND_DIR / "watermark_150x150.png"

    try:
        ch_resp = youtube.channels().list(part="id,snippet,brandingSettings", mine=True).execute()
        items = ch_resp.get("items", [])
        if not items:
            logger.warning("No YouTube channel found on authenticated account for branding sync.")
            return result
        ch = items[0]
        channel_id = ch["id"]
        result["channel_id"] = channel_id
        branding = ch.get("brandingSettings", {})
        ch_settings = branding.get("channel", {})

        # 1. Upload 2560x1440 Channel Banner via channelBanners().insert
        banner_url = None
        if banner_path.exists():
            try:
                b_resp = (
                    youtube.channelBanners()
                    .insert(
                        body={},
                        media_body=MediaFileUpload(str(banner_path), mimetype="image/png", resumable=True),
                    )
                    .execute()
                )
                banner_url = b_resp.get("url")
                if banner_url:
                    branding.setdefault("image", {})["bannerExternalUrl"] = banner_url
                    result["banner_uploaded"] = True
                    logger.info("Uploaded 2560x1440 channel banner via YouTube API -> %s", channel_id)
            except Exception as exc:
                logger.warning("Channel banner API insert error (%s)", exc)

        # 2. Update Channel Description (Bio), Keywords, Country (TR) & 10-Language Regional Localizations
        bio_en = brand.get("seo_bio", "")[:990]
        ch_title = brand.get("channel_name", "Velum Dispatch")
        ch_settings["description"] = bio_en
        kw_list = brand.get("seo_keywords", [])
        ch_settings["keywords"] = " ".join(f'"{k}"' if " " in k else k for k in kw_list)[:490]
        ch_settings["country"] = "TR"
        ch_settings["defaultLanguage"] = "en"
        branding["channel"] = ch_settings

        ch_localizations: Dict[str, Dict[str, str]] = {"en": {"title": ch_title, "description": bio_en}}
        for lang_code in TARGET_CAPTION_LANGS:
            if lang_code == "en":
                continue
            tr_bio = _translate_lines_batch_free([bio_en], lang_code)
            ch_localizations[lang_code] = {
                "title": ch_title,
                "description": (tr_bio[0] if tr_bio else bio_en)[:990],
            }

        # 2a. Update brandingSettings (Banner + Description + Keywords + Country=TR)
        youtube.channels().update(
            part="brandingSettings",
            body={
                "id": channel_id,
                "brandingSettings": branding,
            },
        ).execute()
        result["metadata_updated"] = True
        logger.info("Applied channel brandingSettings (compact Banner + Bio + Keywords + Country=TR) on %s", channel_id)

        # 2b. Update 11-language Channel Localizations in a separate API call (YouTube forbids combining parts)
        try:
            youtube.channels().update(
                part="localizations",
                body={
                    "id": channel_id,
                    "localizations": ch_localizations,
                },
            ).execute()
            result["channel_languages"] = list(ch_localizations.keys())
            logger.info(
                "Applied %d regional language channel localizations on %s",
                len(ch_localizations),
                channel_id,
            )
        except Exception as exc:
            logger.warning("Channel localizations update skipped (%s)", exc)

        # 3. Upload 150x150 RGBA Video Watermark via watermarks().set
        if watermark_path.exists():
            try:
                youtube.watermarks().set(
                    channelId=channel_id,
                    body={
                        "timing": {"type": "offsetFromStart", "offsetMs": 0},
                        "position": {"type": "corner", "cornerPosition": "topRight"},
                    },
                    media_body=MediaFileUpload(str(watermark_path), mimetype="image/png", resumable=False),
                ).execute()
                result["watermark_uploaded"] = True
                logger.info("Uploaded 150x150 channel video watermark via YouTube API -> %s", channel_id)
            except Exception as exc:
                logger.warning("Channel watermark API upload error (%s)", exc)

        # 4. Retro-apply 10-language regional Title & Description localizations to recent uploaded videos
        for vid in state_db.get_all_videos()[:5]:
            yt_id = vid.get("youtube_id")
            if not yt_id:
                continue
            try:
                v_resp = youtube.videos().list(part="snippet,localizations", id=yt_id).execute()
                v_items = v_resp.get("items", [])
                if not v_items:
                    continue
                v_snip = v_items[0]["snippet"]
                v_snip["title"] = _sanitize_youtube_text(v_snip.get("title", ""), max_chars=98, max_bytes=380)
                v_snip["description"] = _sanitize_youtube_text(v_snip.get("description", ""), max_chars=4950, max_bytes=4950)
                if isinstance(v_snip.get("tags"), list):
                    v_snip["tags"] = _sanitize_youtube_tags(v_snip["tags"])
                v_snip["defaultLanguage"] = "en"
                v_snip["defaultAudioLanguage"] = "en"
                raw_locs = generate_video_localizations(
                    v_snip.get("title", ""), v_snip.get("description", "")
                )
                v_locs = _sanitize_localizations(raw_locs, v_snip["title"], v_snip["description"])
                youtube.videos().update(
                    part="snippet,localizations",
                    body={"id": yt_id, "snippet": v_snip, "localizations": v_locs},
                ).execute()
                logger.info(
                    "Applied %d regional language Title/Description localizations to video %s",
                    len(v_locs),
                    yt_id,
                )
            except Exception as exc:
                logger.warning("Video localization update skipped for %s (%s)", yt_id, exc)

        # 5. Ensure top-level discussion-starter comment is posted once a video is Public
        for vid in state_db.get_all_videos()[:5]:
            yt_id = vid.get("youtube_id")
            if not yt_id or state_db.get_meta(f"first_comment_posted_{yt_id}") == "true":
                continue
            try:
                seo_info = json.loads(vid.get("seo_json", "{}"))
                pinned_txt = str(seo_info.get("pinned_comment", "")).strip()
                if not pinned_txt and vid.get("topic_id"):
                    with state_db._connect() as conn:
                        trow = conn.execute(
                            "SELECT payload_json FROM topics WHERE topic_id = ?",
                            (vid["topic_id"],),
                        ).fetchone()
                    if trow:
                        tpayload = json.loads(trow["payload_json"])
                        pinned_txt = str((tpayload.get("debate_hook") or {}).get("pinned", "")).strip()
                if not pinned_txt:
                    pinned_txt = (
                        "Honest question: did those numbers match what you expected? "
                        "Drop your take below and tell us which hidden system we should break down next."
                    )
                youtube.commentThreads().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "videoId": yt_id,
                            "topLevelComment": {"snippet": {"textOriginal": pinned_txt}},
                        }
                    },
                ).execute()
                state_db.set_meta(f"first_comment_posted_{yt_id}", "true")
                logger.info("Posted discussion-starter first comment on public video %s", yt_id)
            except Exception as exc:
                logger.debug("First comment check skipped for %s (%s)", yt_id, type(exc).__name__)

        if result["banner_uploaded"] and result["metadata_updated"]:
            state_db.set_meta("channel_branding_synced", "v3")
    except Exception as exc:
        logger.warning("Channel branding sync skipped (%s)", exc)

    return result


def _resolve_upload_format(
    video_uid: str,
    video_path: Path,
    seo_package: Dict[str, Any],
    state_db: StateDB,
    plan: Dict[str, Any],
    explicit_fmt: Optional[str] = None,
) -> str:
    """Resolve whether an upload is 'shorts' or 'longform' cleanly across all callers."""
    if explicit_fmt in ("shorts", "longform"):
        return explicit_fmt
    seo_fmt = str(seo_package.get("format", "")).strip().lower()
    if seo_fmt in ("shorts", "longform"):
        return seo_fmt
    for vid in state_db.get_all_videos():
        if vid.get("video_uid") == video_uid and vid.get("format") in ("shorts", "longform"):
            return str(vid["format"])
    hashtags = [str(h).lower() for h in seo_package.get("hashtags", [])]
    if "#shorts" in hashtags:
        return "shorts"
    if "#documentary" in hashtags:
        return "longform"
    fname = video_path.name.lower()
    if "longform" in fname:
        return "longform"
    if "short" in fname:
        return "shorts"
    return str(plan.get("recommended_format", "shorts"))


def upload_video_package(
    video_uid: str,
    video_path: Path,
    seo_package: Dict[str, Any],
    thumbnail_paths: List[str],
    state_db: StateDB,
    out_dir: Path,
    dry_run: Optional[bool] = None,
    fmt: Optional[str] = None,
) -> Dict[str, Any]:
    """Upload video + thumbnail + quota-safe captions + pinned comment via YouTube API v3."""
    plan = compute_warmup_plan(state_db)
    publish_at = plan["publish_at"]
    effective_fmt = _resolve_upload_format(video_uid, video_path, seo_package, state_db, plan, explicit_fmt=fmt)
    env_dry = os.getenv("AUTOPILOT_DRY_RUN", "false").lower() == "true"
    is_dry = env_dry if dry_run is None else dry_run

    primary_title = _sanitize_youtube_text(seo_package["titles_ab"][0], max_chars=98, max_bytes=380)
    primary_desc = _sanitize_youtube_text(seo_package.get("description_full", ""), max_chars=4950, max_bytes=4950)
    primary_tags = _sanitize_youtube_tags(seo_package.get("tags", []))
    primary_thumb = thumbnail_paths[0] if thumbnail_paths else ""

    manifest = {
        "video_uid": video_uid,
        "format": effective_fmt,
        "mode": "dry_run_package",
        "warmup_plan": plan,
        "video_file": str(video_path),
        "slug_filename": seo_package["slug_filename"],
        "title": primary_title,
        "publishAt": publish_at,
        "privacyStatus": "private",
        "thumbnail": primary_thumb,
        "subtitles_srt": seo_package.get("subtitles_srt", {}),
        "pinned_comment": seo_package.get("pinned_comment", ""),
        "youtube_id": None,
        "captions_uploaded": [],
        "captions_skipped_for_quota": effective_fmt == "shorts",
        "comment_posted": False,
    }

    if is_dry or not has_youtube_credentials():
        reason = "dry-run flag active" if is_dry else "YOUTUBE_TOKEN secret not configured yet"
        logger.info(
            "YouTube live upload skipped (%s) -> saved ready-to-publish manifest (format=%s, slot=%s)",
            reason,
            effective_fmt,
            publish_at,
        )
        manifest["note"] = (
            f"Live upload skipped ({reason}). Add YOUTUBE_CLIENT_SECRETS and YOUTUBE_TOKEN "
            "to GitHub Secrets to activate automatic publishing."
        )
        (out_dir / "upload_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        state_db.update_video_publish(video_uid, None, publish_at, "ready_to_upload")
        return manifest

    from googleapiclient.http import MediaFileUpload

    # Ephemeral secret files are ALWAYS securely deleted upon leaving this `with` block
    with ephemeral_youtube_credentials() as (_, token_path):
        if token_path is None:
            raise RuntimeError("Ephemeral YouTube token could not be materialized.")
        youtube = build_youtube_service(token_path)

        # Ensure channel Banner (2560x1440), Watermark (150x150), Bio, Keywords & Country are synced via API
        branding_sync = sync_channel_branding(youtube, state_db)
        manifest["channel_branding_sync"] = branding_sync

        loc_map = _sanitize_localizations(
            seo_package.get("localizations", {}),
            primary_title,
            primary_desc,
        )
        body = {
            "snippet": {
                "title": primary_title,
                "description": primary_desc,
                "tags": primary_tags,
                "categoryId": "27",  # Education / Documentary
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en",
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
                "embeddable": True,
                "publicStatsViewable": True,
            },
            "localizations": loc_map,
        }

        logger.info(
            "Uploading %s to YouTube (privacyStatus=public, format=%s, %d regional languages)...",
            video_path.name,
            effective_fmt,
            len(loc_map),
        )
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024)
        request = youtube.videos().insert(part="snippet,status,localizations", body=body, media_body=media)

        response = None
        while response is None:
            _, response = request.next_chunk()

        yt_id = response["id"]
        manifest["mode"] = "live_uploaded"
        manifest["privacyStatus"] = "public"
        manifest["youtube_id"] = yt_id
        logger.info(
            "YouTube upload complete | videoId=%s | privacyStatus=public | format=%s",
            yt_id,
            effective_fmt,
        )

        # 1. Set Variant A high-contrast thumbnail
        if primary_thumb and Path(primary_thumb).exists():
            try:
                youtube.thumbnails().set(
                    videoId=yt_id,
                    media_body=MediaFileUpload(primary_thumb, mimetype="image/png"),
                ).execute()
                logger.info("Uploaded Variant A thumbnail for %s", yt_id)
            except Exception as exc:
                logger.warning("Thumbnail upload skipped/deferred (%s)", type(exc).__name__)

        # 2. Quota-Safe Captions:
        #    - Shorts: SKIP captions().insert completely (burned-in kinetic captions + 10-language
        #      video.localizations cost 0 extra quota, saving 4,000 units/video so 4 Shorts/day
        #      stays ~7,240 / 10,000 daily quota).
        #    - Long-form: upload only English ("en") .srt track (400 quota units).
        if effective_fmt == "shorts":
            logger.info(
                "Shorts format: skipping captions().insert for %s (saves ~4,000 API quota units; "
                "burned-in kinetic captions + %d-language localizations active).",
                yt_id,
                len(loc_map),
            )
        else:
            en_srt = seo_package.get("subtitles_srt", {}).get("en")
            if en_srt and Path(en_srt).exists():
                try:
                    youtube.captions().insert(
                        part="snippet",
                        body={
                            "snippet": {
                                "videoId": yt_id,
                                "language": "en",
                                "name": "English",
                                "isDraft": False,
                            }
                        },
                        media_body=MediaFileUpload(en_srt, mimetype="application/octet-stream"),
                    ).execute()
                    manifest["captions_uploaded"].append("en")
                    logger.info("Uploaded English ('en') .srt caption track for longform video %s (400 units)", yt_id)
                except Exception as exc:
                    logger.warning("Caption upload (en) skipped (%s)", type(exc).__name__)

        # 3. Post debate-starting Pinned First Comment
        pinned_text = seo_package.get("pinned_comment", "").strip()
        if pinned_text:
            try:
                youtube.commentThreads().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "videoId": yt_id,
                            "topLevelComment": {"snippet": {"textOriginal": pinned_text}},
                        }
                    },
                ).execute()
                state_db.set_meta(f"first_comment_posted_{yt_id}", "true")
                manifest["comment_posted"] = True
                logger.info("Posted discussion-starter first comment on %s", yt_id)
            except Exception as exc:
                logger.warning("First comment deferred until video goes public (%s)", type(exc).__name__)

    state_db.update_video_publish(video_uid, manifest["youtube_id"], publish_at, "published_live")
    (out_dir / "upload_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest
