"""
Audio silence analysis and jump-cut generator.
Automatically removes awkward pauses, coughs, and silent gaps to boost retention.
"""

import numpy as np


def get_audio_rms(clip, sample_rate: int = 44100, window_sec: float = 0.05) -> np.ndarray:
    """Extract mono RMS envelope (e.g. 50 ms windows) from a MoviePy clip's audio."""
    if clip.audio is None:
        return np.array([], dtype=np.float64)

    try:
        audio = clip.audio.to_soundarray(fps=sample_rate)
    except Exception:
        return np.array([], dtype=np.float64)

    if audio.size == 0:
        return np.array([], dtype=np.float64)

    # Convert to mono if stereo/multichannel
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    audio = audio.astype(np.float64)

    window = int(sample_rate * window_sec)
    if window == 0:
        return np.array([], dtype=np.float64)

    n = len(audio) // window
    if n == 0:
        return np.array([], dtype=np.float64)

    trimmed = audio[:n * window]
    rms = np.sqrt(np.mean(trimmed.reshape(n, window) ** 2, axis=1))
    return rms


def detect_silences(
    clip,
    sample_rate: int = 44100,
    min_len: float = 0.55,
    thresh_ratio: float = 0.03,
    window_sec: float = 0.05,
) -> list[tuple[float, float]]:
    """
    Detect silent gaps longer than or equal to `min_len` seconds.
    Returns a list of (start_sec, end_sec) intervals relative to the clip start.
    """
    rms = get_audio_rms(clip, sample_rate, window_sec)
    if len(rms) == 0:
        return []

    peak = float(rms.max())
    if peak <= 1e-6:
        return []

    threshold = peak * thresh_ratio
    silent = rms < threshold

    silences: list[tuple[float, float]] = []
    i = 0
    total_len = len(silent)

    while i < total_len:
        if silent[i]:
            start_t = i * window_sec
            while i < total_len and silent[i]:
                i += 1
            end_t = i * window_sec
            if end_t - start_t >= min_len:
                silences.append((start_t, end_t))
        else:
            i += 1

    return silences


def remove_silence_from_clip(clip, silences: list[tuple[float, float]], pad_sec: float = 0.06):
    """
    Split the clip at silent gaps and concatenate the active speech segments.
    Applies small padding so words aren't abruptly truncated.
    """
    if not silences:
        return clip

    from moviepy import concatenate_videoclips

    duration = clip.duration
    chunks = []
    prev_end = 0.0

    for s, e in silences:
        # Keep speech up to silence start (+ tiny pad)
        speech_end = min(duration, s + pad_sec)
        if speech_end > prev_end + 0.1:
            chunks.append(clip.subclipped(prev_end, speech_end))
        prev_end = max(0.0, e - pad_sec)

    if prev_end < duration - 0.1:
        chunks.append(clip.subclipped(prev_end, duration))

    if not chunks:
        return clip
    if len(chunks) == 1:
        return chunks[0]

    return concatenate_videoclips(chunks, method="chain")

