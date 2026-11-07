"""
get_timestamps.py — scan video audio, find viral clips via Groq AI, save to clip_data.json
Reads API key securely from .env.
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

import cliper
from cliper.config import default_config


def main():
    url = input("Video URL or file path: ").strip()
    if not url:
        print("No URL or file provided.")
        sys.exit(1)

    api_key = os.getenv("GROQ_API_KEY", default_config.groq_api_key)
    if not api_key or api_key in ("PASTE_YOUR_KEY_HERE", "your_groq_api_key_here"):
        print("Error: Please set GROQ_API_KEY in your .env file or environment.")
        sys.exit(1)

    print(f"🎙️ Extracting audio and transcribing from: {url}…")
    cache_dir = ROOT_DIR / ".cache"
    cache_dir.mkdir(exist_ok=True)

    audio_path = cliper.download_audio(url, output_dir=cache_dir)
    try:
        segments = cliper.transcribe_audio(audio_path, model_name=default_config.whisper_model)
        print(f"Transcribed {len(segments)} spoken segments.")

        srt_path = ROOT_DIR / "examples" / "full_transcript.srt"
        cliper.save_srt(segments, srt_path)
        print(f"Saved {srt_path}")

        print("🤖 Evaluating viral hooks with Groq AI (LLaMA 3.3 70B)…")
        clips = cliper.find_viral_clips(
            segments=segments,
            api_key=api_key,
            model=default_config.groq_model,
        )

        data = {"url": url, "clips": clips}
        json_path = ROOT_DIR / "examples" / "clip_data.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n✨ Successfully found {len(clips)} viral clip(s) and saved to {json_path}!")
        for i, c in enumerate(clips, 1):
            print(f"  [{i}] {c.get('title')} ({c['start']} -> {c['end']}) - Score: {c.get('virality_score', 'N/A')}/100")
            print(f"      Hook: \"{c.get('hook', '')}\"")

    finally:
        if audio_path.exists():
            try:
                audio_path.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    main()
