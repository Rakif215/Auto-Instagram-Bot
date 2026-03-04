"""
video_maker.py — Creates a vertical 1080x1920 Instagram Reel.
Uses Pillow to render text overlay as PNG, then FFmpeg to composite it.
(FFmpeg drawtext requires libfreetype which may not be available.)
"""

import os
import random
import subprocess
import json
import logging
import glob
import textwrap
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from config import (
    VIDEOS_DIR, OUTPUT_DIR, MUSIC_DIR, DATA_DIR,
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_MIN_DURATION, VIDEO_MAX_DURATION,
    PEXELS_API_KEY, USE_DYNAMIC_BACKGROUND, USE_BACKGROUND_MUSIC,
    FFMPEG_PATH, FFPROBE_PATH
)

logger = logging.getLogger(__name__)

# ─── Font resolution ──────────────────────────────────────────────────────────
# Clean fonts for small text
CLEAN_FONTS = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
]
# Serif fonts for headline
SERIF_FONTS = [
    "/Library/Fonts/Georgia.ttf",
    "/Library/Fonts/Times New Roman.ttf",
    "/System/Library/Fonts/Times.ttc",
    "/System/Library/Fonts/Charter.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"
]

def _get_font(size: int, serif: bool = False) -> ImageFont.FreeTypeFont:
    candidates = SERIF_FONTS if serif else CLEAN_FONTS
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _check_ffmpeg():
    result = subprocess.run([FFMPEG_PATH, "-version"], capture_output=True)
    if result.returncode != 0:
        raise EnvironmentError(f"{FFMPEG_PATH} failed. Install with: brew install ffmpeg")


