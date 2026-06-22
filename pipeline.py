"""
pipeline.py
Orchestrates the full streaming extraction pipeline:

  Catalog API  →  GDMirror  →  StreamWish / StreamP2P  →  m3u8 URL

Usage
─────
    from extractor.pipeline import get_stream_urls

    # Movie
    result = get_stream_urls(media_type="movie", imdb_id="tt0137523")

    # TV episode
    result = get_stream_urls(media_type="tv", tmdb_id=1399, season=1, episode=1)

    # result["servers"] is a list of { "provider": str, "streaming_url": str, ... }
"""

from bs4 import BeautifulSoup
from . import catalog, gdmirror, streamwish, streamp2p

# ─────────────────────────────────────────────
# PROVIDER ROUTING
# ─────────────────────────────────────────────

# Keys returned by GDMirror's embed_urls dict
_STREAMWISH_KEYS = {
    "StreamHG", "streamhg",
    "EarnVids", "earnvids",
    "FileMoon", "filemoon",
    "StreamWish", "streamwish",
}

_STREAMP2P_KEYS = {
    "RpmShare", "UpnShare",
    "StreamP2p", "rpmhub",
}

_PLYR_WRAPPER = "https://plyr.technocosmos.surf/hlsplayer?url="


def _unwrap_plyr(url: str) -> str:
    """Strip the plyr.technocosmos wrapper if present."""
    if _PLYR_WRAPPER in url:
        return url.split("?url=")[-1]
    return url


# ─────────────────────────────────────────────
# CORE EXTRACTION
# ─────────────────────────────────────────────

def _extract_from_embed_urls(embed_urls: dict) -> list[dict]:
    """
    Given a dict of { provider_name: iframe_url }, call the right
    sub-extractor for each known provider and collect results.
    """
    servers = []

    for provider_key, embed_url in embed_urls.items():
        # ── StreamWish family ──────────────────────────────────────────
        if provider_key in _STREAMWISH_KEYS:
            try:
                res = streamwish.real_extract(embed_url)
                servers.append({"provider": provider_key, "result": res})
            except Exception as exc:
                servers.append({
                    "provider": provider_key,
                    "status":   "error",
                    "error":    str(exc),
                })

        # ── StreamP2P family ──────────────────────────────────────────
        elif provider_key in _STREAMP2P_KEYS:
            url = _unwrap_plyr(embed_url)
            try:
                res = streamp2p.real_extract(url)
                servers.append({"provider": provider_key, "result": res})
            except Exception as exc:
                servers.append({
                    "provider": provider_key,
                    "status":   "error",
                    "error":    str(exc),
                })

    return servers


def _process_file(fileslug: str) -> list[dict]:
    """Run GDMirror → provider extractors for a single fileslug."""
    gd = gdmirror.real_extract(fileslug)

    if gd["status"] == "error":
        return [{"provider": "gdmirror", "status": "error", "error": gd["error"]}]

    return _extract_from_embed_urls(gd["embed_urls"])


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def get_stream_urls(
    media_type: str,          # "movie" | "tv"
    imdb_id:    str = None,   # for movies  e.g. "tt0137523"
    tmdb_id:    int = None,   # for TV      e.g. 1399
    season:     int = None,
    episode:    int = None,
) -> dict:
    """
    Full pipeline: catalog lookup → embed resolve → stream extract.

    Returns:
        {
            "status":      "success" | "error",
            "status_code": 200 | 4xx,
            "error":       None | str,
            "files":       [...],   # raw catalog entries
            "servers": [
                {
                    "provider": "StreamHG",
                    "result": {
                        "status":        "success",
                        "streaming_url": "https://...m3u8",
                        "headers":       {...},
                        ...
                    }
                },
                ...
            ],
        }
    """
    response = {
        "status":      "error",
        "status_code": 400,
        "error":       None,
        "files":       [],
        "servers":     [],
    }

    # ── 1. Catalog lookup ─────────────────────────────────────────────
    if media_type == "movie":
        if not imdb_id:
            response["error"] = "imdb_id required for movies"
            return response
        cat = catalog.fetch_movie(imdb_id)

    elif media_type == "tv":
        if not all([tmdb_id, season, episode]):
            response["error"] = "tmdb_id, season, and episode required for TV"
            return response
        cat = catalog.fetch_episode(tmdb_id, season, episode)

    else:
        response["error"] = f"Unknown media_type: {media_type!r}"
        return response

    if cat["status"] == "error":
        response["error"] = cat["error"]
        return response

    response["files"] = cat["files"]

    # ── 2. Extract from each file (stop after first success) ──────────
    all_servers = []
    for file_entry in cat["files"]:
        fileslug = file_entry.get("fileslug")
        if not fileslug:
            continue

        servers = _process_file(fileslug)
        all_servers.extend(servers)

        # Stop if we got at least one working stream
        if any(
            s.get("result", {}).get("status") == "success"
            for s in servers
        ):
            break

    if not all_servers:
        response["error"] = "No servers could be resolved"
        return response

    response["status"]      = "success"
    response["status_code"] = 200
    response["servers"]     = all_servers
    return response
