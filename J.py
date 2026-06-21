# api/views.py
import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# Import your existing scraping modules (gdmirrorbot, streamwish, streamp2p)
from .sites import gdmirrorbot, streamwish, streamp2p

@csrf_exempt
def get_stream(request):
    """
    Accepts query parameters:
      - type: 'movie' or 'tv'
      - imdbid: for movies (e.g., tt0137523)
      - tmdbid: for TV shows (e.g., 1399)
      - season: for TV
      - episode: for TV
    Returns:
      {
        "status": "success",
        "servers": [
          {
            "provider": "StreamWish",
            "hls_url": "https://...m3u8",
            "subtitles": { ... }  # optional
          },
          ...
        ]
      }
    """
    try:
        req_type = request.GET.get('type')
        if req_type not in ('movie', 'tv'):
            return JsonResponse({"status": "error", "error": "Invalid type"}, status=400)

        # --- 1. Call Google Apps Script to get file slugs ---
        if req_type == 'movie':
            imdbid = request.GET.get('imdbid')
            if not imdbid:
                return JsonResponse({"status": "error", "error": "Missing imdbid"}, status=400)
            gscript_url = f"https://script.google.com/macros/s/AKfycbw8pW6LI6nNDxqn1wXaPOzHN5QBaeqB12qv-J5NaNcu7IWqbsX9KJkruY_8y8wW12hv/exec?type=movie&imdbid={imdbid}&key=e11a7debaaa4f5d25b671706ffe4d2acb56efbd4"
        else:
            tmdbid = request.GET.get('tmdbid')
            season = request.GET.get('season')
            episode = request.GET.get('episode')
            if not all([tmdbid, season, episode]):
                return JsonResponse({"status": "error", "error": "Missing tmdbid, season, or episode"}, status=400)
            gscript_url = f"https://script.google.com/macros/s/AKfycbw8pW6LI6nNDxqn1wXaPOzHN5QBaeqB12qv-J5NaNcu7IWqbsX9KJkruY_8y8wW12hv/exec?type=tv&tmdbid={tmdbid}&season={season}&epname={episode}&key=e11a7debaaa4f5d25b671706ffe4d2acb56efbd4"

        gscript_resp = requests.get(gscript_url, timeout=10)
        gscript_resp.raise_for_status()
        gscript_data = gscript_resp.json()
        if not gscript_data.get('success'):
            return JsonResponse({"status": "error", "error": "Google Script returned error"}, status=500)

        # We'll use the first file slug (or let the client choose later)
        files = gscript_data.get('data', [])
        if not files:
            return JsonResponse({"status": "error", "error": "No files found"}, status=404)

        # For simplicity, pick the first one; you could let the player choose by filename
        first_file = files[0]
        fileslug = first_file.get('fileslug')

        # --- 2. Call gdmirrorbot to get embed iframe URLs ---
        # gdmirrorbot.real_extract expects a URL or direct sid; we'll use the fileslug
        # We need to adapt gdmirrorbot to accept just the slug, or we pass a constructed URL.
        # Based on your code, we can call _fetch_embed_data directly.
        # I'll assume you have a function `extract_embed_urls(fileslug)` that returns iframe_urls.

        # Let's create a helper that wraps the logic:
        embed_data = gdmirrorbot.real_extract_for_slug(fileslug)  # you'll need to implement this
        # Or we can call the existing real_extract with a special URL:
        # embed_data = gdmirrorbot.real_extract(f"fileslug://{fileslug}", request)

        # For simplicity, we'll inline the steps:
        from .sites.gdmirrorbot import _fetch_embed_data, _build_iframe_urls
        embed_data = _fetch_embed_data(fileslug)
        iframe_urls = _build_iframe_urls(embed_data)

        # --- 3. Extract final HLS from each iframe provider ---
        media_results = []

        # StreamWish extractor
        for provider in ['StreamHG', 'streamhg', 'EarnVids', 'earnvids', 'FileMoon', 'filemoon', 'StreamWish', 'streamwish']:
            url = iframe_urls.get(provider)
            if url:
                try:
                    result = streamwish.real_extract(url, request)
                    media_results.append({
                        "provider": provider,
                        "hls_url": result.get('url'),  # depending on your extractor's return
                        "subtitles": result.get('subtitles', {}),
                    })
                except Exception as e:
                    media_results.append({"provider": provider, "error": str(e)})

        # RpmShare / UpnShare / StreamP2P
        for provider in ['RpmShare', 'UpnShare', 'StreamP2p', 'rpmhub']:
            url = iframe_urls.get(provider)
            if url and "https://plyr.technocosmos.surf/hlsplayer?url=" in url:
                url = url.split("?url=")[-1]
            if url:
                try:
                    result = streamp2p.real_extract(url, request)
                    media_results.append({
                        "provider": provider,
                        "hls_url": result.get('url'),
                        "subtitles": result.get('subtitles', {}),
                    })
                except Exception as e:
                    media_results.append({"provider": provider, "error": str(e)})

        # --- 4. Return success ---
        return JsonResponse({
            "status": "success",
            "servers": media_results
        })

    except Exception as e:
        return JsonResponse({"status": "error", "error": str(e)}, status=500)
