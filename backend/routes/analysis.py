"""Stored transcript -> semantic analysis -> persistence and dashboard API."""
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.services.semantic import analyze_transcript
from backend.services.meeting_store import load_meeting, save_local, read_local

logger = logging.getLogger("meeting_analyzer.analysis")
router = APIRouter()
FAILURE_MESSAGE = "Meeting transcription completed, but analysis could not be generated. Please retry analysis."


def _get_db():
    try:
        from backend.db import get_client
        return get_client()
    except Exception:
        logger.warning("Database unavailable; using local meeting storage.")
        return None


def _valid_id(file_id):
    try:
        UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid meeting ID")


def _fetch_transcript(file_id):
    meeting = load_meeting(file_id, _get_db())
    if meeting is not None and "full_text" in meeting:
        return meeting["full_text"]
    from backend.services.meeting_store import path_for
    wav_path = path_for(file_id, "audio.wav")
    if not wav_path.exists():
        raise HTTPException(status_code=404, detail="Meeting transcript not found. Upload a recording first.")
    from backend.services.transcription import transcribe
    transcript = transcribe(str(wav_path))
    save_local(file_id, "transcript.json", transcript)
    return transcript["full_text"]


def _persist_analysis(file_id, payload):
    payload["topics"]["analysis_state"] = payload["analysis_state"]
    payload["topics"]["analysis_issues"] = payload["analysis_issues"]
    saved = False
    try:
        save_local(file_id, "analysis.json", payload)
        saved = True
    except (OSError, ValueError):
        logger.exception("Local analysis save failed for %s", file_id)
    db = _get_db()
    if db:
        row = {key: payload[key] for key in
               ("entities", "topics", "classifications", "action_items", "decisions", "questions")}
        row.update(id=file_id, summary_extractive=payload["summary"]["extractive"],
                   summary_abstractive="", analyzed_at=payload["analyzed_at"])
        try:
            db.table("analysis_results").upsert(row).execute()
            saved = True
        except Exception:
            logger.exception("Database analysis save failed for %s", file_id)
    if not saved:
        raise RuntimeError("Analysis could not be saved")


def _fetch_stored_analysis(file_id):
    local = read_local(file_id, "analysis.json")
    if local:
        local.setdefault("analysis_state", "legacy")
        return local
    db = _get_db()
    if db:
        try:
            row = db.table("analysis_results").select(
                "entities,topics,classifications,action_items,decisions,questions,"
                "summary_extractive,summary_abstractive,analyzed_at"
            ).eq("id", file_id).single().execute()
            if row.data:
                value = row.data
                value["summary"] = {"extractive": value.get("summary_extractive", ""),
                                    "abstractive": "", "preferred": "semantic"}
                value["intelligence"] = (value.get("topics") or {}).get("intelligence")
                value["analysis_state"] = (value.get("topics") or {}).get("analysis_state", "legacy")
                value["analysis_issues"] = (value.get("topics") or {}).get("analysis_issues", [])
                return value
        except Exception:
            logger.exception("Stored analysis lookup failed for %s", file_id)
    return None


def run_nlp_pipeline(transcript_text, abstractive_model=None, language="en", segments=None, duration=None):
    """Keep the existing entry point; the old model query is accepted for compatibility."""
    return analyze_transcript(transcript_text, segments, language, duration)


def _attempt(file_id, state):
    try:
        save_local(file_id, "analysis_state.json", {
            "state": state, "updated_at": datetime.now(timezone.utc).isoformat()})
    except OSError:
        logger.exception("Could not save analysis attempt state")


@router.post("/{file_id}", summary="Analyze a stored meeting with transcript-grounded semantic extraction")
def analyze(file_id: str, abstractive_model: str | None = Query(default=None, deprecated=True)):
    _valid_id(file_id)
    meeting = load_meeting(file_id, _get_db())
    if meeting is None:
        _fetch_transcript(file_id)
        meeting = load_meeting(file_id, _get_db()) or {}
    transcript = meeting.get("full_text", "")
    _attempt(file_id, "processing")
    try:
        result = run_nlp_pipeline(transcript, language=meeting.get("language") or "en",
                                  segments=meeting.get("segments"), duration=meeting.get("duration"))
        result.update(file_id=file_id, analyzed_at=datetime.now(timezone.utc).isoformat())
        _persist_analysis(file_id, result)
    except Exception:
        logger.exception("Meeting analysis failed for %s", file_id)
        _attempt(file_id, "failed")
        raise HTTPException(status_code=502, detail=FAILURE_MESSAGE)
    _attempt(file_id, result["analysis_state"])
    return JSONResponse(content=result)


@router.get("/{file_id}", summary="Retrieve the last saved meeting analysis and latest attempt state")
async def get_analysis(file_id: str):
    _valid_id(file_id)
    stored = _fetch_stored_analysis(file_id)
    attempt = read_local(file_id, "analysis_state.json")
    if stored is None:
        if attempt and attempt.get("state") == "failed":
            raise HTTPException(status_code=502, detail=FAILURE_MESSAGE)
        raise HTTPException(status_code=404, detail="No analysis yet. Analyze this meeting first.")
    return JSONResponse(content={**stored, "file_id": file_id, "analysis_attempt": attempt})
