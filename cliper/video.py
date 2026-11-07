"""
High-performance video processing, framing, cropping, and rendering.
Supports 9:16 vertical re-framing, silence jump-cuts, audio crossfades, and animated progress bars.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from .audio import sanitize_filename, ts_to_sec
from .silence import detect_silences, remove_silence_from_clip


def download_source_video(
    url: str,
    output_dir: Path,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Path:
    """Download full high-resolution MP4 video from YouTube or online source."""
    if progress_callback:
        progress_callback("Downloading source video (1080p/best MP4)…")

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"__dl_{sanitize_filename(url)}_{os.getpid()}.mp4"

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", str(out_path),
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        url,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        subprocess.run([
            "yt-dlp", "-f", "bestvideo+bestaudio/best",
            "-o", str(out_path), "--merge-output-format", "mp4", url
        ], check=True)

    if not out_path.exists():
        matches = list(output_dir.glob(f"__dl_{sanitize_filename(url)}_{os.getpid()}.*"))
        if matches:
            return matches[0]
        raise FileNotFoundError(f"Failed to find downloaded video at {out_path}")

    return out_path


def crop_to_ratio(clip, target_w: int = 1080, target_h: int = 1920, center_bias: float = 0.5):
    """
    Intelligently crop video clip to target aspect ratio (default 9:16 vertical 1080x1920).
    `center_bias` ranges from 0.0 (left-aligned) to 0.5 (centered) to 1.0 (right-aligned).
    """
    src_w, src_h = clip.w, clip.h
    target_ratio = target_w / target_h

    if (src_w / src_h) > target_ratio:
        # Video is wider than target (e.g. 16:9 to 9:16)
        crop_w = int(src_h * target_ratio)
        crop_h = src_h
    else:
        # Video is taller than target
        crop_w = src_w
        crop_h = int(src_w / target_ratio)

    # Position crop window horizontally based on center bias
    total_slack_x = src_w - crop_w
    x1 = int(total_slack_x * center_bias)
    y1 = (src_h - crop_h) // 2

    return (
        clip.cropped(x1=x1, y1=y1, x2=x1 + crop_w, y2=y1 + crop_h)
        .resized(width=target_w, height=target_h)
    )


def make_progress_bar(duration: float, width: int = 1080, height: int = 6, color_rgb: tuple[int, int, int] = (255, 59, 48)):
    """Generate a dynamic animated bottom progress bar overlay."""
    from moviepy import VideoClip

    color = np.array(color_rgb, dtype=np.uint8)

    def frame_func(t):
        progress = min(t / max(duration, 0.001), 1.0)
        bar_w = int(width * progress)
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        if bar_w > 0:
            frame[:, :bar_w] = color
        return frame

    return VideoClip(frame_func, duration=duration)


def cut_clip(
    source_file_or_url: str,
    start: str | float,
    end: str | float,
    output_path: str | Path,
    aspect_ratio: str = "9:16",
    remove_silence: bool = True,
    silence_min_len: float = 0.55,
    silence_thresh: float = 0.03,
    add_progress_bar: bool = True,
    bar_color: tuple[int, int, int] = (255, 59, 48),
    fade_duration: float = 0.4,
    center_bias: float = 0.5,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Path:
    """
    Cut a single video segment, apply aspect framing, jump cuts, audio fades,
    and progress bar overlay, then render to output_path.
    """
    from moviepy import VideoFileClip, CompositeVideoClip
    from moviepy.audio.fx import AudioFadeIn, AudioFadeOut

    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    start_s = ts_to_sec(str(start)) if isinstance(start, str) else float(start)
    end_s = ts_to_sec(str(end)) if isinstance(end, str) else float(end)
    duration = end_s - start_s
    if duration <= 0:
        raise ValueError(f"Invalid duration: start={start} ({start_s}s), end={end} ({end_s}s)")

    source_path = Path(source_file_or_url)
    is_url = not source_path.exists()
    temp_download = None

    try:
        if is_url:
            temp_download = download_source_video(source_file_or_url, out_file.parent, progress_callback)
            input_video_path = str(temp_download)
        else:
            input_video_path = str(source_path)

        if progress_callback:
            progress_callback(f"Extracting subclip {start_s:.1f}s to {end_s:.1f}s…")

        clip = VideoFileClip(input_video_path).subclipped(start_s, end_s)

        # 1. Framing / Aspect Ratio Crop
        target_w, target_h = 1080, 1920
        if aspect_ratio == "9:16":
            target_w, target_h = 1080, 1920
            clip = crop_to_ratio(clip, target_w, target_h, center_bias=center_bias)
        elif aspect_ratio == "1:1":
            target_w, target_h = 1080, 1080
            clip = crop_to_ratio(clip, target_w, target_h, center_bias=center_bias)
        elif aspect_ratio == "16:9":
            target_w, target_h = 1920, 1080
            # Keep original wide framing, ensure max 1080p
            if clip.h > 1080:
                clip = clip.resized(height=1080)
            target_w, target_h = clip.w, clip.h

        # 2. Silence detection & jump cuts
        if remove_silence:
            if progress_callback:
                progress_callback("Scanning audio for pauses and dead silence…")
            silences = detect_silences(clip, min_len=silence_min_len, thresh_ratio=silence_thresh)
            if silences:
                total_silent = sum(e - s for s, e in silences)
                if progress_callback:
                    progress_callback(f"Trimming {len(silences)} silent gaps ({total_silent:.1f}s removed)…")
                clip = remove_silence_from_clip(clip, silences)

        # 3. Audio crossfades (smooth beginning and end)
        if clip.audio is not None and fade_duration > 0 and clip.duration > (fade_duration * 2):
            try:
                audio = clip.audio.with_effects([
                    AudioFadeIn(fade_duration),
                    AudioFadeOut(fade_duration)
                ])
                clip = clip.with_audio(audio)
            except Exception:
                pass

        # 4. Progress bar overlay
        layers = [clip]
        if add_progress_bar and clip.duration > 2.0:
            bar = make_progress_bar(clip.duration, width=target_w, height=6, color_rgb=bar_color)
            bar = bar.with_position((0, target_h - 6))
            layers.append(bar)

        final_clip = CompositeVideoClip(layers) if len(layers) > 1 else clip

        if progress_callback:
            progress_callback(f"Encoding MP4: {out_file.name}…")

        final_clip.write_videofile(
            str(out_file),
            codec="libx264",
            audio_codec="aac",
            preset="fast",
            ffmpeg_params=["-crf", "22", "-pix_fmt", "yuv420p"],
            logger=None,
        )

        clip.close()
        if len(layers) > 1:
            layers[1].close()
        final_clip.close()

        return out_file

    finally:
        # Clean up temporary download if URL was used, BUT DO NOT TOUCH user's local file!
        if temp_download and temp_download.exists():
            try:
                temp_download.unlink()
            except Exception:
                pass
