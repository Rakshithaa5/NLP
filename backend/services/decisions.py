"""
services/decisions.py — Decision & unresolved question extraction service.

Processes sentences classified as DECISION or QUESTION.

  - DECISION sentences → clean decision statements via keyword/pattern detection.
  - QUESTION sentences → "Unresolved Question" entries for the dashboard.

Pipeline position: Classification → [Decisions] → Summarization
Phase 3: full implementation.
Phase 0: stub only.
"""


def extract_decisions(decision_sentences: list[str]) -> list[dict]:
    """
    [STUB — Phase 3]
    Accept sentences pre-classified as DECISION.

    Returns a list of decision dicts:
      [{"statement": str}, ...]
    """
    raise NotImplementedError("decisions.extract_decisions — implement in Phase 3")


def extract_questions(question_sentences: list[str]) -> list[dict]:
    """
    [STUB — Phase 3]
    Accept sentences pre-classified as QUESTION.

    Returns a list of unresolved question dicts:
      [{"question": str}, ...]
    """
    raise NotImplementedError("decisions.extract_questions — implement in Phase 3")
