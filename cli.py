"""
Cliper AI — Command Line Interface
Run full AI viral clipping, precision trimming, transcription, or launch the web studio.
"""

import sys
import argparse
from pathlib import Path

import cliper
from cliper.config import default_config
from cliper.audio import sec_to_ts, ts_to_sec


def print_banner():
    banner = r"""
   _____ _ _                     _____ 
  / ____| (_)                   |  __ \
 | |    | |_ _ __   ___ _ __    | |__) |
 | |    | | | '_ \ / _ \ '__|   |  ___/ 
 | |____| | | |_) |  __/ |      | |     
  \_____|_|_| .__/ \___|_|      |_|     
            | |                         
            |_|   AI Viral Shorts Studio
    """
    print(banner)


def cmd_auto(args):
    print_banner()
    source = args.source
    print(f"🎬 Starting Auto-Pilot Viral Clipper on: {source}")
    print(f"⚙️ Config: Whisper={default_config.whisper_model}, Model={default_config.groq_model}, SilenceRemoval={default_config.remove_silence}")
    
    result = cliper.run_pipeline(
        source=source,
        config=default_config,
        render_videos=not args.no_render,
    )
    
    print("\n" + "=" * 60)
    print("✨ SUCCESS: Generated Viral Clips Summary")
    print("=" * 60)
    for i, clip in enumerate(result.clips, 1):
        print(f"[{i}] {clip.get('title')} ({clip['start']} -> {clip['end']}) | Viral Score: {clip.get('virality_score', 'N/A')}/100")
        print(f"    Hook: \"{clip.get('hook', '')}\"")
        if clip.get("rendered_path"):
            print(f"    File: {clip['rendered_path']}")
        print()

    if result.transcript_srt:
        print(f"📝 Full Subtitles: {result.transcript_srt}")
    if result.clip_data_json:
        print(f"📊 Metadata JSON: {result.clip_data_json}")


def cmd_clip(args):
    print_banner()
    source = args.source
    start = args.start
    end = args.end
    output = args.output or f"clip_{Path(source).stem}_{start.replace(':', '')}_{end.replace(':', '')}.mp4"
    
    print(f"✂️ Cutting precision clip from: {source}")
    print(f"⏱️ Range: {start} -> {end} (Aspect Ratio: {args.ratio})")
    
    out_file = cliper.cut_clip(
        source_file_or_url=source,
        start=start,
        end=end,
        output_path=output,
        aspect_ratio=args.ratio,
        remove_silence=not args.keep_silence,
        add_progress_bar=not args.no_bar,
    )
    print(f"\n✅ Clip saved successfully to: {out_file}")


def cmd_transcribe(args):
    print_banner()
    source = args.source
    print(f"🎙️ Transcribing: {source}")
    
    audio_path = cliper.download_audio(source, output_dir=default_config.cache_dir)
    segments = cliper.transcribe_audio(audio_path, model_name=args.model)
    out_srt = Path(args.output or f"transcript_{Path(source).stem}.srt")
    cliper.save_srt(segments, out_srt)
    print(f"✅ Saved transcript to: {out_srt.resolve()}")


def cmd_ui(args):
    import subprocess
    print_banner()
    print("🚀 Launching Cliper AI Web Studio on http://localhost:8501 ...")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", str(args.port)])


def main():
    parser = argparse.ArgumentParser(
        prog="cliper",
        description="Cliper AI — Autonomous Viral Shorts & Video Clipping Studio",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available sub-commands")

    # Command: auto
    p_auto = subparsers.add_parser("auto", help="Autonomous viral hook detection and video rendering")
    p_auto.add_argument("source", help="YouTube URL or local video file path")
    p_auto.add_argument("--no-render", action="store_true", help="Analyze & detect hooks only without rendering MP4 clips")
    p_auto.set_defaults(func=cmd_auto)

    # Command: clip
    p_clip = subparsers.add_parser("clip", help="Precision manual video segment cutter")
    p_clip.add_argument("source", help="YouTube URL or local video file path")
    p_clip.add_argument("start", help="Start time (e.g. 01:23 or 83)")
    p_clip.add_argument("end", help="End time (e.g. 02:05 or 125)")
    p_clip.add_argument("-o", "--output", help="Output file path (default: auto generated)")
    p_clip.add_argument("--ratio", choices=["9:16", "1:1", "16:9"], default="9:16", help="Target aspect ratio framing")
    p_clip.add_argument("--keep-silence", action="store_true", help="Disable automatic silence jump cuts")
    p_clip.add_argument("--no-bar", action="store_true", help="Disable dynamic bottom progress bar overlay")
    p_clip.set_defaults(func=cmd_clip)

    # Command: transcribe
    p_tr = subparsers.add_parser("transcribe", help="Extract audio and generate timestamped SRT transcript")
    p_tr.add_argument("source", help="YouTube URL or local video file path")
    p_tr.add_argument("-m", "--model", default="base", help="Whisper model (tiny, base, small, medium, large)")
    p_tr.add_argument("-o", "--output", help="Output SRT filepath")
    p_tr.set_defaults(func=cmd_transcribe)

    # Command: ui
    p_ui = subparsers.add_parser("ui", help="Launch modern Streamlit Web Studio UI")
    p_ui.add_argument("-p", "--port", type=int, default=8501, help="Port to run Streamlit server on")
    p_ui.set_defaults(func=cmd_ui)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()

