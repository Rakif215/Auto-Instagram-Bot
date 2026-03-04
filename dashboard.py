import streamlit as st
import os
import glob
import logging
import subprocess
from datetime import datetime
from PIL import Image
from main import run_pipeline
from config import OUTPUT_DIR, LOGS_DIR, VIDEOS_DIR

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Trending HubX Center",
    page_icon="🎬",
    layout="wide",
)

# ─── Custom CSS for Premium Look ──────────────────────────────────────────────
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #7B2FBE;
        color: white;
        font-weight: bold;
        border: none;
    }
    .stButton>button:hover {
        background-color: #9b4de3;
        color: white;
    }
    .reportview-container .main .block-container {
        padding-top: 2rem;
    }
    h1, h2, h3 {
        color: #ffffff;
    }
    .stVideo {
        border-radius: 15px;
        overflow: hidden;
        border: 1px solid #30363d;
    }
    .log-container {
        background-color: #161b22;
        color: #d1d5db;
        padding: 15px;
        border-radius: 8px;
        font-family: 'Courier New', Courier, monospace;
        font-size: 14px;
        height: 300px;
        overflow-y: scroll;
        border: 1px solid #30363d;
    }
    </style>
""", unsafe_allow_html=True)

# ─── Sidebar: Controls & Stats ────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/flat-round/512/play--v1.png", width=100)
    st.title("HubX Controls")
    
    st.markdown("---")
    
    # Toggles for features
    st.subheader("🛠️ Run Settings")
    news_mode_option = st.selectbox("📰 News Source Mode", options=[
        "Auto-Rotate (2 YouTube, 1 RSS)",
        "Force YouTube-First (Exact Video)",
        "Force RSS-First (Local Videos)"
    ])
    
    # Map the dropdown to the exact backend enum string
    if "Auto-Rotate" in news_mode_option:
        news_mode = "auto"
    elif "YouTube" in news_mode_option:
        news_mode = "youtube"
    else:
        news_mode = "rss"
        
    use_music_toggle = st.checkbox("🎵 Background Music (from /music folder)", value=True)
    use_original_audio = st.checkbox("🔊 Use Original Video Audio", value=False,
                                     help="When checked, uses the YouTube video's own audio instead of the music tracks.")
    use_dynamic_toggle = st.checkbox("🔮 Dynamic Background", value=True)

    # Video Selection
    available_videos = sorted([os.path.basename(v) for v in glob.glob(os.path.join(VIDEOS_DIR, "*.mp4"))])
    if available_videos:
        video_options = ["Randomly Picked"] + available_videos
        selected_video_name = st.selectbox("📹 Background Video", options=video_options)
        selected_video_path = None if selected_video_name == "Randomly Picked" else os.path.join(VIDEOS_DIR, selected_video_name)
    else:
        st.error("No videos found in videos/ folder!")
        selected_video_path = None

    st.markdown("---")

    # Manual Trigger
    if st.button("🚀 Run Pipeline Now"):
        with st.status("Running pipeline...", expanded=True) as status:
            st.write("Fetching news...")
            # If original audio is selected, disable music
            effective_music = use_music_toggle and not use_original_audio
            success, caption_data = run_pipeline(
                dry_run=False, 
                use_music=effective_music, 
                use_dynamic=use_dynamic_toggle,
                manual_video=selected_video_path,
                news_mode=news_mode
            )
            if success and caption_data:
                status.update(label="Reel Published Successfully!", state="complete", expanded=False)
                st.balloons()
                st.success("### Generated Caption & Metadata\n"
                           f"**Caption:**\n\n{caption_data['caption']}\n\n"
                           f"**Hashtags:** {caption_data['hashtags']}")
            else:
                status.update(label="Pipeline Failed or No New News.", state="error")

    if st.button("🧪 Dry Run (No Post)"):
        with st.status("Generating Preview Reel...", expanded=True) as status:
            effective_music = use_music_toggle and not use_original_audio
            success, caption_data = run_pipeline(
                dry_run=True, 
                use_music=effective_music, 
                use_dynamic=use_dynamic_toggle,
                manual_video=selected_video_path,
                news_mode=news_mode
            )
            if success and caption_data:
                status.update(label="Preview Ready!", state="complete", expanded=False)
                st.info("### Dry Run Results (Not Posted to Instagram)\n"
                        f"**Caption:**\n\n{caption_data['caption']}\n\n"
                        f"**Hashtags:** {caption_data['hashtags']}")
                # Store the output path in session_state so we can offer to post it
                import glob as _glob
                recent = sorted(_glob.glob(os.path.join(OUTPUT_DIR, "reel_*.mp4")), key=os.path.getmtime, reverse=True)
                if recent:
                    st.session_state["last_dry_run"] = {
                        "path": recent[0],
                        "caption": caption_data["caption"],
                        "hashtags": caption_data["hashtags"],
                    }
            else:
                status.update(label="Dry Run Failed or No New News.", state="error")

    # If a dry-run result is available, show a "Post Now" button
    if "last_dry_run" in st.session_state:
        dry = st.session_state["last_dry_run"]
        st.markdown("---")
        st.success(f"✅ Dry run ready: `{os.path.basename(dry['path'])}`")
        if st.button("📤 Post This Reel to Instagram"):
            from instagram_publisher import post_reel
            with st.spinner("Posting to Instagram..."):
                result = post_reel(
                    video_path=dry["path"],
                    caption=f"{dry['caption']}\n\n{dry['hashtags']}"
                )
            if result:
                st.success("🎉 Posted to Instagram successfully!")
                del st.session_state["last_dry_run"]
            else:
                st.error("❌ Instagram post failed. Check logs.")

    st.markdown("---")
    st.info("💡 **Cron Status:** Active (8 AM, 4 PM, 12 AM)")

# ─── Main Content ────────────────────────────────────────────────────────────
st.title("🎬 Trending HubX Dashboard")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🎥 Recent Productions")
    video_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "reel_*.mp4")), key=os.path.getmtime, reverse=True)
    
    if video_files:
        # Display latest 6 in a grid
        cols = st.columns(2)
        for idx, vid in enumerate(video_files[:6]):
            with cols[idx % 2]:
                st.video(vid)
                st.caption(f"📅 {datetime.fromtimestamp(os.path.getmtime(vid)).strftime('%Y-%m-%d %H:%M')}")
    else:
        st.info("No videos generated yet. Click 'Run Pipeline' to start!")

with col2:
    st.subheader("📜 Live Logs")
    # Get latest log file
    log_files = sorted(glob.glob(os.path.join(LOGS_DIR, "pipeline_*.log")), key=os.path.getmtime, reverse=True)
    
    if log_files:
        latest_log = log_files[0]
        with open(latest_log, "r") as f:
            lines = f.readlines()
            log_content = "".join(lines[-50:]) # last 50 lines
            log_html = log_content.replace("\n", "<br>")
            st.markdown(f'<div class="log-container">{log_html}</div>', unsafe_allow_html=True)
    else:
        st.write("No logs found.")
    
    st.markdown("---")
    st.subheader("⚙️ Settings Quick-View")
    from config import USE_DYNAMIC_BACKGROUND, USE_BACKGROUND_MUSIC, POST_INTERVAL_HOURS
    st.write(f"**Music:** {'✅ Enabled' if USE_BACKGROUND_MUSIC else '❌ Disabled'}")
    st.write(f"**Dynamic BG:** {'✅ Enabled' if USE_DYNAMIC_BACKGROUND else '❌ Disabled'}")
    st.write(f"**Interval:** Every {POST_INTERVAL_HOURS} hours")

st.markdown("---")
st.caption("© 2026 Trending HubX Automation Engine")
