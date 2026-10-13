"""
backend/scripts/test_diarization.py — Diarization unit and integration tests.

Tests:
  1. Alignment logic (pure unit, no model required)
  2. Speaker metadata builder
  3. Display name rename (API-level, no model)
  4. Diarization service disabled path
  5. Over-segmentation regression: baseline.json (3 actual speakers)
     — verifies the previous 8-speaker failure is not reproduced.
     — requires the audio file to be present; skipped otherwise.

Run:
    python -m unittest backend.scripts.test_diarization -v
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.services.diarization import (
    align_speakers,
    build_speaker_metadata,
    apply_display_names,
)


# ── 1. Alignment unit tests ───────────────────────────────────────────────────

class TestAlignment(unittest.TestCase):

    def _diar(self, intervals):
        return {"intervals": intervals, "speakers": list({iv["speaker"] for iv in intervals})}

    def test_exact_overlap(self):
        segs = [{"id": 0, "start": 0.0, "end": 2.0, "text": "Hello"}]
        diar = self._diar([{"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"}])
        result = align_speakers(segs, diar)
        self.assertEqual(result[0]["speaker_id"], "SPEAKER_00")

    def test_partial_overlap_above_threshold(self):
        # 1.5 s overlap out of 2.0 s segment = 75 % → assigned
        segs = [{"id": 0, "start": 0.0, "end": 2.0, "text": "Hello"}]
        diar = self._diar([{"start": 0.5, "end": 2.0, "speaker": "SPEAKER_01"}])
        result = align_speakers(segs, diar)
        self.assertEqual(result[0]["speaker_id"], "SPEAKER_01")

    def test_partial_overlap_below_threshold(self):
        # 0.4 s overlap out of 2.0 s segment = 20 % → None
        segs = [{"id": 0, "start": 0.0, "end": 2.0, "text": "Hello"}]
        diar = self._diar([{"start": 1.6, "end": 2.0, "speaker": "SPEAKER_00"}])
        result = align_speakers(segs, diar)
        self.assertIsNone(result[0]["speaker_id"])

    def test_no_overlap(self):
        segs = [{"id": 0, "start": 5.0, "end": 7.0, "text": "Silence gap"}]
        diar = self._diar([{"start": 0.0, "end": 3.0, "speaker": "SPEAKER_00"}])
        result = align_speakers(segs, diar)
        self.assertIsNone(result[0]["speaker_id"])

    def test_best_speaker_wins(self):
        segs = [{"id": 0, "start": 0.0, "end": 4.0, "text": "Mixed"}]
        diar = self._diar([
            {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"},  # 1 s
            {"start": 1.0, "end": 4.0, "speaker": "SPEAKER_01"},  # 3 s ← winner
        ])
        result = align_speakers(segs, diar)
        self.assertEqual(result[0]["speaker_id"], "SPEAKER_01")

    def test_text_preserved(self):
        segs = [{"id": 0, "start": 0.0, "end": 1.0, "text": "Keep this text"}]
        diar = self._diar([{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}])
        result = align_speakers(segs, diar)
        self.assertEqual(result[0]["text"], "Keep this text")

    def test_empty_diarization(self):
        segs = [{"id": 0, "start": 0.0, "end": 2.0, "text": "Hello"}]
        result = align_speakers(segs, {"intervals": [], "speakers": []})
        self.assertIsNone(result[0]["speaker_id"])


# ── 2. Speaker metadata ───────────────────────────────────────────────────────

class TestSpeakerMetadata(unittest.TestCase):

    def test_chronological_display_names(self):
        speakers = ["SPEAKER_02", "SPEAKER_00", "SPEAKER_01"]
        meta = build_speaker_metadata(speakers)
        self.assertEqual(meta["SPEAKER_02"]["display_name"], "Speaker 1")
        self.assertEqual(meta["SPEAKER_00"]["display_name"], "Speaker 2")
        self.assertEqual(meta["SPEAKER_01"]["display_name"], "Speaker 3")

    def test_order_field(self):
        speakers = ["SPEAKER_00", "SPEAKER_01"]
        meta = build_speaker_metadata(speakers)
        self.assertEqual(meta["SPEAKER_00"]["order"], 0)
        self.assertEqual(meta["SPEAKER_01"]["order"], 1)

    def test_apply_display_names(self):
        segs = [
            {"id": 0, "text": "Hi", "speaker_id": "SPEAKER_00", "speaker_name": None},
            {"id": 1, "text": "Hey", "speaker_id": None, "speaker_name": None},
        ]
        meta = {"SPEAKER_00": {"display_name": "Alice", "order": 0}}
        result = apply_display_names(segs, meta)
        self.assertEqual(result[0]["speaker_name"], "Alice")
        self.assertIsNone(result[1]["speaker_name"])


# ── 3. Disabled path ──────────────────────────────────────────────────────────

class TestDisabledDiarization(unittest.TestCase):

    def test_disabled_raises(self):
        import importlib
        import backend.services.diarization as mod
        original_enabled = mod._ENABLED
        original_pipeline = mod._pipeline
        original_error = mod._pipeline_error
        try:
            mod._ENABLED = False
            mod._pipeline = None
            mod._pipeline_error = None
            with self.assertRaises(RuntimeError):
                mod.get_pipeline()
        finally:
            mod._ENABLED = original_enabled
            mod._pipeline = original_pipeline
            mod._pipeline_error = original_error


# ── 4. Over-segmentation regression ──────────────────────────────────────────

BASELINE_PATH = Path(__file__).resolve().parents[2] / "data" / "validation" / "speakers" / "baseline.json"
MEETING_ID = "7e4062fd-e39e-45d9-960e-7addf54f769d"
WAV_PATH = Path(__file__).resolve().parents[2] / "data" / MEETING_ID / "audio.wav"


@unittest.skipUnless(WAV_PATH.exists(), "Audio file not present; skipping live diarization test")
class TestOverSegmentationRegression(unittest.TestCase):
    """
    Reproduces the previous failure: 3 actual speakers detected as 8.
    Passes if Community-1 detects ≤ 6 speakers (generous tolerance).
    The previous implementation detected 8 distinct SPEAKER_XX labels.
    """

    def test_speaker_count_not_over_segmented(self):
        from backend.services.diarization import run_diarization
        result = run_diarization(str(WAV_PATH))
        count = len(result["speakers"])
        print(f"\n[regression] Detected {count} speakers (previous failure: 8)")
        # The recording has 3 actual speakers. We allow up to 6 as a generous
        # tolerance for acoustic variation, but flag anything ≥ 7 as regression.
        self.assertLessEqual(
            count, 6,
            f"Over-segmentation regression: detected {count} speakers, expected ≤ 6 "
            f"(actual: 3). Previous failure was 8."
        )

    def test_alignment_covers_majority_of_segments(self):
        from backend.services.diarization import run_diarization, align_speakers
        if not BASELINE_PATH.exists():
            self.skipTest("baseline.json not present")
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        whisper_segs = baseline["whisper"]["segments"]
        raw = run_diarization(str(WAV_PATH))
        enriched = align_speakers(whisper_segs, raw)
        assigned = sum(1 for s in enriched if s.get("speaker_id") is not None)
        coverage = assigned / len(enriched) if enriched else 0
        print(f"\n[alignment] {assigned}/{len(enriched)} segments assigned ({coverage:.0%})")
        self.assertGreater(coverage, 0.5, "Less than 50% of segments received a speaker label")


if __name__ == "__main__":
    unittest.main(verbosity=2)
