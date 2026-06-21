# app.py (Flask example)
from flask import Flask, request, jsonify
import requests
import json
import base64
import re

app = Flask(__name__)

# ------------------------------
# 1. Google Apps Script call
# ------------------------------
def get_fileslug(type_, imdbid=None, tmdbid=None, season=None, episode=None):
    if type_ == 'movie':
        url = f"https://script.google.com/macros/s/AKfycbw8pW6LI6nNDxqn1wXaPOzHN5QBaeqB12qv-J5NaNcu7IWqbsX9KJkruY_8y8wW12hv/exec?type=movie&imdbid={imdbid}&key=e11a7debaaa4f5d25b671706ffe4d2acb56efbd4"
    else:
        url = f"https://script.google.com/macros/s/AKfycbw8pW6LI6nNDxqn1wXaPOzHN5QBaeqB12qv-J5NaNcu7IWqbsX9KJkruY_8y8wW12hv/exec?type=tv&tmdbid={tmdbid}&season={season}&epname={episode}&key=e11a7debaaa4f5d25b671706ffe4d2acb56efbd4"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not data.get('success') or not data.get('data'):
        raise ValueError('No file slugs from Google Script')
    return data['data'][0]['fileslug']   # pick the first

# ------------------------------
# 2. Fetch embed data from pro.iqsmartgames.com
# ------------------------------
def fetch_embed_data(fileslug):
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "DNT": "1",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
    }
    url = "https://pro.iqsmartgames.com/embedhelper.php"
    params = {"type": "post", "post_sid": fileslug}
    resp = requests.post(url, data=params, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()

def build_iframe_urls(embed_data):
    mresult = embed_data.get('mresult')
    if not mresult:
        raise ValueError('mresult missing')
    decoded = base64.b64decode(mresult).decode('utf-8')
    stream_ids = json.loads(decoded)
    site_urls = embed_data.get('siteUrls', {})
    friendly = embed_data.get('siteFriendlyNames', {})
    iframe_urls = {}
    for key, sid in stream_ids.items():
        if sid and site_urls.get(key):
            iframe_urls[friendly.get(key, key)] = f"{site_urls[key]}{sid}"
    return iframe_urls

# ------------------------------
# 3. StreamWish / StreamP2P extractors
# (You'll need to implement these as Python functions that take the iframe URL and return final HLS + subtitles)
# For example:
#   def extract_streamwish(url): ...
#   def extract_streamp2p(url): ...
# I'll assume you have them in separate modules.
# ------------------------------

# For now, let's stub them:
def extract_streamwish(url):
    # Simulate: fetch the iframe page, find m3u8, etc.
    # Return dict with 'url' and 'subtitles'
    return {"url": "https://...", "subtitles": {}}

def extract_streamp2p(url):
    return {"url": "https://...", "subtitles": {}}

# ------------------------------
# 4. Main endpoint
# ------------------------------
@app.route('/api/stream')
def get_stream():
    try:
        req_type = request.args.get('type')
        if req_type not in ('movie', 'tv'):
            return jsonify({"status": "error", "error": "Invalid type"}), 400

        # 1. Get fileslug
        if req_type == 'movie':
            imdbid = request.args.get('imdbid')
            if not imdbid:
                return jsonify({"status": "error", "error": "Missing imdbid"}), 400
            fileslug = get_fileslug('movie', imdbid=imdbid)
        else:
            tmdbid = request.args.get('tmdbid')
            season = request.args.get('season')
            episode = request.args.get('episode')
            if not all([tmdbid, season, episode]):
                return jsonify({"status": "error", "error": "Missing tmdbid/season/episode"}), 400
            fileslug = get_fileslug('tv', tmdbid=tmdbid, season=season, episode=episode)

        # 2. Get embed data and iframe URLs
        embed_data = fetch_embed_data(fileslug)
        iframe_urls = build_iframe_urls(embed_data)

        # 3. Extract from each provider
        servers = []
        # StreamWish providers
        for provider in ['StreamHG', 'streamhg', 'EarnVids', 'earnvids', 'FileMoon', 'filemoon', 'StreamWish', 'streamwish']:
            iframe = iframe_urls.get(provider)
            if iframe:
                try:
                    result = extract_streamwish(iframe)
                    if result.get('url'):
                        servers.append({
                            "provider": provider,
                            "hls_url": result['url'],
                            "subtitles": result.get('subtitles', {})
                        })
                except Exception as e:
                    pass  # log error

        # StreamP2P providers
        for provider in ['RpmShare', 'UpnShare', 'StreamP2p', 'rpmhub']:
            iframe = iframe_urls.get(provider)
            if iframe:
                # unwrap plyr if needed
                if "https://plyr.technocosmos.surf/hlsplayer?url=" in iframe:
                    iframe = iframe.split("?url=")[-1]
                try:
                    result = extract_streamp2p(iframe)
                    if result.get('url'):
                        servers.append({
                            "provider": provider,
                            "hls_url": result['url'],
                            "subtitles": result.get('subtitles', {})
                        })
                except Exception as e:
                    pass

        if not servers:
            return jsonify({"status": "error", "error": "No playable streams found"}), 404

        return jsonify({"status": "success", "servers": servers})

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
