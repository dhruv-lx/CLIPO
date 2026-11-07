"""
Audio extraction, download, and Whisper transcription engine.
Supports both faster-whisper (GPU/CPU optimized) and openai-whisper with seamless fallback.
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import Callable, Optional


def sanitize_filename(name: str) -> str:
    """Sanitize arbitrary strings for safe use as filenames."""
    cleaned = re.sub(r'https?://(?:www\.)?', '', name)
    cleaned = re.sub(r'[\\/*?:"<>|&=]', '_', cleaned)
    return cleaned[:80].strip("._ ")


def ts_to_sec(ts: str) -> float:
    """Convert 'HH:MM:SS' or 'MM:SS' or seconds string to float seconds."""
    parts = [float(p) for p in str(ts).strip().split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0]


def sec_to_ts(seconds: float, include_ms: bool = False) -> str:
    """Format seconds into HH:MM:SS or HH:MM:SS,mmm string."""
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if include_ms:
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    return f"{h:02d}:{m:02d}:{s:02d}"


def normalise_ts(ts: str) -> str:
    """Ensure timestamp string is always formatted as HH:MM:SS."""
    return sec_to_ts(ts_to_sec(ts))


def download_audio(
    source: str,
    output_dir: Optional[Path] = None,
    audio_format: str = "m4a",
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Path:
    """
    Download audio stream from YouTube URL or extract audio from local video file.
    Returns path to the downloaded/extracted audio file.
    """
    if progress_callback:
        progress_callback("Extracting audio from source…")

    target_dir = Path(output_dir) if output_dir else Path.cwd()
    target_dir.mkdir(parents=True, exist_ok=True)

    source_path = Path(source)
    is_url = not source_path.exists()

    if is_url:
        out_name = f"__audio_{sanitize_filename(source)}_{os.getpid()}.{audio_format}"
        out_path = target_dir / out_name

        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-f", "bestaudio[ext=m4a]/bestaudio",
            "--extract-audio",
            "--audio-format", audio_format,
            "-o", str(out_path),
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            source,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            # Fallback to direct yt-dlp binary if available
            subprocess.run(["yt-dlp", "-f", "bestaudio/best", "-x", "-o", str(out_path), source], check=True)

        if not out_path.exists():
            # Sometimes yt-dlp adjusts extension, search matching prefix
            matches = list(target_dir.glob(f"__audio_{sanitize_filename(source)}_{os.getpid()}.*"))
            if matches:
                return matches[0]
            raise FileNotFoundError(f"Failed to find downloaded audio at {out_path}")
        return out_path
    else:
        # Local video file -> extract mono audio with ffmpeg directly
        out_path = target_dir / f"__audio_{source_path.stem}_{os.getpid()}.{audio_format}"
        cmd = [
            "ffmpeg", "-y", "-i", str(source_path),
            "-vn", "-acodec", "aac", "-ar", "16000", "-ac", "1",
            str(out_path)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return out_path


def transcribe_audio(
    audio_path: Path,
    model_name: str = "base",
    progress_callback: Optional[Callable[[str], None]] = None,
) -> list[dict]:
    """
    Transcribe audio file into timestamped segments:
    [{"start": float, "end": float, "text": str}, ...]

    Tries faster-whisper first for 4x speedup, then falls back to openai-whisper.
    """
    audio_str = str(audio_path)
    if progress_callback:
        progress_callback(f"Transcribing audio with Whisper ({model_name})…")

    segments = []

    # 1. Try faster-whisper
    try:
        from faster_whisper import WhisperModel
        # Use CPU with int8 quantization for broad compatibility and blazing speed
        fw_model = WhisperModel(model_name, device="auto", compute_type="int8")
        raw_segments, info = fw_model.transcribe(audio_str, beam_size=5)
        for s in raw_segments:
            segments.append({
                "start": float(s.start),
                "end": float(s.end),
                "text": s.text.strip(),
            })
        return segments
    except Exception:
        pass

    # 2. Fallback to standard openai-whisper
    try:
        import whisper
        w_model = whisper.load_model(model_name)
        result = w_model.transcribe(audio_str, verbose=False)
        for s in result.get("segments", []):
            segments.append({
                "start": float(s["start"]),
                "end": float(s["end"]),
                "text": s["text"].strip(),
            })
        return segments
    except Exception as e:
        raise RuntimeError(f"Whisper transcription failed: {e}")


def chunk_segments(segments: list[dict], chunk_seconds: float = 300.0) -> list[list[dict]]:
    """Group segments into time chunks (e.g. 5 minutes) to fit LLM token contexts."""
    chunks = []
    current: list[dict] = []
    chunk_start = 0.0

    for seg in segments:
        if seg["end"] - chunk_start > chunk_seconds and current:
            chunks.append(current)
            current = []
            chunk_start = seg["start"]
        current.append(seg)

    if current:
        chunks.append(current)
    return chunks


def build_chunk_text(segments: list[dict]) -> str:
    """Format segments into lines with timestamps for the LLM prompt."""
    lines = []
    for seg in segments:
        lines.append(f"[{sec_to_ts(seg['start'])}] {seg['text']}")
    return "\n".join(lines)


def save_srt(segments: list[dict], path: Path):
    """Export segments as standard SRT subtitle file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            s_ts = sec_to_ts(seg["start"], include_ms=True)
            e_ts = sec_to_ts(seg["end"], include_ms=True)
            text = seg["text"].strip()
            f.write(f"{i}\n{s_ts} --> {e_ts}\n{text}\n\n")
