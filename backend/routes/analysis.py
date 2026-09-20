"""
routes/analysis.py — Analysis pipeline endpoint.

Triggers the full NLP pipeline in the fixed order defined by the implementation plan:
  preprocessing → NER → classification → topics → actions → decisions → questions → summarization

POST /api/analysis/{file_id}
  Fetches the stored transcript for file_id, runs the pipeline,
  persists results to Supabase, and returns the full analysis payload.

GET /api/analysis/{file_id}
  Returns the previously stored analysis results for file_id.

Phase 2: preprocessing, NER, classification, topics.
Phase 3: actions, decisions, questions, summarization — fully wired in.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.services.preprocessing import preprocess
from backend.services.ner import extract_entities
from backend.services.classification import classify_sentences
from backend.services.topics import extract_topics
from backend.services.actions import extract_actions
from backend.services.decisions import extract_decisions, extract_questions
from backend.services.summarization import summarize
from backend.services.intelligence import build_intelligence
from backend.services.meeting_store import load_meeting, save_local, read_local

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
    Retrieve the raw transcript text for *file_id*.
    1. Try Supabase first.
    2. Fall back to re-transcribing from the saved WAV on disk.
    Raises HTTPException(404) only if neither source has the data.
    """
    import os  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    cached = load_meeting(file_id, _get_db())
    if cached and cached.get("full_text"):
        return cached["full_text"]
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

    # Disk fallback — re-transcribe from the saved WAV
    data_dir = Path(os.getenv("DATA_DIR", "data")).resolve()
    wav_path = data_dir / file_id / "audio.wav"
    if wav_path.exists():
        logger.info("DB miss for [%s] — transcribing from disk: %s", file_id, wav_path)
        try:
            from backend.services.transcription import transcribe  # noqa: PLC0415
            result = transcribe(str(wav_path))
            return result["full_text"]
        except Exception as exc:
            logger.error("Disk transcription fallback failed for [%s]: %s", file_id, exc)
            raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")

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
      id                TEXT PRIMARY KEY REFERENCES meetings(id)
      entities          JSONB
      topics            JSONB
      classifications   JSONB
      action_items      JSONB
      decisions         JSONB
      questions         JSONB
      summary_extractive TEXT
      summary_abstractive TEXT
      analyzed_at       TIMESTAMPTZ
    """
    try:
        save_local(file_id, "analysis.json", payload)
    except (OSError, ValueError) as exc:
        logger.warning("Local analysis save failed: %s", exc)
    db = _get_db()
    if not db:
        return

    row = {
        "id":                  file_id,
        "entities":            payload["entities"],
        "topics":              payload["topics"],
        "classifications":     payload["classifications"],
        "action_items":        payload["action_items"],
        "decisions":           payload["decisions"],
        "questions":           payload["questions"],
        "summary_extractive":  payload["summary"]["extractive"],
        "summary_abstractive": payload["summary"]["abstractive"],
        "analyzed_at":         datetime.now(timezone.utc).isoformat(),
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
    local = read_local(file_id, "analysis.json")
    if local:
        return {**local, "summary_extractive": local.get("summary", {}).get("extractive", ""),
                "summary_abstractive": local.get("summary", {}).get("abstractive", "")}
    db = _get_db()
    if not db:
        return None
    try:
        row = (
            db.table("analysis_results")
            .select(
                "entities, topics, classifications, "
                "action_items, decisions, questions, "
                "summary_extractive, summary_abstractive, analyzed_at"
            )
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

def run_nlp_pipeline(
    transcript_text: str,
    abstractive_model: str = "facebook/bart-large-cnn",
    language: str = "en",
) -> dict:
    """
    Execute the full Phase 2 + Phase 3 NLP pipeline in the fixed order:
      preprocess → NER → classify_sentences → extract_topics
      → extract_actions → extract_decisions → extract_questions → summarize

    Args:
        transcript_text:   Raw transcript string.
        abstractive_model: HuggingFace model ID for abstractive summarization.

    Returns:
        Dict with keys:
          "sentences"         — segmented sentence strings
          "entities"          — NER results
          "classifications"   — per-sentence labels + confidence
          "topics"            — TF-IDF keywords + LDA/NMF topic clusters
          "action_items"      — structured action items (person/task/deadline/status)
          "decisions"         — clean decision statements
          "questions"         — unresolved question entries
          "summary"           — {"extractive": str, "abstractive": str, "preferred": str}
    """
    # ── Phase 2 pipeline ─────────────────────────────────────────────────────

    # Step 1: Preprocessing (spaCy + NLTK)
    logger.info("Running preprocessing …")
    if not transcript_text or not transcript_text.strip():
        raise RuntimeError("Transcript is empty; no meeting report can be generated.")
    if language and language.lower().split("-")[0] != "en":
        return {"sentences": [], "entities": [], "classifications": [], "topics": {},
                "action_items": [], "decisions": [], "questions": [],
                "summary": {"extractive": transcript_text, "abstractive": "", "preferred": "extractive"}}
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
    topics = extract_topics(sentences, n_topics=5, doc=doc)

    # ── Phase 3 pipeline ─────────────────────────────────────────────────────

    # Bucket sentences by classification label for Phase 3 services
    action_sentences   = [c["sentence"] for c in classifications if c["label"] == "ACTION ITEM"]
    decision_sentences = [c["sentence"] for c in classifications if c["label"] == "DECISION"]
    question_sentences = [c["sentence"] for c in classifications if c["label"] == "QUESTION"]

    # Step 5: Action item extraction (dependency parsing + NER + regex rules)
    logger.info(
        "Running action item extraction on %d ACTION ITEM sentences …",
        len(action_sentences),
    )
    action_items = extract_actions(action_sentences, doc=doc)

    # Step 6: Decision extraction (keyword/pattern detection)
    logger.info(
        "Running decision extraction on %d DECISION sentences …",
        len(decision_sentences),
    )
    decisions = extract_decisions(decision_sentences)

    # Step 7: Question / unresolved issue extraction
    logger.info(
        "Running question extraction on %d QUESTION sentences …",
        len(question_sentences),
    )
    questions = extract_questions(question_sentences)

    # Step 8: Summarization (extractive TF-IDF/TextRank + abstractive BART/T5)
    logger.info("Running summarization …")
    summary = summarize(
        transcript_text,
        n_extractive_sentences=6,
        focus_sentences=[t["evidence"] for t in topics.get("discussion", [])],
        abstractive_model=abstractive_model,
    )

    return {
        "sentences":       sentences,
        "entities":        entities,
        "classifications": classifications,
        "topics":          topics,
        "action_items":    action_items,
        "decisions":       decisions,
        "questions":       questions,
        "summary":         summary,
    }


# ── POST /api/analysis/{file_id} ──────────────────────────────────────────────

@router.post(
    "/{file_id}",
    summary="Run full NLP analysis pipeline (Phase 2 + Phase 3) on a stored meeting transcript",
)
def analyze(
    file_id: str,
    abstractive_model: str = Query(
        default="facebook/bart-large-cnn",
        description=(
            "HuggingFace model ID for abstractive summarization. "
            "Options: 'facebook/bart-large-cnn', 'google/flan-t5-base', 't5-small'. "
            "Use a lighter model if GPU/memory is constrained."
        ),
    ),
):
    """
    Run the full Phase 2 + Phase 3 NLP pipeline on the transcript stored
    for *file_id*.

    Pipeline stages (in fixed order per implementation plan):
      1. Preprocessing   — spaCy sentence segmentation, tokenization,
                           lemmatization, stop-word removal (NLTK + spaCy)
      2. NER             — spaCy EntityRuler + statistical NER
      3. Classification  — TF-IDF + Logistic Regression per sentence
      4. Topic modeling  — TF-IDF keywords + LDA topic clusters
      5. Action items    — dependency parsing + NER + regex deadline extraction
      6. Decisions       — keyword/pattern matching + negation detection
      7. Questions       — unresolved issue detection + normalisation
      8. Summarization   — extractive (TF-IDF/TextRank) + abstractive (BART/T5)

    Returns JSON with full analysis payload including action items, decisions,
    questions, and both summary variants.
    """
    logger.info("Analysis requested for meeting [%s]", file_id)

    # Fetch transcript from DB (raises 404 if missing)
    meeting = load_meeting(file_id, _get_db()) or {}
    transcript_text = meeting.get("full_text") or _fetch_transcript(file_id)

    # Run pipeline
    try:
        result = run_nlp_pipeline(
            transcript_text,
            abstractive_model=abstractive_model,
            language=meeting.get("language") or "en",
        )
    except RuntimeError as exc:
        logger.exception("Pipeline failed for [%s]: %s", file_id, exc)
        raise HTTPException(status_code=422, detail=f"NLP pipeline error: {exc}")
    except Exception as exc:
        logger.exception("Unexpected pipeline error for [%s]: %s", file_id, exc)
        raise HTTPException(status_code=500, detail=f"Internal pipeline error: {exc}")

    result["intelligence"] = build_intelligence(result, transcript_text, meeting.get("segments"), meeting.get("language") or "en")
    result["topics"]["intelligence"] = result["intelligence"]  # Existing JSONB column; no migration.
    result["analyzed_at"] = datetime.now(timezone.utc).isoformat()
    # Persist to Supabase (best-effort)
    _persist_analysis(file_id, result)

    analyzed_at = datetime.now(timezone.utc).isoformat()
    return JSONResponse(
        content={
            "file_id":         file_id,
            "analyzed_at":     analyzed_at,
            # Phase 2 outputs
            "sentences":       result["sentences"],
            "entities":        result["entities"],
            "classifications": result["classifications"],
            "topics":          result["topics"],
            # Phase 3 outputs
            "action_items":    result["action_items"],
            "decisions":       result["decisions"],
            "questions":       result["questions"],
            "summary":         result["summary"],
            "intelligence":    result["intelligence"],
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

    The response includes all Phase 2 and Phase 3 fields so the frontend
    dashboard can render the full meeting intelligence payload.
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
            "file_id":             file_id,
            # Phase 2
            "entities":            stored.get("entities", []),
            "classifications":     stored.get("classifications", []),
            "topics":              stored.get("topics", {}),
            # Phase 3
            "action_items":        stored.get("action_items", []),
            "decisions":           stored.get("decisions", []),
            "questions":           stored.get("questions", []),
            "summary": {
                "extractive":  stored.get("summary_extractive", ""),
                "abstractive": stored.get("summary_abstractive", ""),
                "preferred":   "extractive",
            },
            "analyzed_at":         stored.get("analyzed_at"),
            "intelligence":        stored.get("intelligence") or (stored.get("topics") or {}).get("intelligence"),
        }
    )
