"""
views.py
Django views that wire the extraction pipeline to HTTP endpoints
and serve the player HTML with the resolved m3u8 URL.

URL patterns (add to your urls.py):
────────────────────────────────────
    path("movie/<str:imdb_id>/",              views.movie_player),
    path("tv/<int:tmdb_id>/S<int:season>/E<int:episode>/", views.tv_player),
    path("api/stream/movie/<str:imdb_id>/",   views.api_movie),
    path("api/stream/tv/<int:tmdb_id>/",      views.api_tv_episode),
"""

import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET

from .extractor.pipeline import get_stream_urls


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _first_m3u8(pipeline_result: dict) -> str | None:
    """Pick the first successful m3u8 URL from a pipeline result."""
    for srv in pipeline_result.get("servers", []):
        url = srv.get("result", {}).get("streaming_url") or srv.get("result", {}).get("m3u8_url")
        if url:
            return url
    return None


def _player_html(m3u8_url: str, title: str = "") -> str:
    """
    Return the player HTML with the resolved m3u8 URL injected.
    The player page is served from the static template; we just
    inject ?url=<m3u8> into the page's resolveAndPlay() router.
    """
    # Redirect to the player page with ?url= so the frontend resolveAndPlay()
    # picks it up in the `urlParam` branch — no template change required.
    return (
        f'<script>window.location.replace('
        f'window.location.pathname + "?url=" + encodeURIComponent("{m3u8_url}"));</script>'
    )


# ─────────────────────────────────────────────
# JSON API VIEWS
# ─────────────────────────────────────────────

@require_GET
def api_movie(request, imdb_id: str):
    """
    GET /api/stream/movie/<imdb_id>/
    Returns full pipeline result as JSON.
    """
    result = get_stream_urls(media_type="movie", imdb_id=imdb_id)
    return JsonResponse(result, status=result["status_code"])


@require_GET
def api_tv_episode(request, tmdb_id: int):
    """
    GET /api/stream/tv/<tmdb_id>/?season=1&episode=1
    Returns full pipeline result as JSON.
    """
    season  = request.GET.get("season")
    episode = request.GET.get("episode")

    if not season or not episode:
        return JsonResponse(
            {"status": "error", "error": "season and episode query params required"},
            status=400,
        )

    result = get_stream_urls(
        media_type="tv",
        tmdb_id=int(tmdb_id),
        season=int(season),
        episode=int(episode),
    )
    return JsonResponse(result, status=result["status_code"])


# ─────────────────────────────────────────────
# PLAYER VIEWS
# ─────────────────────────────────────────────

@require_GET
def movie_player(request, imdb_id: str):
    """
    GET /movie/<imdb_id>/
    Resolves stream and redirects the player to ?url=<m3u8>.
    """
    result = get_stream_urls(media_type="movie", imdb_id=imdb_id)

    if result["status"] == "error":
        return HttpResponse(
            f"<h1>Stream Error</h1><p>{result['error']}</p>",
            status=502,
            content_type="text/html",
        )

    m3u8 = _first_m3u8(result)
    if not m3u8:
        return HttpResponse(
            "<h1>No stream found</h1>",
            status=404,
            content_type="text/html",
        )

    return HttpResponse(_player_html(m3u8), content_type="text/html")


@require_GET
def tv_player(request, tmdb_id: int, season: int, episode: int):
    """
    GET /tv/<tmdb_id>/S<season>/E<episode>/
    Resolves stream and redirects the player to ?url=<m3u8>.
    """
    result = get_stream_urls(
        media_type="tv",
        tmdb_id=tmdb_id,
        season=season,
        episode=episode,
    )

    if result["status"] == "error":
        return HttpResponse(
            f"<h1>Stream Error</h1><p>{result['error']}</p>",
            status=502,
            content_type="text/html",
        )

    m3u8 = _first_m3u8(result)
    if not m3u8:
        return HttpResponse(
            "<h1>No stream found</h1>",
            status=404,
            content_type="text/html",
        )

    return HttpResponse(_player_html(m3u8), content_type="text/html")
