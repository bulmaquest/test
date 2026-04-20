"""
BulmaFlix – IPTV Web Player
Run: python app.py
Dependencies are installed automatically on first run.
"""

import subprocess
import sys
import importlib


def _ensure_deps():
    """Install missing dependencies from requirements.txt automatically."""
    required = {"flask": "flask", "requests": "requests", "cachetools": "cachetools"}
    missing = []
    for import_name, pkg_name in required.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append(pkg_name)
    if missing:
        print(f"[BulmaFlix] Installing missing packages: {', '.join(missing)}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", *missing]
        )
        print("[BulmaFlix] Dependencies installed successfully.")


_ensure_deps()

import re
import io
import threading
import time
import logging
from urllib.parse import urlparse, urljoin

import requests
from cachetools import TTLCache
from flask import Flask, jsonify, render_template, request, Response, stream_with_context

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PAGE_SIZE = 40          # channels returned per page request
M3U_FETCH_TIMEOUT = 30  # seconds to wait for M3U download
IMG_FETCH_TIMEOUT = 8   # seconds for thumbnail proxy
CACHE_TTL = 3600        # seconds to keep a parsed M3U in memory
MAX_CACHED_LISTS = 10   # how many different M3U URLs to keep cached

# Patterns that indicate a "24-hour" channel (case-insensitive)
_24H_PATTERNS = re.compile(
    r"\b(24\s*h(ours?|oras?|rs?)?|ao\s*vivo\s*24h?|24x7)\b", re.IGNORECASE
)

