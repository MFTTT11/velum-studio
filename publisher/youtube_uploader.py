"""YouTube Data API v3 Uploader + 7-Day Anti-Spam Warm-Up Scheduler.

Features:
- Ephemeral OAuth credential handling strictly from ENV / GitHub Secrets
  (client_secrets.json & token.json are zero-wiped & deleted immediately after use).
- 7-Day Anti-Spam Warm-Up Cadence (`publishAt`):
    * Days 1–2: 1 Short/day (16:00 UTC)
    * Days 3–7: 2–3 Shorts/day (13:00, 17:00, 21:00 UTC) + 1 Long-form every 2 days (18:30 UTC)
    * Day 8+:   3 Shorts/day + 1 Long-form every 2 days
- Automatic A/B Variant #1 thumbnail upload (`thumbnails().set`)
- Automatic multi-language `.srt` caption uploads (`captions().insert`)
- Automatic Pinned First Comment publishing (`commentThreads().insert`)
- Clean dry-run/package mode when OAuth secrets are absent (never crashes or leaks).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import (
    ephemeral_youtube_credentials,
    get_logger,
    has_youtube_credentials,
)
from core.state_db import StateDB

logger = get_logger("youtube_uploader")

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def compute_warmup_plan(state_db: StateDB, now_utc: Optional[datetime] = None) -> Dict[str, Any]:
    """Determine channel warm-up day, next allowed format, and anti-spam `publishAt` slot."""
    now = now_utc or datetime.now(timezone.utc)
    launch_iso = state_db.get_meta("launch_date")
    try:
        launch_dt = datetime.fromisoformat(launch_iso) if launch_iso else now
        if launch_dt.tzinfo is None:
            launch_dt = launch_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        launch_dt = now

    day_num = max(1, (now.date() - launch_dt.date()).days + 1)

    if day_num <= 2:
        daily_shorts_cap = 1
        shorts_hours = [16]
        allow_longform = False
        phase = f"WARMUP_DAY_{day_num} (1 Short/day anti-spam)"
    elif day_num <= 7:
        daily_shorts_cap = 3 if day_num >= 5 else 2
        shorts_hours = [13, 17, 21][:daily_shorts_cap]
        allow_longform = (day_num % 2 == 1)  # Days 3, 5, 7 -> 1 Long-form every 2 days
        phase = f"WARMUP_DAY_{day_num} ({daily_shorts_cap} Shorts/day + Long-form every 2d)"
    else:
        daily_shorts_cap = 3
        shorts_hours = [13, 17, 21]
        allow_longform = (day_num % 2 == 1)
        phase = f"SCALE_PHASE_DAY_{day_num} (3 Shorts/day + Long-form every 2d)"

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

    # Collect already-scheduled publishAt timestamps so slots never collide
    existing_slots = {
        v.get("publish_at") for v in state_db.get_all_videos() if v.get("publish_at")
    }

    # Find next clean future slot (>= 25 min ahead for YouTube HD processing)
    min_publish_dt = now + timedelta(minutes=25)
    chosen_dt: Optional[datetime] = None
    for day_offset in range(0, 14):
        target_day = (now + timedelta(days=day_offset)).date()
        for hr in candidate_hours:
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


def upload_video_package(
    video_uid: str,
    video_path: Path,
    seo_package: Dict[str, Any],
    thumbnail_paths: List[str],
    state_db: StateDB,
    out_dir: Path,
    dry_run: Optional[bool] = None,
) -> Dict[str, Any]:
    """Upload video + thumbnail + multi-language SRTs + pinned comment via YouTube API v3."""
    plan = compute_warmup_plan(state_db)
    publish_at = plan["publish_at"]
    env_dry = os.getenv("AUTOPILOT_DRY_RUN", "false").lower() == "true"
    is_dry = env_dry if dry_run is None else dry_run

    primary_title = seo_package["titles_ab"][0][:98]
    primary_thumb = thumbnail_paths[0] if thumbnail_paths else ""

    manifest = {
        "video_uid": video_uid,
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
        "comment_posted": False,
    }

    if is_dry or not has_youtube_credentials():
        reason = "dry-run flag active" if is_dry else "YOUTUBE_TOKEN secret not configured yet"
        logger.info(
            "YouTube live upload skipped (%s) -> saved ready-to-publish manifest (slot=%s)",
            reason,
            publish_at,
        )
        manifest["note"] = (
            f"Live upload skipped ({reason}). Add YOUTUBE_CLIENT_SECRETS and YOUTUBE_TOKEN "
            "to GitHub Secrets to activate automatic scheduled publishing."
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

        body = {
            "snippet": {
                "title": primary_title,
                "description": seo_package["description_full"][:4950],
                "tags": seo_package.get("tags", [])[:20],
                "categoryId": "27",  # Education / Documentary
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en",
            },
            "status": {
                "privacyStatus": "private",
                "publishAt": publish_at,
                "selfDeclaredMadeForKids": False,
                "embeddable": True,
                "publicStatsViewable": True,
            },
        }

        logger.info("Uploading %s to YouTube (scheduled publishAt=%s)...", video_path.name, publish_at)
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            _, response = request.next_chunk()

        yt_id = response["id"]
        manifest["mode"] = "live_uploaded"
        manifest["youtube_id"] = yt_id
        logger.info("YouTube upload complete | videoId=%s | publishAt=%s", yt_id, publish_at)

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

        # 2. Upload multi-language `.srt` caption tracks
        lang_names = {"en": "English", "tr": "Türkçe", "es": "Español", "de": "Deutsch", "fr": "Français"}
        for lang_code, srt_file in seo_package.get("subtitles_srt", {}).items():
            if not Path(srt_file).exists():
                continue
            try:
                youtube.captions().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "videoId": yt_id,
                            "language": lang_code,
                            "name": lang_names.get(lang_code, lang_code.upper()),
                            "isDraft": False,
                        }
                    },
                    media_body=MediaFileUpload(srt_file, mimetype="application/octet-stream"),
                ).execute()
                manifest["captions_uploaded"].append(lang_code)
            except Exception as exc:
                logger.warning("Caption upload (%s) skipped (%s)", lang_code, type(exc).__name__)

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
                manifest["comment_posted"] = True
                logger.info("Posted discussion-starter first comment on %s", yt_id)
            except Exception as exc:
                logger.warning("First comment deferred until video goes public (%s)", type(exc).__name__)

    state_db.update_video_publish(video_uid, manifest["youtube_id"], publish_at, "scheduled_live")
    (out_dir / "upload_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest
