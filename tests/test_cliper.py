"""
Unit tests for Cliper AI package.
"""

import pytest
from pathlib import Path
from cliper.audio import ts_to_sec, sec_to_ts, normalise_ts, sanitize_filename
from cliper.ai import parse_clips_json, merge_overlapping_clips
from cliper.config import Config


def test_timestamp_conversions():
    assert ts_to_sec("00:01:30") == 90.0
    assert ts_to_sec("01:30") == 90.0
    assert ts_to_sec("45") == 45.0
    assert sec_to_ts(90.0) == "00:01:30"
    assert normalise_ts("1:30") == "00:01:30"


def test_sanitize_filename():
    sanitized = sanitize_filename("https://youtube.com/watch?v=123")
    assert "watch_v_123" in sanitized
    assert sanitize_filename("AI <Life> & *Tricks*") == "AI _Life_ _ _Tricks"


def test_parse_clips_json():
    raw_json = """
    ```json
    [
      {
        "start": "00:00:10",
        "end": "00:00:45",
        "title": "Insane AI Feature",
        "hook": "Wait until you see this",
        "virality_score": 95,
        "category": "Insight"
      }
    ]
    ```
    """
    clips = parse_clips_json(raw_json)
    assert len(clips) == 1
    assert clips[0]["title"] == "Insane AI Feature"
    assert clips[0]["virality_score"] == 95
    assert clips[0]["start"] == "00:00:10"


def test_merge_overlapping_clips():
    clips = [
        {"start": "00:01:00", "end": "00:01:35", "title": "Clip A", "virality_score": 85},
        {"start": "00:01:02", "end": "00:01:40", "title": "Clip B", "virality_score": 92},
        {"start": "00:05:00", "end": "00:05:40", "title": "Clip C", "virality_score": 88},
    ]
    merged = merge_overlapping_clips(clips, threshold_sec=5.0)
    assert len(merged) == 2
    # Should keep highest virality score for overlapping
    assert merged[0]["title"] == "Clip B"
    assert merged[0]["virality_score"] == 92


def test_config_defaults():
    cfg = Config()
    assert cfg.target_width == 1080
    assert cfg.target_height == 1920
    assert cfg.min_clip_duration == 30
    assert cfg.max_clip_duration == 60
