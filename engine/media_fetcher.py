"""VELUM V3 Autonomous Parallel Zero-Key Real Video & Relevance-Locked Visual Engine.

Sources license-safe, visually verified real moving HD video clips and crisp photography:
1. Real Moving Video B-Roll:
   - Optional Pexels Video API (if PEXELS_API_KEY configured)
   - NASA Image & Video Library API (zero-key public domain HD MP4 footage)
   - Wikimedia Commons Real HD Video API (zero-key relevance-filtered WebM/OGV/MP4)
   - Persistent URL-keyed raw video cache (`raw_cache/`) with strict 12 MB / 10s caps
   - Distinct per-variant seek offsets and 5-worker parallel batch prefetch (`prefetch_beats`)
2. High-Aesthetic Relevance-Locked Photography:
   - Optional Pexels / Pixabay Photo APIs
   - Openverse API (zero-key CC Flickr / StockSnap / Rawpixel photography)
   - Strict relevance-filtered Wikimedia Commons photography (rejects diagrams/unrelated noise)
3. Rich Procedural Dark Cinema Atmospheric Plate fallback (never returns black/broken frames).
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import io
import math
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter

from core.config import get_ffmpeg_bin, get_logger

logger = get_logger("media_fetcher")

USER_AGENT = "VelumBroadcastEngine/3.0 (https://github.com/MFTTT11/velum-studio; educational)"
MAX_RAW_VIDEO_BYTES = 12_000_000
SEARCH_TIMEOUT_SEC = 7
DOWNLOAD_TIMEOUT_SEC = 10

GENERIC_STOP_WORDS = {
    "dark",
    "cinematic",
    "night",
    "macro",
    "closeup",
    "close",
    "aerial",
    "view",
    "photo",
    "photography",
    "lighting",
    "modern",
    "abstract",
    "dramatic",
    "moody",
    "scale",
    "comparison",
    "high",
    "ultra",
    "deep",
    "wide",
    "angle",
    "minimalist",
    "background",
    "texture",
    "glowing",
    "neon",
    "blurred",
    "interior",
    "exterior",
    "vintage",
    "monochrome",
    "extreme",
    "massive",
    "giant",
    "tiny",
    "global",
    "world",
    "the",
    "and",
    "from",
    "with",
    "into",
    "over",
    "under",
}

BANNED_MEDIA_TERMS = (
    "diagram",
    "chart",
    "graph",
    "logo",
    "icon",
    "signature",
    "coat of arms",
    "coat_of_arms",
    "flag of",
    "flag_of",
    "screenshot",
    "pdf",
    "djvu",
    "christmas",
    "wedding",
    "grave",
    "cemetery",
    "cartoon",
    "drawing",
    "sketch",
    "map of",
    "map_of",
    "stamp",
    "receipt",
    "flyer",
    "poster",
    "book page",
    "scan",
    "wikimedia",
    "wikipedia",
    "portrait of",
    "selfie",
    "meme",
)

NASA_DOMAIN_HINTS = {
    "space",
    "earth",
    "orbit",
    "orbital",
    "satellite",
    "astronaut",
    "iss",
    "pluto",
    "planet",
    "star",
    "nebula",
    "pulsar",
    "supernova",
    "galaxy",
    "milky",
    "sun",
    "solar",
    "asteroid",
    "rocket",
    "spacecraft",
    "moon",
    "mars",
    "jupiter",
    "saturn",
    "gravity",
    "black",
    "hole",
    "ocean",
    "pacific",
    "climate",
    "horizon",
    "atmosphere",
    "telescope",
}


def _extract_core_terms(query: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]+", query.lower())
    core = [t for t in tokens if len(t) >= 3 and t not in GENERIC_STOP_WORDS]
    return core if core else [t for t in tokens if len(t) >= 3]


def _relevance_score(query: str, title: str) -> int:
    """Score visual candidate relevance; return -1 if candidate is non-photographic noise."""
    t_low = (title or "").lower().replace("_", " ").replace("-", " ")
    for banned in BANNED_MEDIA_TERMS:
        if banned in t_low:
            return -1
    core_terms = _extract_core_terms(query)
    if not core_terms:
        return 1
    score = 0
    for term in core_terms:
        stem = term[:-1] if len(term) > 5 and term.endswith("s") else term
        if stem in t_low:
            score += 2
    return score


def _cover_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Scale and center-crop image to exact target_w x target_h with zero letterboxing + crisp sharpen."""
    src_w, src_h = img.size
    scale = max(target_w / max(src_w, 1), target_h / max(src_h, 1))
    new_w = max(target_w, int(math.ceil(src_w * scale)))
    new_h = max(target_h, int(math.ceil(src_h * scale)))
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    cropped = resized.crop((left, top, left + target_w, top + target_h)).convert("RGB")
    return cropped.filter(ImageFilter.UnsharpMask(radius=1.1, percent=110, threshold=3))


