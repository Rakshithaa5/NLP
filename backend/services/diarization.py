"""
services/diarization.py — Speaker diarization using pyannote/speaker-diarization-community-1.

Architecture:
  - Model loaded once as a module-level singleton; reused across all requests.
  - Diarization is strictly separate from NLP analysis: it enriches transcript
    segments with speaker metadata but never modifies the canonical text.
  - Two representations are maintained:
      A. Canonical transcript  — original text/timestamps, used by all NLP.
      B. Speaker-enriched      — same segments + speaker_id / speaker_name.
  - Alignment uses exclusive_speaker_diarization (no overlapping turns) so
    each Whisper segment gets exactly one speaker assignment.
  - Speaker IDs are stable internal keys (SPEAKER_00, SPEAKER_01, …).
    Display names ("Speaker 1", "Speaker 2", …) are assigned in chronological
    order of first appearance and stored separately so renaming never touches IDs.
"""

import logging
import os
import threading
from pathlib import Path
from typing import Optional

import torch

logger = logging.getLogger("meeting_analyzer.diarization")

# ── Configuration ─────────────────────────────────────────────────────────────
_MODEL_ID = os.getenv("DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1")
_DEVICE_ENV = os.getenv("DIARIZATION_DEVICE", "auto")  # "auto" | "cuda" | "cpu"
_ENABLED = os.getenv("DIARIZATION_ENABLED", "true").lower() not in {"false", "0", "no"}


def _get_hf_token() -> Optional[str]:
    """Read token at call time so load_dotenv() has already run."""
    return (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGINGFACE_TOKEN")
        or os.getenv("PYANNOTE_AUTH_TOKEN")
    )

# ── Singleton ─────────────────────────────────────────────────────────────────
_pipeline = None
_pipeline_lock = threading.Lock()
_pipeline_error: Optional[str] = None  # set if load failed permanently


def _resolve_device() -> str:
    if _DEVICE_ENV == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return _DEVICE_ENV


def get_pipeline():
    """Return the cached diarization pipeline, loading it on first call."""
    global _pipeline, _pipeline_error
    if not _ENABLED:
        raise RuntimeError("Diarization is disabled (DIARIZATION_ENABLED=false).")
    if _pipeline_error:
        raise RuntimeError(f"Diarization model failed to load: {_pipeline_error}")
    if _pipeline is not None:
        return _pipeline
    with _pipeline_lock:
        if _pipeline is not None:
            return _pipeline
        if _pipeline_error:
            raise RuntimeError(f"Diarization model failed to load: {_pipeline_error}")
        try:
            from pyannote.audio import Pipeline
            device = _resolve_device()
            logger.info("Loading diarization model '%s' on %s …", _MODEL_ID, device)
            token = _get_hf_token()
            if not token:
                raise ValueError(
                    "No HuggingFace token found. Set HF_TOKEN (or PYANNOTE_AUTH_TOKEN) in .env."
                )
            pipeline = Pipeline.from_pretrained(_MODEL_ID, token=token)
            pipeline.to(torch.device(device))
            _pipeline = pipeline
            logger.info("Diarization model loaded on %s.", device)
        except Exception as exc:
            _pipeline_error = str(exc)
            logger.error("Diarization model load failed: %s", exc)
            raise RuntimeError(f"Diarization model failed to load: {exc}") from exc
    return _pipeline


# ── Core diarization ──────────────────────────────────────────────────────────

def run_diarization(wav_path: str) -> dict:
    """
    Run pyannote Community-1 on *wav_path* and return raw intervals.

    Returns
    -------
    {
        "intervals": [{"start": float, "end": float, "speaker": str}, …],
        "speakers":  [str, …],          # unique speaker IDs in appearance order
        "model":     str,
    }
    """
    if not Path(wav_path).is_file():
        raise FileNotFoundError(f"Audio file not found: {wav_path}")

    pipeline = get_pipeline()
    logger.info("Running diarization on %s", wav_path)

    import soundfile as sf
    import torch
    data, sample_rate = sf.read(wav_path, dtype="float32", always_2d=True)
    # soundfile returns (time, channels) — pyannote needs (channels, time)
    waveform = torch.from_numpy(data.T)
    audio_input = {"waveform": waveform, "sample_rate": sample_rate}
    output = pipeline(audio_input)  # no num_speakers — fully automatic

    # Community-1 returns DiarizeOutput; fall back to plain Annotation
    from pyannote.audio.pipelines.speaker_diarization import DiarizeOutput
    if isinstance(output, DiarizeOutput):
        annotation = output.exclusive_speaker_diarization
    else:
        annotation = output  # legacy Annotation

    intervals = []
    seen: list[str] = []
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        if speaker not in seen:
            seen.append(speaker)
        intervals.append({"start": round(turn.start, 3), "end": round(turn.end, 3), "speaker": speaker})

    logger.info(
        "Diarization complete — %d intervals, %d speakers detected",
        len(intervals), len(seen),
    )
    return {"intervals": intervals, "speakers": seen, "model": _MODEL_ID}


# ── Alignment ─────────────────────────────────────────────────────────────────

def _overlap(a_start, a_end, b_start, b_end) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def align_speakers(whisper_segments: list[dict], diarization: dict) -> list[dict]:
    """
    Assign a speaker_id to each Whisper segment using overlap-maximisation.

    Rules:
    - For each segment, find the diarization interval with the greatest
      temporal overlap.
    - If no overlap exists (silence gap, very short segment), speaker_id = None.
    - Ambiguous segments (top overlap < 30 % of segment duration) → None.
    - Original text and timestamps are never modified.

    Returns a new list of segments with added keys:
        speaker_id   : str | None   (stable pyannote label, e.g. "SPEAKER_00")
        speaker_name : str | None   (display name, set later from metadata)
    """
    intervals = diarization.get("intervals", [])
    enriched = []
    for seg in whisper_segments:
        start, end = seg.get("start") or 0.0, seg.get("end") or 0.0
        duration = end - start
        best_speaker = None
        best_overlap = 0.0
        for iv in intervals:
            ov = _overlap(start, end, iv["start"], iv["end"])
            if ov > best_overlap:
                best_overlap = ov
                best_speaker = iv["speaker"]
        # Require at least 30 % overlap to assign confidently
        if duration > 0 and best_overlap / duration < 0.30:
            best_speaker = None
        enriched.append({**seg, "speaker_id": best_speaker, "speaker_name": None})
    return enriched


def build_speaker_metadata(speakers: list[str]) -> dict:
    """
    Build display-name mapping in chronological first-appearance order.

    Returns
    -------
    {
        "SPEAKER_00": {"display_name": "Speaker 1", "order": 0},
        "SPEAKER_01": {"display_name": "Speaker 2", "order": 1},
        …
    }
    """
    return {
        spk: {"display_name": f"Speaker {i + 1}", "order": i}
        for i, spk in enumerate(speakers)
    }


def apply_display_names(segments: list[dict], metadata: dict) -> list[dict]:
    """Populate speaker_name from metadata display names."""
    result = []
    for seg in segments:
        sid = seg.get("speaker_id")
        name = metadata.get(sid, {}).get("display_name") if sid else None
        result.append({**seg, "speaker_name": name})
    return result
