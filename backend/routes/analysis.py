"""
routes/analysis.py — Analysis pipeline endpoint.

Triggers the full NLP pipeline in the fixed order defined by the implementation plan:
  preprocessing → NER → classification → topics

POST /api/analysis/{file_id}
  Fetches the stored transcript for file_id, runs the pipeline,
  persists results to Supabase, and returns the full analysis payload.

GET /api/analysis/{file_id}
  Returns the previously stored analysis results for file_id.

Phase 2: full implementation (preprocessing, NER, classification, topics).
Phase 3: will extend with actions, decisions, questions, summarization.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.services.preprocessing import preprocess
from backend.services.ner import extract_entities
from backend.services.classification import classify_sentences
from backend.services.topics import extract_topics

logger = logging.getLogger("meeting_analyzer.analysis")

router = APIRouter()


# ── DB helper (mirrors pattern in routes/upload.py) ───────────────────────────

def _get_db():
    """Return Supabase client or None if not configured (graceful degradation)."""
    try:
        from backend.db import get_client  # noqa: PLC0415
        return get_client()
    except Exception as exc:
        logger.warning("DB unavailable — running without persistence: %s", exc)
        return None


def _fetch_transcript(file_id: str) -> str:
    """
    Retrieve the raw transcript text for *file_id* from Supabase.
    Raises HTTPException(404) if the meeting or transcript is not found.
    """
    db = _get_db()
    if db:
        try:
            row = (
                db.table("meetings")
                .select("transcript, status")
                .eq("id", file_id)
                .single()
                .execute()
            )
            if row.data:
                transcript_text = row.data.get("transcript", "")
                if transcript_text:
                    return transcript_text
        except Exception as exc:
            logger.warning("DB transcript fetch failed: %s", exc)

    raise HTTPException(
        status_code=404,
        detail=f"Transcript for meeting '{file_id}' not found. "
               "Ensure the meeting has been uploaded and transcribed first.",
    )


def _persist_analysis(file_id: str, payload: dict) -> None:
    """
    Upsert analysis results into the `analysis_results` table in Supabase.
    Fails silently so a DB outage does not break the API response.

    Table schema (create in Supabase dashboard or via migration):
      id           TEXT PRIMARY KEY REFERENCES meetings(id)
      entities     JSONB
      topics       JSONB
      classifications JSONB
      analyzed_at  TIMESTAMPTZ
    """
    db = _get_db()
    if not db:
        return

    row = {
        "id":               file_id,
        "entities":         payload["entities"],
        "topics":           payload["topics"],
        "classifications":  payload["classifications"],
        "analyzed_at":      datetime.now(timezone.utc).isoformat(),
    }
    try:
        db.table("analysis_results").upsert(row).execute()
        logger.info("Analysis results persisted for meeting [%s].", file_id)
    except Exception as exc:
        logger.warning("Failed to persist analysis results: %s", exc)


def _fetch_stored_analysis(file_id: str) -> dict | None:
    """
    Return previously stored analysis results, or None if not found.
    """
    db = _get_db()
    if not db:
        return None
    try:
        row = (
            db.table("analysis_results")
            .select("entities, topics, classifications, analyzed_at")
            .eq("id", file_id)
            .single()
            .execute()
        )
        if row.data:
            return row.data
    except Exception as exc:
        logger.warning("Could not fetch stored analysis: %s", exc)
    return None


# ── Pipeline runner ────────────────────────────────────────────────────────────

def run_nlp_pipeline(transcript_text: str) -> dict:
    """
    Execute the Phase 2 NLP pipeline in the fixed order:
      preprocess → NER → classify_sentences → extract_topics

    Args:
        transcript_text: Raw transcript string.

    Returns:
        Dict with keys:
          "sentences"       — segmented sentence strings
          "entities"        — NER results
          "classifications" — per-sentence labels + confidence
          "topics"          — TF-IDF keywords + LDA/NMF topic clusters
    """
    # Step 1: Preprocessing (spaCy + NLTK)
    logger.info("Running preprocessing …")
    preprocessed = preprocess(transcript_text)
    sentences = preprocessed["sentences"]
    doc       = preprocessed["doc"]

    # Step 2: NER (spaCy EntityRuler + statistical NER)
    logger.info("Running NER …")
    entities = extract_entities(doc)

    # Step 3: Sentence classification (TF-IDF + Logistic Regression)
    logger.info("Running sentence classification …")
    classifications = classify_sentences(sentences)

    # Step 4: Topic extraction (TF-IDF keywords + LDA topic modeling)
    logger.info("Running topic extraction …")
    topics = extract_topics(sentences, n_topics=5)

    return {
        "sentences":       sentences,
        "entities":        entities,
        "classifications": classifications,
        "topics":          topics,
    }


# ── POST /api/analysis/{file_id} ──────────────────────────────────────────────

@router.post(
    "/{file_id}",
    summary="Run NLP analysis pipeline on a stored meeting transcript",
)
async def analyze(file_id: str):
    """
    Run the full Phase 2 NLP pipeline on the transcript stored for *file_id*.

    Pipeline stages (in fixed order per implementation plan):
      1. Preprocessing   — spaCy sentence segmentation, tokenization,
                           lemmatization, stop-word removal (NLTK + spaCy)
      2. NER             — spaCy EntityRuler + statistical NER
      3. Classification  — TF-IDF + Logistic Regression per sentence
      4. Topic modeling  — TF-IDF keywords + LDA topic clusters

    Returns JSON with keys:
      file_id, sentences, entities, classifications, topics, analyzed_at
    """
    logger.info("Analysis requested for meeting [%s]", file_id)

    # Fetch transcript from DB (raises 404 if missing)
    transcript_text = _fetch_transcript(file_id)

    # Run pipeline
    try:
        result = run_nlp_pipeline(transcript_text)
    except RuntimeError as exc:
        logger.exception("Pipeline failed for [%s]: %s", file_id, exc)
        raise HTTPException(status_code=422, detail=f"NLP pipeline error: {exc}")
    except Exception as exc:
        logger.exception("Unexpected pipeline error for [%s]: %s", file_id, exc)
        raise HTTPException(status_code=500, detail=f"Internal pipeline error: {exc}")

    # Persist to Supabase (best-effort)
    _persist_analysis(file_id, result)

    analyzed_at = datetime.now(timezone.utc).isoformat()
    return JSONResponse(
        content={
            "file_id":         file_id,
            "analyzed_at":     analyzed_at,
            "sentences":       result["sentences"],
            "entities":        result["entities"],
            "classifications": result["classifications"],
            "topics":          result["topics"],
        }
    )


# ── GET /api/analysis/{file_id} ───────────────────────────────────────────────

@router.get(
    "/{file_id}",
    summary="Retrieve stored NLP analysis results for a meeting",
)
async def get_analysis(file_id: str):
    """
    Return previously stored analysis results for *file_id*.
    If no analysis has been run yet, returns 404 with a helpful message.
    """
    stored = _fetch_stored_analysis(file_id)
    if stored is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No analysis found for meeting '{file_id}'. "
                "Call POST /api/analysis/{file_id} first."
            ),
        )

    return JSONResponse(
        content={
            "file_id":         file_id,
            "entities":        stored.get("entities", []),
            "classifications": stored.get("classifications", []),
            "topics":          stored.get("topics", {}),
            "analyzed_at":     stored.get("analyzed_at"),
        }
    )
