"""
services/audio.py — Audio extraction service.

Uses FFmpeg to extract audio from video files (MP4, MOV, M4A)
and produce a normalized mono 16 kHz .wav file ready for Faster-Whisper.

Pipeline position: Upload → Validate → [Extract Audio] → Transcribe
Phase 1: full implementation.
"""

import subprocess
import logging
import os

logger = logging.getLogger("meeting_analyzer.audio")

# Extensions that Faster-Whisper can ingest directly (no FFmpeg extraction needed)
_AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}
# Extensions that are video containers — audio must be extracted first
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


def extract_audio(input_path: str, output_path: str) -> str:
    """
    If *input_path* is a video file, extract the audio track via FFmpeg and
    write a mono 16 kHz PCM WAV to *output_path*.

    If *input_path* is already an audio file it is still re-encoded to a
    normalized mono 16 kHz WAV so Faster-Whisper always receives a consistent
    format regardless of source codec.

    Args:
        input_path:  Absolute path to the uploaded media file.
        output_path: Desired absolute path for the resulting .wav file.
                     The directory must already exist.

    Returns:
        The path to the resulting .wav file (== output_path on success).

    Raises:
        FileNotFoundError: if *input_path* does not exist.
        RuntimeError:      if FFmpeg is not found or exits with a non-zero code.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    ext = os.path.splitext(input_path)[1].lower()
    if ext not in _AUDIO_EXTENSIONS and ext not in _VIDEO_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension '{ext}'. "
            f"Supported: {_AUDIO_EXTENSIONS | _VIDEO_EXTENSIONS}"
        )

    logger.info("Extracting/normalizing audio: %s → %s", input_path, output_path)

    # FFmpeg flags:
    #   -y              overwrite output without prompting
    #   -i              input file
    #   -vn             drop video stream (no-op for audio files)
    #   -ac 1           mix down to mono
    #   -ar 16000       resample to 16 kHz (Whisper's preferred rate)
    #   -acodec pcm_s16le  linear PCM — universally supported WAV codec
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-acodec", "pcm_s16le",
        output_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10-minute timeout for long recordings
        )
    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg not found. Install FFmpeg and make sure it is on the system PATH."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("FFmpeg timed out after 10 minutes — recording too long?")

    if result.returncode != 0:
        logger.error("FFmpeg stderr:\n%s", result.stderr)
        raise RuntimeError(
            f"FFmpeg failed (exit {result.returncode}).\n"
            f"Stderr: {result.stderr[-1000:]}"  # last 1 kB to avoid log spam
        )

    logger.info("Audio ready: %s", output_path)
    return output_path