def _generate_cinematic_editorial_plate(
    seed_key: str, width: int, height: int
) -> Image.Image:
    """Generate a high-aesthetic dark architectural/cinematic atmospheric frame when stock is sparse."""
    digest = int(hashlib.sha256(seed_key.encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.default_rng(digest)

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    nx = xx / max(width - 1, 1)
    ny = yy / max(height - 1, 1)

    palettes = [
        ((9, 15, 28), (0, 210, 245), (255, 175, 0)),
        ((14, 10, 24), (255, 45, 90), (0, 215, 245)),
        ((8, 18, 24), (45, 230, 155), (0, 190, 245)),
        ((16, 14, 22), (255, 184, 0), (50, 135, 230)),
    ]
    base_c, acc1, acc2 = palettes[digest % len(palettes)]
    cx1, cy1 = float(rng.uniform(0.22, 0.78)), float(rng.uniform(0.22, 0.58))
    cx2, cy2 = float(rng.uniform(0.18, 0.82)), float(rng.uniform(0.45, 0.82))

    g1 = np.exp(-((nx - cx1) ** 2 + (ny - cy1) ** 2) / 0.14) * 0.45
    g2 = np.exp(-((nx - cx2) ** 2 + (ny - cy2) ** 2) / 0.18) * 0.30
    wave = (np.sin((nx * 14.0 + ny * 6.0) + (digest % 7)) * 0.5 + 0.5) ** 4 * 0.09

    arr = np.zeros((height, width, 3), dtype=np.float32)
    for c in range(3):
        arr[:, :, c] = np.clip(base_c[c] + acc1[c] * (g1 + wave) + acc2[c] * g2, 0, 255)
    img = Image.fromarray(arr.astype(np.uint8), mode="RGB").convert("RGBA")

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for i in range(14):
        r = int(rng.integers(int(min(width, height) * 0.05), int(min(width, height) * 0.38)))
        px = int(rng.integers(0, width))
        py = int(rng.integers(0, height))
        col = acc1 if i % 2 == 0 else acc2
        draw.ellipse([px - r, py - r, px + r, py + r], outline=(*col, 60), width=2)
    vx, vy = int(width * cx1), int(height * cy1)
    for angle_idx in range(20):
        ang = (angle_idx / 20.0) * math.pi * 2.0
        ex = int(vx + math.cos(ang) * max(width, height))
        ey = int(vy + math.sin(ang) * max(width, height))
        draw.line([(vx, vy), (ex, ey)], fill=(*acc1, 26), width=1)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=1.1))
    img.alpha_composite(overlay)
    return img.convert("RGB")


