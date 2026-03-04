# 📈 Trending HubX Video Automation

A fully automated, AI-powered system designed to fetch breaking news from Al Jazeera (via YouTube and RSS), generate insightful captions using Google's Gemini/Groq LLMs, stitch together a professional vertical video (Reel) complete with dynamic background footage and music, and publish it directly to Instagram unconditionally on a recurring schedule.

## ✨ Features

- **Hybrid News Fetcher:** Auto-rotates between downloading the exact Al Jazeera YouTube broadcast and mapping RSS headlines to beautiful, local stock footage.
- **AI-Generated Captions:** Leverages Gemini/Groq to parse the raw news text, extract key facts without hallucination, and write engaging Instagram captions and hashtags.
- **Automated Video Editing:** Uses `FFmpeg` to stack videos, add text overlays, handle audio mixing (reducing video audio volume when music plays), and enforce a rigid 1080x1920 Instagram Reel aspect ratio.
- **Background Music Support:** Seamlessly maps and randomly selects background audio from a local `/music/` directory.
- **Custom Web Dashboard:** Includes a user-friendly Streamlit dashboard (`dashboard.py`) for live monitoring, manual generation, and dry-run previewing.
- **24/7 PM2 Scheduling:** Runs as a headless daemon on cloud infrastructure (DigitalOcean) via `APScheduler`, pushing videos every 6 hours automatically.

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.12+**
- **FFmpeg** (Must be installed on the system path or specified in `.env`)
- **Node.js & PM2** (For permanent background processing on servers)

### Installation
1. Clone this repository to your local machine or cloud server.
2. Initialize a virtual environment and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
3. Copy the `.env.example` file to `.env` and fill in your Instagram credentials, API keys (Gemini, Groq, Pexels), and settings.

### Running Locally
To test the pipeline out or use the visual interface:
```bash
# Launch the web dashboard (accessible at localhost:8501)
streamlit run dashboard.py

# Or run a single local test via terminal (no posting to Instagram)
python main.py --dry-run
```

### Production Deployment (PM2)
The script uses `APScheduler` to run a post every 6 hours (configurable via `POST_INTERVAL_HOURS` in `.env`). To run this permanently on a server like DigitalOcean:
```bash
# Start the automation bot
pm2 start 'venv/bin/python main.py --schedule' --name 'hubx-bot'

# Start the public dashboard
pm2 start 'venv/bin/python -m streamlit run dashboard.py --server.port 8501' --name 'hubx-dash'

pm2 save
```

## 🗂️ Project Structure

- `main.py` - The central orchestrator (ties fetching, captioning, video gen, and posting together). Includes automatic disk cleanup.
- `dashboard.py` - The frontend Streamlit UI.
- `scheduler.py` - Background daemon runner using APScheduler.
- `news_fetcher.py` - Scrapes Al Jazeera via YouTube playlists and RSS xml.
- `llm_caption.py` - Connects to Groq/Gemini to write the caption.
- `video_maker.py` - The heavy lifter handling local videos, dynamic downloads, and all FFmpeg video/audio rendering.
- `instagram_publisher.py` - Connects to Meta Graph API for seamless Reel uploads.
- `config.py` - Global constants and environment variable loading. 

## 🛡️ Best Practices & Maintenance
- **Rate Limits:** To avoid Instagram action-blocks, avoid posting more than 4 times a day.
- **Disk Space:** In cloud environments, raw video files fill up drives quickly. `main.py` handles auto-deletion of old temporary processing files, but always monitor overall disk space.
- **Used Articles:** The system remembers what it has posted in `data/used_headlines.db`. Do not delete this file unless you want the bot to repeat old news.
