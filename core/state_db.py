"""Public-repo safe SQLite state management (state.db).

Zero secrets, zero OAuth tokens, and zero personal user data are stored here.
Safe to commit back to a public GitHub repository after each GitHub Actions run.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import STATE_DB_PATH


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class StateDB:
    """SQLite state repository for topics, videos, warmup slots, comments, and mutations."""

    def __init__(self, db_path: Path = STATE_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=DELETE;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS channel_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS topics (
                    topic_id TEXT PRIMARY KEY,
                    pillar TEXT NOT NULL,
                    primary_keyword TEXT NOT NULL,
                    shock_hook_stat TEXT NOT NULL,
                    viral_score INTEGER NOT NULL,
                    format_signature TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'approved',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS videos (
                    video_uid TEXT PRIMARY KEY,
                    youtube_id TEXT,
                    topic_id TEXT NOT NULL,
                    format TEXT NOT NULL,
                    slug_filename TEXT NOT NULL,
                    active_variant INTEGER NOT NULL DEFAULT 0,
                    titles_json TEXT NOT NULL,
                    thumbnails_json TEXT NOT NULL,
                    seo_json TEXT NOT NULL,
                    qa_report_json TEXT NOT NULL,
                    publish_at TEXT,
                    status TEXT NOT NULL DEFAULT 'rendered',
                    views INTEGER NOT NULL DEFAULT 0,
                    avg_view_pct REAL NOT NULL DEFAULT 0.0,
                    ctr REAL NOT NULL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (topic_id) REFERENCES topics(topic_id)
                );

                CREATE TABLE IF NOT EXISTS comment_replies (
                    comment_hash TEXT PRIMARY KEY,
                    youtube_comment_id TEXT NOT NULL,
                    video_ref TEXT NOT NULL,
                    detected_lang TEXT NOT NULL,
                    reply_text TEXT NOT NULL,
                    is_spam INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'scheduled',
                    scheduled_at TEXT NOT NULL,
                    replied_at TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS mutations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_uid TEXT NOT NULL,
                    mutation_type TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    old_variant INTEGER NOT NULL,
                    new_variant INTEGER NOT NULL,
                    metric_snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS run_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode TEXT NOT NULL,
                    video_uid TEXT,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            now = utc_now_iso()
            conn.execute(
                "INSERT OR IGNORE INTO channel_meta (key, value, updated_at) VALUES (?, ?, ?)",
                ("launch_date", now, now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO channel_meta (key, value, updated_at) VALUES (?, ?, ?)",
                ("total_runs", "0", now),
            )

    # --- Channel Meta ---
    def get_meta(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM channel_meta WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO channel_meta (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, value, utc_now_iso()),
            )

    def increment_runs(self) -> int:
        current = int(self.get_meta("total_runs", "0") or "0") + 1
        self.set_meta("total_runs", str(current))
        return current

    # --- Topics ---
    def topic_exists(self, topic_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM topics WHERE topic_id = ?", (topic_id,)).fetchone()
            return row is not None

    def save_topic(self, topic: Dict[str, Any], format_signature: str = "scale_comparison") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO topics
                (topic_id, pillar, primary_keyword, shock_hook_stat, viral_score, format_signature, payload_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    topic["topic_id"],
                    topic["pillar"],
                    topic["primary_keyword"],
                    topic["shock_hook_stat"],
                    int(topic["total_score"]),
                    format_signature,
                    json.dumps(topic, ensure_ascii=False),
                    "approved" if topic.get("approved") else "rejected",
                    utc_now_iso(),
                ),
            )

    def mark_topic_used(self, topic_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE topics SET status = 'produced' WHERE topic_id = ?", (topic_id,))

    def get_used_topic_ids(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT topic_id FROM topics WHERE status = 'produced'").fetchall()
            return [r["topic_id"] for r in rows]

    # --- Videos ---
    def save_video(
        self,
        video_uid: str,
        topic_id: str,
        fmt: str,
        slug_filename: str,
        titles: List[str],
        thumbnails: List[str],
        seo_payload: Dict[str, Any],
        qa_report: Dict[str, Any],
        publish_at: Optional[str] = None,
        youtube_id: Optional[str] = None,
        status: str = "rendered",
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO videos
                (video_uid, youtube_id, topic_id, format, slug_filename, active_variant,
                 titles_json, thumbnails_json, seo_json, qa_report_json, publish_at,
                 status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_uid,
                    youtube_id,
                    topic_id,
                    fmt,
                    slug_filename,
                    json.dumps(titles, ensure_ascii=False),
                    json.dumps(thumbnails, ensure_ascii=False),
                    json.dumps(seo_payload, ensure_ascii=False),
                    json.dumps(qa_report, ensure_ascii=False),
                    publish_at,
                    status,
                    now,
                    now,
                ),
            )

    def update_video_publish(
        self, video_uid: str, youtube_id: Optional[str], publish_at: str, status: str
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE videos
                SET youtube_id = COALESCE(?, youtube_id),
                    publish_at = ?,
                    status = ?,
                    updated_at = ?
                WHERE video_uid = ?
                """,
                (youtube_id, publish_at, status, utc_now_iso(), video_uid),
            )

    def update_video_metrics(
        self, video_uid: str, views: int, avg_view_pct: float, ctr: float
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE videos
                SET views = ?, avg_view_pct = ?, ctr = ?, updated_at = ?
                WHERE video_uid = ?
                """,
                (views, avg_view_pct, ctr, utc_now_iso(), video_uid),
            )

    def set_video_variant(self, video_uid: str, variant_index: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE videos SET active_variant = ?, updated_at = ? WHERE video_uid = ?",
                (variant_index, utc_now_iso(), video_uid),
            )

    def get_all_videos(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM videos ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def count_videos_by_format_since(self, fmt: str, since_iso: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM videos WHERE format = ? AND created_at >= ?",
                (fmt, since_iso),
            ).fetchone()
            return int(row["cnt"])

    # --- Comments (deduplicated via SHA256 hash of youtube_comment_id) ---
    @staticmethod
    def hash_comment_id(comment_id: str) -> str:
        return hashlib.sha256(comment_id.encode("utf-8")).hexdigest()[:32]

    def is_comment_processed(self, youtube_comment_id: str) -> bool:
        c_hash = self.hash_comment_id(youtube_comment_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM comment_replies WHERE comment_hash = ?", (c_hash,)
            ).fetchone()
            return row is not None

    def record_comment_reply(
        self,
        youtube_comment_id: str,
        video_ref: str,
        detected_lang: str,
        reply_text: str,
        is_spam: bool,
        scheduled_at: str,
        status: str = "scheduled",
        replied_at: Optional[str] = None,
    ) -> None:
        c_hash = self.hash_comment_id(youtube_comment_id)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO comment_replies
                (comment_hash, youtube_comment_id, video_ref, detected_lang, reply_text,
                 is_spam, status, scheduled_at, replied_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    c_hash,
                    youtube_comment_id,
                    video_ref,
                    detected_lang,
                    reply_text,
                    1 if is_spam else 0,
                    status,
                    scheduled_at,
                    replied_at,
                    utc_now_iso(),
                ),
            )

    def get_due_comment_replies(self, now_iso: Optional[str] = None) -> List[Dict[str, Any]]:
        cutoff = now_iso or utc_now_iso()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM comment_replies
                WHERE status = 'scheduled' AND is_spam = 0 AND scheduled_at <= ?
                ORDER BY scheduled_at ASC
                """,
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]

    def mark_comment_replied(self, comment_hash: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE comment_replies SET status = 'sent', replied_at = ? WHERE comment_hash = ?",
                (utc_now_iso(), comment_hash),
            )

    # --- Mutations & Run History ---
    def record_mutation(
        self,
        video_uid: str,
        mutation_type: str,
        reason: str,
        old_variant: int,
        new_variant: int,
        metric_snapshot: Dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mutations
                (video_uid, mutation_type, reason, old_variant, new_variant, metric_snapshot_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_uid,
                    mutation_type,
                    reason,
                    old_variant,
                    new_variant,
                    json.dumps(metric_snapshot, ensure_ascii=False),
                    utc_now_iso(),
                ),
            )

    def record_run(self, mode: str, video_uid: Optional[str], status: str, summary: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO run_history (mode, video_uid, status, summary, created_at) VALUES (?, ?, ?, ?, ?)",
                (mode, video_uid, status, summary, utc_now_iso()),
            )
