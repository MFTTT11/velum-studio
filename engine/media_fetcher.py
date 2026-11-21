"""Zero-Cost Free Visual Sourcing Engine (Wikimedia Commons + Optional Pexels/Pixabay).

Downloads real, license-safe high-resolution photography for `photo_grade` beats,
validates integrity and dimensions, cover-crops with overscan (zero black borders),
and falls back to rich procedural editorial dark-photography plates when offline.
"""

from __future__ import annotations

import hashlib
import io
import math
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter

from core.config import get_logger

logger = get_logger("media_fetcher")

USER_AGENT = "ScaleZeroDocumentaryEngine/1.0 (https://github.com/scale-zero-lab; educational)"


def _cover_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Scale and center-crop image to exact target_w x target_h with zero letterboxing."""
    src_w, src_h = img.size
    scale = max(target_w / max(src_w, 1), target_h / max(src_h, 1))
    new_w = max(target_w, int(math.ceil(src_w * scale)))
    new_h = max(target_h, int(math.ceil(src_h * scale)))
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h)).convert("RGB")


def _generate_cinematic_editorial_plate(
    seed_key: str, width: int, height: int
) -> Image.Image:
    """Generate a high-aesthetic dark architectural/cinematic atmospheric frame if offline."""
    digest = int(hashlib.sha256(seed_key.encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.default_rng(digest)

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    nx = xx / max(width - 1, 1)
    ny = yy / max(height - 1, 1)

    # Rich documentary atmospheric gradient (deep obsidian + cyan/amber/crimson mood lights)
    palettes = [
        ((10, 16, 28), (0, 200, 235), (255, 165, 0)),
        ((14, 12, 24), (255, 50, 90), (0, 210, 245)),
        ((9, 20, 24), (45, 225, 150), (0, 185, 240)),
        ((16, 15, 22), (255, 184, 0), (45, 130, 220)),
    ]
    base_c, acc1, acc2 = palettes[digest % len(palettes)]
    cx1, cy1 = float(rng.uniform(0.22, 0.78)), float(rng.uniform(0.22, 0.58))
    cx2, cy2 = float(rng.uniform(0.18, 0.82)), float(rng.uniform(0.45, 0.82))

    g1 = np.exp(-((nx - cx1) ** 2 + (ny - cy1) ** 2) / 0.14) * 0.42
    g2 = np.exp(-((nx - cx2) ** 2 + (ny - cy2) ** 2) / 0.18) * 0.28

    # Subtle architectural perspective light streaks
    wave = (np.sin((nx * 14.0 + ny * 6.0) + (digest % 7)) * 0.5 + 0.5) ** 4 * 0.08

    arr = np.zeros((height, width, 3), dtype=np.float32)
    for c in range(3):
        arr[:, :, c] = np.clip(
            base_c[c] + acc1[c] * (g1 + wave) + acc2[c] * g2,
            0,
            255,
        )
    img = Image.fromarray(arr.astype(np.uint8), mode="RGB").convert("RGBA")

    # Add geometric depth rings & bokeh lighting for unmistakable documentary production value
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for i in range(12):
        r = int(rng.integers(int(min(width, height) * 0.06), int(min(width, height) * 0.36)))
        px = int(rng.integers(0, width))
        py = int(rng.integers(0, height))
        col = acc1 if i % 2 == 0 else acc2
        draw.ellipse([px - r, py - r, px + r, py + r], outline=(*col, 55), width=2)
    # Perspective architectural lines converging to vanishing point
    vx, vy = int(width * cx1), int(height * cy1)
    for angle_idx in range(18):
        ang = (angle_idx / 18.0) * math.pi * 2.0
        ex = int(vx + math.cos(ang) * max(width, height))
        ey = int(vy + math.sin(ang) * max(width, height))
        draw.line([(vx, vy), (ex, ey)], fill=(*acc1, 24), width=1)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=1.2))
    img.alpha_composite(overlay)
    return img.convert("RGB")


class MediaFetcher:
    """Sources high-res royalty-free editorial photography across free zero-cost APIs."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.pexels_key = os.getenv("PEXELS_API_KEY", "").strip()
        self.pixabay_key = os.getenv("PIXABAY_API_KEY", "").strip()
        self._query_url_cache: Dict[str, List[str]] = {}

    def _search_pexels(self, query: str, orientation: str) -> List[str]:
        if not self.pexels_key:
            return []
        try:
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": self.pexels_key, "User-Agent": USER_AGENT},
                params={"query": query, "orientation": orientation, "per_page": 6},
                timeout=8,
            )
            if resp.status_code == 200:
                photos = resp.json().get("photos", [])
                return [p["src"]["large2x"] for p in photos if p.get("src", {}).get("large2x")]
        except Exception as exc:
            logger.debug("Pexels search fallback (%s)", type(exc).__name__)
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
                timeout=8,
            )
            if resp.status_code == 200:
                hits = resp.json().get("hits", [])
                return [h["largeImageURL"] for h in hits if h.get("largeImageURL")]
        except Exception as exc:
            logger.debug("Pexels search fallback (%s)", type(exc).__name__)
        return []

    def _search_wikimedia_commons(self, query: str) -> List[str]:
        """Zero-key high-resolution photography search via Wikimedia Commons API."""
        try:
            resp = requests.get(
                "https://commons.wikimedia.org/w/api.php",
                headers={"User-Agent": USER_AGENT},
                params={
                    "action": "query",
                    "format": "json",
                    "generator": "search",
                    "gsrnamespace": 6,
                    "gsrsearch": f"{query} filetype:bitmap",
                    "gsrlimit": 8,
                    "prop": "imageinfo",
                    "iiprop": "url|size|mime",
                    "iiurlwidth": 1600,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            pages = resp.json().get("query", {}).get("pages", {})
            urls: List[str] = []
            for page in pages.values():
                infos = page.get("imageinfo", [])
                if not infos:
                    continue
                info = infos[0]
                mime = info.get("mime", "")
                if mime not in ("image/jpeg", "image/png", "image/webp"):
                    continue
                if info.get("width", 0) < 640 or info.get("height", 0) < 480:
                    continue
                thumb_url = info.get("thumburl") or info.get("url")
                if thumb_url:
                    urls.append(thumb_url)
            return urls
        except Exception:
            return []

    def _download_valid_image(self, url: str) -> Optional[Image.Image]:
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=12)
            if resp.status_code != 200 or len(resp.content) < 8_000:
                return None
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            if img.width < 500 or img.height < 400:
                return None
            # Reject flat/empty single-color images
            arr = np.asarray(img.resize((64, 64)), dtype=np.float32)
            if float(arr.std()) < 14.0:
                return None
            return img
        except Exception:
            return None

    def fetch_photo_plate(
        self, query: str, target_size: Tuple[int, int], variant_index: int = 0
    ) -> Path:
        """Fetch and cover-crop a real photo (with overscan for smooth Ken Burns pan/zoom)."""
        w, h = target_size
        # Overscan by 18% so 60fps zoom/pan never exposes edges or letterboxes
        ov_w = int(round(w * 1.18))
        ov_h = int(round(h * 1.18))
        orientation = "portrait" if h > w else "landscape"

        key = hashlib.md5(f"{query}|{ov_w}x{ov_h}|{variant_index}".encode("utf-8")).hexdigest()[:12]
        out_path = self.cache_dir / f"photo_{key}.jpg"
        if out_path.exists():
            return out_path

        cache_key = f"{query}|{orientation}"
        if cache_key not in self._query_url_cache:
            urls: List[str] = []
            urls.extend(self._search_pexels(query, orientation))
            if not urls:
                urls.extend(self._search_pixabay(query, orientation))
            if not urls:
                urls.extend(self._search_wikimedia_commons(query))
            # Broader fallback query with top 2 nouns if multi-word search returned empty
            if not urls and len(query.split()) > 2:
                short_q = " ".join(query.split()[:2])
                urls.extend(self._search_wikimedia_commons(short_q))
            self._query_url_cache[cache_key] = urls

        urls = self._query_url_cache.get(cache_key, [])
        chosen_img: Optional[Image.Image] = None
        if urls:
            # Try rotated candidate URLs so consecutive beats use distinct frames
            for offset in range(min(4, len(urls))):
                candidate_url = urls[(variant_index + offset) % len(urls)]
                chosen_img = self._download_valid_image(candidate_url)
                if chosen_img is not None:
                    break

        if chosen_img is not None:
            final = _cover_resize(chosen_img, ov_w, ov_h)
            final.save(out_path, format="JPEG", quality=93)
            logger.info("Sourced real photo [%s] -> %s", query[:32], out_path.name)
        else:
            fallback = _generate_cinematic_editorial_plate(f"{query}-{variant_index}", ov_w, ov_h)
            fallback.save(out_path, format="JPEG", quality=93)
            logger.info("Rendered editorial atmospheric plate [%s] -> %s", query[:32], out_path.name)

        return out_path
