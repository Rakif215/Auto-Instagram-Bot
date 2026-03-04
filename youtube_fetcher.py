import os
import re
import glob
import logging
import yt_dlp
from config import OUTPUT_DIR

logger = logging.getLogger(__name__)

# Temporary directory to store downloaded clips before processing
TEMP_YT_DIR = os.path.join(OUTPUT_DIR, "temp_youtube")
os.makedirs(TEMP_YT_DIR, exist_ok=True)

# Official Al Jazeera English YouTube channel - scan latest videos for direct matching
AJ_CHANNEL_LATEST_URL = "https://www.youtube.com/@aljazeeraenglish/videos"
# AJ Shorts lives under the same channel, just /shorts
AJ_SHORTS_LATEST_URL = "https://www.youtube.com/@aljazeeraenglish/shorts"


def download_youtube_clip(video_url: str) -> str:
    """
    Downloads the specific YouTube video URL provided.
    Returns the local file path to the mp4, or None if download fails.
    """
    logger.info(f"youtube_fetcher — Downloading exact URL: {video_url}")

    ydl_download_opts = {
        'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(TEMP_YT_DIR, 'yt_%(id)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        # Bypass YouTube Bot Defense / Sign-in requirements on cloud IPs
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
    }

    try:
        with yt_dlp.YoutubeDL(ydl_download_opts) as ydl:
            download_info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(download_info)

            if os.path.exists(filename):
                logger.info(f"Successfully downloaded: {filename}")
                return filename

            # Fallback: newest file in temp dir
            files = glob.glob(os.path.join(TEMP_YT_DIR, "yt_*"))
            if files:
                newest = max(files, key=os.path.getctime)
                logger.info(f"Found via glob fallback: {newest}")
                return newest

    except Exception as e:
        logger.error(f"Download failed: {e}")

    return None


def cleanup_temp_youtube():
    """Removes all files in the temp youtube directory"""
    try:
        files = glob.glob(os.path.join(TEMP_YT_DIR, "*"))
        for f in files:
            os.remove(f)
        logger.info("Cleaned up temp_youtube directory.")
    except Exception as e:
        logger.error(f"Failed to cleanup temp_youtube: {e}")
