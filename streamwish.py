"""
streamwish.py
Extracts HLS streaming URL from StreamWish / FileMoon / EarnVids / StreamHG
"""

import re
import ast
import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

TAG = "streamwish"

HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "DNT": "1",
    "Pragma": "no-cache",
    "Referer": "https://multimovies.makeup/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; K) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
}

session = requests.Session()


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _to_base36(n: int) -> str:
    """Converts an integer to a base-36 string."""
    if n == 0:
        return "0"
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    result = ""
    while n:
        result = chars[n % 36] + result
        n //= 36
    return result


def _unpack_js(js_code: str) -> str:
    """Unpacks eval(function(p,a,c,k,e,d){...}) packed JS."""
    # Strip the eval wrapper, keep the argument tuple
    encoded = re.sub(
        r"eval\(function\([^\)]*\)\{[^\}]*\}\(|\.split\('\|'\)\)\)",
        "",
        js_code,
    )
    p, a, c, k = ast.literal_eval(encoded)[:4]
    a = int(a)
    c = int(c)
    k = k.split("|")
    for i in range(c):
        token = k[c - i - 1]
        if token:
            p = re.sub(r"\b" + _to_base36(c - i - 1) + r"\b", token, p)
    return p


# ─────────────────────────────────────────────
# PUBLIC
# ─────────────────────────────────────────────

def real_extract(url: str, request=None) -> dict:
    """
    Extract HLS streaming URL from a StreamWish-family embed page.

    Returns:
        {
            "status":        "success" | "error",
            "status_code":   200 | 4xx,
            "error":         None | str,
            "tag":           "streamwish",
            "headers":       dict,
            "streaming_url": str | None,
        }
    """
    result = {
        "status":        "error",
        "status_code":   400,
        "error":         None,
        "tag":           TAG,
        "headers":       None,
        "streaming_url": None,
    }

    try:
        resp = session.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        html = resp.text

        if "File is no longer" in html:
            result["status"]      = "error"
            result["status_code"] = 410
            result["error"]       = "Link expired"
            return result

        soup    = BeautifulSoup(html, "html.parser")
        js_code = next(
            (
                s.string
                for s in soup.find_all("script")
                if s.string and "eval(function(p,a,c,k,e,d)" in s.string
            ),
            None,
        )

        if not js_code:
            result["error"] = "Packed JS not found in page"
            return result

        unpacked   = _unpack_js(js_code)
        m3u8_match = re.search(r'"hls2"\s*:\s*"([^"]+)', unpacked)

        if not m3u8_match:
            result["error"] = "HLS URL not found in unpacked JS"
            return result

        result["status"]        = "success"
        result["status_code"]   = 200
        result["headers"]       = HEADERS
        result["streaming_url"] = m3u8_match.group(1)

    except requests.exceptions.Timeout:
        result["error"] = "[StreamWish] Request timed out"

    except requests.exceptions.RequestException as exc:
        result["error"] = f"[StreamWish] HTTP error: {exc}"

    except (ValueError, SyntaxError) as exc:
        result["error"] = f"[StreamWish] JS unpack failed: {exc}"

    except Exception as exc:
        result["error"] = f"[StreamWish] Unexpected error: {exc}"

    return result
