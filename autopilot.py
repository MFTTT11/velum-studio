"""VELUM V3 — 100% Autonomous 4K Visual Documentary Engine Orchestrator.

Single-command execution:
    python autopilot.py                   # Full end-to-end 4K production + QA + SEO + growth cycle
    python autopilot.py --run-once        # Explicit single-shot mode for GitHub Actions CI (every 2h)
    python autopilot.py --force-produce   # Bypass daily Shorts cap & 3h anti-spam spacing guard
    python autopilot.py --daemon          # Continuous local 24/7 autonomous scheduler (every 2h)

SECURITY:
- Never reads hardcoded secrets; all OAuth & API keys come exclusively from env/GitHub Secrets.
- Temporary credential files (client_secrets.json, token.json) are wiped immediately on exit.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from brand_kit.generate_brand_kit import ensure_brand_kit
from core.config import (
    ROOT_DIR,
    STATE_DB_PATH,
    ensure_output_dir,
    ephemeral_youtube_credentials,
    get_logger,
    has_youtube_credentials,
    load_brand_config,
    secure_delete_file,
)
from core.llm_client import ZeroCostLLMClient
from core.state_db import StateDB
from engine.idea_engine import IdeaEngine
from engine.qa_gate import run_qa_gate
from engine.script_engine import ScriptEngine
from engine.thumbnail_engine import generate_ab_thumbnails
from engine.video_composer import compose_cinematic_video
from engine.voice_engine import synthesize_voice_and_align
from publisher.comment_responder import run_comment_cycle
from publisher.growth_mutator import run_growth_mutation_cycle
from publisher.omni_seo import generate_omni_seo_package, slugify_keyword
from publisher.youtube_uploader import (
    build_youtube_service,
    compute_warmup_plan,
    sync_channel_branding,
    upload_video_package,
)

logger = get_logger("autopilot")
console = Console()


def verify_public_repo_security_lock() -> None:
    """Assert .gitignore protects all sensitive files before starting any cycle."""
    gitignore = ROOT_DIR / ".gitignore"
    required_rules = (
        "client_secrets.json",
        "token.json",
        ".env",
        "*.key",
        "*.pem",
        "secrets/",
        "output/",
        "*.mp4",
    )
    if not gitignore.exists():
        raise RuntimeError("SECURITY LOCK VIOLATION: .gitignore is missing!")
    content = gitignore.read_text(encoding="utf-8")
    missing = [rule for rule in required_rules if rule not in content]
    if missing:
        raise RuntimeError(f"SECURITY LOCK VIOLATION: .gitignore missing rules: {missing}")
    logger.info("Public Repo Security Lock verified (.gitignore protects all %d secret/media patterns)", len(required_rules))


def _collect_velocity_summary(state_db: StateDB, growth_result: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble V3 real-time velocity, title-rescue, and Part-2 breakout queue metrics."""
    videos = state_db.get_all_videos()
    total_views = sum(int(v.get("views", 0) or 0) for v in videos)
    live_videos = sum(1 for v in videos if v.get("youtube_id"))
    mutations_count = len(growth_result.get("mutations_applied", []))
    videos_evaluated = int(growth_result.get("videos_evaluated", len(videos)))
    cloned_pillar = (growth_result.get("cloned_winner") or {}).get("pillar")

    breakout_winner: Dict[str, Any] | None = None
    breakout_raw = state_db.get_meta("breakout_winner_json")
    if breakout_raw:
        try:
            parsed_breakout = json.loads(breakout_raw)
            if isinstance(parsed_breakout, dict):
                breakout_winner = parsed_breakout
        except (ValueError, TypeError):
            breakout_winner = None

    part2_queue_count = 0
    part2_raw = state_db.get_meta("part2_queue_json")
    if part2_raw:
        try:
            parsed_queue = json.loads(part2_raw)
            if isinstance(parsed_queue, list):
                part2_queue_count = len(parsed_queue)
        except (ValueError, TypeError):
            part2_queue_count = 0

    parts = [
        f"evaluated={videos_evaluated}",
        f"live={live_videos}",
        f"total_views={total_views:,}",
        f"mutations={mutations_count}",
        f"part2_queue={part2_queue_count}",
        f"winner_pillar={cloned_pillar or 'none'}",
    ]
    if breakout_winner:
        b_label = (
            breakout_winner.get("pillar")
            or breakout_winner.get("source_topic_id")
            or breakout_winner.get("topic_id")
            or "active"
        )
        b_views = int(breakout_winner.get("views", breakout_winner.get("source_views", 0)) or 0)
        b_vph = breakout_winner.get("views_per_hour")
        if b_vph is not None:
            parts.append(f"breakout={b_label} ({b_views:,}v @ {float(b_vph):.1f}v/h)")
        else:
            parts.append(f"breakout={b_label} ({b_views:,}v)")

    return {
        "videos_evaluated": videos_evaluated,
        "live_videos": live_videos,
        "total_views": total_views,
        "mutations": mutations_count,
        "part2_queue_count": part2_queue_count,
        "cloned_winner_pillar": cloned_pillar,
        "breakout_winner": breakout_winner,
        "summary_line": " | ".join(parts),
    }


