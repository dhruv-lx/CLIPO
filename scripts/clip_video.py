"""
clip_video.py — Quick precision clipper from YouTube URLs or local video files.
Usage: python scripts/clip_video.py [URL_or_path] [START] [END] [output.mp4]
"""

import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import clipo
from clipo.audio import ts_to_sec


def main():
    args = sys.argv[1:]

    if not args:
        source = input("Video URL or file path: ").strip()
        start = input("Start time (e.g. 0:30 or 1:02:15): ").strip()
        end = input("End time (e.g. 1:15 or 1:03:45): ").strip()
        output = input("Output filename [clip.mp4]: ").strip() or "clip.mp4"
    elif len(args) >= 3:
        source, start, end = args[0], args[1], args[2]
        output = args[3] if len(args) > 3 else "clip.mp4"
    else:
        print("Usage: python scripts/clip_video.py <URL|path> <start> <end> [output.mp4]")
        sys.exit(1)

    print(f"\n✂️ Clipping {start} -> {end} from {source}...")
    try:
        out = clipo.cut_clip(
            source_file_or_url=source,
            start=start,
            end=end,
            output_path=output,
            aspect_ratio="16:9",  # standard original ratio for manual clip
            remove_silence=False,
            add_progress_bar=False,
        )
        print(f"✨ Done → {Path(out).resolve()}")
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
