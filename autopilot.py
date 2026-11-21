"""VELUM — 100% Autonomous Autonomous Visual Documentary Engine Orchestrator.

Single-command execution:
    python autopilot.py              # Full end-to-end production + QA + SEO + growth cycle
    python autopilot.py --run-once   # Explicit single-shot mode for GitHub Actions CI
    python autopilot.py --daemon     # Continuous local 24/7 autonomous scheduler (every 8h)

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

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from brand_kit.generate_brand_kit import ensure_brand_kit
from core.config import (
    ROOT_DIR,
    STATE_DB_PATH,
    ensure_output_dir,
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
from publisher.youtube_uploader import compute_warmup_plan, upload_video_package

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
            title="VELUM // BROADCAST AUTOPILOT",
            border_style="cyan",
        )
    )

    # 1. Ensure Brand Kit assets exist (Profile 800x800, Banner 2560x1440, Watermark 150x150)
    brand_assets = ensure_brand_kit(force=force_brand_kit)

    # 2. Check 7-Day Anti-Spam Warm-Up Schedule & lock video format
    warmup_plan = compute_warmup_plan(state_db)
    target_format = warmup_plan["recommended_format"] if fmt_override == "auto" else fmt_override
    logger.info(
        "Warm-up phase: %s | Selected format: %s | Next slot: %s",
        warmup_plan["phase"],
        target_format,
        warmup_plan["publish_at"],
    )

    # Respect Day 1-2 anti-spam warm-up cap on multi-daily CI runs: switch cleanly to Engagement-Only Mode
    if warmup_plan.get("daily_quota_reached") and not force_produce and not dry_run and fmt_override == "auto":
        logger.info(
            "Daily warm-up video quota already met (%d/%d Shorts today) -> running Engagement & Growth cycle only.",
            warmup_plan["shorts_produced_today"],
            warmup_plan["daily_shorts_cap"],
        )
        comment_result = run_comment_cycle(state_db, out_dir=None, llm=llm)
        growth_result = run_growth_mutation_cycle(state_db, out_dir=None)
        elapsed = round(time.time() - t0, 1)
        state_db.record_run(
            "engagement_only",
            None,
            "success",
            f"Warm-up cap respected; comments_sent={comment_result['sent_now']}, mutations={len(growth_result['mutations_applied'])}",
        )
        return {
            "run_number": run_number,
            "mode": "engagement_only",
            "elapsed_sec": elapsed,
            "warmup_plan": warmup_plan,
            "comment_bot": comment_result,
            "growth_mutator": growth_result,
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
    final_video_path = out_dir / seo_package["slug_filename"]

    # 8. Generate 3 High-Contrast A/B/C Thumbnails (1280x720, <= 3 bold words)
    thumbnail_paths = generate_ab_thumbnails(
        topic=topic,
        out_dir=out_dir / "thumbnails",
        media_cache_dir=work_dir / "media_cache",
    )

    # 9. Render Broadcast-Grade 1080p 60fps Cinematic Video + Automated QA Gate with Auto-Regen
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

    # 12. Growth Mutator (Shorts <70% / Long-form <5% CTR A/B swap + Winner Format Clone)
    growth_result = run_growth_mutation_cycle(state_db, out_dir=out_dir)

    elapsed = round(time.time() - t0, 1)
    summary = {
        "run_number": run_number,
        "elapsed_sec": elapsed,
        "video_uid": video_uid,
        "format": target_format,
        "topic_score": topic["total_score"],
        "video_file": str(final_video_path),
        "qa_passed": qa_report["passed"],
        "qa_checks": qa_report["checks"],
        "thumbnails": thumbnail_paths,
        "seo_file": str(out_dir / "omni_seo_package.json"),
        "subtitles_srt": seo_package["subtitles_srt"],
        "upload_mode": upload_result["mode"],
        "publish_at": upload_result["publishAt"],
        "comment_bot": {
            "mode": comment_result["mode"],
            "spam_filtered": comment_result["spam_filtered"],
            "queued": comment_result["queued"],
            "sent_now": comment_result["sent_now"],
        },
        "growth_mutator": {
            "mutations": len(growth_result["mutations_applied"]),
            "cloned_winner_pillar": (growth_result.get("cloned_winner") or {}).get("pillar"),
        },
        "brand_assets": {k: str(v) for k, v in brand_assets.items()},
    }

    (out_dir / "autopilot_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    state_db.record_run(
        "single_cycle",
        video_uid,
        "success",
        f"QA passed ({qa_report['checks']['resolution']['value']} @ {qa_report['checks']['fps']['value']}fps, "
        f"{qa_report['checks']['loudness_lufs']['value']} LUFS) in {elapsed}s",
    )

    # Render crisp execution proof table
    table = Table(title=f"VELUM — CYCLE #{run_number} COMPLETE ({elapsed}s)", border_style="green")
    table.add_column("Subsystem", style="cyan", no_wrap=True)
    table.add_column("Status / Proof", style="white")
    table.add_row("Public Security Lock", "VERIFIED (.gitignore active, 0 secrets stored)")
    table.add_row("Brand Kit", "800x800 Profile + 2560x1440 Banner + 150x150 Watermark")
    table.add_row("Idea Viral Gate", f"{topic['topic_id']} -> {topic['total_score']}/100 (>=85 PASS)")
    table.add_row(
        "Cinematic Video + QA",
        f"PASSED | {final_video_path.name} | {qa_report['checks']['resolution']['value']} @ "
        f"{qa_report['checks']['fps']['value']}fps | {qa_report['checks']['duration_sec']['value']}s | "
        f"{qa_report['checks']['loudness_lufs']['value']} LUFS",
    )
    table.add_row("A/B/C Thumbnails", f"{len(thumbnail_paths)}x 1280x720 high-contrast PNGs")
    table.add_row(
        "Omni-SEO + SRTs",
        f"VSEO<15s={seo_package['vseo']['verified_under_15s']} | "
        f"Desc={seo_package['seo_description_word_count']}w | "
        f"SRTs={','.join(seo_package['subtitles_srt'].keys())}",
    )
    table.add_row("Warm-Up Schedule", f"{upload_result['mode']} -> publishAt {upload_result['publishAt']}")
    table.add_row(
        "Comment Responder",
        f"checked={comment_result['fetched']} | spam_blocked={comment_result['spam_filtered']} | "
        f"queued={comment_result['queued']} | sent={comment_result['sent_now']}",
    )
    table.add_row(
        "Growth Mutator",
        f"mutations={len(growth_result['mutations_applied'])} | "
        f"cloned_pillar={(growth_result.get('cloned_winner') or {}).get('pillar')}",
    )
    console.print(table)
    return summary


def _wipe_stray_credentials() -> None:
    """Defense-in-depth guarantee: remove any transient credential files from workspace root."""
    for name in ("client_secrets.json", "token.json"):
        target = ROOT_DIR / name
        if target.exists():
            secure_delete_file(target)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="VELUM — 100% Autonomous Autonomous Autonomous Visual Documentary Engine"
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run exactly one autonomous production & growth cycle (used by GitHub Actions).",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously on an 8-hour autonomous interval (3x/day local daemon).",
    )
    parser.add_argument(
        "--format",
        choices=["auto", "shorts", "longform"],
        default="auto",
        help="Video format override (default: auto via 7-day warm-up schedule).",
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
        help="Produce a new video even if today's warm-up daily cap has already been met.",
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
            logger.info("Starting 24/7 local autopilot daemon (interval: 8 hours / 3x daily)...")
            while True:
                run_single_cycle(
                    fmt_override=args.format,
                    dry_run=args.dry_run,
                    max_qa_retries=args.max_qa_retries,
                    force_brand_kit=args.force_brand_kit,
                    force_produce=args.force_produce,
                )
                logger.info("Sleeping 8 hours until next scheduled autonomous cycle...")
                time.sleep(8 * 3600)
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
