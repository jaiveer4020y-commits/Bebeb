"""
catalog.py
Fetches file listings (fileslug + metadata) for movies and TV episodes
from the Google Apps Script catalog API.
"""

import requests

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

TAG = "catalog"

CATALOG_API = (
    "https://script.google.com/macros/s/"
    "AKfycbw8pW6LI6nNDxqn1wXaPOzHN5QBaeqB12qv-J5NaNcu7IWqbsX9KJkruY_8y8wW12hv/exec"
)

API_KEY = "e11a7debaaa4f5d25b671706ffe4d2acb56efbd4"

HEADERS = {
    "Accept":          "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/116.0.0.0 Safari/537.36"
    ),
}

session = requests.Session()


# ─────────────────────────────────────────────
# PUBLIC
# ─────────────────────────────────────────────

def fetch_movie(imdb_id: str) -> dict:
    """
    Fetch available file listings for a movie.

    Args:
        imdb_id:  e.g. "tt0137523"

    Returns:
        {
            "status":  "success" | "error",
            "error":   None | str,
            "files": [
                {
                    "filename": "Fight Club 1080p BluRay",
                    "fileslug": "t69pjnr",
                    "fsize":    "2.1 GB",
                },
                ...
            ],
        }
    """
    return _fetch(params={"type": "movie", "imdbid": imdb_id, "key": API_KEY})


def fetch_episode(tmdb_id: str | int, season: int, episode: int) -> dict:
    """
    Fetch available file listings for a TV episode.

    Args:
        tmdb_id:  e.g. 1399  (Game of Thrones)
        season:   1
        episode:  1

    Returns same shape as fetch_movie().
    """
    return _fetch(
        params={
            "type":    "tv",
            "tmdbid":  str(tmdb_id),
            "season":  str(season),
            "epname":  str(episode),
            "key":     API_KEY,
        }
    )


# ─────────────────────────────────────────────
# INTERNAL
# ─────────────────────────────────────────────

def _fetch(params: dict) -> dict:
    result = {"status": "error", "error": None, "files": []}

    try:
        resp = session.get(CATALOG_API, params=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            result["error"] = data.get("message", "API returned success=false")
            return result

        files = data.get("data", [])
        if not files:
            result["error"] = "No files found"
            return result

        result["status"] = "success"
        result["files"]  = files

    except requests.exceptions.Timeout:
        result["error"] = "[Catalog] Request timed out"

    except requests.exceptions.RequestException as exc:
        result["error"] = f"[Catalog] HTTP error: {exc}"

    except ValueError as exc:
        result["error"] = f"[Catalog] JSON parse failed: {exc}"

    except Exception as exc:
        result["error"] = f"[Catalog] Unexpected error: {exc}"

    return result
