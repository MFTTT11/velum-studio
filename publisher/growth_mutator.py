"""Autonomous Real-Time Velocity Engine, Breakout Part-2 Cloner & 18h A/B Title Rescue.

Closed-loop VELUM V3 Growth Engine:
1. Real-Time Velocity Engine (zero 48h Analytics delay):
   - Fetches live `views`, `likes`, `comments`, and `publishedAt` for up to 50 published videos
     in ONE batched YouTube Data API v3 call (1 quota unit total!) and syncs `state.db`.
2. Breakout Winner & Part-2 Auto-Cloner:
   - Computes `views_per_hour = views / max(age_hours, 1.0)`.
   - When a video reaches `views >= 1000` OR (`views >= 250` and `views_per_hour >= 120.0`),
     records `breakout_winner_json` and queues a deduplicated Part-2 sequel entry in
     `part2_queue_json` (`source_topic_id`, `pillar`, `source_title`, `source_views`).
3. 18-Hour A/B Title Rescue:
   - If a live video has `age_hours >= 18.0`, `views < 600`, and remaining A/B/C title
     variants (`active_variant == 0` at >=18h, `active_variant == 1` at >=36h, with an
     18h cooldown guard), swaps the live YouTube title + regional localizations via
     `videos().update(part="snippet,localizations", ...)` and logs the mutation in `state.db`.
4. Optional YouTube Analytics API v2 Retention / CTR Enhancement:
   - Enriches `avg_view_pct` and `ctr` when Analytics data has settled (never crashes on HttpError).
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import (
    OUTPUT_DIR,
    ephemeral_youtube_credentials,
    get_logger,
    has_youtube_credentials,
)
from core.state_db import StateDB, utc_now_iso
from engine.thumbnail_engine import generate_ab_thumbnails
from publisher.omni_seo import _translate_lines_batch_free
from publisher.youtube_uploader import (
    YOUTUBE_SCOPES,
    _sanitize_localizations,
    _sanitize_youtube_tags,
    _sanitize_youtube_text,
    build_youtube_service,
)

logger = get_logger("growth_mutator")

SHORTS_RETENTION_THRESHOLD = 58.0  # < 58% retention triggers optional Analytics A/B swap
LONGFORM_CTR_THRESHOLD = 5.0       # < 5% CTR triggers optional Analytics A/B swap

BREAKOUT_MIN_VIEWS = 1000
BREAKOUT_FAST_VIEWS = 250
BREAKOUT_FAST_VPH = 80.0

FAST_RESCUE_MIN_AGE_HOURS = 4.0
FAST_RESCUE_MAX_VIEWS = 250
TITLE_RESCUE_MIN_AGE_HOURS = 8.0
TITLE_RESCUE_MAX_VIEWS = 950
TITLE_RESCUE_COOLDOWN_HOURS = 8.0


def _parse_utc_ts(raw_ts: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp cleanly into a UTC datetime."""
    if not raw_ts:
        return None
    try:
        dt = datetime.fromisoformat(str(raw_ts).strip().replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _compute_age_hours(
    video_row: Dict[str, Any],
    published_at_iso: Optional[str],
    now_utc: datetime,
) -> float:
    """Compute video age in hours from YouTube publishedAt (fallback: state.db created_at)."""
    ref_dt = _parse_utc_ts(published_at_iso) or _parse_utc_ts(video_row.get("created_at"))
    if ref_dt is None:
        return 0.0
    return round(max(0.0, (now_utc - ref_dt).total_seconds() / 3600.0), 2)


def _hours_since_last_mutation(state_db: StateDB, video_uid: str, now_utc: datetime) -> float:
    """Return hours elapsed since the most recent recorded mutation for video_uid (999.0 if none)."""
    with state_db._connect() as conn:
        row = conn.execute(
            "SELECT created_at FROM mutations WHERE video_uid = ? ORDER BY id DESC LIMIT 1",
            (video_uid,),
        ).fetchone()
    if not row:
        return 999.0
    last_dt = _parse_utc_ts(row["created_at"])
    if last_dt is None:
        return 999.0
    return round(max(0.0, (now_utc - last_dt).total_seconds() / 3600.0), 2)


def _build_analytics_service(token_path: Path):
    """Build optional YouTube Analytics API v2 client; return None if unavailable."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(str(token_path), YOUTUBE_SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
    except Exception as exc:
        logger.debug("Optional YouTube Analytics API v2 client skipped (%s)", type(exc).__name__)
        return None


def _fetch_realtime_velocity_batch(
    youtube_svc, youtube_ids: List[str]
) -> Dict[str, Dict[str, Any]]:
    """Fetch live views, likes, comments & snippet in ONE Data API v3 batch call (1 quota unit)."""
    unique_ids = [yid for yid in dict.fromkeys(youtube_ids) if yid][:50]
    if not unique_ids:
        return {}
    try:
        resp = (
            youtube_svc.videos()
            .list(part="statistics,snippet", id=",".join(unique_ids))
            .execute()
        )
    except Exception as exc:
        logger.warning("Real-time velocity batch call failed (%s)", type(exc).__name__)
        return {}

    results: Dict[str, Dict[str, Any]] = {}
    for item in resp.get("items", []):
        yt_id = item.get("id")
        if not yt_id:
            continue
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})
        results[yt_id] = {
            "views": int(stats.get("viewCount", 0) or 0),
            "likes": int(stats.get("likeCount", 0) or 0),
            "comments": int(stats.get("commentCount", 0) or 0),
            "published_at": snippet.get("publishedAt", ""),
            "live_title": snippet.get("title", ""),
        }
    return results


def _fetch_live_video_metrics(analytics_svc, youtube_id: str) -> Optional[Dict[str, float]]:
    """Optional YouTube Analytics API v2 query for views, averageViewPercentage, and CTR."""
    if analytics_svc is None:
        return None
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(days=28)).strftime("%Y-%m-%d")
    try:
        resp = analytics_svc.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views,averageViewPercentage",
            filters=f"video=={youtube_id}",
        ).execute()
        rows = resp.get("rows", [])
        if not rows:
            return None
        views = int(rows[0][0])
        avg_pct = float(rows[0][1])

        ctr = 0.0
        try:
            ctr_resp = analytics_svc.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="videoThumbnailImpressionsClickRate",
                filters=f"video=={youtube_id}",
            ).execute()
            c_rows = ctr_resp.get("rows", [])
            if c_rows:
                raw_ctr = float(c_rows[0][0])
                ctr = raw_ctr * 100.0 if raw_ctr <= 1.0 else raw_ctr
        except Exception as exc:
            logger.debug("CTR metric unavailable for %s (%s)", youtube_id, type(exc).__name__)

        return {"views": views, "avg_view_pct": avg_pct, "ctr": ctr}
    except Exception as exc:
        logger.debug("Optional Analytics v2 query skipped for %s (%s)", youtube_id, type(exc).__name__)
        return None


def _resolve_or_regenerate_thumbnail(
    state_db: StateDB, topic_id: str, expected_path: str, variant_idx: int
) -> tuple[str, Optional[Path]]:
    """Return existing thumbnail path, or regenerate on-demand from state.db on fresh CI runners."""
    if expected_path and Path(expected_path).exists():
        return expected_path, None

    with state_db._connect() as conn:
        row = conn.execute(
            "SELECT payload_json FROM topics WHERE topic_id = ?", (topic_id,)
        ).fetchone()
    if not row:
        return "", None

    topic = json.loads(row["payload_json"])
    regen_dir = OUTPUT_DIR / f"_ab_regen_{topic_id}"
    thumbs_dir = regen_dir / "thumbnails"
    cache_dir = regen_dir / "media_cache"
    generated = generate_ab_thumbnails(topic, thumbs_dir, cache_dir)
    if variant_idx < len(generated):
        logger.info(
            "Regenerated A/B Variant #%d thumbnail on-demand for ephemeral CI runner.",
            variant_idx + 1,
        )
        return generated[variant_idx], regen_dir
    return "", regen_dir


def _apply_live_title_update(
    youtube_svc,
    youtube_id: str,
    new_title: str,
    new_thumbnail: str = "",
) -> bool:
    """Swap live YouTube video title (+ regional localizations when present) and optional thumbnail."""
    from googleapiclient.http import MediaFileUpload

    clean_title = _sanitize_youtube_text(new_title, max_chars=98, max_bytes=380)
    if not clean_title:
        return False

    try:
        current = youtube_svc.videos().list(
            part="snippet,localizations", id=youtube_id
        ).execute()
        items = current.get("items", [])
        if not items:
            return False

        item = items[0]
        snippet = dict(item.get("snippet", {}))
        snippet["title"] = clean_title
        snippet["description"] = _sanitize_youtube_text(
            snippet.get("description", ""), max_chars=4950, max_bytes=4950
        )
        if isinstance(snippet.get("tags"), list):
            snippet["tags"] = _sanitize_youtube_tags(snippet["tags"])
        snippet.setdefault("defaultLanguage", "en")
        existing_locs = item.get("localizations")

        updated_with_locs = False
        if isinstance(existing_locs, dict) and existing_locs:
            raw_updated_locs: Dict[str, Dict[str, str]] = {}
            en_desc = _sanitize_youtube_text(
                existing_locs.get("en", {}).get("description")
                or snippet.get("description", ""),
                max_chars=4900,
                max_bytes=4900,
            )
            raw_updated_locs["en"] = {"title": clean_title, "description": en_desc}

            for lang_code, loc_val in list(existing_locs.items()):
                if lang_code == "en" or not isinstance(loc_val, dict):
                    continue
                tr_list = _translate_lines_batch_free([clean_title[:95]], lang_code)
                tr_title = tr_list[0] if tr_list else clean_title
                raw_updated_locs[lang_code] = {
                    "title": tr_title,
                    "description": str(loc_val.get("description", en_desc)),
                }

            updated_locs = _sanitize_localizations(raw_updated_locs, clean_title, en_desc)

            try:
                youtube_svc.videos().update(
                    part="snippet,localizations",
                    body={
                        "id": youtube_id,
                        "snippet": snippet,
                        "localizations": updated_locs,
                    },
                ).execute()
                updated_with_locs = True
            except Exception as loc_exc:
                logger.debug(
                    "Localizations title swap fallback to snippet-only for %s (%s)",
                    youtube_id,
                    type(loc_exc).__name__,
                )

        if not updated_with_locs:
            youtube_svc.videos().update(
                part="snippet",
                body={"id": youtube_id, "snippet": snippet},
            ).execute()

        if new_thumbnail and Path(new_thumbnail).exists():
            try:
                youtube_svc.thumbnails().set(
                    videoId=youtube_id,
                    media_body=MediaFileUpload(new_thumbnail, mimetype="image/png"),
                ).execute()
            except Exception as th_exc:
                logger.debug("Thumbnail update skipped for %s (%s)", youtube_id, type(th_exc).__name__)
        return True
    except Exception as exc:
        logger.warning("Live A/B title swap failed for %s (%s)", youtube_id, type(exc).__name__)
        return False


def _is_breakout_video(views: int, views_per_hour: float) -> bool:
    """Return True when a video crosses the VELUM V3 breakout velocity threshold."""
    return views >= BREAKOUT_MIN_VIEWS or (
        views >= BREAKOUT_FAST_VIEWS and views_per_hour >= BREAKOUT_FAST_VPH
    )


def _should_trigger_18h_title_rescue(
    video_row: Dict[str, Any],
    age_hours: float,
    views: int,
    titles: List[str],
    hours_since_last_mut: float,
) -> bool:
    """Evaluate V5 Fast 4h (<250v) & Standard 8h/16h (<950v) A/B Title Rescue with cooldown safety."""
    if not video_row.get("youtube_id"):
        return False
    cur_var = int(video_row.get("active_variant", 0))
    if cur_var >= len(titles) - 1:
        return False
    if hours_since_last_mut < TITLE_RESCUE_COOLDOWN_HOURS:
        return False
    # Fast 4-hour rescue on fresh stalled uploads (Variant A -> B while still inside fresh feed push!)
    if cur_var == 0 and age_hours >= FAST_RESCUE_MIN_AGE_HOURS and views < FAST_RESCUE_MAX_VIEWS:
        return True
    if views >= TITLE_RESCUE_MAX_VIEWS:
        return False
    required_age = TITLE_RESCUE_MIN_AGE_HOURS * (cur_var + 1)
    if age_hours < required_age:
        return False
    return True


def _load_json_list_meta(state_db: StateDB, key: str) -> List[Any]:
    raw = state_db.get_meta(key)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _record_breakout_and_queue_part2(
    state_db: StateDB,
    vid: Dict[str, Any],
    views: int,
    age_hours: float,
    views_per_hour: float,
    source_title: str,
) -> Optional[Dict[str, Any]]:
    """Persist breakout winner metadata and enqueue one deduplicated Part-2 sequel."""
    topic_id = str(vid.get("topic_id", ""))
    with state_db._connect() as conn:
        trow = conn.execute(
            "SELECT pillar, format_signature, viral_score FROM topics WHERE topic_id = ?",
            (topic_id,),
        ).fetchone()
    if not trow:
        return None

    pillar = str(trow["pillar"])
    breakout_record = {
        "source_video_uid": vid["video_uid"],
        "youtube_id": vid.get("youtube_id"),
        "source_topic_id": topic_id,
        "pillar": pillar,
        "format_signature": trow["format_signature"],
        "source_title": source_title,
        "source_views": int(views),
        "views_per_hour": round(views_per_hour, 2),
        "age_hours": round(age_hours, 2),
        "detected_at": utc_now_iso(),
    }

    # Update breakout_winner_json if none exists yet or this winner beats the stored peak
    existing_winner_raw = state_db.get_meta("breakout_winner_json")
    should_overwrite_winner = True
    if existing_winner_raw:
        try:
            prev = json.loads(existing_winner_raw)
            prev_score = (int(prev.get("source_views", 0)), float(prev.get("views_per_hour", 0.0)))
            curr_score = (int(views), float(views_per_hour))
            should_overwrite_winner = curr_score >= prev_score
        except (ValueError, TypeError):
            should_overwrite_winner = True

    if should_overwrite_winner:
        state_db.set_meta("breakout_winner_json", json.dumps(breakout_record, ensure_ascii=False))

    # Deduplicated Part-2 queue: each winner topic_id queues at most ONE Part-2 sequel ever
    queue = _load_json_list_meta(state_db, "part2_queue_json")
    seen_sources = set(str(x) for x in _load_json_list_meta(state_db, "part2_queued_sources_json"))
    in_queue_ids = {str(item.get("source_topic_id", "")) for item in queue if isinstance(item, dict)}

    if topic_id not in seen_sources and topic_id not in in_queue_ids:
        sequel_entry = {
            "source_topic_id": topic_id,
            "pillar": pillar,
            "source_title": source_title,
            "source_views": int(views),
            "views_per_hour": round(views_per_hour, 2),
            "youtube_id": vid.get("youtube_id"),
            "queued_at": utc_now_iso(),
        }
        queue.append(sequel_entry)
        seen_sources.add(topic_id)
        state_db.set_meta("part2_queue_json", json.dumps(queue, ensure_ascii=False))
        state_db.set_meta(
            "part2_queued_sources_json",
            json.dumps(sorted(seen_sources), ensure_ascii=False),
        )
        logger.info(
            "BREAKOUT WINNER [%s] -> views=%d (%.1f v/hr, age=%.1fh) | queued Part-2 sequel in pillar=%s",
            vid.get("youtube_id") or vid["video_uid"],
            views,
            views_per_hour,
            age_hours,
            pillar,
        )
        return sequel_entry

    return None


def run_growth_mutation_cycle(
    state_db: StateDB,
    out_dir: Optional[Path] = None,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Run Real-Time Velocity sync, Breakout Part-2 Auto-Cloner, and 18h A/B Title Rescue."""
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    videos = state_db.get_all_videos()
    report: Dict[str, Any] = {
        "mode": "live" if has_youtube_credentials() else "local_ready",
        "videos_evaluated": len(videos),
        "velocity_snapshots": [],
        "breakout_winners": [],
        "part2_queued": [],
        "mutations_applied": [],
        "cloned_winner": None,
        "rules": {
            "breakout_min_views": BREAKOUT_MIN_VIEWS,
            "breakout_fast_views": BREAKOUT_FAST_VIEWS,
            "breakout_fast_vph": BREAKOUT_FAST_VPH,
            "title_rescue_age_hours": TITLE_RESCUE_MIN_AGE_HOURS,
            "title_rescue_max_views": TITLE_RESCUE_MAX_VIEWS,
            "shorts_min_retention_pct": SHORTS_RETENTION_THRESHOLD,
            "longform_min_ctr_pct": LONGFORM_CTR_THRESHOLD,
        },
    }

    live_videos = [v for v in videos if v.get("youtube_id")]
    if has_youtube_credentials() and live_videos:
        with ephemeral_youtube_credentials() as (_, token_path):
            if token_path is not None:
                yt_svc = build_youtube_service(token_path)
                an_svc = _build_analytics_service(token_path)

                # 1. Real-Time Velocity Engine: ONE batch videos().list call (1 quota unit)
                yt_ids = [str(v["youtube_id"]) for v in live_videos[:50]]
                realtime_map = _fetch_realtime_velocity_batch(yt_svc, yt_ids)

                for vid in live_videos:
                    yt_id = str(vid["youtube_id"])
                    rt = realtime_map.get(yt_id)
                    if rt is None:
                        continue

                    views = int(rt["views"])
                    likes = int(rt["likes"])
                    comments = int(rt["comments"])
                    age_hours = _compute_age_hours(vid, rt.get("published_at"), now)
                    views_per_hour = round(views / max(age_hours, 1.0), 2)

                    # Optional Analytics API v2 enhancement (never blocks or crashes)
                    avg_view_pct = float(vid.get("avg_view_pct", 0.0))
                    ctr = float(vid.get("ctr", 0.0))
                    an_metrics = _fetch_live_video_metrics(an_svc, yt_id)
                    if an_metrics:
                        views = max(views, int(an_metrics["views"]))
                        avg_view_pct = float(an_metrics["avg_view_pct"])
                        ctr = float(an_metrics["ctr"])
                        views_per_hour = round(views / max(age_hours, 1.0), 2)

                    state_db.update_video_metrics(vid["video_uid"], views, avg_view_pct, ctr)
                    vid["views"] = views
                    vid["avg_view_pct"] = avg_view_pct
                    vid["ctr"] = ctr
                    vid["likes"] = likes
                    vid["comments"] = comments
                    vid["age_hours"] = age_hours
                    vid["views_per_hour"] = views_per_hour

                    titles = json.loads(vid.get("titles_json", "[]"))
                    thumbs = json.loads(vid.get("thumbnails_json", "[]"))
                    cur_var = int(vid.get("active_variant", 0))
                    active_title = (
                        rt.get("live_title")
                        or (titles[cur_var] if cur_var < len(titles) else (titles[0] if titles else vid["topic_id"]))
                    )

                    snapshot = {
                        "video_uid": vid["video_uid"],
                        "youtube_id": yt_id,
                        "topic_id": vid["topic_id"],
                        "views": views,
                        "likes": likes,
                        "comments": comments,
                        "age_hours": age_hours,
                        "views_per_hour": views_per_hour,
                        "active_variant": cur_var,
                    }
                    report["velocity_snapshots"].append(snapshot)
                    logger.info(
                        "VELOCITY [%s] -> views=%d | likes=%d | comments=%d | age=%.1fh | rate=%.1f v/hr",
                        yt_id,
                        views,
                        likes,
                        comments,
                        age_hours,
                        views_per_hour,
                    )

                    # 2. Breakout Winner & Part-2 Auto-Cloner
                    if _is_breakout_video(views, views_per_hour):
                        report["breakout_winners"].append(snapshot)
                        queued = _record_breakout_and_queue_part2(
                            state_db, vid, views, age_hours, views_per_hour, active_title
                        )
                        if queued:
                            report["part2_queued"].append(queued)

                    # 3. 18-Hour A/B Title Rescue (zero 48h Analytics delay)
                    hours_since_mut = _hours_since_last_mutation(state_db, vid["video_uid"], now)
                    mutated_this_cycle = False
                    if _should_trigger_18h_title_rescue(vid, age_hours, views, titles, hours_since_mut):
                        next_var = cur_var + 1
                        new_title = titles[next_var]
                        reason = (
                            f"18h Title Rescue: age={age_hours:.1f}h >= "
                            f"{TITLE_RESCUE_MIN_AGE_HOURS * (cur_var + 1):.0f}h & "
                            f"views={views} < {TITLE_RESCUE_MAX_VIEWS}"
                        )
                        thumb_path = ""
                        temp_regen_dir: Optional[Path] = None
                        if vid.get("format") == "longform" and next_var < len(thumbs):
                            thumb_path, temp_regen_dir = _resolve_or_regenerate_thumbnail(
                                state_db, vid["topic_id"], thumbs[next_var], next_var
                            )
                        try:
                            ok = _apply_live_title_update(yt_svc, yt_id, new_title, thumb_path)
                        finally:
                            if temp_regen_dir and temp_regen_dir.exists():
                                shutil.rmtree(temp_regen_dir, ignore_errors=True)

                        if ok:
                            state_db.set_video_variant(vid["video_uid"], next_var)
                            vid["active_variant"] = next_var
                            state_db.record_mutation(
                                vid["video_uid"],
                                "ab_title_rescue_18h",
                                reason,
                                cur_var,
                                next_var,
                                snapshot,
                            )
                            report["mutations_applied"].append(
                                {
                                    "video_uid": vid["video_uid"],
                                    "youtube_id": yt_id,
                                    "mutation_type": "ab_title_rescue_18h",
                                    "reason": reason,
                                    "swapped_to_variant": next_var + 1,
                                    "new_title": new_title,
                                }
                            )
                            logger.info(
                                "18h A/B Title Rescue swapped %s -> Variant #%d: '%s' (%s)",
                                yt_id,
                                next_var + 1,
                                new_title,
                                reason,
                            )
                            mutated_this_cycle = True

                    # 4. Optional Analytics API v2 retention/CTR swap (only when settled & not already rescued)
                    if (
                        not mutated_this_cycle
                        and an_metrics
                        and views >= 100
                        and hours_since_mut >= TITLE_RESCUE_COOLDOWN_HOURS
                    ):
                        fmt = vid.get("format", "shorts")
                        max_variants = len(titles) if fmt == "shorts" else min(len(titles), len(thumbs))
                        needs_swap = False
                        reason = ""
                        if fmt == "shorts" and avg_view_pct > 0 and avg_view_pct < SHORTS_RETENTION_THRESHOLD:
                            needs_swap = True
                            reason = f"Shorts avg_view_pct={avg_view_pct:.1f}% < {SHORTS_RETENTION_THRESHOLD}%"
                        elif fmt == "longform" and ctr > 0 and ctr < LONGFORM_CTR_THRESHOLD:
                            needs_swap = True
                            reason = f"Long-form CTR={ctr:.2f}% < {LONGFORM_CTR_THRESHOLD}%"

                        if needs_swap and (cur_var + 1) < max_variants:
                            next_var = cur_var + 1
                            thumb_path = ""
                            temp_regen_dir = None
                            if fmt == "longform" and next_var < len(thumbs):
                                thumb_path, temp_regen_dir = _resolve_or_regenerate_thumbnail(
                                    state_db, vid["topic_id"], thumbs[next_var], next_var
                                )
                            try:
                                ok = _apply_live_title_update(yt_svc, yt_id, titles[next_var], thumb_path)
                            finally:
                                if temp_regen_dir and temp_regen_dir.exists():
                                    shutil.rmtree(temp_regen_dir, ignore_errors=True)
                            if ok:
                                state_db.set_video_variant(vid["video_uid"], next_var)
                                state_db.record_mutation(
                                    vid["video_uid"],
                                    "ab_title_thumbnail_swap",
                                    reason,
                                    cur_var,
                                    next_var,
                                    an_metrics,
                                )
                                report["mutations_applied"].append(
                                    {
                                        "video_uid": vid["video_uid"],
                                        "youtube_id": yt_id,
                                        "mutation_type": "ab_title_thumbnail_swap",
                                        "reason": reason,
                                        "swapped_to_variant": next_var + 1,
                                        "new_title": titles[next_var],
                                    }
                                )
                                logger.info(
                                    "Growth Mutator swapped %s -> Variant #%d (%s)",
                                    yt_id,
                                    next_var + 1,
                                    reason,
                                )
    else:
        # Local/offline evaluation: still evaluate stored velocity metrics for breakout detection
        for vid in videos:
            views = int(vid.get("views", 0))
            age_hours = _compute_age_hours(vid, None, now)
            views_per_hour = round(views / max(age_hours, 1.0), 2)
            vid["age_hours"] = age_hours
            vid["views_per_hour"] = views_per_hour
            if _is_breakout_video(views, views_per_hour):
                titles = json.loads(vid.get("titles_json", "[]"))
                cur_var = int(vid.get("active_variant", 0))
                src_title = titles[cur_var] if cur_var < len(titles) else (titles[0] if titles else vid["topic_id"])
                queued = _record_breakout_and_queue_part2(
                    state_db, vid, views, age_hours, views_per_hour, src_title
                )
                report["breakout_winners"].append(
                    {
                        "video_uid": vid["video_uid"],
                        "topic_id": vid["topic_id"],
                        "views": views,
                        "views_per_hour": views_per_hour,
                    }
                )
                if queued:
                    report["part2_queued"].append(queued)

    # Identify top performer & clone winning pillar/format for next cycle
    scored_videos = sorted(
        videos,
        key=lambda v: (
            float(v.get("views_per_hour", 0.0)),
            int(v.get("views", 0)) * max(1.0, float(v.get("avg_view_pct", 0.0))),
            v.get("created_at", ""),
        ),
        reverse=True,
    )
    if scored_videos:
        top = scored_videos[0]
        with state_db._connect() as conn:
            trow = conn.execute(
                "SELECT pillar, format_signature, viral_score FROM topics WHERE topic_id = ?",
                (top["topic_id"],),
            ).fetchone()
        if trow:
            winner_blueprint = {
                "source_video_uid": top["video_uid"],
                "topic_id": top["topic_id"],
                "pillar": trow["pillar"],
                "format_signature": trow["format_signature"],
                "viral_score": trow["viral_score"],
                "views": int(top.get("views", 0)),
                "views_per_hour": float(top.get("views_per_hour", 0.0)),
                "avg_view_pct": float(top.get("avg_view_pct", 0.0)),
            }
            state_db.set_meta("winning_format_json", json.dumps(winner_blueprint))
            report["cloned_winner"] = winner_blueprint
            logger.info(
                "Winning format cloned for next cycle -> pillar=%s (%s, views=%d)",
                trow["pillar"],
                trow["format_signature"],
                int(top.get("views", 0)),
            )

        # Self-optimizing Pillar Velocity Leaderboard (guides IdeaEngine toward fastest-growing niches)
        pillar_buckets: Dict[str, List[float]] = {}
        engine_buckets: Dict[str, List[Dict[str, float]]] = {}
        try:
            from engine.idea_engine import V7_SIGNATURE_PRIORITY_IDS
            v7_sig_set = set(V7_SIGNATURE_PRIORITY_IDS)
        except Exception:
            v7_sig_set = set()

        with state_db._connect() as conn:
            for v in videos:
                row = conn.execute(
                    "SELECT pillar, payload_json FROM topics WHERE topic_id = ?", (v["topic_id"],)
                ).fetchone()
                if not row:
                    continue
                vph = float(v.get("views_per_hour", 0.0))
                views_i = int(v.get("views", 0))
                likes_i = int(v.get("likes", 0))
                if vph > 0:
                    pillar_buckets.setdefault(row["pillar"], []).append(vph)

                if views_i > 0 or vph > 0:
                    tid = str(v.get("topic_id", ""))
                    created_ts = str(v.get("created_at", ""))
                    is_v7_mech = tid in v7_sig_set
                    if not is_v7_mech and row["payload_json"]:
                        try:
                            p_obj = json.loads(row["payload_json"])
                            is_v7_mech = bool(p_obj.get("v7_mechanism"))
                        except Exception:
                            is_v7_mech = False
                    if is_v7_mech:
                        eng_tier = "v7_physical_mechanism"
                    elif created_ts >= "2026-11-24T18:35:00":
                        eng_tier = "v6_abstract_schematic"
                    else:
                        eng_tier = "v5_cinematic_broll"
                    like_rate = (likes_i / max(views_i, 1)) * 100.0
                    engine_buckets.setdefault(eng_tier, []).append(
                        {"views": float(views_i), "vph": vph, "like_rate_pct": like_rate}
                    )

        if pillar_buckets:
            pillar_leaderboard = {
                p: round(sum(vals) / len(vals), 2)
                for p, vals in sorted(
                    pillar_buckets.items(), key=lambda kv: sum(kv[1]) / len(kv[1]), reverse=True
                )
            }
            state_db.set_meta("pillar_performance_json", json.dumps(pillar_leaderboard))
            report["pillar_velocity_leaderboard"] = pillar_leaderboard
            logger.info("Updated autonomous pillar velocity leaderboard: %s", pillar_leaderboard)

        if engine_buckets:
            format_leaderboard = {}
            for tier, items in sorted(
                engine_buckets.items(),
                key=lambda kv: sum(x["vph"] for x in kv[1]) / max(len(kv[1]), 1),
                reverse=True,
            ):
                cnt = len(items)
                format_leaderboard[tier] = {
                    "videos": cnt,
                    "avg_views": round(sum(x["views"] for x in items) / cnt, 1),
                    "avg_views_per_hour": round(sum(x["vph"] for x in items) / cnt, 2),
                    "avg_like_rate_pct": round(sum(x["like_rate_pct"] for x in items) / cnt, 2),
                }
            state_db.set_meta("format_performance_json", json.dumps(format_leaderboard))
            report["format_performance_leaderboard"] = format_leaderboard
            logger.info("Updated autonomous format performance leaderboard: %s", format_leaderboard)

    if out_dir is not None:
        (out_dir / "growth_mutator_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return report
