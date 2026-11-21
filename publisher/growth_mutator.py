"""Autonomous A/B Growth Mutator & Winning Format Cloner (`growth_mutator.py`).

Closed-loop YouTube Analytics feedback engine:
1. Fetches real performance metrics via YouTube Analytics API v2 (views,
   averageViewPercentage, impressionClickThroughRate) when OAuth is active.
2. Evaluates strict performance triggers:
   - Shorts:    averageViewPercentage < 70.0%  -> swap Title & Thumbnail to next A/B/C variant
   - Long-form: CTR < 5.0%                     -> swap Title & Thumbnail to next A/B/C variant
3. Pushes live title & thumbnail updates via YouTube Data API v3 and logs every
   mutation in `state.db`.
4. Finds the top-performing video and clones its winning pillar/format signature
   into `state.db` (`winning_format_json`) so tomorrow's pipeline doubles down on winners.
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
from core.state_db import StateDB
from engine.thumbnail_engine import generate_ab_thumbnails
from publisher.youtube_uploader import YOUTUBE_SCOPES, build_youtube_service

logger = get_logger("growth_mutator")

SHORTS_RETENTION_THRESHOLD = 70.0  # < 70% viewed/retention triggers A/B swap
LONGFORM_CTR_THRESHOLD = 5.0       # < 5% CTR triggers A/B swap


def _build_analytics_service(token_path: Path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(str(token_path), YOUTUBE_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)


def _fetch_live_video_metrics(analytics_svc, youtube_id: str) -> Optional[Dict[str, float]]:
    """Query YouTube Analytics API v2 for a video's views, averageViewPercentage, and CTR."""
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

        # Try fetching CTR separately (availability depends on YouTube Analytics scope/age)
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
                ctr = float(c_rows[0][0]) * 100.0 if float(c_rows[0][0]) <= 1.0 else float(c_rows[0][0])
        except Exception as exc:
            logger.debug("CTR metric unavailable for %s (%s)", youtube_id, type(exc).__name__)

        return {"views": views, "avg_view_pct": avg_pct, "ctr": ctr}
    except Exception as exc:
        logger.warning("Analytics query skipped for %s (%s)", youtube_id, type(exc).__name__)
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


def _apply_live_ab_swap(
    youtube_svc, youtube_id: str, new_title: str, new_thumbnail: str
) -> bool:
    """Update title and thumbnail on YouTube Data API v3."""
    from googleapiclient.http import MediaFileUpload

    try:
        current = youtube_svc.videos().list(part="snippet", id=youtube_id).execute()
        items = current.get("items", [])
        if not items:
            return False
        snippet = items[0]["snippet"]
        snippet["title"] = new_title[:98]
        youtube_svc.videos().update(
            part="snippet", body={"id": youtube_id, "snippet": snippet}
        ).execute()

        if new_thumbnail and Path(new_thumbnail).exists():
            youtube_svc.thumbnails().set(
                videoId=youtube_id,
                media_body=MediaFileUpload(new_thumbnail, mimetype="image/png"),
            ).execute()
        return True
    except Exception as exc:
        logger.warning("Live A/B swap failed for %s (%s)", youtube_id, type(exc).__name__)
        return False


def run_growth_mutation_cycle(
    state_db: StateDB, out_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """Inspect video performance, execute A/B title+thumbnail mutations, and clone top format."""
    videos = state_db.get_all_videos()
    report: Dict[str, Any] = {
        "mode": "live" if has_youtube_credentials() else "local_ready",
        "videos_evaluated": len(videos),
        "mutations_applied": [],
        "cloned_winner": None,
        "rules": {
            "shorts_min_retention_pct": SHORTS_RETENTION_THRESHOLD,
            "longform_min_ctr_pct": LONGFORM_CTR_THRESHOLD,
        },
    }

    if has_youtube_credentials() and any(v.get("youtube_id") for v in videos):
        with ephemeral_youtube_credentials() as (_, token_path):
            if token_path is not None:
                yt_svc = build_youtube_service(token_path)
                an_svc = _build_analytics_service(token_path)

                for vid in videos:
                    yt_id = vid.get("youtube_id")
                    if not yt_id:
                        continue
                    metrics = _fetch_live_video_metrics(an_svc, yt_id)
                    if not metrics:
                        continue
                    state_db.update_video_metrics(
                        vid["video_uid"],
                        int(metrics["views"]),
                        float(metrics["avg_view_pct"]),
                        float(metrics["ctr"]),
                    )
                    vid["views"] = int(metrics["views"])
                    vid["avg_view_pct"] = float(metrics["avg_view_pct"])
                    vid["ctr"] = float(metrics["ctr"])

                    # Require minimal statistical signal (>= 100 views) before mutating live videos
                    if vid["views"] < 100:
                        continue

                    fmt = vid["format"]
                    cur_var = int(vid.get("active_variant", 0))
                    titles = json.loads(vid.get("titles_json", "[]"))
                    thumbs = json.loads(vid.get("thumbnails_json", "[]"))
                    max_variants = min(len(titles), len(thumbs))

                    needs_swap = False
                    reason = ""
                    if fmt == "shorts" and vid["avg_view_pct"] < SHORTS_RETENTION_THRESHOLD:
                        needs_swap = True
                        reason = f"Shorts avg_view_pct={vid['avg_view_pct']:.1f}% < {SHORTS_RETENTION_THRESHOLD}%"
                    elif fmt == "longform" and vid["ctr"] > 0 and vid["ctr"] < LONGFORM_CTR_THRESHOLD:
                        needs_swap = True
                        reason = f"Long-form CTR={vid['ctr']:.2f}% < {LONGFORM_CTR_THRESHOLD}%"

                    if needs_swap and (cur_var + 1) < max_variants:
                        next_var = cur_var + 1
                        thumb_path, temp_regen_dir = _resolve_or_regenerate_thumbnail(
                            state_db, vid["topic_id"], thumbs[next_var], next_var
                        )
                        try:
                            ok = _apply_live_ab_swap(yt_svc, yt_id, titles[next_var], thumb_path)
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
                                metrics,
                            )
                            report["mutations_applied"].append(
                                {
                                    "video_uid": vid["video_uid"],
                                    "youtube_id": yt_id,
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

    # Identify top performer (or highest-scored rendered topic on Day 1) & clone format for tomorrow
    scored_videos = sorted(
        videos,
        key=lambda v: (v.get("views", 0) * max(1.0, float(v.get("avg_view_pct", 0.0))), v.get("created_at", "")),
        reverse=True,
    )
    if scored_videos:
        top = scored_videos[0]
        # Look up topic pillar via state.db
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
                "views": top.get("views", 0),
                "avg_view_pct": top.get("avg_view_pct", 0.0),
            }
            state_db.set_meta("winning_format_json", json.dumps(winner_blueprint))
            report["cloned_winner"] = winner_blueprint
            logger.info(
                "Winning format cloned for next cycle -> pillar=%s (%s)",
                trow["pillar"],
                trow["format_signature"],
            )

    if out_dir is not None:
        (out_dir / "growth_mutator_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return report
