"""
routes/topics.py — Topic Segmentation & Evolution API endpoints.

GET  /api/topics/{file_id}          — retrieve saved topic analysis
POST /api/topics/{file_id}          — run (or re-run) topic segmentation
GET  /api/topics/{file_id}/evolution — per-meeting topic evolution
GET  /api/topics/cross-meeting       — cross-meeting topic comparison
"""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.services.meeting_store import read_local, save_local, load_meeting
from backend.services.topic_segmentation import analyze_topics

logger = logging.getLogger("meeting_analyzer.routes.topics")
router = APIRouter()


def _valid_id(file_id: str):
    try:
        UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid meeting ID")


def _get_db():
    try:
        from backend.db import get_client
        return get_client()
    except Exception:
        return None


def _load_transcript(file_id: str) -> tuple[str, list[dict]]:
    meeting = read_local(file_id, "transcript.json") or load_meeting(file_id, _get_db())
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting transcript not found. Upload a recording first.")
    return meeting.get("full_text", ""), meeting.get("segments") or []


def _load_analysis(file_id: str) -> dict:
    return read_local(file_id, "analysis.json") or {}


@router.post("/{file_id}", summary="Run topic segmentation for a meeting")
def run_topic_segmentation(file_id: str, force: bool = Query(default=False)):
    _valid_id(file_id)
    transcript, segments = _load_transcript(file_id)

    # Cache check: skip if transcript unchanged and result exists
    saved = read_local(file_id, "topic_segments.json")
    if not force and saved:
        from backend.services.topic_segmentation import _transcript_hash
        current_hash = _transcript_hash(transcript, segments)
        if saved.get("transcript_hash") == current_hash:
            logger.info("Topic segmentation cache hit for %s", file_id)
            return JSONResponse(content=saved)

    analysis = _load_analysis(file_id)
    try:
        result = analyze_topics(transcript, segments, analysis)
    except Exception:
        logger.exception("Topic segmentation failed for %s", file_id)
        raise HTTPException(status_code=502, detail="Topic segmentation failed. Please retry.")

    result["meeting_id"] = file_id
    save_local(file_id, "topic_segments.json", result)
    return JSONResponse(content=result)


@router.get("/{file_id}", summary="Retrieve saved topic analysis for a meeting")
def get_topic_segmentation(file_id: str):
    _valid_id(file_id)
    saved = read_local(file_id, "topic_segments.json")
    if not saved:
        raise HTTPException(status_code=404, detail="No topic analysis yet.")
    return JSONResponse(content=saved)


@router.get("/{file_id}/evolution", summary="Topic evolution within a single meeting")
def get_topic_evolution(file_id: str):
    _valid_id(file_id)
    saved = read_local(file_id, "topic_segments.json")
    if not saved:
        raise HTTPException(status_code=404, detail="No topic analysis yet. Run topic segmentation first.")
    return JSONResponse(content={
        "meeting_id": file_id,
        "evolution": saved.get("evolution", []),
        "canonical_topics": saved.get("canonical_topics", []),
    })


@router.get("/cross-meeting/compare", summary="Compare topics across all analyzed meetings")
def cross_meeting_topics(meeting_ids: str = Query(default="")):
    from backend.services.topic_evolution import cross_meeting_evolution
    ids = [mid.strip() for mid in meeting_ids.split(",") if mid.strip()] if meeting_ids else None
    try:
        result = cross_meeting_evolution(ids)
    except Exception:
        logger.exception("Cross-meeting topic evolution failed")
        raise HTTPException(status_code=502, detail="Cross-meeting analysis failed.")
    return JSONResponse(content=result)