logging.basicConfig(level=logging.INFO, format="[BulmaFlix] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)

# TTLCache: key = M3U URL, value = list of channel dicts
_channel_cache: TTLCache = TTLCache(maxsize=MAX_CACHED_LISTS, ttl=CACHE_TTL)
_cache_lock = threading.Lock()

# Per-URL loading state: 'loading' | 'ready' | 'error'
_load_state: dict = {}
_load_lock = threading.Lock()

# ---------------------------------------------------------------------------
# M3U parsing
# ---------------------------------------------------------------------------

def _parse_m3u(text: str) -> list[dict]:
    """Parse raw M3U text and return a list of channel dicts."""
    channels = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            meta = line
            # Find the actual stream URL (skip blank lines)
            url_line = ""
            j = i + 1
            while j < len(lines):
                candidate = lines[j].strip()
                if candidate and not candidate.startswith("#"):
                    url_line = candidate
                    i = j  # advance outer loop past the URL line
                    break
                j += 1
            channel = _extract_channel(meta, url_line)
            if channel:
                channels.append(channel)
        i += 1
    return channels


def _extract_channel(extinf_line: str, stream_url: str) -> dict | None:
    """Build a channel dict from a parsed #EXTINF line and its stream URL."""
    if not stream_url:
        return None

    # --- display name (after last comma) ---
    name_match = re.search(r",(.+)$", extinf_line)
    name = name_match.group(1).strip() if name_match else "Unknown"

    # --- attributes ---
    logo = _attr(extinf_line, "tvg-logo") or ""
    group = _attr(extinf_line, "group-title") or "Geral"
    tvg_id = _attr(extinf_line, "tvg-id") or ""

    return {
        "name": name,
        "url": stream_url,
        "logo": logo,
        "group": group,
        "tvg_id": tvg_id,
    }


def _attr(line: str, key: str) -> str:
    """Extract a quoted attribute value from an #EXTINF line."""
    pattern = rf'{re.escape(key)}="([^"]*)"'
    m = re.search(pattern, line, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _is_24h(channel: dict) -> bool:
    """Return True if the channel appears to be a 24-hour loop / schedule channel."""
    haystack = f"{channel['name']} {channel['group']}"
    return bool(_24H_PATTERNS.search(haystack))


def _fetch_and_parse(url: str) -> None:
    """Background thread: fetch, parse, filter and cache a M3U playlist."""
    with _load_lock:
        _load_state[url] = "loading"
    try:
        log.info("Fetching M3U: %s", url)
        resp = requests.get(
            url,
            timeout=M3U_FETCH_TIMEOUT,
            headers={"User-Agent": "BulmaFlix/1.0"},
            stream=True,
        )
        resp.raise_for_status()

        # Read up to 50 MB to avoid runaway downloads
        content_chunks = []
        total = 0
        for chunk in resp.iter_content(chunk_size=65536):
            content_chunks.append(chunk)
            total += len(chunk)
            if total > 50 * 1024 * 1024:
                log.warning("M3U file too large – truncating at 50 MB")
                break
        raw = b"".join(content_chunks).decode("utf-8", errors="replace")

        channels = _parse_m3u(raw)
        before = len(channels)
        channels = [ch for ch in channels if not _is_24h(ch)]
        log.info(
            "Parsed %d channels (%d removed as 24h) from %s",
            len(channels),
            before - len(channels),
            url,
        )

        with _cache_lock:
            _channel_cache[url] = channels
        with _load_lock:
            _load_state[url] = "ready"

    except Exception as exc:
        log.error("Failed to load M3U %s: %s", url, exc)
        with _load_lock:
            _load_state[url] = f"error:{exc}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/load", methods=["POST"])
def api_load():
    """Start background loading of a M3U URL. Returns immediately."""
    data = request.get_json(force=True, silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL is required"}), 400

    with _load_lock:
        state = _load_state.get(url, "")

    # Already cached and ready – no need to re-fetch
    with _cache_lock:
        already_cached = url in _channel_cache

    if already_cached and state == "ready":
        return jsonify({"status": "ready"})

    if state == "loading":
        return jsonify({"status": "loading"})

    # Kick off background fetch
    t = threading.Thread(target=_fetch_and_parse, args=(url,), daemon=True)
    t.start()
    return jsonify({"status": "loading"})


@app.route("/api/status")
def api_status():
    """Return current load state for a given M3U URL."""
    url = request.args.get("url", "").strip()
    with _load_lock:
        state = _load_state.get(url, "unknown")
    return jsonify({"status": state})


@app.route("/api/channels")
def api_channels():
    """
    Return a page of channels for a given M3U URL.
    Query params:
      url      – the M3U URL (required)
      page     – 1-based page number (default 1)
      search   – filter by name/group substring
      group    – filter by exact group name
    """
    url = request.args.get("url", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    search = request.args.get("search", "").strip().lower()
    group_filter = request.args.get("group", "").strip()

    with _cache_lock:
        channels = list(_channel_cache.get(url, []))

    if not channels:
        return jsonify({"channels": [], "total": 0, "pages": 0, "page": page})

    # Apply filters
    if search:
        channels = [
            ch for ch in channels
            if search in ch["name"].lower() or search in ch["group"].lower()
        ]
    if group_filter:
        channels = [ch for ch in channels if ch["group"] == group_filter]

    total = len(channels)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_channels = channels[start:end]

    return jsonify({
        "channels": page_channels,
        "total": total,
        "pages": pages,
        "page": page,
    })


@app.route("/api/groups")
def api_groups():
    """Return sorted list of groups/categories for a given M3U URL."""
    url = request.args.get("url", "").strip()
    with _cache_lock:
        channels = list(_channel_cache.get(url, []))
    groups = sorted({ch["group"] for ch in channels})
    return jsonify({"groups": groups})


@app.route("/api/imgproxy")
def api_imgproxy():
    """
    Proxy a thumbnail image to avoid mixed-content / CORS issues.
    ?url=<image-url>
    """
    img_url = request.args.get("url", "").strip()
    if not img_url:
        return "", 400

    # Basic URL validation
    parsed = urlparse(img_url)
    if parsed.scheme not in ("http", "https"):
        return "", 400

    try:
        resp = requests.get(
            img_url,
            timeout=IMG_FETCH_TIMEOUT,
            headers={"User-Agent": "BulmaFlix/1.0"},
            stream=True,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/jpeg")

        def generate():
            for chunk in resp.iter_content(chunk_size=8192):
                yield chunk

        return Response(
            stream_with_context(generate()),
            content_type=content_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception:
        return "", 502


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  BulmaFlix IPTV Player")
    print("  Acesse: http://localhost:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)
