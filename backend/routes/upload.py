"""
routes/upload.py — File upload + transcript pipeline endpoint.

Phase 1 implementation:
  POST /api/upload/           — receive, validate, store file, run audio+transcription pipeline
  GET  /api/upload/{file_id}  — return stored transcript + metadata for a given meeting ID

Pipeline order enforced here:
  Receive → Validate → Save → Extract Audio (FFmpeg) → Transcribe (Faster-Whisper) → Persist → Return
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from backend.services.audio import extract_audio
from backend.services.transcription import transcribe

logger = logging.getLogger("meeting_analyzer.upload")

router = APIRouter()

# ── Configuration ─────────────────────────────────────────────────────────────
# Absolute path to the data directory (project-root/data/)
_DATA_DIR = Path(os.getenv("DATA_DIR", "data")).resolve()
_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Maximum allowed upload size: 500 MB
_MAX_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(500 * 1024 * 1024)))

# Accepted MIME types and their corresponding extensions
_ALLOWED_TYPES: dict[str, str] = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/x-m4a": ".m4a",
    "audio/mp4": ".m4a",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "application/octet-stream": "",  # pass-through; extension validated separately
}
_ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".mov"}


def _get_db():
    """Return Supabase client or None if not configured (graceful degradation)."""
    try:
        from backend.db import get_client
        return get_client()
    except Exception as exc:
        logger.warning("DB unavailable — running without persistence: %s", exc)
        return None


def _validate_file(file: UploadFile) -> str:
    """
    Validate MIME type and file extension.
    Returns the canonical extension (e.g. '.mp4').
    Raises HTTPException(415) on unsupported type.
    """
    content_type = (file.content_type or "").lower().split(";")[0].strip()
    original_name = file.filename or ""
    ext = Path(original_name).suffix.lower()

    # Check extension first (most reliable for browser uploads)
    if ext not in _ALLOWED_EXTENSIONS:
        if content_type not in _ALLOWED_TYPES:
            raise HTTPException(
                status_code=415,
                detail=(
                    f"Unsupported file type '{ext or content_type}'. "
                    f"Accepted: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
                ),
            )
        ext = _ALLOWED_TYPES[content_type] or ext

    return ext


# ── POST /api/upload/ ─────────────────────────────────────────────────────────
@router.post("/", summary="Upload a meeting recording and get back a transcript")
async def upload_file(file: UploadFile = File(...)):
    """
    Accept an audio/video file (MP4, MP3, WAV, M4A, MOV), validate it,
    save to data/, extract audio via FFmpeg, transcribe with Faster-Whisper,
    persist metadata + transcript to Supabase, and return the result.

    Returns:
        JSON with keys: file_id, filename, duration, language, segments, full_text
    """
    # 1. Validate type ──────────────────────────────────────────────────────────
    ext = _validate_file(file)

    # 2. Stream to disk with size check ────────────────────────────────────────
    file_id = str(uuid.uuid4())
    upload_dir = _DATA_DIR / file_id
    upload_dir.mkdir(parents=True)

    original_filename = file.filename or f"recording{ext}"
    raw_path = upload_dir / f"raw{ext}"
    wav_path = upload_dir / "audio.wav"

    logger.info("Saving upload [%s] → %s", file_id, raw_path)

    total_bytes = 0
    try:
        with open(raw_path, "wb") as fp:
            chunk_size = 1024 * 1024  # 1 MB chunks
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > _MAX_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum size of {_MAX_BYTES // (1024**2)} MB.",
                    )
                fp.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to save upload: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")

    logger.info("Upload saved — %d bytes", total_bytes)

    # 3. Extract audio (FFmpeg) ─────────────────────────────────────────────────
    try:
        extract_audio(str(raw_path), str(wav_path))
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=f"Audio extraction failed: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error in audio extraction: %s", exc)
        raise HTTPException(status_code=500, detail=f"Audio extraction error: {exc}")

    # 4. Transcribe (Faster-Whisper) ────────────────────────────────────────────
    try:
        transcript = transcribe(str(wav_path))
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=f"Transcription failed: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error in transcription: %s", exc)
        raise HTTPException(status_code=500, detail=f"Transcription error: {exc}")

    # 5. Persist to Supabase ────────────────────────────────────────────────────
    upload_ts = datetime.now(timezone.utc).isoformat()
    # Column names match the Supabase schema:
    #   duration_sec  (REAL)  ← NOT "duration"
    #   transcript    (TEXT)  ← full text blob
    #   status CHECK constraint accepts: uploaded | processing | done | error
    meeting_row = {
        "id":           file_id,
        "filename":     original_filename,
        "file_path":    str(raw_path),
        "duration_sec": transcript["duration"],
        "language":     transcript["language"],
        "transcript":   transcript["full_text"],
        "uploaded_at":  upload_ts,
        "status":       "done",
    }

    db = _get_db()
    if db:
        try:
            db.table("meetings").insert(meeting_row).execute()
            logger.info("Meeting [%s] persisted to Supabase.", file_id)

            # Persist individual segments to transcript_segments table
            if transcript["segments"]:
                segment_rows = [
                    {
                        "meeting_id": file_id,
                        "start_sec":  seg["start"],
                        "end_sec":    seg["end"],
                        "text":       seg["text"],
                    }
                    for seg in transcript["segments"]
                ]
                db.table("transcript_segments").insert(segment_rows).execute()
                logger.info("Inserted %d segments for [%s].", len(segment_rows), file_id)

        except Exception as exc:
            logger.warning("Supabase insert failed (continuing without DB): %s", exc)

    # 6. Return — shape matches what TranscriptPreview.jsx expects ───────────────
    return JSONResponse(
        status_code=200,
        content={
            "file_id":     file_id,
            "filename":    original_filename,
            "duration":    transcript["duration"],   # frontend key stays "duration"
            "language":    transcript["language"],
            "segments":    transcript["segments"],
            "full_text":   transcript["full_text"],
            "uploaded_at": upload_ts,
        },
    )


# ── GET /api/upload/{file_id} ─────────────────────────────────────────────────
@router.get("/{file_id}", summary="Retrieve stored transcript for a meeting")
async def get_transcript(file_id: str):
    """
    Return the stored transcript and metadata for a given meeting ID.
    Reconstructs the frontend-expected shape from the Supabase schema:
      meetings.duration_sec  → response.duration
      meetings.transcript    → response.full_text
      transcript_segments.*  → response.segments
    Falls back to local disk re-transcription if DB is unavailable.
    """
    db = _get_db()
    if db:
        try:
            row = (
                db.table("meetings")
                .select("id, filename, duration_sec, language, transcript, uploaded_at, status")
                .eq("id", file_id)
                .single()
                .execute()
            )
            if row.data:
                # Fetch segments from child table
                segs_resp = (
                    db.table("transcript_segments")
                    .select("start_sec, end_sec, text")
                    .eq("meeting_id", file_id)
                    .order("start_sec")
                    .execute()
                )
                segments = [
                    {"start": s["start_sec"], "end": s["end_sec"], "text": s["text"]}
                    for s in (segs_resp.data or [])
                ]
                m = row.data
                return JSONResponse(content={
                    "file_id":     m["id"],
                    "filename":    m["filename"],
                    "duration":    m["duration_sec"],   # normalise to frontend key
                    "language":    m["language"],
                    "full_text":   m["transcript"],
                    "segments":    segments,
                    "uploaded_at": m["uploaded_at"],
                    "status":      m["status"],
                })
        except Exception as exc:
            logger.warning("DB lookup failed, trying disk: %s", exc)

    # Fallback: serve from local file store (re-transcribe from saved WAV)
    wav_path = _DATA_DIR / file_id / "audio.wav"
    if not wav_path.exists():
        raise HTTPException(status_code=404, detail=f"Meeting '{file_id}' not found.")

    try:
        transcript = transcribe(str(wav_path))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read transcript: {exc}")

    return JSONResponse(
        content={
            "file_id":   file_id,
            "duration":  transcript["duration"],
            "language":  transcript["language"],
            "segments":  transcript["segments"],
            "full_text": transcript["full_text"],
        }
    )


# ── GET /api/upload/ (list all meetings) ─────────────────────────────────────
@router.get("/", summary="List all uploaded meetings")
async def list_meetings():
    """Return a list of all uploaded meetings (id, filename, duration, uploaded_at)."""
    db = _get_db()
    if db:
        try:
            resp = (
                db.table("meetings")
                .select("id, filename, duration_sec, language, uploaded_at, status")
                .order("uploaded_at", desc=True)
                .execute()
            )
            # Normalise duration_sec → duration for frontend consistency
            meetings = [
                {**m, "duration": m.pop("duration_sec")}
                for m in (resp.data or [])
            ]
            return JSONResponse(content={"meetings": meetings})
        except Exception as exc:
            logger.warning("DB list failed: %s", exc)

    return JSONResponse(content={"meetings": [], "warning": "Database unavailable"})