def _fetch_pexels_video(query: str) -> str:
    """
    Searches Pexels for a vertical video based on the query, downloads it to OUTPUT_DIR,
    and returns the local file path. Returns None if it fails.
    """
    if not PEXELS_API_KEY:
        logger.warning("Pexels API Key is missing.")
        return None

    try:
        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": PEXELS_API_KEY}
        params = {
            "query": query,
            "orientation": "portrait",
            "size": "large",
            "per_page": 10
        }
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        
        videos = data.get("videos", [])
        if not videos:
            logger.info(f"No vertical Pexels videos found for '{query}'.")
            return None

        # Pick a random video from top results
        chosen_video = random.choice(videos[:5])
        video_files = chosen_video.get("video_files", [])
        
        # Prefer HD vertical files
        hd_files = [f for f in video_files if f.get("quality") == "hd" and f.get("height", 0) >= f.get("width", 0)]
        if hd_files:
            video_url = hd_files[0]["link"]
        elif video_files:
            video_url = video_files[0]["link"]
        else:
            return None

        # Download the video temporarily
        temp_video_path = os.path.join(OUTPUT_DIR, f"temp_pexels_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.mp4")
        logger.info(f"Downloading Pexels video for '{query}': {video_url}")
        
        with requests.get(video_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(temp_video_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
        return temp_video_path
        
    except Exception as e:
        logger.error(f"Failed to fetch Pexels video: {e}")
        return None


def _get_used_videos() -> list:
    """Load the list of used local videos from a JSON file."""
    path = os.path.join(DATA_DIR, "used_videos.json")
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_used_videos(used_list: list):
    """Save the list of used local videos to a JSON file."""
    path = os.path.join(DATA_DIR, "used_videos.json")
    with open(path, "w") as f:
        json.dump(used_list, f)

def _extract_random_clip(input_video: str, duration: int = 15) -> str:
    """Takes a potentially long YouTube video and extracts a random 'duration' second clip from it."""
    # First get the total duration of the video
    try:
        cmd_duration = [
            FFPROBE_PATH, "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_video
        ]
        result = subprocess.run(cmd_duration, capture_output=True, text=True, check=True)
        total_duration = float(result.stdout.strip())
        
        if total_duration <= duration:
            # Video is already shorter than 15s, just return it
            return input_video
            
        # Pick a random start time, leaving enough room for the clip duration
        max_start = max(0, total_duration - duration)
        
        # Don't pick a completely random time deep in the video, because that's usually an interview or a news anchor talking.
        # The actual "action/raw footage" hook is almost always shown in the first 0-15 seconds of a news clip.
        start_time = random.uniform(0.0, min(10.0, max_start))
        
        output_clip = os.path.join(OUTPUT_DIR, f"yt_clip_{random.randint(1000,9999)}.mp4")
        
        cmd_clip = [
            FFMPEG_PATH, "-y",
            "-ss", str(start_time),
            "-i", input_video,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            output_clip
        ]
        
        logger.info(f"Extracting {duration}s clip starting at {start_time:.1f}s from YouTube footage...")
        subprocess.run(cmd_clip, capture_output=True, check=True)
        return output_clip
        
    except Exception as e:
        logger.error(f"Failed to extract sub-clip from YouTube video: {e}")
        return input_video # return original if clipping fails


def _pick_random_video(query: str = "", headline: str = "", direct_url: str = "") -> str:
    # Attempt YouTube fetching first if query or direct_url is provided
    if direct_url or query:
        logger.info(f"Attempting to fetch dynamic YouTube background for '{headline or query}'...")
        from youtube_fetcher import download_youtube_clip
        
        # If we have a direct URL from the fetcher, use it! Otherwise fallback to text search (if ever used)
        if direct_url:
             yt_vid = download_youtube_clip(video_url=direct_url)
        else:
             # Legacy text search fallback if needed
             yt_vid = download_youtube_clip(query=query)
        
        if yt_vid and os.path.exists(yt_vid):
            logger.info(f"Downloaded dynamic YouTube video: {yt_vid}")
            clipped_vid = _extract_random_clip(yt_vid, duration=15)
            if clipped_vid:
                 return clipped_vid
            
        logger.warning(f"YouTube fetch failed. Attempting Pexels fallback...")
        
        # Fallback to Pexels API
        pexels_vid = _fetch_pexels_video(query)
        if pexels_vid and os.path.exists(pexels_vid):
            logger.info(f"Using dynamic Pexels video: {pexels_vid}")
            return pexels_vid

    # Fallback to local videos with Fair Rotation
    logger.info("Selecting local pre-made video (Fair Rotation)...")
    all_videos = [v for v in glob.glob(os.path.join(VIDEOS_DIR, "*.mp4")) if "test_bg" not in v]
    if not all_videos:
        all_videos = glob.glob(os.path.join(VIDEOS_DIR, "*.mp4"))
    if not all_videos:
        raise FileNotFoundError(f"No .mp4 files found in '{VIDEOS_DIR}/'.")
    
    used_videos = _get_used_videos()
    available_videos = [v for v in all_videos if os.path.basename(v) not in used_videos]
    
    # If all videos used, reset the tracker
    if not available_videos:
        logger.info("All local videos used once. Resetting Fair Rotation tracker.")
        used_videos = []
        available_videos = all_videos
        _save_used_videos([])

    chosen_video = random.choice(available_videos)
    
    # Mark as used and save
    used_videos.append(os.path.basename(chosen_video))
    _save_used_videos(used_videos)
    
    logger.info(f"Selected video: {os.path.basename(chosen_video)} ({len(used_videos)}/{len(all_videos)} in current rotation)")
    return chosen_video


def _pick_random_music() -> str:
    """Returns a random audio file from the MUSIC_DIR, or None if empty."""
    if not os.path.exists(MUSIC_DIR):
        return None
    tracks = glob.glob(os.path.join(MUSIC_DIR, "*.mp3")) + glob.glob(os.path.join(MUSIC_DIR, "*.wav"))
    if not tracks:
        return None
    chosen = random.choice(tracks)
    logger.info(f"Selected background music: {os.path.basename(chosen)}")
    return chosen


def _get_video_duration(video_path: str) -> float:
    result = subprocess.run(
        [FFPROBE_PATH, "-v", "quiet", "-print_format", "json", "-show_format", video_path],
        capture_output=True, text=True
    )
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


# ─── Text Overlay PNG (via Pillow) ────────────────────────────────────────────

def _make_overlay_png(headline: str, source: str, date_str: str, out_path: str):
    """
    Renders the text overlay as a transparent RGBA PNG at 1080x1920.
    Layers:
      - Top-left: logo + "trending_hubx"
      - Top-right: "VIA [source name]" badge
      - Bottom bar: Date, Headline, Social handles
    """
    W, H = VIDEO_WIDTH, VIDEO_HEIGHT
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)) # FFmpeg will pad video with black, so background can remain transparent
    draw = ImageDraw.Draw(img)

    # Padding
    PAD_X = 60
    PAD_Y = 80

    # ── Top-left: Logo + trending_hubx ──
    clean_small = _get_font(36, serif=False)
    # Placeholder logo: a 40x40 circle
    logo_size = 40
    logo_x, logo_y = PAD_X, PAD_Y
    draw.ellipse([logo_x, logo_y, logo_x + logo_size, logo_y + logo_size], fill="white")
    
    brand_text = "trending_hubx"
    # Vertically center text with the logo
    draw.text((logo_x + logo_size + 15, logo_y - 2), brand_text, font=clean_small, fill="white")

    # ── Top-right: Source badge ──
    source_text = f"VIA {source.upper()}"
    bbox = draw.textbbox((0, 0), source_text, font=clean_small)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    badge_px = 20 # horizontal padding within pill
    badge_py = 10 # vertical padding within pill
    badge_w = text_w + badge_px * 2
    badge_h = text_h + badge_py * 2 + 10 # manual adjustment for visual center
    
    badge_x = W - PAD_X - badge_w
    badge_y = PAD_Y - 5
    draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], radius=15, fill="#1c1c1c")
    draw.text((badge_x + badge_px, badge_y + badge_py), source_text, font=clean_small, fill="white")

    # ── Top area text ──
    # The logo and badge end around Y=120. We can start text around Y=200 
    # so it sits in the top black bar above the video.
    top_start_y = 200
    
    # Date
    date_font = _get_font(40, serif=False)
    # #7B2FBE is Purple/Violet
    draw.text((PAD_X, top_start_y), date_str, font=date_font, fill="#7B2FBE")

    # Headline
    # Allow up to 5 lines, large bold white serif
    # If headline is very long, we drop the font size a bit
    font_size = 76
    if len(headline) > 80:
        font_size = 64
    
    headline_font = _get_font(font_size, serif=True)
    wrapped = textwrap.fill(headline, width=24 if font_size == 76 else 28)
    
    # Enforce max 5 lines visually to be safe
    lines = wrapped.split("\n")[:5]
    
    headline_y = top_start_y + 60
    line_spacing = 10
    current_y = headline_y
    for line in lines:
        draw.text((PAD_X, current_y), line, font=headline_font, fill="white")
        bbox = draw.textbbox((0, 0), line, font=headline_font)
        # Use a consistent height increment based on font size + spacing
        current_y += (font_size + line_spacing)

    # ── Bottom area text: Social handles ──
    # The video height is approx 608px centered. So video ends at Y=1264. 
    # Center the text in the bottom black bar roughly around Y=1580.
    social_y = 1580
    social_text = "f © trending_hubx  |  ▶ X trending_hubx"
    social_font = _get_font(32, serif=False)
    
    # Calculate center X position
    social_bbox = draw.textbbox((0, 0), social_text, font=social_font)
    social_w = social_bbox[2] - social_bbox[0]
    social_x = (W - social_w) // 2
    
    draw.text((social_x, social_y), social_text, font=social_font, fill="#CCCCCC")

    img.save(out_path, "PNG")
    logger.info(f"Text overlay PNG saved: {out_path}")


# ─── Main builder ─────────────────────────────────────────────────────────────

def make_reel(article: dict, caption_data: dict, use_music: bool = None, use_dynamic: bool = None, manual_video: str = None) -> str:
    """
    Creates the final Reel: trims video + composites text overlay with FFmpeg.
    Returns path to output MP4.
    """
    _check_ffmpeg()

    # Use arguments if provided, otherwise fallback to config defaults
    actual_use_music = use_music if use_music is not None else USE_BACKGROUND_MUSIC
    actual_use_dynamic = use_dynamic if use_dynamic is not None else USE_DYNAMIC_BACKGROUND

    search_query = caption_data.get("search_query", "")
    
    # Priority: 1. Manual Video, 2. Dynamic (YouTube -> Pexels), 3. Random Local
    if manual_video and os.path.exists(manual_video):
        logger.info(f"Using manually selected background video: {manual_video}")
        video_path = manual_video
    else:
        # _pick_random_video handles dynamic searching if enabled, else defaults to local fair rotation
        # If the fetcher provided a direct YouTube URL (YouTube-First logic), use that instead of searching
        headline = article.get("title", "") if article else ""
        video_url = article.get("url", "") if article and article.get("is_video_url") else ""
        
        if actual_use_dynamic:
            video_path = _pick_random_video(query=search_query, headline=headline, direct_url=video_url)
        else:
            video_path = _pick_random_video()
    
    is_temp_pexels = "temp_pexels" in video_path

    video_duration = _get_video_duration(video_path)

    clip_duration = random.randint(VIDEO_MIN_DURATION, VIDEO_MAX_DURATION)
    if clip_duration > video_duration:
        clip_duration = int(video_duration)

    max_start = max(0, video_duration - clip_duration)
    start_time = random.uniform(0, max_start)

    headline = article.get("title", "Breaking News")
    source = article.get("source", "Source")
    # Format date strictly as 03•03•2026
    date_str = datetime.utcnow().strftime("%m•%d•%Y")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    overlay_path = os.path.join(OUTPUT_DIR, f"overlay_{timestamp}.png")
    output_path = os.path.join(OUTPUT_DIR, f"reel_{timestamp}.mp4")

    # Create text overlay PNG
    _make_overlay_png(headline, source, date_str, overlay_path)

    music_path = None
    if actual_use_music:
        music_path = _pick_random_music()

    cmd = [
        FFMPEG_PATH, "-y",
        "-ss", str(start_time),
        "-i", video_path,
        "-i", overlay_path
    ]

    # Add music input if enabled and found
    if music_path:
        # We start the music at a random offset to not always hear the same intro
        # For simplicity we just start at 0 or a fixed offset, let's start at 0.
        cmd.extend(["-i", music_path])

    cmd.extend(["-t", str(clip_duration)])
    # Video filter:
    # Scale to a taller frame first (608+125=733px), then crop the top 608px cleanly.
    # This discards the bottom 125px (where the Al Jazeera ticker lives) while keeping
    # the video at the full 608px target height — no black bars, no stretching.
    cmd.extend([
        "-filter_complex",
        (
            f"[0:v]scale={VIDEO_WIDTH}:733:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={VIDEO_WIDTH}:608:0:0[vid];"
            f"[vid]pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black[bg];"
            f"[bg][1:v]overlay=0:0[outv]"
        )
    ])

    cmd.extend([
        "-map", "[outv]"
    ])

    # Audio mapping
    if music_path:
        # Use music track only — drop the original YouTube video audio entirely
        cmd.extend([
            "-af", f"afade=t=out:st={max(0, clip_duration - 1.5)}:d=1.5",
            "-map", "2:a",   # Music is input[2]
        ])
    else:
        # Original audio from the video (pass-through)
        cmd.extend(["-map", "0:a?"])

    # Encoding specs (High Quality)
    cmd.extend([
        "-c:v", "libx264",
        "-preset", "medium",  # Slower preset for better quality/size balance
        "-crf", "18",         # Visually lossless
        "-c:a", "aac",
        "-b:a", "192k",       # Higher audio bitrate
        "-shortest",
        "-movflags", "+faststart",
        output_path
    ])

    logger.info(f"Running FFmpeg to generate reel: {output_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Clean up temporary files
    try:
        os.remove(overlay_path)
        if is_temp_pexels:
            os.remove(video_path)
    except Exception:
        pass

    if result.returncode != 0:
        logger.error(f"FFmpeg stderr:\n{result.stderr[-1500:]}")
        raise RuntimeError("FFmpeg failed. Check logs for details.")

    logger.info(f"Reel created: {output_path}")
    return output_path
