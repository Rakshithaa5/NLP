"""
services/transcription.py — Speech-to-text service.

Uses Faster-Whisper to transcribe a .wav audio file into a full
word-level and segment-level transcript.

Pipeline position: Extract Audio → [Transcribe] → NLP Preprocess
Phase 1: full implementation.
Phase 0: stub only.
"""


def transcribe(audio_path: str) -> dict:
    """
    [STUB — Phase 1]
    Run Faster-Whisper on audio_path.

    Returns a dict with:
      - "segments": list of {start, end, text} dicts
      - "full_text": complete transcript as a single string
      - "language": detected language code
    """
    raise NotImplementedError("transcription.transcribe — implement in Phase 1")
