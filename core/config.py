"""Centralized configuration, font resolution, and strict public-repo security controls.

SECURITY CONTRACT:
- Never hardcode API keys, tokens, emails, passwords, or channel IDs.
- All secrets come strictly from environment variables (or GitHub Secrets).
- Temporary credential files (client_secrets.json, token.json) are created only
  inside ephemeral context managers and immediately zeroed & deleted on exit.
"""

from __future__ import annotations

import atexit
import base64
import json
import logging
import os
import platform
import re
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple

from dotenv import load_dotenv

# Project root & directories
ROOT_DIR = Path(__file__).resolve().parent.parent
BRAND_DIR = ROOT_DIR / "brand_kit"
PROMPTS_DIR = ROOT_DIR / "prompts"
ENGINE_DIR = ROOT_DIR / "engine"
PUBLISHER_DIR = ROOT_DIR / "publisher"
OUTPUT_DIR = ROOT_DIR / "output"
STATE_DB_PATH = ROOT_DIR / "state.db"

# Load local .env if present (gitignored; absent in public GitHub Actions)
_ENV_FILE = ROOT_DIR / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=False)

# Track any ephemeral credential paths for emergency atexit cleanup
_EPHEMERAL_CREDENTIAL_FILES: set[Path] = set()

_SECRET_PATTERNS = [
    re.compile(r"(AIza[0-9A-Za-z\-_]{20,})"),
    re.compile(r"(ya29\.[0-9A-Za-z\-_]+)"),
    re.compile(r"(gsk_[0-9A-Za-z]{20,})"),
    re.compile(r"(sk-[0-9A-Za-z\-_]{20,})"),
    re.compile(r"(ghp_[0-9A-Za-z]{20,})"),
    re.compile(r"(\"refresh_token\"\s*:\s*\")([^\"]+)(\")"),
    re.compile(r"(\"client_secret\"\s*:\s*\")([^\"]+)(\")"),
    re.compile(r"(\"access_token\"\s*:\s*\")([^\"]+)(\")"),
    re.compile(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"),
]


def redact_secrets(text: str) -> str:
    """Scrub any accidental secrets, tokens, or emails from log output."""
    if not text:
        return text
    cleaned = str(text)
    for env_key in (
        "YOUTUBE_CLIENT_SECRETS",
        "YOUTUBE_TOKEN",
        "GEMINI_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
        "PEXELS_API_KEY",
        "PIXABAY_API_KEY",
    ):
        val = os.getenv(env_key, "").strip()
        if val and len(val) >= 8:
            cleaned = cleaned.replace(val, f"[REDACTED:{env_key}]")
    for pattern in _SECRET_PATTERNS:
        if pattern.groups == 3:
            cleaned = pattern.sub(r"\1[REDACTED]\3", cleaned)
        else:
            cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned


class RedactingFormatter(logging.Formatter):
    """Logging formatter that guarantees no secret ever appears in console output."""

    def format(self, record: logging.LogRecord) -> str:
        raw = super().format(record)
        return redact_secrets(raw)


def get_logger(name: str) -> logging.Logger:
    """Return a consistently formatted, secret-redacting logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            RedactingFormatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def secure_delete_file(path: Path) -> None:
    """Overwrite with zeros and unlink a sensitive file immediately."""
    try:
        if path.exists() and path.is_file():
            size = path.stat().st_size
            if size > 0:
                with open(path, "wb") as fh:
                    fh.write(b"\x00" * size)
                    fh.flush()
                    os.fsync(fh.fileno())
            path.unlink(missing_ok=True)
    except OSError:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            return None


def _cleanup_all_ephemeral_files() -> None:
    for path in list(_EPHEMERAL_CREDENTIAL_FILES):
        secure_delete_file(path)
        _EPHEMERAL_CREDENTIAL_FILES.discard(path)
    # Also sweep root directory for any stray credential files
    for stray_name in ("client_secrets.json", "token.json"):
        stray = ROOT_DIR / stray_name
        if stray.exists() and os.getenv("GITHUB_ACTIONS", "").lower() == "true":
            secure_delete_file(stray)


atexit.register(_cleanup_all_ephemeral_files)


def decode_env_json(env_var: str) -> Optional[dict]:
    """Read a JSON secret from env (accepts raw JSON or base64-encoded JSON)."""
    raw = os.getenv(env_var, "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            decoded = base64.b64decode(raw).decode("utf-8")
            return json.loads(decoded)
        except Exception:
            return None


@contextmanager
def ephemeral_youtube_credentials() -> Iterator[Tuple[Optional[Path], Optional[Path]]]:
    """Materialize temporary YouTube credential files ONLY from env, then wipe them.

    Yields (client_secrets_path, token_path). Both are None if credentials are not configured.
    Guaranteed to zero-overwrite and delete both temporary files upon exit.
    """
    secrets_obj = decode_env_json("YOUTUBE_CLIENT_SECRETS")
    token_obj = decode_env_json("YOUTUBE_TOKEN")

    if not secrets_obj and not token_obj:
        yield None, None
        return

    secrets_path: Optional[Path] = None
    token_path: Optional[Path] = None
    try:
        if secrets_obj:
            secrets_path = ROOT_DIR / "client_secrets.json"
            secrets_path.write_text(json.dumps(secrets_obj), encoding="utf-8")
            _EPHEMERAL_CREDENTIAL_FILES.add(secrets_path)
        if token_obj:
            token_path = ROOT_DIR / "token.json"
            token_path.write_text(json.dumps(token_obj), encoding="utf-8")
            _EPHEMERAL_CREDENTIAL_FILES.add(token_path)
        yield secrets_path, token_path
    finally:
        for path in (secrets_path, token_path):
            if path is not None:
                secure_delete_file(path)
                _EPHEMERAL_CREDENTIAL_FILES.discard(path)


def has_youtube_credentials() -> bool:
    """Return True if valid YouTube OAuth env secrets are configured."""
    return decode_env_json("YOUTUBE_TOKEN") is not None


def load_brand_config() -> Dict:
    """Load the locked channel identity and design tokens from brand_kit/brand.json."""
    brand_path = BRAND_DIR / "brand.json"
    with open(brand_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_prompt(prompt_filename: str) -> str:
    """Load a specialized prompt specification from prompts/."""
    prompt_path = PROMPTS_DIR / prompt_filename
    return prompt_path.read_text(encoding="utf-8")


def resolve_font(role: str = "headline") -> str:
    """Locate an installed bold/body/mono TrueType font across Windows, Linux, and macOS."""
    brand = load_brand_config()
    role_key = {
        "headline": "headline_candidates",
        "body": "body_candidates",
        "mono": "mono_candidates",
    }.get(role, "headline_candidates")
    candidates = brand.get("typography", {}).get(role_key, [])

    search_dirs = []
    system = platform.system().lower()
    if system == "windows":
        win_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        search_dirs.append(win_fonts)
    elif system == "darwin":
        search_dirs.extend([Path("/System/Library/Fonts"), Path("/Library/Fonts")])
    else:
        search_dirs.extend(
            [
                Path("/usr/share/fonts/truetype/dejavu"),
                Path("/usr/share/fonts/truetype/liberation"),
                Path("/usr/share/fonts/truetype/ubuntu"),
                Path("/usr/share/fonts/truetype/noto"),
                Path("/usr/share/fonts"),
            ]
        )

    # First pass: exact candidate match
    for directory in search_dirs:
        if not directory.exists():
            continue
        for candidate in candidates:
            direct = directory / candidate
            if direct.exists():
                return str(direct)
            for found in directory.rglob(candidate):
                return str(found)

    # Second pass: broad fallback to any usable TTF
    fallback_names = [
        "DejaVuSans-Bold.ttf",
        "LiberationSans-Bold.ttf",
        "arialbd.ttf",
        "arial.ttf",
        "DejaVuSans.ttf",
    ]
    for directory in search_dirs:
        if not directory.exists():
            continue
        for name in fallback_names:
            for found in directory.rglob(name):
                return str(found)

    return ""


def get_ffmpeg_bin() -> str:
    """Resolve ffmpeg binary path."""
    found = shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("FFmpeg binary not found on PATH. Install FFmpeg to render videos.")
    return found


def get_ffprobe_bin() -> str:
    """Resolve ffprobe binary path."""
    found = shutil.which("ffprobe")
    if not found:
        raise RuntimeError("FFprobe binary not found on PATH. Install FFmpeg/FFprobe.")
    return found


def ensure_output_dir(run_slug: str) -> Path:
    """Create and return an isolated output folder under output/<run_slug>."""
    target = OUTPUT_DIR / run_slug
    target.mkdir(parents=True, exist_ok=True)
    return target
