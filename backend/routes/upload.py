"""
routes/upload.py — File upload endpoint.

Receives audio/video files from the frontend, validates them,
and persists them to data/ for downstream processing.

Phase 1: full implementation.
Phase 0: stub only.
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/")
async def upload_file():
    """
    [STUB — Phase 1]
    Accept an audio/video file (MP4, MP3, WAV, M4A, MOV),
    validate type/size, save to data/, return a job/file ID.
    """
    return {"message": "upload stub — not yet implemented"}
