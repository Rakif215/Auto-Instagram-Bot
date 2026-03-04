import logging
import sys
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

from video_maker import make_reel

article = {
    "title": "Breaking: AI Models Gain New Reasoning Capabilities",
    "source": "Tech Daily"
}

caption_data = {
    "caption": "Testing the reel generation natively.",
    "hashtags": "#test",
    "search_query": "technology"
}

try:
    path = make_reel(article, caption_data)
    print(f"Success! Output at: {path}")
except Exception as e:
    print(f"Error: {e}")
