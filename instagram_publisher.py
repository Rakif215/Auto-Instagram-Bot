"""
instagram_publisher.py — Posts a Reel to Instagram via Meta's Resumable
Upload API. Local MP4 files are uploaded as binary — no public URL needed.
"""

import os
import time
import logging
import requests
from config import (
    PUBLISH_METHOD,
    INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, SESSION_FILE,
    IG_USER_ID, IG_ACCESS_TOKEN, GRAPH_API_VERSION,
    MAX_RETRIES, RETRY_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)
BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


# ─── Graph API — Resumable Upload ────────────────────────────────────────────

def _publish_graph_api(video_path: str, caption: str) -> str:
    """Upload a local Reel MP4 using Meta's Resumable Upload (no public URL needed)."""
    file_size = os.path.getsize(video_path)

    # Step 1: Create container + get upload URI
    logger.info("Creating Instagram Reels container (resumable upload)...")
    r = requests.post(
        f"{BASE}/{IG_USER_ID}/media",
        params={"access_token": IG_ACCESS_TOKEN},
        data={
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": caption,
        },
        timeout=30,
    )
    r.raise_for_status()
    resp = r.json()
    container_id = resp.get("id")
    upload_uri = resp.get("uri")

    if not container_id or not upload_uri:
        raise RuntimeError(f"Unexpected container response: {resp}")
    logger.info(f"Container ID: {container_id}")

    # Step 2: Upload the video binary
    logger.info(f"Uploading video ({file_size / 1024 / 1024:.1f} MB)...")
    with open(video_path, "rb") as f:
        video_bytes = f.read()

    upload_resp = requests.post(
        upload_uri,
        headers={
            "Authorization": f"OAuth {IG_ACCESS_TOKEN}",
            "offset": "0",
            "file_size": str(file_size),
        },
        data=video_bytes,
        timeout=120,
    )
    if upload_resp.status_code != 200:
        logger.error(f"Binary upload failed: {upload_resp.status_code} - {upload_resp.text}")
    upload_resp.raise_for_status()
    logger.info("Video upload complete.")

    # Step 3: Poll until FINISHED
    logger.info("Waiting for Instagram to process the video...")
    for attempt in range(30):
        time.sleep(5)
        status_r = requests.get(
            f"{BASE}/{container_id}",
            params={"fields": "status_code,status", "access_token": IG_ACCESS_TOKEN},
            timeout=15,
        )
        status_r.raise_for_status()
        data = status_r.json()
        status = data.get("status_code", data.get("status", ""))
        logger.info(f"  Container status ({attempt + 1}/30): {status}")

        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing failed: {status}")
    else:
        raise TimeoutError("Timed out waiting for Instagram to process the video.")

    # Step 4: Publish
    logger.info("Publishing Reel...")
    pub_r = requests.post(
        f"{BASE}/{IG_USER_ID}/media_publish",
        params={"access_token": IG_ACCESS_TOKEN},
        data={"creation_id": container_id},
        timeout=15,
    )
    pub_r.raise_for_status()
    post_id = pub_r.json().get("id", "unknown")
    logger.info(f"✅ Reel published! Post ID: {post_id}")
    return post_id


# ─── instagrapi Method (fallback) ────────────────────────────────────────────

def _publish_instagrapi(video_path: str, caption: str) -> str:
    from instagrapi import Client
    cl = Client()
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        except Exception:
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
    else:
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
    cl.dump_settings(SESSION_FILE)
    media = cl.clip_upload(video_path, caption)
    post_id = str(media.pk)
    logger.info(f"✅ Posted via instagrapi. Post ID: {post_id}")
    return post_id


# ─── Public Interface ─────────────────────────────────────────────────────────

def publish_reel(video_path: str, caption_data: dict) -> str:
    """Publish the reel with retries. Returns post ID on success."""
    full_caption = f"{caption_data['caption']}\n\n{caption_data['hashtags']}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if PUBLISH_METHOD == "graph_api":
                return _publish_graph_api(video_path, full_caption)
            else:
                return _publish_instagrapi(video_path, full_caption)
        except Exception as e:
            logger.error(f"Publish attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                logger.info(f"Retrying in {RETRY_DELAY_SECONDS}s...")
                time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError(f"All {MAX_RETRIES} publish attempts failed.")


def post_reel(video_path: str, caption: str) -> bool:
    """
    Convenience wrapper called directly by the dashboard's 'Post Now' button.
    Accepts a pre-formatted caption string (caption + hashtags joined).
    Returns True on success, False on failure.
    """
    try:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if PUBLISH_METHOD == "graph_api":
                    _publish_graph_api(video_path, caption)
                else:
                    _publish_instagrapi(video_path, caption)
                logger.info("post_reel: Posted successfully.")
                return True
            except Exception as e:
                logger.error(f"post_reel attempt {attempt}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_SECONDS)
        return False
    except Exception as e:
        logger.error(f"post_reel: Fatal error: {e}")
        return False
