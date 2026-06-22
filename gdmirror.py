"""
gdmirror.py
Resolves a GDMirror / BollyFlix embed URL to a dict of provider stream URLs.

Flow
────
1.  Receive a fileslug  →  call embedhelper.php via the proxy
2.  Decode base64 mresult  →  { provider_key: stream_id }
3.  Combine with siteUrls + siteFriendlyNames  →  full iframe URLs
"""

import base64
import json
import requests

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

TAG = "gdmirror"

PROXY_API = "https://pro.iqsmartgames.com/embedhelper.php"   # adjust if proxy differs

HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Encoding":        "gzip, deflate, br",
    "Accept-Language":        "en-US,en;q=0.9",
    "Cache-Control":          "no-cache",
    "Connection":             "keep-alive",
    "DNT":                    "1",
    "Pragma":                 "no-cache",
    "Sec-Fetch-Dest":         "document",
    "Sec-Fetch-Mode":         "navigate",
    "Sec-Fetch-Site":         "same-origin",
    "Sec-Fetch-User":         "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/116.0.0.0 Safari/537.36"
    ),
}

session = requests.Session()


# ─────────────────────────────────────────────
# INTERNAL
# ─────────────────────────────────────────────

def _fetch_embed_data(fileslug: str) -> dict:
    """POST to the embedhelper proxy and return the JSON payload."""
    resp = session.get(
        PROXY_API,
        params={
            "type":     "post",
            "post_sid": fileslug,
            "url":      "https://pro.iqsmartgames.com/embedhelper.php",
        },
        headers=HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def _build_iframe_urls(embed_data: dict) -> dict:
    """
    Decode base64 mresult and map each provider key to its full iframe URL.

    Returns:  { "StreamHG": "https://...", "FileMoon": "https://...", ... }
    """
    mresult = embed_data.get("mresult")
    if not mresult:
        raise ValueError("mresult missing in embed data")

    stream_ids   = json.loads(base64.b64decode(mresult).decode("utf-8"))
    site_urls    = embed_data.get("siteUrls", {})
    friendly     = embed_data.get("siteFriendlyNames", {})

    urls = {}
    for key, sid in stream_ids.items():
        if not sid:
            continue
        base_url = site_urls.get(key)
        if not base_url:
            continue
        name       = friendly.get(key, key)
        urls[name] = f"{base_url}{sid}"

    return urls


# ─────────────────────────────────────────────
# PUBLIC
# ─────────────────────────────────────────────

def real_extract(fileslug: str) -> dict:
    """
    Given a fileslug, return a dict of provider → iframe URL.

    Args:
        fileslug:  e.g. "t69pjnr"

    Returns:
        {
            "status":      "success" | "error",
            "status_code": 200 | 4xx,
            "error":       None | str,
            "embed_urls":  { "StreamHG": "https://...", ... },
        }
    """
    result = {
        "status":      "error",
        "status_code": 400,
        "error":       None,
        "embed_urls":  {},
    }

    try:
        embed_data = _fetch_embed_data(fileslug)
        iframe_urls = _build_iframe_urls(embed_data)

        if not iframe_urls:
            result["error"] = "No playable stream URLs found"
            return result

        result["status"]      = "success"
        result["status_code"] = 200
        result["embed_urls"]  = iframe_urls

    except requests.exceptions.Timeout:
        result["error"] = "[GDMirror] Request timed out"

    except requests.exceptions.RequestException as exc:
        result["error"] = f"[GDMirror] HTTP error: {exc}"

    except json.JSONDecodeError as exc:
        result["error"] = f"[GDMirror] JSON parse failed: {exc}"

    except base64.binascii.Error as exc:
        result["error"] = f"[GDMirror] Base64 decode failed: {exc}"

    except ValueError as exc:
        result["error"] = f"[GDMirror] {exc}"

    except Exception as exc:
        result["error"] = f"[GDMirror] Unexpected error: {exc}"

    return result
