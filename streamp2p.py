"""
streamp2p.py
Extracts HLS streaming URL from RpmShare / UpnShare / StreamP2P / RpmHub
Uses AES-CBC decryption on the /api/v1/video endpoint.
"""

import json
import requests
from urllib.parse import urlparse
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

TAG = "rpmhub"

# AES-CBC credentials (embedded in the player)
_AES_KEY = b"kiemtienmua911ca"
_AES_IV  = b"1234567890oiuytr"

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 10; K) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Mobile Safari/537.36"
)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _decrypt_video_data(hex_payload: str) -> dict:
    """AES-CBC decrypt the hex-encoded API response."""
    cipher    = AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV)
    encrypted = bytes.fromhex(hex_payload)
    decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
    return json.loads(decrypted.decode("utf-8"))


# ─────────────────────────────────────────────
# PUBLIC
# ─────────────────────────────────────────────

def real_extract(url: str, request=None) -> dict:
    """
    Extract HLS streaming URL from an RpmHub / StreamP2P embed.

    URL format:  https://<domain>/#<video_id>
    or           https://<domain>/v/<video_id>

    Returns:
        {
            "status":        "success" | "error",
            "status_code":   200 | 4xx,
            "error":         None | str,
            "tag":           "rpmhub",
            "headers":       dict,
            "streaming_url": str | None,
            "subtitles":     list | None,   # optional
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
        parsed   = urlparse(url)
        domain   = f"{parsed.scheme}://{parsed.netloc}"
        video_id = parsed.fragment or parsed.path.rstrip("/").split("/")[-1]

        if not video_id:
            result["error"] = "[StreamP2P] Could not extract video ID from URL"
            return result

        headers = {
            "Referer":    domain + "/",
            "User-Agent": USER_AGENT,
        }

        # Warm-up request (sets cookies / session)
        requests.get(url, headers=headers, timeout=20)

        # Fetch encrypted payload
        api_url  = f"{domain}/api/v1/video?id={video_id}"
        api_resp = requests.get(api_url, headers=headers, timeout=20)
        api_resp.raise_for_status()

        data = _decrypt_video_data(api_resp.text.strip())

        streaming_url = data.get("cf")
        if not streaming_url:
            result["error"] = "[StreamP2P] 'cf' key missing in decrypted data"
            return result

        result["status"]        = "success"
        result["status_code"]   = 200
        result["headers"]       = headers
        result["streaming_url"] = streaming_url

        if data.get("subtitle"):
            result["subtitles"] = data["subtitle"]

    except requests.exceptions.Timeout:
        result["error"] = "[StreamP2P] Request timed out"

    except requests.exceptions.RequestException as exc:
        result["error"] = f"[StreamP2P] HTTP error: {exc}"

    except ValueError as exc:
        result["error"] = f"[StreamP2P] Hex decode / JSON parse failed: {exc}"

    except Exception as exc:
        result["error"] = f"[StreamP2P] Unexpected error: {exc}"

    return result
