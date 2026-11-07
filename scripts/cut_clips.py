"""
cut_clips.py — read clip_data.json, cut + crop 9:16, jump cuts, progress bar, audio fades
Uses clipo core engine.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import clipo
from clipo.config import default_config


def main():
    # Check current directory and examples directory
    json_path = ROOT_DIR / "examples" / "clip_data.json"
    if not json_path.is_file():
        json_path = ROOT_DIR / "clip_data.json"
    if not json_path.is_file():
        print("clip_data.json not found in examples/ or root. Run get_timestamps.py first.")
        sys.exit(1)

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    source = data.get("url", "")
    clips = data.get("clips", [])
    if not clips:
        print("No clips found in clip_data.json.")
        sys.exit(1)

    print(f"🎬 Processing {len(clips)} clip(s) from {source}...")
    output_dir = ROOT_DIR / "output"
    output_dir.mkdir(exist_ok=True)

    for idx, clip in enumerate(clips, 1):
        title = clip.get("title", f"Clip_{idx}")
        start = clip["start"]
        end = clip["end"]
        out_name = f"clip_{idx:02d}.mp4"
        out_path = output_dir / out_name

        print(f"\n[{idx}/{len(clips)}] Rendering '{title}' ({start} -> {end})...")
        try:
            rendered = clipo.cut_clip(
                source_file_or_url=source,
                start=start,
                end=end,
                output_path=out_path,
                aspect_ratio="9:16",
                remove_silence=default_config.remove_silence,
                add_progress_bar=default_config.show_progress_bar,
                bar_color=default_config.bar_color,
                fade_duration=default_config.fade_duration,
            )
            print(f"  ✅ Done: {rendered}")
        except Exception as e:
            print(f"  ❌ Error on clip {idx}: {e}")

    print("\n✨ All clips finished rendering in ./output/")


if __name__ == "__main__":
    main()
