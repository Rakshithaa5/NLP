"""
services/transcription.py — Speech-to-text service.

Uses Faster-Whisper (CTranslate2 backend) to transcribe a .wav audio file into
a full word-level and segment-level transcript.

Pipeline position: Extract Audio → [Transcribe] → NLP Preprocess
Phase 1: full implementation.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger("meeting_analyzer.transcription")

# Model size is configurable via env; "base" is fast enough for demos and keeps
# RAM usage low. Upgrade to "small" or "medium" for higher accuracy.
_DEFAULT_MODEL = os.getenv("WHISPER_MODEL_SIZE", "base")
_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")          # "cpu" or "cuda"
_COMPUTE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")  # "int8", "float16", "float32"

# Module-level singleton so the model is loaded only once per worker process.
_model = None


def _get_model():
    """Lazily load and cache the Faster-Whisper model."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel  # imported lazily to avoid slow startup

        logger.info(
            "Loading Faster-Whisper model '%s' on device=%s compute=%s …",
            _DEFAULT_MODEL,
            _DEVICE,
            _COMPUTE,
        )
        _model = WhisperModel(_DEFAULT_MODEL, device=_DEVICE, compute_type=_COMPUTE)
        logger.info("Faster-Whisper model loaded.")
    return _model


def transcribe(audio_path: str, language: Optional[str] = None) -> dict:
    """
    Run Faster-Whisper on *audio_path* and return a structured transcript.

    Args:
        audio_path: Absolute path to a .wav (or other audio) file.
        language:   Optional BCP-47 language code (e.g. "en") to skip
                    language detection and speed up transcription.

    Returns:
        A dict with the following keys:
            "segments"  — list of {start (s), end (s), text} dicts, one per
                          detected speech segment.
            "full_text" — the complete transcript as a single string
                          (segments joined by a space).
            "language"  — detected (or forced) language code string.
            "duration"  — total audio duration in seconds (float).

    Raises:
        FileNotFoundError: if *audio_path* does not exist.
        RuntimeError:      if Faster-Whisper is unavailable or transcription fails.
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    logger.info("Transcribing: %s (language=%s)", audio_path, language or "auto-detect")

    try:
        model = _get_model()
        segments_iter, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True,          # voice-activity detection — skips silences
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        segments = []
        for seg in segments_iter:
            segments.append(
                {
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "text": seg.text.strip(),
                }
            )
            logger.debug("[%.1fs → %.1fs] %s", seg.start, seg.end, seg.text.strip())

    except Exception as exc:
        logger.exception("Transcription failed: %s", exc)
        raise RuntimeError(f"Transcription failed: {exc}") from exc

    full_text = " ".join(s["text"] for s in segments)
    duration = round(info.duration, 3)

    logger.info(
        "Transcription complete — %d segments, %.1f s, language=%s",
        len(segments),
        duration,
        info.language,
    )

    return {
        "segments": segments,
        "full_text": full_text,
        "language": info.language,
        "duration": duration,
    }
