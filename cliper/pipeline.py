"""
Autonomous End-to-End Clipping Pipeline.
Combines Audio Extraction -> Whisper Transcription -> Groq AI Hook Detection -> Video Rendering.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .config import Config, default_config
from .audio import download_audio, transcribe_audio, save_srt, sanitize_filename
from .ai import find_viral_clips
from .video import cut_clip


@dataclass
class ClipPipelineResult:
    source: str
    transcript_srt: Optional[Path] = None
    clip_data_json: Optional[Path] = None
    clips: list[dict] = field(default_factory=list)
    rendered_files: list[Path] = field(default_factory=list)


def run_pipeline(
    source: str,
    config: Optional[Config] = None,
    render_videos: bool = True,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> ClipPipelineResult:
    """
    Run full autonomous viral clipping workflow.
    `progress_callback` receives (status_message, percent_progress 0.0 to 1.0).
    """
    cfg = config or default_config
    result = ClipPipelineResult(source=source)

    def notify(msg: str, pct: float):
        if progress_callback:
            progress_callback(msg, pct)
        else:
            print(f"[{int(pct*100)}%] {msg}")

    # Step 1: Download or extract audio (0% - 15%)
    notify("Extracting audio from source…", 0.05)
    audio_path = download_audio(
        source=source,
        output_dir=cfg.cache_dir,
        progress_callback=lambda m: notify(m, 0.10),
    )

    try:
        # Step 2: Transcribe audio with Whisper (15% - 40%)
        notify(f"Transcribing audio with Whisper ({cfg.whisper_model})…", 0.15)
        segments = transcribe_audio(
            audio_path=audio_path,
            model_name=cfg.whisper_model,
            progress_callback=lambda m: notify(m, 0.25),
        )

        if not segments:
            raise RuntimeError("Transcription produced 0 segments. Check audio source.")

        # Save SRT subtitle
        srt_path = cfg.output_dir / f"transcript_{sanitize_filename(source)}.srt"
        save_srt(segments, srt_path)
        result.transcript_srt = srt_path
        notify(f"Saved subtitle transcript: {srt_path.name}", 0.40)

        # Step 3: AI Viral Hook Detection via Groq (40% - 60%)
        notify("Analyzing transcript with Groq AI for viral hooks…", 0.45)
        if not cfg.has_valid_groq_key:
            raise ValueError(
                "Invalid or missing Groq API Key! Please set GROQ_API_KEY in your .env "
                "or configure it in Studio Settings."
            )

        clips = find_viral_clips(
            segments=segments,
            api_key=cfg.groq_api_key,
            model=cfg.groq_model,
            chunk_minutes=cfg.chunk_minutes,
            min_duration=cfg.min_clip_duration,
            max_duration=cfg.max_clip_duration,
            progress_callback=lambda m: notify(m, 0.52),
        )

        result.clips = clips
        json_path = cfg.output_dir / f"clips_{sanitize_filename(source)}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"source": source, "clips": clips}, f, indent=2, ensure_ascii=False)
        result.clip_data_json = json_path
        notify(f"Discovered {len(clips)} viral hook(s)!", 0.60)

        # Step 4: Video Cutting & Framing (60% - 100%)
        if render_videos and clips:
            total_clips = len(clips)
            for idx, clip in enumerate(clips, 1):
                pct_start = 0.60 + (0.38 * ((idx - 1) / total_clips))
                clip_title = clip.get("title", f"Clip_{idx}")
                out_name = f"clip_{idx:02d}_{sanitize_filename(clip_title)[:25]}.mp4"
                out_path = cfg.output_dir / out_name

                notify(f"Rendering clip {idx}/{total_clips}: {clip_title}…", pct_start)

                rendered = cut_clip(
                    source_file_or_url=source,
                    start=clip["start"],
                    end=clip["end"],
                    output_path=out_path,
                    aspect_ratio="9:16",
                    remove_silence=cfg.remove_silence,
                    silence_min_len=cfg.silence_min_len,
                    silence_thresh=cfg.silence_thresh,
                    add_progress_bar=cfg.show_progress_bar,
                    bar_color=cfg.bar_color,
                    fade_duration=cfg.fade_duration,
                    progress_callback=lambda m: notify(f"[{idx}/{total_clips}] {m}", pct_start),
                )
                result.rendered_files.append(rendered)
                clip["rendered_path"] = str(rendered)

            # Update JSON with rendered paths
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump({"source": source, "clips": clips}, f, indent=2, ensure_ascii=False)

        notify("✨ Pipeline complete! Clips are ready.", 1.0)
        return result

    finally:
        # Cleanup temp audio
        if audio_path.exists():
            try:
                audio_path.unlink()
            except Exception:
                pass
