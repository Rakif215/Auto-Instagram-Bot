"""
news_fetcher.py — Fetches latest Al Jazeera headlines directly from their
public RSS feed. No API key required — completely free.

RSS Feed: https://www.aljazeera.com/xml/rss/all.xml
"""

import sqlite3
import logging
import feedparser
from datetime import datetime
from config import NEWS_MAX_ARTICLES, DB_PATH

logger = logging.getLogger(__name__)

AJ_RSS_URL = "https://www.aljazeera.com/xml/rss/all.xml"

# ─── Database Setup ───────────────────────────────────────────────────────────

def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS used_headlines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE NOT NULL,
            url TEXT,
            posted_at TEXT
        )
    """)
    conn.commit()
    return conn


def _is_used(conn, title: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM used_headlines WHERE title = ?", (title,)
    ).fetchone()
    return row is not None


def _mark_used(conn, title: str, url: str):
    conn.execute(
        "INSERT OR IGNORE INTO used_headlines (title, url, posted_at) VALUES (?, ?, ?)",
        (title, url, datetime.utcnow().isoformat())
    )
    conn.commit()


# ─── YouTube-First Fetcher ───────────────────────────────────────────────────

def fetch_latest_youtube() -> dict | None:
    """
    Fetches the latest unused video from Al Jazeera's English YouTube channel.
    The video title becomes the official headline, guaranteeing 100% video availability.
    Returns a dict {title, url, source, published_at} or None.
    """
    import yt_dlp
    logger.info("Fetching latest Al Jazeera YouTube videos as primary news source...")

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'playlistend': 15, # Check latest 15 videos
    }
    
    channel_url = "https://www.youtube.com/@aljazeeraenglish/videos"
    
    conn = _get_db()
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            if not info or 'entries' not in info:
                logger.warning("No videos found on Al Jazeera channel.")
                return None
                
            from llm_caption import is_relevant_news
            
            for entry in info['entries']:
                if not entry:
                    continue
                    
                title = entry.get('title', '').strip()
                if not title:
                    continue
                    
                if not _is_used(conn, title):
                    # Clean up common prefixes
                    import re
                    clean_title = re.sub(r'^(Video|Photos?|Watch|Listen|WATCH|LISTEN|PHOTOS?):\s*', '', title, flags=re.IGNORECASE).strip()
                    
                    if is_relevant_news(clean_title):
                        logger.info(f"New relevant YouTube story found: {clean_title}")
                        video_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                        return {
                            "title": clean_title,
                            "url": video_url,     # The YouTube URL itself!
                            "source": "Al Jazeera",
                            "published_at": datetime.utcnow().isoformat(),
                            "is_video_url": True  # Flag so youtube_fetcher.py knows it doesn't need to search
                        }
                    else:
                        logger.info(f"Skipping irrelevant video (AI filter): {title}")
                        _mark_used(conn, title, entry.get('url', ''))
            
        logger.info("All recent YouTube videos have been processed or skipped.")
        return None
        
    except Exception as e:
        logger.error(f"Failed to fetch from YouTube: {e}")
        return None
    finally:
        conn.close()


def fetch_latest_rss() -> dict | None:
    """
    Fetches the latest unused headline from Al Jazeera's RSS feed (Fallback mode).
    This mode pairs the text headline with a randomized video from the local collection.
    """
    logger.info(f"Fetching Al Jazeera RSS: {AJ_RSS_URL}")
    feed = feedparser.parse(AJ_RSS_URL)
    
    conn = _get_db()
    try:
        from llm_caption import is_relevant_news
        
        for entry in feed.entries[:NEWS_MAX_ARTICLES]:
            title = entry.title.strip()
            url = entry.link
            
            if not _is_used(conn, title):
                # Clean up typical prefixes
                import re
                clean_title = re.sub(r'^(Video|Photos?|Watch|Listen|WATCH|LISTEN|PHOTOS?):\s*', '', title, flags=re.IGNORECASE).strip()
                
                if is_relevant_news(clean_title):
                    logger.info(f"New relevant RSS story found: {clean_title}")
                    return {
                        "title": clean_title,
                        "url": url,
                        "source": "Al Jazeera",
                        "published_at": entry.get('published', datetime.utcnow().isoformat()),
                        "is_video_url": False # Needs local/pexels video matching
                    }
                else:
                    logger.info(f"Skipping irrelevant RSS story: {title}")
                    _mark_used(conn, title, url)
                    
        return None
    except Exception as e:
        logger.error(f"Failed to fetch from RSS: {e}")
        return None
    finally:
        conn.close()


def get_auto_mode() -> str:
    """Returns 'youtube' for 2 posts, then 'rss' for 1 post, based on DB post count."""
    conn = _get_db()
    try:
        count = conn.execute("SELECT count(*) FROM used_headlines").fetchone()[0]
        # 0, 1 -> youtube, 2 -> rss, 3, 4 -> youtube, 5 -> rss, etc.
        if count % 3 == 2:
            return "rss"
        return "youtube"
    finally:
        conn.close()


def fetch_latest(mode: str = "auto") -> dict | None:
    """
    Master fetch function.
    mode can be: "auto", "youtube", "rss"
    """
    if mode == "auto":
        assigned_mode = get_auto_mode()
        logger.info(f"Auto-mode selected: {assigned_mode.upper()}")
    else:
        assigned_mode = mode
        logger.info(f"Manual mode forced: {assigned_mode.upper()}")
        
    if assigned_mode == "youtube":
        return fetch_latest_youtube()
    elif assigned_mode == "rss":
        return fetch_latest_rss()
    else:
        logger.error(f"Unknown mode: {assigned_mode}")
        return None


def mark_headline_used(title: str, url: str):
    """Call this after a successful post to prevent reposting."""
    conn = _get_db()
    try:
        _mark_used(conn, title, url)
        logger.info(f"Marked headline as used: {title[:60]}...")
    finally:
        conn.close()
