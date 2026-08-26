"""
services/actions.py — Action item extraction service.

Processes sentences classified as ACTION ITEM and uses NER +
dependency/semantic analysis + rule-based patterns to extract
structured action items.

Output schema per action item:
  { "person": str | None, "task": str, "deadline": str | None, "status": "Pending" }

Default status is always "Pending" unless stated otherwise in the text.

Pipeline position: Classification → [Actions] → Summarization
Phase 3: full implementation.
Phase 0: stub only.
"""


def extract_actions(action_sentences: list[str], doc=None) -> list[dict]:
    """
    [STUB — Phase 3]
    Accept sentences pre-classified as ACTION ITEM.
    Optionally accept a spaCy Doc for dependency/NER reuse.

    Returns a list of action item dicts:
      [{"person": str|None, "task": str, "deadline": str|None, "status": str}, ...]
    """
    raise NotImplementedError("actions.extract_actions — implement in Phase 3")
