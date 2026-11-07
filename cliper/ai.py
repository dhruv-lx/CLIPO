"""
AI-powered viral hook and clip detection using Groq (LLaMA 3.3 70B).
Identifies high-impact talking points, hooks, and punchlines for TikTok, Reels & Shorts.
"""

import json
import re
import time
from typing import Callable, Optional
from groq import Groq
from groq import APIError as GroqError

from .audio import build_chunk_text, ts_to_sec, normalise_ts, sec_to_ts


GROQ_SYSTEM_PROMPT = """You are an elite short-form content strategist and viral video editor.
Your job is to analyze long-form video transcripts and pinpoint the HIGHEST-RETENTION, most VIRAL standalone clips.

REQUIREMENTS for every clip:
1. Duration MUST be between {min_duration} and {max_duration} seconds.
2. Self-contained: The clip must have a strong opening hook, deliver valuable context or punchline, and end smoothly without cutting off mid-sentence.
3. Content Types to prioritize:
   - "Curiosity Hook" (surprising statement, contrary opinion, hot take)
   - "Actionable Tutorial / Life Hack" (clear step-by-step insight)
   - "Emotional / Inspiring Story"
   - "Mind-Blowing Fact or Statistic"

Return an array of JSON objects. For each clip include:
  "start"         : exact start timestamp (HH:MM:SS)
  "end"           : exact end timestamp (HH:MM:SS)
  "title"         : punchy, click-worthy headline (under 8 words)
  "hook"          : the opening 1-sentence hook phrase that grabs attention
  "virality_score": estimated viral potential from 80 to 99
  "category"      : one of ["Contrarian", "Insight", "Story", "Tutorial", "Humor"]
  "summary"       : 1 brief sentence explaining why this clip will perform well

OUTPUT FORMAT:
Return ONLY a valid JSON array. No markdown, no preface, no trailing text.
Example:
[
  {{
    "start": "00:01:15",
    "end": "00:01:55",
    "title": "Why 99% Of People Fail At Coding",
    "hook": "The biggest lie in tech is that you need math.",
    "virality_score": 94,
    "category": "Contrarian",
    "summary": "High curiosity opening with relatable career controversy."
  }}
]

TRANSCRIPT TO ANALYZE:
{transcript}
"""


def parse_clips_json(text: str) -> list[dict]:
    """Parse JSON array from raw model text output, cleaning any markdown formatting."""
    cleaned = text.strip()
    # Strip markdown code fencing if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    
    # Try direct parse
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Match outermost brackets [...]
        match = re.search(r'\[\s*\{.*\}\s*\]', cleaned, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
        else:
            raise ValueError(f"Could not parse valid JSON list from model output: {cleaned[:150]}...")

    if not isinstance(data, list):
        if isinstance(data, dict) and "clips" in data:
            data = data["clips"]
        else:
            raise ValueError("Expected JSON array of clips from AI model.")

    formatted_clips = []
    for item in data:
        if not isinstance(item, dict):
            continue
        start_str = normalise_ts(str(item.get("start", "00:00:00")))
        end_str = normalise_ts(str(item.get("end", "00:00:30")))
        
        # Verify valid duration
        start_s = ts_to_sec(start_str)
        end_s = ts_to_sec(end_str)
        if end_s <= start_s:
            end_s = start_s + 30.0
            end_str = sec_to_ts(end_s)

        formatted_clips.append({
            "start": start_str,
            "end": end_str,
            "title": str(item.get("title", "Untitled Clip")).strip(),
            "hook": str(item.get("hook", "")).strip(),
            "virality_score": int(item.get("virality_score", 88)),
            "category": str(item.get("category", "Insight")).strip(),
            "summary": str(item.get("summary", "")).strip(),
            "text": "",  # Populated from whisper segments
        })

    return formatted_clips


FALLBACK_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "llama3-70b-8192",
]


def call_groq_chunk(
    client: Groq,
    segments: list[dict],
    model: str = "qwen/qwen3.8-27b",
    min_duration: int = 30,
    max_duration: int = 60,
    max_retries: int = 3,
) -> list[dict]:
    """Call Groq API on a transcript chunk to extract candidate clips."""
    transcript_text = build_chunk_text(segments)
    prompt = GROQ_SYSTEM_PROMPT.format(
        min_duration=min_duration,
        max_duration=max_duration,
        transcript=transcript_text,
    )

    candidate_models = [model] + [m for m in FALLBACK_MODELS if m != model]

    for current_model in candidate_models:
        for attempt in range(1, max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=current_model,
                    messages=[
                        {"role": "system", "content": "You are a professional video editor specializing in YouTube Shorts and TikTok."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                )
                raw_reply = response.choices[0].message.content or ""
                return parse_clips_json(raw_reply)
            except GroqError as gerr:
                # If model is not found, try next candidate model immediately
                if "model_not_found" in str(gerr) or "does not exist" in str(gerr):
                    break
                if attempt < max_retries:
                    time.sleep(2)
                else:
                    break
            except Exception as err:
                if attempt < max_retries:
                    time.sleep(2)
                else:
                    break
    return []


def merge_overlapping_clips(clips: list[dict], threshold_sec: float = 6.0) -> list[dict]:
    """Deduplicate clips that start within threshold_sec of each other."""
    unique: list[dict] = []
    for candidate in clips:
        cand_start = ts_to_sec(candidate["start"])
        duplicate = False
        for existing in unique:
            ex_start = ts_to_sec(existing["start"])
            if abs(cand_start - ex_start) < threshold_sec:
                duplicate = True
                # Keep whichever has the higher virality score
                if candidate.get("virality_score", 0) > existing.get("virality_score", 0):
                    existing.update(candidate)
                break
        if not duplicate:
            unique.append(candidate)
    return unique


def find_viral_clips(
    segments: list[dict],
    api_key: str,
    model: str = "qwen/qwen3.8-27b",
    chunk_minutes: int = 5,
    min_duration: int = 30,
    max_duration: int = 60,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> list[dict]:
    """
    Scan full transcript, chunk into context windows, evaluate with Groq AI,
    and return ranked list of viral clips with full spoken transcript text attached.
    """
    if not api_key:
        raise ValueError("Groq API Key is required for AI viral hook detection.")

    client = Groq(api_key=api_key)
    chunk_seconds = chunk_minutes * 60
    
    # Split segments into chunks
    from .audio import chunk_segments
    chunks = chunk_segments(segments, chunk_seconds)

    if progress_callback:
        progress_callback(f"Divided video into {len(chunks)} chunk(s). Evaluating viral hooks with {model}…")

    all_clips: list[dict] = []
    for i, chunk in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(f"Analyzing chunk {i}/{len(chunks)} with Groq AI…")
        clips = call_groq_chunk(
            client=client,
            segments=chunk,
            model=model,
            min_duration=min_duration,
            max_duration=max_duration,
        )
        if clips:
            all_clips = merge_overlapping_clips(all_clips + clips)

    # Sort chronologically
    all_clips.sort(key=lambda c: ts_to_sec(c["start"]))

    # Populate exact spoken transcript text for each clip range
    for clip in all_clips:
        c_start = ts_to_sec(clip["start"])
        c_end = ts_to_sec(clip["end"])
        spoken_tokens = []
        for s in segments:
            # Overlap check
            if s["start"] < c_end and s["end"] > c_start:
                spoken_tokens.append(s["text"].strip())
        if spoken_tokens:
            clip["text"] = " ".join(spoken_tokens)

    return all_clips

