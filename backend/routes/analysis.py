"""Stored transcript -> semantic analysis -> persistence and dashboard API."""
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.services.semantic import analyze_transcript, ProviderError, GroqAnalyzer, transcript_units
from backend.services.consistency import manifest, same_pipeline, reconcile
from backend.services.meeting_store import load_meeting, save_local, read_local, analysis_lock, AnalysisInProgress

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
    meeting = read_local(file_id, "transcript.json") or load_meeting(file_id, _get_db())
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


def run_nlp_pipeline(transcript_text, abstractive_model=None, language="en", segments=None, duration=None, analyzer=None, meeting_id="transcript"):
    """Keep the existing entry point; the old model query is accepted for compatibility."""
    return analyze_transcript(transcript_text, segments, language, duration, analyzer, meeting_id)


def _attempt(file_id, state):
    try:
        save_local(file_id, "analysis_state.json", {
            "state": state, "updated_at": datetime.now(timezone.utc).isoformat()})
    except OSError:
        logger.exception("Could not save analysis attempt state")


@router.post("/{file_id}", summary="Analyze a stored meeting with transcript-grounded semantic extraction")
def analyze(file_id: str, abstractive_model: str | None = Query(default=None, deprecated=True), force: bool = False):
    _valid_id(file_id)
    try:
        with analysis_lock(file_id):
            return _analyze_locked(file_id, force)
    except AnalysisInProgress as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _analyze_locked(file_id, force):
    meeting = read_local(file_id, "transcript.json") or load_meeting(file_id, _get_db())
    if meeting is None:
        _fetch_transcript(file_id)
        meeting = read_local(file_id, "transcript.json") or load_meeting(file_id, _get_db()) or {}
    transcript = meeting.get("full_text", "")
    previous = _fetch_stored_analysis(file_id)
    _attempt(file_id, "processing")
    try:
        analyzer = GroqAnalyzer()
        units = transcript_units(transcript, meeting.get("segments") or [])
        segments = [{k: v for k, v in u.items() if k != "segment_id"} for u in units]
        transcript = " ".join(u["text"] for u in units)
        current = manifest(transcript, segments, meeting.get("language") or "en", analyzer)
        prior = ((previous or {}).get("intelligence") or {}).get("analysis_manifest", {})
        if not force and previous and previous.get("analysis_state") == "complete" and same_pipeline(prior, current):
            logger.info("Analysis cache hit meeting=%s input_hash=%s", file_id, current["input_hash"])
            _attempt(file_id, "complete")
            return JSONResponse(content=previous)
        save_local(file_id, "analysis_input.json", {"manifest": current, "segments": segments, "transcript": transcript})
        result = run_nlp_pipeline(transcript, language=meeting.get("language") or "en",
                                  segments=segments, duration=meeting.get("duration"), analyzer=analyzer, meeting_id=file_id)
        if previous:
            save_local(file_id, "analysis_previous.json", previous)
        save_local(file_id, "analysis_candidate.json", result)
        result = reconcile(previous, result, transcript, segments, file_id)
        result.update(file_id=file_id, analyzed_at=datetime.now(timezone.utc).isoformat())
        _persist_analysis(file_id, result)
    except ProviderError as exc:
        logger.warning("Meeting analysis provider unavailable for %s: %s", file_id, exc)
        _attempt(file_id, "failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
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
