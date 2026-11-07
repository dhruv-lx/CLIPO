"""
Cliper AI — Modern Autonomous Viral Shorts & Video Clipping Studio
Built with Streamlit, MoviePy, OpenAI Whisper, and Groq LLMs.
"""

import os
import sys
import json
import time
import zipfile
from io import BytesIO
from pathlib import Path
from datetime import datetime

import streamlit as st

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import cliper
from cliper.config import Config, default_config
from cliper.audio import sec_to_ts, ts_to_sec, sanitize_filename
from cliper.video import cut_clip
from cliper.pipeline import run_pipeline

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG & MODERN CUSTOM THEME
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Cliper AI — Viral Shorts Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom High-End SaaS Dark Theme Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Main container styling */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1300px;
    }

    /* Hero Banner */
    .hero-container {
        background: linear-gradient(135deg, rgba(30, 27, 75, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(139, 92, 246, 0.25);
        border-radius: 20px;
        padding: 28px 36px;
        margin-bottom: 24px;
        backdrop-filter: blur(12px);
        box-shadow: 0 10px 30px -10px rgba(99, 102, 241, 0.2);
    }
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #FFFFFF 0%, #C4B5FD 50%, #818CF8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .hero-subtitle {
        color: #94A3B8;
        font-size: 1.05rem;
        line-height: 1.6;
        margin-bottom: 0px;
    }

    /* Metric Badges */
    .badge-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .badge-viral {
        background: rgba(239, 68, 68, 0.15);
        color: #F87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .badge-category {
        background: rgba(139, 92, 246, 0.15);
        color: #C4B5FD;
        border: 1px solid rgba(139, 92, 246, 0.3);
    }
    .badge-time {
        background: rgba(59, 130, 246, 0.15);
        color: #93C5FD;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }

    /* Glassmorphic Cards */
    .glass-card {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 18px;
        backdrop-filter: blur(10px);
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }
    .glass-card:hover {
        border-color: rgba(139, 92, 246, 0.4);
        box-shadow: 0 8px 25px -5px rgba(124, 58, 237, 0.25);
    }

    /* Primary Buttons */
    .stButton > button {
        border-radius: 12px;
        font-weight: 600;
        padding: 0.55rem 1.4rem;
        transition: all 0.2s ease;
        border: none;
    }

    /* Status Indicator Dot */
    .status-dot {
        height: 10px;
        width: 10px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 6px;
    }
    .status-online {
        background-color: #10B981;
        box-shadow: 0 0 8px #10B981;
    }
    .status-warning {
        background-color: #F59E0B;
        box-shadow: 0 0 8px #F59E0B;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — SYSTEM STATUS & CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🎬 **Cliper AI Studio**")
    st.caption("Autonomous Viral Shorts Engine • v1.0.0")
    st.divider()

    # System Health Panel
    st.markdown("#### ⚡ System Status")
    
    # 1. Groq Key Check
    has_groq = default_config.has_valid_groq_key
    if has_groq:
        st.markdown('<span class="status-dot status-online"></span> **Groq AI**: Connected', unsafe_allow_html=True)
        st.caption(f"Model: `{default_config.groq_model}`")
    else:
        st.markdown('<span class="status-dot status-warning"></span> **Groq AI**: Key Needed', unsafe_allow_html=True)
        st.caption("Add key in Settings or .env")

    # 2. Whisper Model
    st.markdown('<span class="status-dot status-online"></span> **Whisper**: Ready', unsafe_allow_html=True)
    st.caption(f"Engine: Fast Speech-to-Text ({default_config.whisper_model})")

    # 3. FFmpeg Engine
    st.markdown('<span class="status-dot status-online"></span> **FFmpeg / MoviePy**: Ready', unsafe_allow_html=True)
    st.caption("GPU/CPU Accelerated Transcoding")

    st.divider()

    # Global Quick Presets
    st.markdown("#### ⚙️ Quick Defaults")
    selected_whisper = st.selectbox(
        "Whisper Size",
        ["tiny", "base", "small", "medium"],
        index=["tiny", "base", "small", "medium"].index(default_config.whisper_model) if default_config.whisper_model in ["tiny", "base", "small", "medium"] else 1,
        help="Larger models improve speech accuracy but take longer to process."
    )
    default_config.whisper_model = selected_whisper

    remove_silence_toggle = st.checkbox(
        "Auto-Trim Silence (Jump Cuts)",
        value=default_config.remove_silence,
        help="Automatically removes pauses, coughs, and silent gaps between sentences to skyrocket short-form retention."
    )
    default_config.remove_silence = remove_silence_toggle

    show_bar_toggle = st.checkbox(
        "Add Dynamic Progress Bar",
        value=default_config.show_progress_bar,
        help="Adds an animated retention progress bar along the bottom of vertical clips."
    )
    default_config.show_progress_bar = show_bar_toggle

    st.divider()
    st.caption("Crafted for creators, editors & tech portfolio showcase. 🚀")


# ─────────────────────────────────────────────────────────────────────────────
# HERO BANNER
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero-container">
    <div class="hero-title">
        <span>🎬</span> Cliper AI — Autonomous Shorts Studio
    </div>
    <div class="hero-subtitle">
        Transform long-form YouTube videos, podcasts, and recordings into high-converting <b>9:16 vertical shorts, reels, and TikToks</b>.
        Powered by <b>Whisper Speech-to-Text</b>, <b>Groq LLaMA 3.3 70B</b> hook intelligence, and <b>Smart Jump-Cut Silence Removal</b>.
    </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TABS INTERFACE
# ─────────────────────────────────────────────────────────────────────────────

tab_auto, tab_manual, tab_library, tab_transcripts, tab_settings = st.tabs([
    "🚀 Auto-Pilot Viral Clipper",
    "✂️ Precision Manual Trimmer",
    "📁 Clip Library & Exports",
    "📝 Subtitles & Transcripts",
    "⚙️ Studio Settings",
])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1: AUTO-PILOT VIRAL CLIPPER
# ═════════════════════════════════════════════════════════════════════════════

with tab_auto:
    st.markdown("### 🤖 Autonomous Viral Clip Extraction")
    st.markdown("Paste a YouTube link or specify a local video file. Cliper AI will automatically transcribe speech, evaluate talking points for retention hooks with Groq AI, and render vertical clips with animated progress bars.")

    col1, col2 = st.columns([3, 1])
    with col1:
        video_input = st.text_input(
            "Video Source (YouTube URL or Local File Path)",
            placeholder="https://www.youtube.com/watch?v=... or C:/Videos/podcast.mp4",
            help="Enter any YouTube video link or the absolute path to a local MP4 file."
        )
    with col2:
        st.write("")
        st.write("")
        sample_btn = st.button("💡 Load Demo URL", help="Loads a popular high-quality tech talk for testing")
        if sample_btn:
            video_input = "https://www.youtube.com/watch?v=aircAruvnKk"
            st.session_state["demo_url"] = video_input

    # Sample URL persistence
    if "demo_url" in st.session_state and not video_input:
        video_input = st.session_state["demo_url"]

    with st.expander("🛠️ Advanced Extraction Controls", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            clip_min_sec = st.slider("Min Clip Duration (seconds)", 15, 60, default_config.min_clip_duration)
            default_config.min_clip_duration = clip_min_sec
        with c2:
            clip_max_sec = st.slider("Max Clip Duration (seconds)", 30, 90, default_config.max_clip_duration)
            default_config.max_clip_duration = clip_max_sec
        with c3:
            aspect_choice = st.selectbox("Framing Format", ["9:16 Vertical (Shorts/Reels)", "1:1 Square", "16:9 Landscape"])
            aspect_map = {"9:16 Vertical (Shorts/Reels)": "9:16", "1:1 Square": "1:1", "16:9 Landscape": "16:9"}

    # Start Autonomous Pipeline Button
    start_auto = st.button("✨ Launch Autonomous AI Clipper", type="primary", use_container_width=True)

    if start_auto:
        if not video_input.strip():
            st.error("⚠️ Please provide a valid YouTube URL or local video path.")
        elif not default_config.has_valid_groq_key:
            st.error("⚠️ Groq API Key is not set or invalid! Please configure it in the '⚙️ Studio Settings' tab.")
        else:
            progress_bar = st.progress(0.0)
            status_text = st.empty()

            try:
                def update_progress(msg: str, pct: float):
                    status_text.markdown(f"**⏳ Status:** {msg}")
                    progress_bar.progress(min(max(pct, 0.0), 1.0))

                start_time = time.time()
                result = run_pipeline(
                    source=video_input.strip(),
                    config=default_config,
                    render_videos=True,
                    progress_callback=update_progress,
                )
                elapsed = time.time() - start_time

                progress_bar.progress(1.0)
                status_text.markdown(f"✅ **Extraction Completed in {elapsed:.1f}s!** Found {len(result.clips)} viral clips.")
                st.session_state["last_result"] = result
                st.balloons()

            except Exception as ex:
                st.error(f"❌ An error occurred during pipeline execution: {ex}")
                st.exception(ex)

    # Display Extracted Clips if available
    current_result = st.session_state.get("last_result", None)

    # If no run this session, check if there's sample clip_data.json
    if not current_result:
        sample_candidates = [Path("examples/clip_data.json"), Path("clip_data.json")]
        for sc in sample_candidates:
            if sc.exists():
                try:
                    with open(sc, encoding="utf-8") as f:
                        saved_data = json.load(f)
                        if saved_data.get("clips"):
                            st.info("💡 Displaying pre-analyzed demo clips from `examples/clip_data.json`:")
                            current_result = type("Obj", (), {
                                "source": saved_data.get("url", "Demo Video"),
                                "clips": saved_data.get("clips", []),
                                "rendered_files": list(Path("output").glob("clip_*.mp4")),
                            })()
                            break
                except Exception:
                    pass

    if current_result and getattr(current_result, "clips", None):
        st.divider()
        st.markdown(f"### 🏆 Viral Clips Detected ({len(current_result.clips)})")

        for idx, clip in enumerate(current_result.clips, 1):
            with st.container():
                st.markdown(f"""
                <div class="glass-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <h4 style="margin: 0; font-size: 1.2rem; font-weight: 700; color: #FFFFFF;">
                            #{idx} {clip.get('title', 'Viral Clip')}
                        </h4>
                        <div>
                            <span class="badge-pill badge-viral">🔥 {clip.get('virality_score', 85)}% Viral Score</span>
                            <span class="badge-pill badge-category">📌 {clip.get('category', 'Insight')}</span>
                            <span class="badge-pill badge-time">⏱️ {clip.get('start')} → {clip.get('end')}</span>
                        </div>
                    </div>
                    <div style="font-size: 0.95rem; color: #E2E8F0; margin-bottom: 6px;">
                        <b>Attention Hook:</b> <i>"{clip.get('hook', 'High retention talking point')}"</i>
                    </div>
                    <div style="font-size: 0.85rem; color: #94A3B8; margin-bottom: 12px;">
                        <b>AI Why-It-Works:</b> {clip.get('summary', 'Compelling explanation that drives viewer engagement.')}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col_video, col_text = st.columns([1, 2])
                with col_video:
                    # Check if rendered file exists
                    rendered_path = clip.get("rendered_path")
                    if not rendered_path:
                        expected_file = Path("output") / f"clip_{idx:02d}.mp4"
                        if expected_file.exists():
                            rendered_path = str(expected_file)

                    if rendered_path and Path(rendered_path).exists():
                        st.video(rendered_path)
                        with open(rendered_path, "rb") as vf:
                            st.download_button(
                                label=f"⬇️ Download Clip #{idx}",
                                data=vf,
                                file_name=Path(rendered_path).name,
                                mime="video/mp4",
                                key=f"dl_clip_{idx}",
                                use_container_width=True,
                            )
                    else:
                        st.caption("🎬 Render this clip individually:")
                        render_this = st.button(f"⚡ Render Clip #{idx}", key=f"render_{idx}")
                        if render_this:
                            with st.spinner(f"Rendering Clip #{idx}..."):
                                out_p = Path("output") / f"clip_{idx:02d}.mp4"
                                cut_clip(
                                    source_file_or_url=current_result.source,
                                    start=clip["start"],
                                    end=clip["end"],
                                    output_path=out_p,
                                    aspect_ratio="9:16",
                                    remove_silence=default_config.remove_silence,
                                    add_progress_bar=default_config.show_progress_bar,
                                )
                                clip["rendered_path"] = str(out_p)
                                st.rerun()

                with col_text:
                    st.markdown("**Transcript Excerpt:**")
                    st.text_area(
                        label=f"Spoken Text #{idx}",
                        value=clip.get("text", "No spoken transcript available."),
                        height=150,
                        key=f"txt_{idx}",
                        disabled=True,
                    )
                st.write("")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2: MANUAL PRECISION TRIMMER
# ═════════════════════════════════════════════════════════════════════════════

with tab_manual:
    st.markdown("### ✂️ Precision Manual Video Clipper")
    st.markdown("Have an exact timestamp you want to isolate? Clip any section with custom framing, dynamic silence removal, and progress bar overlay.")

    source_manual = st.text_input(
        "Video Source (URL or Path)",
        placeholder="https://www.youtube.com/watch?v=... or C:/Videos/input.mp4",
        key="manual_src"
    )

    c_s, c_e, c_ar = st.columns(3)
    with c_s:
        m_start = st.text_input("Start Timestamp", value="00:01:00", help="Format: HH:MM:SS or MM:SS or seconds")
    with c_e:
        m_end = st.text_input("End Timestamp", value="00:01:45", help="Format: HH:MM:SS or MM:SS or seconds")
    with c_ar:
        m_ratio = st.selectbox("Aspect Ratio", ["9:16", "1:1", "16:9"], index=0, key="manual_ratio")

    try:
        dur = ts_to_sec(m_end) - ts_to_sec(m_start)
        st.info(f"⏱️ Target Duration: **{dur:.1f} seconds** ({m_start} → {m_end})")
    except Exception:
        dur = 0

    c_opts1, c_opts2 = st.columns(2)
    with c_opts1:
        m_silence = st.checkbox("Remove Silent Pauses", value=True, key="m_silence")
    with c_opts2:
        m_bar = st.checkbox("Include Animated Progress Bar", value=True, key="m_bar")

    if st.button("🚀 Render Custom Clip", type="primary", use_container_width=True):
        if not source_manual:
            st.error("Please enter a valid source.")
        elif dur <= 0:
            st.error("End timestamp must be strictly greater than start timestamp.")
        else:
            with st.spinner("Processing precision clip..."):
                try:
                    out_dir = Path("output")
                    out_dir.mkdir(exist_ok=True)
                    out_name = f"manual_{int(time.time())}.mp4"
                    out_file = out_dir / out_name

                    rendered = cut_clip(
                        source_file_or_url=source_manual.strip(),
                        start=m_start,
                        end=m_end,
                        output_path=out_file,
                        aspect_ratio=m_ratio,
                        remove_silence=m_silence,
                        add_progress_bar=m_bar,
                    )
                    st.success(f"🎉 Clip rendered successfully!")
                    st.video(str(rendered))

                    with open(rendered, "rb") as f:
                        st.download_button(
                            "⬇️ Download Rendered MP4",
                            data=f,
                            file_name=out_name,
                            mime="video/mp4",
                            use_container_width=True,
                        )
                except Exception as e:
                    st.error(f"Render failed: {e}")
                    st.exception(e)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3: CLIP LIBRARY & EXPORTS
# ═════════════════════════════════════════════════════════════════════════════

with tab_library:
    st.markdown("### 📁 Rendered Video Library")
    st.markdown("Browse, preview, and download all generated shorts.")

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    video_files = sorted(list(output_dir.glob("*.mp4")), key=lambda p: p.stat().st_mtime, reverse=True)

    if not video_files:
        st.info("No rendered clips in `./output/` yet. Run Auto-Pilot or Manual Trimmer to generate clips!")
    else:
        # Batch ZIP download
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for vf in video_files:
                zip_file.write(vf, arcname=vf.name)
        zip_buffer.seek(0)

        c_top1, c_top2 = st.columns([3, 1])
        with c_top1:
            st.caption(f"Showing {len(video_files)} exported video file(s).")
        with c_top2:
            st.download_button(
                "📦 Download All as ZIP",
                data=zip_buffer,
                file_name=f"cliper_all_shorts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
                use_container_width=True,
            )

        st.write("")
        # Display in 2-column grid
        cols = st.columns(2)
        for i, vf in enumerate(video_files):
            col = cols[i % 2]
            with col:
                st.markdown(f"**🎬 {vf.name}**")
                size_mb = vf.stat().st_size / (1024 * 1024)
                mtime = datetime.fromtimestamp(vf.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                st.caption(f"Size: {size_mb:.2f} MB • Rendered: {mtime}")
                st.video(str(vf))
                with open(vf, "rb") as f:
                    st.download_button(
                        f"⬇️ Download {vf.name}",
                        data=f,
                        file_name=vf.name,
                        mime="video/mp4",
                        key=f"lib_dl_{i}",
                        use_container_width=True,
                    )
                st.divider()


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4: SUBTITLES & TRANSCRIPTS
# ═════════════════════════════════════════════════════════════════════════════

with tab_transcripts:
    st.markdown("### 📝 Subtitles & Full Transcripts")
    st.markdown("Inspect Whisper-generated timestamps, search dialogues, and download standard `.srt` subtitle files.")

    # Check for SRT files in output or root
    srt_candidates = list(Path("output").glob("*.srt")) + list(Path(".").glob("*.srt"))
    if not srt_candidates:
        st.info("No transcript `.srt` files found yet. They are automatically produced when running the pipeline.")
    else:
        selected_srt = st.selectbox(
            "Select Transcript to View",
            srt_candidates,
            format_func=lambda p: p.name,
        )

        if selected_srt and selected_srt.exists():
            with open(selected_srt, encoding="utf-8") as f:
                content = f.read()

            st.download_button(
                "⬇️ Download SRT Subtitle File",
                data=content,
                file_name=selected_srt.name,
                mime="text/plain",
            )

            # Search within transcript
            search_query = st.text_input("🔍 Search keyword in transcript", placeholder="e.g. AI, revenue, python")
            if search_query.strip():
                matches = [line for line in content.split("\n") if search_query.lower() in line.lower()]
                st.caption(f"Found {len(matches)} matching lines:")
                for m in matches[:15]:
                    st.markdown(f"- `{m}`")
                st.divider()

            st.text_area("Full Subtitle Preview", content, height=450)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5: STUDIO SETTINGS & API KEYS
# ═════════════════════════════════════════════════════════════════════════════

with tab_settings:
    st.markdown("### ⚙️ Studio Configuration & API Keys")
    st.markdown("Manage your Groq API credentials, AI models, and clean up temporary caches.")

    # Groq API Key Configuration
    st.markdown("#### 🔑 Groq API Key")
    current_key = default_config.groq_api_key
    masked_key = current_key[:8] + "..." + current_key[-4:] if len(current_key) > 12 else current_key

    new_key = st.text_input(
        "Groq API Key",
        value=current_key,
        type="password",
        help="Free key available at https://console.groq.com/keys",
    )

    col_save, col_test = st.columns(2)
    with col_save:
        if st.button("💾 Save Key to .env"):
            if new_key.strip():
                # Update .env
                env_path = ROOT_DIR / ".env"
                lines = []
                if env_path.exists():
                    lines = [l for l in env_path.read_text(encoding="utf-8").splitlines() if not l.startswith("GROQ_API_KEY=")]
                lines.insert(0, f"GROQ_API_KEY={new_key.strip()}")
                env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                default_config.groq_api_key = new_key.strip()
                st.success("API key successfully saved to `.env`!")
                st.rerun()

    with col_test:
        if st.button("🧪 Test Groq Connection"):
            try:
                from groq import Groq
                c = Groq(api_key=new_key.strip() or current_key)
                r = c.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": "Respond with 'Connected'"}],
                    max_tokens=10,
                )
                st.success(f"Connection verified: {r.choices[0].message.content}")
            except Exception as e:
                st.error(f"Connection test failed: {e}")

    st.divider()

    # Cache Management
    st.markdown("#### 🧹 Cache & Storage Maintenance")
    cache_dir = Path(".cache")
    cache_files = list(cache_dir.glob("*")) if cache_dir.exists() else []
    temp_files = list(Path(".").glob("__audio_*")) + list(Path(".").glob("__dl_*"))
    total_temp = len(cache_files) + len(temp_files)

    st.write(f"Temporary audio/video downloads: **{total_temp} file(s)**")

    if st.button("🗑️ Clear Temporary Download Cache"):
        cleaned = 0
        for f in cache_files + temp_files:
            try:
                if f.is_file():
                    f.unlink()
                    cleaned += 1
            except Exception:
                pass
        st.success(f"Cleared {cleaned} cached file(s)!")
        st.rerun()

