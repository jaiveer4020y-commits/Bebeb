"""
urls.py  —  add these to your Django project's urlpatterns
"""

from django.urls import path
from . import views

urlpatterns = [
    # ── Player pages ─────────────────────────────────────────────────
    path("movie/<str:imdb_id>/",                               views.movie_player),
    path("tv/<int:tmdb_id>/S<int:season>/E<int:episode>/",     views.tv_player),

    # ── JSON API ──────────────────────────────────────────────────────
    # GET /api/stream/movie/tt0137523/
    path("api/stream/movie/<str:imdb_id>/",                    views.api_movie),

    # GET /api/stream/tv/1399/?season=1&episode=1
    path("api/stream/tv/<int:tmdb_id>/",                       views.api_tv_episode),
]
