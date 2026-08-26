"""
routes/analysis.py — Analysis pipeline endpoint.

Triggers the full NLP pipeline:
  preprocessing → NER → classification → topics →
  actions → decisions → summarization

Phase 2–3: full implementation.
Phase 0: stub only.
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/{file_id}")
async def analyze(file_id: str):
    """
    [STUB — Phase 2]
    Run the complete NLP pipeline on the stored transcript for file_id.
    Returns entities, topics, sentence classifications, action items,
    decisions, unresolved questions, and summaries.
    """
    return {"message": f"analysis stub for {file_id} — not yet implemented"}
