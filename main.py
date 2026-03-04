"""
main.py — Single-run orchestrator for the Instagram Reel automation pipeline.

Usage:
  python main.py            # Full run (fetch → caption → video → post)
  python main.py --dry-run  # Skip Instagram posting, just save video locally
  python main.py --schedule # Start the scheduler daemon
"""

import sys
import logging
import os
from datetime import datetime

# ─── Logging setup ────────────────────────────────────────────────────────────
from config import LOGS_DIR, DATA_DIR

log_file = os.path.join(LOGS_DIR, f"pipeline_{datetime.utcnow().strftime('%Y%m%d')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("main")

# ─── Pipeline ─────────────────────────────────────────────────────────────────

# Define these constants if they are not already defined elsewhere in config.py or similar
# For the purpose of this edit, we'll assume they are meant to be defined globally or imported.
# If they are not defined, this will cause a NameError.
# Assuming default values for now, or that they will be imported.
USE_BACKGROUND_MUSIC = True # Placeholder, adjust as needed
USE_DYNAMIC_BACKGROUND = True # Placeholder, adjust as needed

LOCK_FILE = os.path.join(DATA_DIR, "pipeline.lock")

def run_pipeline(dry_run: bool = False, use_music: bool = None, use_dynamic: bool = None, manual_video: str = None, news_mode: str = "auto") -> tuple[bool, dict]:
    """
    Core automation pipeline: Fetch news -> AI Caption -> Gen Video -> Post.
    Returns (success_boolean, caption_data_dict) for Dashboard display.
    """
    # Use config defaults if not explicitly overridden by kwargs (e.g. from Dashboard)
    from config import USE_BACKGROUND_MUSIC, USE_DYNAMIC_BACKGROUND
    if use_music is None:
        use_music = USE_BACKGROUND_MUSIC
    if use_dynamic is None:
        use_dynamic = USE_DYNAMIC_BACKGROUND
        
    if os.path.exists(LOCK_FILE):
        import time
        # If lockfile is older than 30 minutes, assume the previous run crashed and clean it up
        if time.time() - os.path.getmtime(LOCK_FILE) > 1800:
            logger.warning("Found a stale lock file (older than 30 mins). Automatically removing it and proceeding.")
            os.remove(LOCK_FILE)
        else:
            logger.warning("Pipeline is already running (lock file exists). Skipping this run.")
            return False, None
    
    # Create lock file
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    try:
        logger.info("=" * 60)
        logger.info("Pipeline run started")
        logger.info("=" * 60)

        # 1. Fetch news
        from news_fetcher import fetch_latest, mark_headline_used
        logger.info(f"Step 1/4 — Fetching latest Al Jazeera headline (Mode: {news_mode})...")
        article = fetch_latest(mode=news_mode)
        if not article:
            logger.info("Pipeline stopped: No new articles to process.")
            return False, None

        logger.info(f"  Headline : {article['title']}")
        logger.info(f"  Source   : {article['source']}")
        logger.info(f"  Published: {article['published_at']}")

        # 2. Generate caption
        from llm_caption import generate_caption
        logger.info("Step 2/4 — Generating Instagram caption with Gemini...")
        caption_data = generate_caption(article["title"], article["source"])
        logger.info(f"  Caption  : {caption_data['caption'][:80]}...")
        logger.info(f"  Hashtags : {caption_data['hashtags']}")

        # 3. Make reel
        from video_maker import make_reel
        logger.info("Step 3/4 — Creating Reel with FFmpeg...")
        video_path = make_reel(article, caption_data, use_music=use_music, use_dynamic=use_dynamic, manual_video=manual_video)
        logger.info(f"  Output   : {video_path}")

        # 4. Publish
        if dry_run:
            logger.info("Step 4/4 — DRY RUN: Skipping Instagram posting.")
            logger.info(f"  Video saved at: {video_path}")
            logger.info(f"  Open it with: open {video_path}")
        else:
            from instagram_publisher import publish_reel
            logger.info("Step 4/4 — Publishing Reel to Instagram...")
            post_id = publish_reel(video_path, caption_data)
            logger.info(f"  Post ID  : {post_id}")

            # Mark headline as used so we don't repost it
            mark_headline_used(article["title"], article["url"])

        logger.info("Pipeline run completed successfully.")
        return True, caption_data
    finally:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
            
        # Run cleanup to prevent DigitalOcean disk space exhaustion
        logger.info("Running disk space cleanup...")
        _cleanup_old_files(days_old=3)


def _cleanup_old_files(days_old: int = 3):
    """
    Prevents DigitalOcean server from running out of disk space by deleting:
    1. Huge raw YouTube downloads in output/temp_youtube
    2. Old generated reels and overlay images
    3. Old log files
    """
    import time
    from config import OUTPUT_DIR, LOGS_DIR
    
    now = time.time()
    cutoff = now - (days_old * 86400)
    
    dirs_to_clean = [
        OUTPUT_DIR,
        os.path.join(OUTPUT_DIR, "temp_youtube"),
        LOGS_DIR
    ]
    
    deleted = 0
    for d in dirs_to_clean:
        if not os.path.exists(d):
            continue
        for f in os.listdir(d):
            file_path = os.path.join(d, f)
            if os.path.isfile(file_path):
                if os.path.getmtime(file_path) < cutoff:
                    try:
                        os.remove(file_path)
                        deleted += 1
                    except Exception:
                        pass
    if deleted > 0:
        logger.info(f"Disk Cleanup: Deleted {deleted} old files (>{days_old} days).")


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    start_scheduler = "--schedule" in sys.argv
    
    # Check for --mode argument (e.g. --mode youtube or --mode rss)
    news_mode = "auto"
    for i, arg in enumerate(sys.argv):
        if arg == "--mode" and i + 1 < len(sys.argv):
            news_mode = sys.argv[i+1]

    if start_scheduler:
        from scheduler import start
        start(dry_run=dry_run, news_mode=news_mode)
    else:
        try:
            run_pipeline(dry_run=dry_run, news_mode=news_mode)
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            sys.exit(1)
