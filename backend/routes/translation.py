"""Translate display text without changing the stored meeting."""
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from backend.services.meeting_store import load_meeting, read_local
from backend.services.translation import translate_texts, TranslationError
from backend.services.semantic import RateLimitError

router = APIRouter()


class TranslationRequest(BaseModel):
    texts: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def bounded(self):
        if sum(len(t.encode("utf-8")) for t in self.texts) > 10000:
            raise ValueError("Translation batch exceeds 10000 UTF-8 bytes")
        if any(not t.strip() for t in self.texts):
            raise ValueError("Translation texts must not be blank")
        return self


@router.post("/{file_id}")
def translate(file_id: str, request: TranslationRequest):
    try:
        UUID(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid meeting ID") from exc
    from backend.routes.analysis import _get_db
    if not (read_local(file_id, "transcript.json") or load_meeting(file_id, _get_db())):
        raise HTTPException(status_code=404, detail="Meeting not found.")
    try:
        return {"translations": translate_texts(file_id, request.texts), "language": "en"}
    except RateLimitError as exc:
        raise HTTPException(status_code=429, detail="Translation rate limit reached. Please retry after the cooldown.",
                            headers={"Retry-After": str(exc.retry_after)}) from exc
    except TranslationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
