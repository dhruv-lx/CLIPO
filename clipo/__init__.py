"""
Clipo AI — Autonomous Viral Shorts & Video Clipping Studio
"""

__version__ = "1.0.0"
__author__ = "Dhruv"

from .config import Config
from .audio import download_audio, transcribe_audio, save_srt, ts_to_sec, sec_to_ts
from .ai import find_viral_clips
from .silence import detect_silences, remove_silence_from_clip
from .video import cut_clip, crop_to_ratio, make_progress_bar
from .pipeline import run_pipeline, ClipPipelineResult

__all__ = [
    "Config",
    "download_audio",
    "transcribe_audio",
    "save_srt",
    "ts_to_sec",
    "sec_to_ts",
    "find_viral_clips",
    "detect_silences",
    "remove_silence_from_clip",
    "cut_clip",
    "crop_to_ratio",
    "make_progress_bar",
    "run_pipeline",
    "ClipPipelineResult",
]

