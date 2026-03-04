"""
config.py — Central configuration for the Instagram automation pipeline.
All settings are loaded from environment variables via .env
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── News ────────────────────────────────────────────────────────────────────
# Al Jazeera RSS — no API key needed
NEWS_MAX_ARTICLES = 5  # how many headlines to check per run

# ─── LLM ─────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")       # Primary LLM (free)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")   # Fallback LLM
GEMINI_MODEL = "gemini-2.0-flash"

# ─── Features ────────────────────────────────────────────────────────────────
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
USE_DYNAMIC_BACKGROUND = os.getenv("USE_DYNAMIC_BACKGROUND", "False").lower() == "true"
USE_BACKGROUND_MUSIC = os.getenv("USE_BACKGROUND_MUSIC", "False").lower() == "true"

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR = os.path.join(BASE_DIR, "videos")        # pre-made Veo clips go here
OUTPUT_DIR = os.path.join(BASE_DIR, "output")        # generated reels
LOGS_DIR = os.path.join(BASE_DIR, "logs")
DATA_DIR = os.path.join(BASE_DIR, "data")
MUSIC_DIR = os.path.join(BASE_DIR, "music")           # background audio tracks go here
DB_PATH = os.path.join(DATA_DIR, "used_headlines.db")

# Auto-create directories
for d in (VIDEOS_DIR, OUTPUT_DIR, LOGS_DIR, DATA_DIR, MUSIC_DIR):
    os.makedirs(d, exist_ok=True)

# ─── Video ───────────────────────────────────────────────────────────────────
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
FFPROBE_PATH = os.getenv("FFPROBE_PATH", "ffprobe")
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_MIN_DURATION = 8   # seconds
VIDEO_MAX_DURATION = 12  # seconds

# Text overlay settings (for FFmpeg drawtext filter)
HEADLINE_FONT_SIZE = 72
HEADLINE_FONT_COLOR = "white"
HEADLINE_SHADOW_COLOR = "black"
HEADLINE_SHADOW_OFFSET = 3
HEADLINE_BOX_COLOR = "0x00000088"  # semi-transparent black (RRGGBBAA hex)
HEADLINE_BOX_BORDER = 20

SOURCE_FONT_SIZE = 36
SOURCE_FONT_COLOR = "white"
SOURCE_BOX_COLOR = "0x00000099"

# ─── Instagram ───────────────────────────────────────────────────────────────
PUBLISH_METHOD = os.getenv("INSTAGRAM_PUBLISH_METHOD", "instagrapi")  # or "graph_api"

# instagrapi
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")
SESSION_FILE = os.path.join(DATA_DIR, "ig_session.json")

# Graph API
IG_USER_ID = os.getenv("IG_USER_ID", "")
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")
GRAPH_API_VERSION = "v21.0"

# ─── Scheduler ───────────────────────────────────────────────────────────────
POST_INTERVAL_HOURS = int(os.getenv("POST_INTERVAL_HOURS", "6"))
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 30
