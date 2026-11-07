"""
Configuration and settings management for Clipo AI.
Reads from environment variables and .env file.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Automatically load .env if present
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


@dataclass
class Config:
    """Global configuration settings for Clipo."""
    # Groq API configuration
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"))
    
    # Whisper configuration
    whisper_model: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL", "base"))
    chunk_minutes: int = 5
    max_retries: int = 3
    
    # Video dimensions
    target_width: int = int(os.getenv("TARGET_WIDTH", 1080))
    target_height: int = int(os.getenv("TARGET_HEIGHT", 1920))
    
    # Progress bar overlay
    show_progress_bar: bool = True
    bar_color: tuple[int, int, int] = (255, 59, 48)  # Vibrant accent red/coral (or custom RGB)
    bar_height: int = 6
    
    # Audio crossfade & quality
    fade_duration: float = 0.4
    audio_sample_rate: int = 44100
    
    # Silence removal (Jump cuts)
    remove_silence: bool = os.getenv("REMOVE_SILENCE", "true").lower() in ("true", "1", "yes")
    silence_min_len: float = float(os.getenv("SILENCE_MIN_LEN", 0.55))
    silence_thresh: float = float(os.getenv("SILENCE_THRESH", 0.03))
    
    # Target clip duration bounds for AI hook detector (in seconds)
    min_clip_duration: int = 30
    max_clip_duration: int = 60
    
    # Directories
    output_dir: Path = field(default_factory=lambda: ROOT_DIR / "output")
    cache_dir: Path = field(default_factory=lambda: ROOT_DIR / ".cache")
    
    def __post_init__(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def has_valid_groq_key(self) -> bool:
        return bool(self.groq_api_key and self.groq_api_key != "your_groq_api_key_here" and self.groq_api_key.startswith("gsk_"))


# Default global instance
default_config = Config()