class MediaFetcher:
    """Sources real moving HD video B-roll and relevance-verified photography across zero-cost APIs."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.raw_cache_dir = self.cache_dir / "raw_cache"
        self.raw_cache_dir.mkdir(parents=True, exist_ok=True)
        self.pexels_key = os.getenv("PEXELS_API_KEY", "").strip()
        self.pixabay_key = os.getenv("PIXABAY_API_KEY", "").strip()
        self._query_url_cache: Dict[str, List[str]] = {}
        self._video_url_cache: Dict[str, List[Tuple[str, float]]] = {}
        self._cache_lock = threading.Lock()
        self._video_search_locks: Dict[str, threading.Lock] = {}
        self._photo_search_locks: Dict[str, threading.Lock] = {}
        self._raw_url_locks: Dict[str, threading.Lock] = {}
        self._output_file_locks: Dict[str, threading.Lock] = {}

    def _get_lock(self, lock_map: Dict[str, threading.Lock], key: str) -> threading.Lock:
        with self._cache_lock:
            lock = lock_map.get(key)
            if lock is None:
                lock = threading.Lock()
                lock_map[key] = lock
            return lock

    # ------------------------------------------------------------------
    # REAL MOVING VIDEO B-ROLL SOURCES (Pexels Video -> NASA -> Wikimedia)
    # ------------------------------------------------------------------
    def _search_pexels_videos(self, query: str, orientation: str) -> List[Tuple[str, float]]:
        if not self.pexels_key:
            return []
        try:
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": self.pexels_key, "User-Agent": USER_AGENT},
                params={"query": query, "orientation": orientation, "per_page": 5},
                timeout=SEARCH_TIMEOUT_SEC,
            )
            if resp.status_code != 200:
                return []
            out: List[Tuple[str, float]] = []
            for v in resp.json().get("videos", []):
                dur = float(v.get("duration", 6.0))
                files = sorted(
                    [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and (f.get("width") or 0) >= 640],
                    key=lambda f: abs((f.get("width") or 1080) - 1080),
                )
                if files and files[0].get("link"):
                    out.append((files[0]["link"], dur))
            return out
        except Exception as exc:
            logger.debug("Pexels video search skipped (%s)", type(exc).__name__)
            return []

    def _search_nasa_videos(self, query: str) -> List[Tuple[str, float]]:
        """Zero-key public-domain HD MP4 footage from NASA Image & Video Library."""
        core_terms = _extract_core_terms(query)
        if not any(t in NASA_DOMAIN_HINTS for t in core_terms):
            return []
        search_q = " ".join(core_terms[:3])
        try:
            resp = requests.get(
                "https://images-api.nasa.gov/search",
                headers={"User-Agent": USER_AGENT},
                params={"q": search_q, "media_type": "video", "page_size": 4},
                timeout=SEARCH_TIMEOUT_SEC,
            )
            if resp.status_code != 200:
                return []
            items = resp.json().get("collection", {}).get("items", [])
            scored: List[Tuple[int, str]] = []
            for item in items:
                data = (item.get("data") or [{}])[0]
                title = f"{data.get('title', '')} {data.get('description', '')[:120]}"
                rel = _relevance_score(query, title)
                href = item.get("href")
                if rel >= 2 and href:
                    scored.append((rel, href))
            scored.sort(key=lambda x: x[0], reverse=True)

            results: List[Tuple[str, float]] = []
            for _, href in scored[:2]:
                try:
                    assets = requests.get(
                        href,
                        headers={"User-Agent": USER_AGENT},
                        timeout=SEARCH_TIMEOUT_SEC,
                    ).json()
                    mp4s = [u for u in assets if isinstance(u, str) and u.lower().endswith(".mp4")]
                    # Prefer medium/small MP4 (fast download, crisp 720p-1080p) over huge multi-GB ~orig.mp4
                    preferred = (
                        [u for u in mp4s if "~medium.mp4" in u]
                        or [u for u in mp4s if "~small.mp4" in u]
                        or [u for u in mp4s if "~mobile.mp4" in u]
                    )
                    if preferred:
                        url = preferred[0].replace("http://", "https://")
                        results.append((url, 20.0))
                except Exception as exc:
                    logger.debug("NASA asset manifest skipped (%s)", type(exc).__name__)
            return results
        except Exception as exc:
            logger.debug("NASA video search skipped (%s)", type(exc).__name__)
            return []

    def _search_wikimedia_videos(self, query: str) -> List[Tuple[str, float]]:
        """Zero-key relevance-locked 720p/1080p real moving video clips from Wikimedia Commons."""
        core_terms = _extract_core_terms(query)
        if not core_terms:
            return []
        search_q = " ".join(core_terms[:2])
        try:
            resp = requests.get(
                "https://commons.wikimedia.org/w/api.php",
                headers={"User-Agent": USER_AGENT},
                params={
                    "action": "query",
                    "format": "json",
                    "generator": "search",
                    "gsrnamespace": 6,
                    "gsrsearch": f"{search_q} filetype:video",
                    "gsrlimit": 8,
                    "prop": "imageinfo",
                    "iiprop": "url|size|mime|duration",
                },
                timeout=SEARCH_TIMEOUT_SEC,
            )
            if resp.status_code != 200:
                return []
            pages = resp.json().get("query", {}).get("pages", {})
            scored: List[Tuple[int, str, float]] = []
            for page in pages.values():
                title = page.get("title", "")
                rel = _relevance_score(query, title)
                if rel < 2:
                    continue
                infos = page.get("imageinfo", [])
                if not infos:
                    continue
                info = infos[0]
                width = int(info.get("width") or 0)
                height = int(info.get("height") or 0)
                size_bytes = int(info.get("size") or 0)
                dur = float(info.get("duration") or 0.0)
                url = info.get("url", "")
                if not url or width < 640 or height < 480:
                    continue
                if dur < 3.0 or dur > 90.0 or size_bytes <= 0 or size_bytes > 22_000_000:
                    continue
                size_bonus = 1 if size_bytes <= MAX_RAW_VIDEO_BYTES else 0
                scored.append((rel + (1 if width >= 1280 else 0) + size_bonus, url, dur))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [(u, d) for _, u, d in scored[:3]]
        except Exception as exc:
            logger.debug("Wikimedia video search skipped (%s)", type(exc).__name__)
            return []

    def _download_raw_video(self, url: str) -> Optional[Path]:
        """Download and persistently cache a raw source video keyed by URL MD5 with strict 12 MB / 10s caps."""
        url_md5 = hashlib.md5(url.encode("utf-8")).hexdigest()
        raw_ext = ".webm" if ".webm" in url.lower() else (".ogv" if ".ogv" in url.lower() else ".mp4")
        raw_path = self.cache_dir / "raw_cache" / f"{url_md5}{raw_ext}"

        with self._get_lock(self._raw_url_locks, url_md5):
            if raw_path.exists() and raw_path.stat().st_size >= 40_000:
                return raw_path

            self.raw_cache_dir.mkdir(parents=True, exist_ok=True)
            tmp_raw = self.raw_cache_dir / f"{url_md5}.{threading.get_ident()}.part"
            try:
                with requests.get(
                    url,
                    headers={"User-Agent": USER_AGENT},
                    stream=True,
                    timeout=DOWNLOAD_TIMEOUT_SEC,
                ) as resp:
                    if resp.status_code != 200:
                        return None
                    dl_start = time.monotonic()
                    total = 0
                    with open(tmp_raw, "wb") as fh:
                        for chunk in resp.iter_content(chunk_size=131072):
                            if not chunk:
                                continue
                            remaining = MAX_RAW_VIDEO_BYTES - total
                            if remaining <= 0:
                                break
                            if len(chunk) > remaining:
                                chunk = chunk[:remaining]
                            fh.write(chunk)
                            total += len(chunk)
                            if (
                                total >= MAX_RAW_VIDEO_BYTES
                                or (time.monotonic() - dl_start) >= DOWNLOAD_TIMEOUT_SEC
                            ):
                                break

                if tmp_raw.exists() and tmp_raw.stat().st_size >= 40_000:
                    os.replace(tmp_raw, raw_path)
                    return raw_path
                tmp_raw.unlink(missing_ok=True)
                return None
            except Exception as exc:
                logger.debug("Raw video download skipped (%s)", type(exc).__name__)
                tmp_raw.unlink(missing_ok=True)
                return None

    def _extract_clip_segment(
        self,
        raw_path: Path,
        out_mp4: Path,
        w: int,
        h: int,
        seek_s: float,
        clip_len: float,
    ) -> bool:
        """Cover-crop a moving HD segment from a cached raw source video into out_mp4 atomically."""
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},fps=30,unsharp=3:3:0.6:3:3:0.0"
        )
        tmp_out = out_mp4.with_name(f"{out_mp4.stem}.{threading.get_ident()}.tmp.mp4")
        seek_attempts = [seek_s, 0.0] if seek_s > 0.0 else [0.0]
        try:
            for attempt_seek in seek_attempts:
                tmp_out.unlink(missing_ok=True)
                cmd = [
                    get_ffmpeg_bin(),
                    "-y",
                    "-stats",
                    "-ss",
                    f"{attempt_seek:.2f}",
                    "-i",
                    str(raw_path),
                    "-t",
                    f"{clip_len:.2f}",
                    "-vf",
                    vf,
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-threads",
                    "2",
                    "-crf",
                    "19",
                    "-pix_fmt",
                    "yuv420p",
                    str(tmp_out),
                ]
                res = subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    errors="replace",
                    timeout=25,
                )
                frame_matches = re.findall(r"frame=\s*(\d+)", res.stderr or "")
                frames_ok = (int(frame_matches[-1]) >= 12) if frame_matches else True
                if (
                    res.returncode == 0
                    and frames_ok
                    and tmp_out.exists()
                    and tmp_out.stat().st_size > 25_000
                ):
                    os.replace(tmp_out, out_mp4)
                    return True
        except Exception as exc:
            logger.debug("FFmpeg clip extraction skipped (%s)", type(exc).__name__)
        finally:
            tmp_out.unlink(missing_ok=True)
        return False

    def fetch_motion_clip(
        self,
        query: str,
        target_size: Tuple[int, int],
        duration_sec: float = 2.6,
        variant_index: int = 0,
    ) -> Optional[Path]:
        """Download and cover-crop a real moving HD video clip ready for 60fps composition."""
        w, h = target_size
        orientation = "portrait" if h > w else "landscape"
        key = hashlib.md5(f"clip|{query}|{w}x{h}|{variant_index}".encode("utf-8")).hexdigest()[:12]
        out_mp4 = self.cache_dir / f"clip_{key}.mp4"
        if out_mp4.exists() and out_mp4.stat().st_size > 25_000:
            return out_mp4

        cache_key = f"{query}|{orientation}"
        with self._cache_lock:
            candidates = self._video_url_cache.get(cache_key)

        if candidates is None:
            with self._get_lock(self._video_search_locks, cache_key):
                with self._cache_lock:
                    candidates = self._video_url_cache.get(cache_key)
                if candidates is None:
                    found: List[Tuple[str, float]] = []
                    found.extend(self._search_pexels_videos(query, orientation))
                    if not found:
                        found.extend(self._search_nasa_videos(query))
                    if not found:
                        found.extend(self._search_wikimedia_videos(query))
                    with self._cache_lock:
                        self._video_url_cache[cache_key] = found
                        candidates = found

        if not candidates:
            return None

        clip_len = max(2.2, min(5.0, duration_sec + 0.6))
        for offset in range(min(2, len(candidates))):
            url, clip_dur = candidates[(variant_index + offset) % len(candidates)]
            raw_path = self._download_raw_video(url)
            if raw_path is None:
                continue

            # Distinct seek offset per variant_index so repeated source clips show unique motion segments
            seek_s = (
                min(max(0.0, clip_dur - clip_len - 0.3), 0.8 + (variant_index % 5) * 2.3)
                if clip_dur > clip_len + 1.2
                else 0.0
            )
            with self._get_lock(self._output_file_locks, f"clip_{key}"):
                if out_mp4.exists() and out_mp4.stat().st_size > 25_000:
                    return out_mp4
                if self._extract_clip_segment(raw_path, out_mp4, w, h, seek_s, clip_len):
                    logger.info("Sourced REAL HD motion clip [%s] -> %s", query[:32], out_mp4.name)
                    return out_mp4

        return None

    # ------------------------------------------------------------------
    # RELEVANCE-LOCKED HIGH-AESTHETIC PHOTOGRAPHY SOURCES
    # ------------------------------------------------------------------
    def _search_pexels(self, query: str, orientation: str) -> List[str]:
        if not self.pexels_key:
            return []
        try:
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": self.pexels_key, "User-Agent": USER_AGENT},
                params={"query": query, "orientation": orientation, "per_page": 6},
                timeout=SEARCH_TIMEOUT_SEC,
            )
            if resp.status_code == 200:
                photos = resp.json().get("photos", [])
                return [p["src"]["large2x"] for p in photos if p.get("src", {}).get("large2x")]
        except Exception as exc:
            logger.debug("Pexels photo search skipped (%s)", type(exc).__name__)
        return []

    def _search_pixabay(self, query: str, orientation: str) -> List[str]:
        if not self.pixabay_key:
            return []
        try:
            pix_orient = "vertical" if orientation == "portrait" else "horizontal"
            resp = requests.get(
                "https://pixabay.com/api/",
                params={
                    "key": self.pixabay_key,
                    "q": query,
                    "image_type": "photo",
                    "orientation": pix_orient,
                    "safesearch": "true",
                    "per_page": 6,
                },
                timeout=SEARCH_TIMEOUT_SEC,
            )
            if resp.status_code == 200:
                hits = resp.json().get("hits", [])
                return [h["largeImageURL"] for h in hits if h.get("largeImageURL")]
        except Exception as exc:
            logger.debug("Pixabay photo search skipped (%s)", type(exc).__name__)
        return []

    def _search_openverse(self, query: str, orientation: str) -> List[str]:
        """Zero-key high-resolution CC photography search via Openverse (Flickr / Rawpixel / StockSnap)."""
        core_terms = _extract_core_terms(query)
        q_clean = " ".join(core_terms[:4]) or query
        params: Dict[str, Any] = {
            "q": q_clean,
            "page_size": 10,
            "mature": "false",
            "category": "photograph",
        }
        if orientation == "portrait":
            params["aspect_ratio"] = "tall"
        try:
            resp = requests.get(
                "https://api.openverse.org/v1/images/",
                headers={"User-Agent": USER_AGENT},
                params=params,
                timeout=SEARCH_TIMEOUT_SEC,
            )
            if resp.status_code != 200:
                return []
            results = resp.json().get("results", [])
            # Retry without strict tall filter if few tall results came back
            if len(results) < 2 and "aspect_ratio" in params:
                params.pop("aspect_ratio", None)
                resp2 = requests.get(
                    "https://api.openverse.org/v1/images/",
                    headers={"User-Agent": USER_AGENT},
                    params=params,
                    timeout=SEARCH_TIMEOUT_SEC,
                )
                if resp2.status_code == 200:
                    results = resp2.json().get("results", [])

            scored: List[Tuple[int, str]] = []
            for item in results:
                w = int(item.get("width") or 0)
                h = int(item.get("height") or 0)
                url = item.get("url") or ""
                if not url or w < 600 or h < 480:
                    continue
                tags_txt = " ".join(
                    str(t.get("name", "")) for t in (item.get("tags") or []) if isinstance(t, dict)
                )
                meta_txt = f"{item.get('title', '')} {tags_txt}"
                rel = _relevance_score(query, meta_txt)
                if rel < 2:
                    continue
                orient_bonus = 2 if ((orientation == "portrait" and h >= w) or (orientation == "landscape" and w >= h)) else 0
                scored.append((rel + orient_bonus, url))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [u for _, u in scored[:6]]
        except Exception as exc:
            logger.debug("Openverse photo search skipped (%s)", type(exc).__name__)
            return []

    def _search_wikimedia_commons(self, query: str) -> List[str]:
        """Zero-key strict relevance-filtered high-resolution photography from Wikimedia Commons."""
        core_terms = _extract_core_terms(query)
        q_clean = " ".join(core_terms[:3]) or query
        try:
            resp = requests.get(
                "https://commons.wikimedia.org/w/api.php",
                headers={"User-Agent": USER_AGENT},
                params={
                    "action": "query",
                    "format": "json",
                    "generator": "search",
                    "gsrnamespace": 6,
                    "gsrsearch": f"{q_clean} filetype:bitmap",
                    "gsrlimit": 12,
                    "prop": "imageinfo",
                    "iiprop": "url|size|mime",
                    "iiurlwidth": 1600,
                },
                timeout=SEARCH_TIMEOUT_SEC,
            )
            if resp.status_code != 200:
                return []
            pages = resp.json().get("query", {}).get("pages", {})
            scored: List[Tuple[int, str]] = []
            for page in pages.values():
                title = page.get("title", "")
                rel = _relevance_score(query, title)
                if rel < 2:
                    continue
                infos = page.get("imageinfo", [])
                if not infos:
                    continue
                info = infos[0]
                mime = info.get("mime", "")
                if mime not in ("image/jpeg", "image/png", "image/webp"):
                    continue
                if (info.get("width") or 0) < 700 or (info.get("height") or 0) < 500:
                    continue
                thumb_url = info.get("thumburl") or info.get("url")
                if thumb_url:
                    scored.append((rel, thumb_url))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [u for _, u in scored[:6]]
        except Exception:
            return []

    def _download_valid_image(self, url: str) -> Optional[Image.Image]:
        try:
            with requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                stream=True,
                timeout=DOWNLOAD_TIMEOUT_SEC,
            ) as resp:
                if resp.status_code != 200:
                    return None
                buf = bytearray()
                dl_start = time.monotonic()
                for chunk in resp.iter_content(chunk_size=131072):
                    if not chunk:
                        continue
                    buf.extend(chunk)
                    if (
                        len(buf) > MAX_RAW_VIDEO_BYTES
                        or (time.monotonic() - dl_start) > DOWNLOAD_TIMEOUT_SEC
                    ):
                        return None
            if len(buf) < 12_000:
                return None
            img = Image.open(io.BytesIO(bytes(buf))).convert("RGB")
            if img.width < 560 or img.height < 420:
                return None
            # Reject flat, blank, or mostly white document scans
            arr = np.asarray(img.resize((64, 64)), dtype=np.float32)
            if float(arr.std()) < 18.0:
                return None
            bright_ratio = float(np.mean(arr > 235.0))
            if bright_ratio > 0.55:
                return None
            return img
        except Exception:
            return None

    def fetch_photo_plate(
        self, query: str, target_size: Tuple[int, int], variant_index: int = 0
    ) -> Path:
        """Fetch and cover-crop a verified high-relevance photo with overscan for 60fps motion."""
        w, h = target_size
        ov_w = int(round(w * 1.18))
        ov_h = int(round(h * 1.18))
        orientation = "portrait" if h > w else "landscape"

        key = hashlib.md5(f"{query}|{ov_w}x{ov_h}|{variant_index}".encode("utf-8")).hexdigest()[:12]
        out_path = self.cache_dir / f"photo_{key}.jpg"
        if out_path.exists() and out_path.stat().st_size > 0:
            return out_path

        cache_key = f"{query}|{orientation}"
        with self._cache_lock:
            urls = self._query_url_cache.get(cache_key)

        if urls is None:
            with self._get_lock(self._photo_search_locks, cache_key):
                with self._cache_lock:
                    urls = self._query_url_cache.get(cache_key)
                if urls is None:
                    found_urls: List[str] = []
                    found_urls.extend(self._search_pexels(query, orientation))
                    if not found_urls:
                        found_urls.extend(self._search_pixabay(query, orientation))
                    if not found_urls:
                        found_urls.extend(self._search_openverse(query, orientation))
                    if len(found_urls) < 2:
                        found_urls.extend(self._search_wikimedia_commons(query))
                    with self._cache_lock:
                        self._query_url_cache[cache_key] = found_urls
                        urls = found_urls

        chosen_img: Optional[Image.Image] = None
        if urls:
            for offset in range(min(5, len(urls))):
                candidate_url = urls[(variant_index + offset) % len(urls)]
                chosen_img = self._download_valid_image(candidate_url)
                if chosen_img is not None:
                    break

        with self._get_lock(self._output_file_locks, f"photo_{key}"):
            if out_path.exists() and out_path.stat().st_size > 0:
                return out_path
            synth_path = self.cache_dir / f"synth_plate_{key}.jpg"
            if chosen_img is None and synth_path.exists() and synth_path.stat().st_size > 0:
                return synth_path
            target_out = out_path if chosen_img is not None else synth_path
            tmp_path = target_out.with_name(f"{target_out.stem}.{threading.get_ident()}.tmp.jpg")
            try:
                if chosen_img is not None:
                    final = _cover_resize(chosen_img, ov_w, ov_h)
                    final.save(tmp_path, format="JPEG", quality=94)
                    os.replace(tmp_path, target_out)
                    logger.info("Sourced verified photo [%s] -> %s", query[:32], target_out.name)
                else:
                    fallback = _generate_cinematic_editorial_plate(
                        f"{query}-{variant_index}", ov_w, ov_h
                    )
                    fallback.save(tmp_path, format="JPEG", quality=94)
                    os.replace(tmp_path, target_out)
                    logger.info(
                        "Rendered cinematic editorial plate [%s] -> %s", query[:32], target_out.name
                    )
            finally:
                tmp_path.unlink(missing_ok=True)

        return target_out

    @staticmethod
    def is_real_media_file(path: Optional[Path]) -> bool:
        """Return True only when the file is genuinely fetched photography/video (never synthetic fallback)."""
        if path is None:
            return False
        p = Path(path)
        return p.exists() and p.stat().st_size > 0 and not p.name.startswith("synth_plate_")

    # ------------------------------------------------------------------
    # PARALLEL BATCH PREFETCH FOR ALL PHOTO_GRADE BEATS
    # ------------------------------------------------------------------
    def prefetch_beats(
        self,
        timed_beats: List[Dict[str, Any]],
        target_size: Tuple[int, int],
    ) -> Dict[str, int]:
        """Parallel batch-prefetch real HD motion clips (with photo fallback) for all photo_grade beats."""
        t0 = time.monotonic()
        targets: List[Tuple[int, Dict[str, Any]]] = [
            (idx, beat)
            for idx, beat in enumerate(timed_beats)
            if beat.get("visual_type") == "photo_grade"
            or beat.get("plate_mode") in ("split_vs_clash", "debate_cta_plate", "dual_fact_spotlight")
        ]
        if not targets:
            return {"video_clips": 0, "photo_plates": 0, "elapsed_sec": 0}

        def _fetch_one(item: Tuple[int, Dict[str, Any]]) -> str:
            idx, beat = item
            query = str(beat.get("visual_query") or "")
            dur = float(beat.get("duration", 2.2))
            clip_path = self.fetch_motion_clip(
                query,
                target_size,
                duration_sec=dur,
                variant_index=idx,
            )
            if clip_path is not None:
                return "video"
            self.fetch_photo_plate(query, target_size, variant_index=idx)
            return "photo"

        n_vid = 0
        n_img = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(_fetch_one, item) for item in targets]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    kind = fut.result()
                    if kind == "video":
                        n_vid += 1
                    else:
                        n_img += 1
                except Exception as exc:
                    logger.warning("Prefetch worker error (%s)", type(exc).__name__)

        elapsed = time.monotonic() - t0
        summary: Dict[str, int] = {
            "video_clips": n_vid,
            "photo_plates": n_img,
            "elapsed_sec": round(elapsed),
        }
        logger.info(
            "Parallel prefetch completed: %d HD video clips, %d photo plates in %.2fs",
            n_vid,
            n_img,
            elapsed,
        )
        return summary
