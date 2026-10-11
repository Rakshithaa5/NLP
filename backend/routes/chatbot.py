"""Current-meeting-only Ask This Meeting endpoint."""
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.chatbot import ChatbotError, ChatbotRateLimitError, ask_meeting
from backend.services.meeting_store import load_meeting, read_local

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=6)


def _meeting(file_id):
    try:
        UUID(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid meeting ID") from exc
    meeting = read_local(file_id, "transcript.json") or load_meeting(file_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting transcript not found.")
    return meeting


@router.post("/{file_id}", summary="Ask a question about the current meeting transcript")
def chat(file_id: str, request: ChatRequest):
    meeting = _meeting(file_id)
    history = [{"role": item.role, "content": item.content} for item in request.history
               if item.role in {"user", "assistant"} and item.content.strip()]
    try:
        return ask_meeting(meeting, request.question.strip(), history)
    except ChatbotRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc),
                            headers={"Retry-After": str(exc.retry_after)}) from exc
    except ChatbotError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc