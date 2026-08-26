"""
services/audio.py — Audio extraction service.

Uses FFmpeg to extract audio from video files (MP4, MOV, M4A)
and produce a normalized .wav file ready for Faster-Whisper.

Pipeline position: Upload → Validate → [Extract Audio] → Transcribe
Phase 1: full implementation.
Phase 0: stub only.
"""


def extract_audio(input_path: str, output_path: str) -> str:
    """
    [STUB — Phase 1]
    If input_path is a video file, use FFmpeg to extract audio to output_path (.wav).
    If input_path is already audio, convert/normalize to .wav.

    Returns the path to the resulting .wav file.
    """
    raise NotImplementedError("audio.extract_audio — implement in Phase 1")