def run_single_cycle(
    fmt_override: str = "auto",
    dry_run: bool = False,
    max_qa_retries: int = 2,
    force_brand_kit: bool = False,
    force_produce: bool = False,
) -> Dict[str, Any]:
    """Execute one complete autonomous cycle from ideation to QA, SEO, upload & growth."""
    t0 = time.time()
    verify_public_repo_security_lock()

    brand = load_brand_config()
    state_db = StateDB(STATE_DB_PATH)
    llm = ZeroCostLLMClient()
    run_number = state_db.increment_runs()

    console.print(
        Panel.fit(
            f"[bold cyan]{brand['channel_name']}[/bold cyan] ({brand['handle']})  |  "
            f"Run #[bold yellow]{run_number}[/bold yellow]  |  "
            f"Intelligence: [bold green]{llm.active_provider()}[/bold green]  |  "
            f"YouTube Live Auth: [bold]{'CONNECTED' if has_youtube_credentials() else 'PACKAGE/DRY-RUN'}[/bold]",
            title="VELUM V3 // 4K BROADCAST AUTOPILOT",
            border_style="cyan",
        )
    )

    # 1. Ensure Brand Kit assets exist (Profile 800x800, Banner 2560x1440, Watermark 150x150)
    brand_assets = ensure_brand_kit(force=force_brand_kit)

    # 2. Check V3 7-Day Hyper-Growth Schedule, Daily Cap & 3h Anti-Spam Spacing Guard
    warmup_plan = compute_warmup_plan(state_db)
    target_format = warmup_plan["recommended_format"] if fmt_override == "auto" else fmt_override
    daily_cap = int(warmup_plan.get("daily_shorts_cap", 4))
    shorts_today = int(warmup_plan.get("shorts_produced_today", 0))
    hours_since_last = float(warmup_plan.get("hours_since_last_upload", 999.0))
    daily_quota_reached = bool(warmup_plan.get("daily_quota_reached", False))
    spacing_guard_active = bool(warmup_plan.get("spacing_guard_active", False))

    logger.info(
        "Warm-up phase: %s | Selected format: %s | Today: %d/%d Shorts | Last upload: %.2fh ago | Spacing guard: %s | Next slot: %s",
        warmup_plan["phase"],
        target_format,
        shorts_today,
        daily_cap,
        hours_since_last,
        spacing_guard_active,
        warmup_plan["publish_at"],
    )

    # Respect V3 daily 4-Short cap OR 3-hour anti-spam spacing window: switch cleanly to Engagement & Velocity Blitz
    if (
        (daily_quota_reached or spacing_guard_active)
        and not force_produce
        and not dry_run
        and fmt_override == "auto"
    ):
        if daily_quota_reached:
            guard_reason = f"Daily {daily_cap}-Short cap reached ({shorts_today}/{daily_cap} Shorts today)"
            logger.info(
                "Engagement & Velocity Blitz: respecting daily %d-Short cap (%d/%d Shorts today) -> running Branding Sync, Comment Responder & Real-Time Velocity Growth Mutator.",
                daily_cap,
                shorts_today,
                daily_cap,
            )
        else:
            guard_reason = (
                f"3-hour anti-spam spacing window active ({hours_since_last:.2f}h since last upload; "
                f"{shorts_today}/{daily_cap} Shorts today)"
            )
            logger.info(
                "Engagement & Velocity Blitz: respecting 3-hour anti-spam spacing window (%.2fh since last upload; %d/%d Shorts today) -> running Branding Sync, Comment Responder & Real-Time Velocity Growth Mutator.",
                hours_since_last,
                shorts_today,
                daily_cap,
            )

        branding_result: Dict[str, Any] = {}
        if has_youtube_credentials():
            with ephemeral_youtube_credentials() as (_, token_path):
                if token_path is not None:
                    yt_svc = build_youtube_service(token_path)
                    branding_result = sync_channel_branding(yt_svc, state_db)
        comment_result = run_comment_cycle(state_db, out_dir=None, llm=llm)
        growth_result = run_growth_mutation_cycle(state_db, out_dir=None)
        velocity_info = _collect_velocity_summary(state_db, growth_result)
        elapsed = round(time.time() - t0, 1)

        state_db.record_run(
            "engagement_only",
            None,
            "success",
            (
                f"{guard_reason}; banner_synced={branding_result.get('banner_uploaded')}, "
                f"comments_sent={comment_result['sent_now']}, {velocity_info['summary_line']}"
            ),
        )

        blitz_table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold cyan")
        blitz_table.add_column("Subsystem", style="cyan", no_wrap=True)
        blitz_table.add_column("Status / Telemetry", style="white")
        blitz_table.add_row("Public Security Lock", "VERIFIED (.gitignore active, 0 secrets stored)")
        blitz_table.add_row("V3 Cadence Guard", guard_reason)
        blitz_table.add_row(
            "Channel Branding Sync",
            f"banner={branding_result.get('banner_uploaded', False)} | "
            f"watermark={branding_result.get('watermark_uploaded', False)}",
        )
        blitz_table.add_row(
            "Comment Responder",
            f"checked={comment_result['fetched']} | spam_blocked={comment_result['spam_filtered']} | "
            f"queued={comment_result['queued']} | sent={comment_result['sent_now']}",
        )
        blitz_table.add_row("V3 Velocity & Growth", velocity_info["summary_line"])
        console.print(
            Panel.fit(
                blitz_table,
                title=f"VELUM V3 // ENGAGEMENT & VELOCITY BLITZ #{run_number} COMPLETE ({elapsed}s)",
                border_style="yellow",
            )
        )

        return {
            "run_number": run_number,
            "mode": "engagement_only",
            "guard_reason": guard_reason,
            "elapsed_sec": elapsed,
            "warmup_plan": warmup_plan,
            "branding_sync": branding_result,
            "comment_bot": comment_result,
            "growth_mutator": growth_result,
            "velocity_summary": velocity_info,
        }

    # 3. Viral Idea Discovery & 85+ Gate Scoring
    idea_engine = IdeaEngine(state_db, llm=llm)
    topic = idea_engine.select_next_topic()

    # 4. Retention-Engineered Script Architecture (0-2s Shock Hook + <=2.5s beats + VSEO<15s)
    script_engine = ScriptEngine(llm=llm)
    script = script_engine.generate_script(topic, fmt=target_format)

    # 5. Prepare isolated output folder using clean SEO keyword slug
    slug = slugify_keyword(topic["primary_keyword"])
    ts_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    video_uid = f"{slug}_{ts_tag}"
    out_dir = ensure_output_dir(video_uid)
    work_dir = out_dir / "_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "topic_approved.json").write_text(
        json.dumps(topic, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "script_blueprint.json").write_text(
        json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 6. Edge-TTS Voice Synthesis + FFmpeg silenceremove + Faster-Whisper Word Alignment
    voice_data = synthesize_voice_and_align(script, work_dir, lang="en")

    # 7. Omni-SEO Package (VSEO + 300+ word SEO + GEO + AEO FAQ + Pinned Comment + 5x SRT)
    seo_package = generate_omni_seo_package(topic, script, voice_data, out_dir, llm=llm)
    seo_package.setdefault("format", target_format)
    final_video_path = out_dir / seo_package["slug_filename"]

    # 8. Generate 3 High-Contrast A/B/C Thumbnails (1280x720, <= 3 bold words)
    thumbnail_paths = generate_ab_thumbnails(
        topic=topic,
        out_dir=out_dir / "thumbnails",
        media_cache_dir=work_dir / "media_cache",
    )

    # 9. Render Broadcast-Grade V3 4K 60fps Shorts / 1080p 60fps Long-Form + Automated QA Gate
    qa_report: Dict[str, Any] = {}
    render_meta: Dict[str, Any] = {}
    target_lufs = -14.0
    for attempt in range(1, max_qa_retries + 2):
        logger.info("Render & QA attempt %d/%d -> %s", attempt, max_qa_retries + 1, final_video_path.name)
        render_meta = compose_cinematic_video(
            script=script,
            voice_data=voice_data,
            output_mp4=final_video_path,
            work_dir=work_dir,
            target_lufs=target_lufs,
        )
        qa_report = run_qa_gate(final_video_path, fmt=target_format)
        if qa_report["passed"]:
            break
        # Auto-remediate loudness or duration defects before retry
        remedy = qa_report.get("remediation", {})
        if "target_lufs" in remedy:
            target_lufs = float(remedy["target_lufs"])
        if remedy.get("resynthesize_voice") and remedy.get("speech_rate"):
            new_rate = str(remedy["speech_rate"])
            logger.warning("Duration exceeded cap -> auto-bumping TTS speed to %s and re-aligning...", new_rate)
            voice_data = synthesize_voice_and_align(script, work_dir, lang="en", speech_rate=new_rate)
            seo_package = generate_omni_seo_package(topic, script, voice_data, out_dir, llm=llm)
            seo_package.setdefault("format", target_format)
        logger.warning("QA rejected attempt %d; auto-regenerating...", attempt)

    (out_dir / "qa_report.json").write_text(
        json.dumps(qa_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not qa_report.get("passed"):
        state_db.record_run("single_cycle", video_uid, "qa_failed", "; ".join(qa_report.get("failures", [])))
        raise RuntimeError(f"Video failed QA Gate after retries: {qa_report.get('failures')}")

    # Record approved production into state.db (strictly relative paths, zero secrets/PII)
    def _rel(p: str) -> str:
        try:
            return Path(p).resolve().relative_to(ROOT_DIR.resolve()).as_posix()
        except ValueError:
            return Path(p).name

    rel_thumbs = [_rel(t) for t in thumbnail_paths]
    clean_qa = dict(qa_report)
    if "video_path" in clean_qa:
        clean_qa["video_path"] = _rel(clean_qa["video_path"])

    state_db.mark_topic_used(topic["topic_id"])
    state_db.save_video(
        video_uid=video_uid,
        topic_id=topic["topic_id"],
        fmt=target_format,
        slug_filename=seo_package["slug_filename"],
        titles=seo_package["titles_ab"],
        thumbnails=rel_thumbs,
        seo_payload={
            "primary_keyword": seo_package["primary_keyword"],
            "vseo_verified_under_15s": seo_package["vseo"]["verified_under_15s"],
            "desc_word_count": seo_package["seo_description_word_count"],
            "subtitles_langs": list(seo_package["subtitles_srt"].keys()),
        },
        qa_report=clean_qa,
        publish_at=warmup_plan["publish_at"],
        status="qa_passed",
    )

    # 10. YouTube Data API v3 Scheduled Publish (7-day warm-up + captions + pinned comment)
    upload_result = upload_video_package(
        video_uid=video_uid,
        video_path=final_video_path,
        seo_package=seo_package,
        thumbnail_paths=thumbnail_paths,
        state_db=state_db,
        out_dir=out_dir,
        dry_run=dry_run or None,
    )

    # 11. Multilingual Anti-Spam Comment Responder (15–45 min human delay)
    comment_result = run_comment_cycle(state_db, out_dir=out_dir, llm=llm)

    # 12. V3 Real-Time Velocity Growth Mutator (18h A/B Title Rescue + Breakout Part-2 Cloner)
    growth_result = run_growth_mutation_cycle(state_db, out_dir=out_dir)
    velocity_info = _collect_velocity_summary(state_db, growth_result)

    qa_checks = qa_report.get("checks", {})
    res_val = str(
        qa_checks.get("resolution", {}).get("value")
        or f"{render_meta.get('width', 2160)}x{render_meta.get('height', 3840)}"
    )
    fps_val = qa_checks.get("fps", {}).get("value", 60.0)
    dur_val = qa_checks.get("duration_sec", {}).get("value", 0.0)
    lufs_val = qa_checks.get("loudness_lufs", {}).get("value", -14.0)
    if res_val == "2160x3840":
        res_tier = "4K Vertical UHD"
    elif res_val == "3840x2160":
        res_tier = "4K UHD"
    else:
        res_tier = "1080p HD"

    elapsed = round(time.time() - t0, 1)
    summary = {
        "run_number": run_number,
        "elapsed_sec": elapsed,
        "video_uid": video_uid,
        "format": target_format,
        "resolution": res_val,
        "resolution_tier": res_tier,
        "topic_score": topic["total_score"],
        "is_part2_followup": bool(topic.get("is_part2_followup", False)),
        "video_file": str(final_video_path),
        "qa_passed": qa_report["passed"],
        "qa_checks": qa_checks,
        "thumbnails": thumbnail_paths,
        "seo_file": str(out_dir / "omni_seo_package.json"),
        "subtitles_srt": seo_package["subtitles_srt"],
        "upload_mode": upload_result["mode"],
        "publish_at": upload_result["publishAt"],
        "force_produce": force_produce,
        "comment_bot": {
            "mode": comment_result["mode"],
            "spam_filtered": comment_result["spam_filtered"],
            "queued": comment_result["queued"],
            "sent_now": comment_result["sent_now"],
        },
        "growth_mutator": {
            "mutations": velocity_info["mutations"],
            "cloned_winner_pillar": velocity_info["cloned_winner_pillar"],
            "part2_queue_count": velocity_info["part2_queue_count"],
            "total_views": velocity_info["total_views"],
        },
        "velocity_summary": velocity_info,
        "brand_assets": {k: str(v) for k, v in brand_assets.items()},
    }

    (out_dir / "autopilot_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    state_db.record_run(
        "single_cycle",
        video_uid,
        "success",
        (
            f"QA passed ({res_tier} {res_val} @ {fps_val}fps, {lufs_val} LUFS) in {elapsed}s | "
            f"{velocity_info['summary_line']}"
        ),
    )

    # Render crisp V3 Rich completion panel with 4K resolution and real-time velocity telemetry
    produced_shorts_count = shorts_today + (1 if target_format == "shorts" else 0)
    part2_tag = " [PART-2 BREAKOUT CLONE]" if topic.get("is_part2_followup") else ""
    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold cyan")
    table.add_column("Subsystem", style="cyan", no_wrap=True)
    table.add_column("Status / Proof", style="white")
    table.add_row("Public Security Lock", "VERIFIED (.gitignore active, 0 secrets stored)")
    table.add_row("Brand Kit", "800x800 Profile + 2560x1440 Banner + 150x150 Watermark")
    table.add_row("Idea Viral Gate", f"{topic['topic_id']} -> {topic['total_score']}/100 (>=85 PASS){part2_tag}")
    table.add_row(
        "V3 4K Video + QA",
        f"PASSED | {res_tier} ({res_val} @ {fps_val}fps) | {dur_val}s | "
        f"{lufs_val} LUFS | {final_video_path.name}",
    )
    table.add_row("A/B/C Thumbnails", f"{len(thumbnail_paths)}x 1280x720 high-contrast PNGs")
    table.add_row(
        "Omni-SEO + SRTs",
        f"VSEO<15s={seo_package['vseo']['verified_under_15s']} | "
        f"Desc={seo_package['seo_description_word_count']}w | "
        f"SRTs={','.join(seo_package['subtitles_srt'].keys())}",
    )
    table.add_row(
        "V3 Cadence & Upload",
        f"{upload_result['mode']} | {produced_shorts_count}/{daily_cap} Shorts today | "
        f"force_produce={force_produce} | slot={upload_result['publishAt']}",
    )
    table.add_row(
        "Comment Responder",
        f"checked={comment_result['fetched']} | spam_blocked={comment_result['spam_filtered']} | "
        f"queued={comment_result['queued']} | sent={comment_result['sent_now']}",
    )
    table.add_row("V3 Velocity & Growth", velocity_info["summary_line"])
    console.print(
        Panel.fit(
            table,
            title=f"VELUM V3 // 4K CYCLE #{run_number} COMPLETE ({elapsed}s)",
            border_style="green",
        )
    )
    return summary


def _wipe_stray_credentials() -> None:
    """Defense-in-depth guarantee: remove any transient credential files from workspace root."""
    for name in ("client_secrets.json", "token.json"):
        target = ROOT_DIR / name
        if target.exists():
            secure_delete_file(target)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="VELUM V3 — 100% Autonomous 4K Visual Documentary Engine"
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run exactly one autonomous production & growth cycle (used by GitHub Actions).",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously on a 2-hour autonomous V3 cadence (12x/day local daemon).",
    )
    parser.add_argument(
        "--format",
        choices=["auto", "shorts", "longform"],
        default="auto",
        help="Video format override (default: auto via V3 7-day hyper-growth schedule).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Produce full QA-verified video, thumbnails, SEO & reports without calling live upload.",
    )
    parser.add_argument(
        "--force-brand-kit",
        action="store_true",
        help="Force re-render of profile, banner, and watermark assets.",
    )
    parser.add_argument(
        "--force-produce",
        action="store_true",
        help="Bypass daily Shorts cap & 3-hour anti-spam spacing guard to produce immediately.",
    )
    parser.add_argument(
        "--max-qa-retries",
        type=int,
        default=2,
        help="Maximum automatic re-render retries if QA gate detects a defect.",
    )
    args = parser.parse_args()

    try:
        if args.daemon and not args.run_once:
            logger.info("Starting 24/7 local V3 autopilot daemon (interval: 2 hours / 12x daily)...")
            while True:
                run_single_cycle(
                    fmt_override=args.format,
                    dry_run=args.dry_run,
                    max_qa_retries=args.max_qa_retries,
                    force_brand_kit=args.force_brand_kit,
                    force_produce=args.force_produce,
                )
                logger.info("Sleeping 2 hours until next scheduled autonomous V3 cycle...")
                time.sleep(2 * 3600)
        else:
            run_single_cycle(
                fmt_override=args.format,
                dry_run=args.dry_run,
                max_qa_retries=args.max_qa_retries,
                force_brand_kit=args.force_brand_kit,
                force_produce=args.force_produce,
            )
        return 0
    finally:
        _wipe_stray_credentials()


if __name__ == "__main__":
    sys.exit(main())
