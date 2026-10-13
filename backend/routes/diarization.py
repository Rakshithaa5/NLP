"""
routes/diarization.py — Speaker diarization endpoints.

POST /api/diarization/{file_id}          — run (or re-run) diarization
GET  /api/diarization/{file_id}          — retrieve saved diarization result
POST /api/diarization/{file_id}/rename   — update a speaker display name
DELETE /api/diarization/{file_id}        — clear saved result (force re-run)

Design:
  - Diarization is independent of NLP analysis. Running or re-running it
    never touches analysis.json, summaries, or any NLP output.
  - The canonical transcript (transcript.json) is never modified.
  - Speaker-enriched segments are stored in diarization.json alongside the
    original transcript.
  - Failed diarization returns a structured error; the original transcript
    remains fully accessible.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.services.meeting_store import read_local, save_local, path_for

logger = logging.getLogger("meeting_analyzer.diarization")
router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _valid_id(file_id: str):
    try:
        UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid meeting ID")


def _wav_path(file_id: str):
    p = path_for(file_id, "audio.wav")
    if not p.exists():
        raise HTTPException(
            status_code=404,
            detail="Audio file not found. Upload a recording first.",
        )
    return str(p)


def _load_transcript_segments(file_id: str) -> list[dict]:
    meeting = read_local(file_id, "transcript.json")
    if not meeting:
        raise HTTPException(
            status_code=404,
            detail="Transcript not found. Upload and transcribe a recording first.",
        )
    return meeting.get("segments") or []


# ── POST /api/diarization/{file_id} ──────────────────────────────────────────

@router.post("/{file_id}", summary="Run speaker diarization for a meeting")
def run_diarization(file_id: str, force: bool = False):
    """
    Run pyannote Community-1 diarization on the stored audio.

    - Does NOT re-transcribe audio.
    - Does NOT regenerate summaries or NLP analysis.
    - Returns speaker-enriched segments alongside the original transcript.
    - If diarization fails, returns HTTP 502 with a structured error; the
      original transcript is unaffected.
    """
    _valid_id(file_id)

    # Cache check
    if not force:
        saved = read_local(file_id, "diarization.json")
        if saved and saved.get("state") == "complete":
            logger.info("Diarization cache hit for %s", file_id)
            return JSONResponse(content=saved)

    wav = _wav_path(file_id)
    segments = _load_transcript_segments(file_id)

    try:
        from backend.services.diarization import (
            run_diarization as _run,
            align_speakers,
            build_speaker_metadata,
            apply_display_names,
        )
        raw = _run(wav)
        enriched = align_speakers(segments, raw)
        metadata = build_speaker_metadata(raw["speakers"])
        enriched = apply_display_names(enriched, metadata)

        result = {
            "state": "complete",
            "file_id": file_id,
            "model": raw["model"],
            "speaker_count": len(raw["speakers"]),
            "speakers": metadata,
            "segments": enriched,
            "diarized_at": datetime.now(timezone.utc).isoformat(),
            "error": None,
        }
        save_local(file_id, "diarization.json", result)
        logger.info(
            "Diarization saved for %s — %d speakers", file_id, len(raw["speakers"])
        )
        return JSONResponse(content=result)

    except RuntimeError as exc:
        error_msg = str(exc)
        logger.warning("Diarization failed for %s: %s", file_id, error_msg)
        # Preserve any previous successful result; save failure state separately
        failure = {
            "state": "failed",
            "file_id": file_id,
            "error": error_msg,
            "diarized_at": datetime.now(timezone.utc).isoformat(),
        }
        save_local(file_id, "diarization_failure.json", failure)
        raise HTTPException(status_code=502, detail=error_msg)
    except Exception as exc:
        logger.exception("Unexpected diarization error for %s", file_id)
        raise HTTPException(
            status_code=502,
            detail=f"Speaker diarization failed unexpectedly: {exc}",
        )


# ── GET /api/diarization/{file_id} ───────────────────────────────────────────

@router.get("/{file_id}", summary="Retrieve saved diarization result")
def get_diarization(file_id: str):
    _valid_id(file_id)
    saved = read_local(file_id, "diarization.json")
    if not saved:
        # Return a structured "not run" response rather than 404 so the
        # frontend can distinguish "never run" from "failed".
        return JSONResponse(
            content={"state": "none", "file_id": file_id},
            status_code=200,
        )
    return JSONResponse(content=saved)


# ── POST /api/diarization/{file_id}/rename ────────────────────────────────────

class RenameRequest(BaseModel):
    speaker_id: str
    display_name: str


@router.post("/{file_id}/rename", summary="Rename a speaker display name")
def rename_speaker(file_id: str, body: RenameRequest):
    """
    Update the display name for a speaker.

    - The stable speaker_id (e.g. SPEAKER_00) is never changed.
    - Only the display_name shown in the UI is updated.
    - Segments are updated in-place in the stored diarization result.
    """
    _valid_id(file_id)
    saved = read_local(file_id, "diarization.json")
    if not saved or saved.get("state") != "complete":
        raise HTTPException(
            status_code=404,
            detail="No completed diarization found. Run diarization first.",
        )

    speaker_id = body.speaker_id
    new_name = body.display_name.strip()
    if not new_name:
        raise HTTPException(status_code=422, detail="Display name cannot be empty.")
    if len(new_name) > 80:
        raise HTTPException(status_code=422, detail="Display name too long (max 80 chars).")

    speakers = saved.get("speakers") or {}
    if speaker_id not in speakers:
        raise HTTPException(
            status_code=404,
            detail=f"Speaker '{speaker_id}' not found in this meeting.",
        )

    # Update metadata
    speakers[speaker_id]["display_name"] = new_name

    # Update all segments that reference this speaker
    for seg in saved.get("segments") or []:
        if seg.get("speaker_id") == speaker_id:
            seg["speaker_name"] = new_name

    save_local(file_id, "diarization.json", saved)
    logger.info("Renamed %s → '%s' for meeting %s", speaker_id, new_name, file_id)
    return JSONResponse(content={"ok": True, "speaker_id": speaker_id, "display_name": new_name})


# ── DELETE /api/diarization/{file_id} ────────────────────────────────────────

@router.delete("/{file_id}", summary="Clear saved diarization result")
def clear_diarization(file_id: str):
    _valid_id(file_id)
    p = path_for(file_id, "diarization.json")
    if p.exists():
        p.unlink()
    return JSONResponse(content={"ok": True, "file_id": file_id})
