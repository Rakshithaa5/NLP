"""
services/ner.py — Named Entity Recognition service.

Uses the spaCy Doc produced by preprocessing.preprocess() directly.
The EntityRuler (TECHNOLOGY, PROJECT patterns) is now added to the shared
nlp instance in preprocessing.py, so no second spaCy load happens here.

Target entity types (after label mapping):
  PERSON, ORG, DATE, TIME, LOCATION (mapped from GPE/LOC),
  TECHNOLOGY, PROJECT, MONEY, PERCENT, EVENT

Pipeline position: NLP Preprocess → [NER] → Classification | Topics
"""

import logging

logger = logging.getLogger("meeting_analyzer.ner")

# ── Label mapping: spaCy labels → readable dashboard labels ──────────────────
_LABEL_MAP: dict[str, str] = {
    "PERSON":      "PERSON",
    "ORG":         "ORG",
    "GPE":         "LOCATION",
    "LOC":         "LOCATION",
    "DATE":        "DATE",
    "TIME":        "TIME",
    "MONEY":       "MONEY",
    "PERCENT":     "PERCENT",
    "EVENT":       "EVENT",
    "PRODUCT":     "TECHNOLOGY",
    "WORK_OF_ART": "PROJECT",
    "TECHNOLOGY":  "TECHNOLOGY",
    "PROJECT":     "PROJECT",
}

_KEEP_LABELS = set(_LABEL_MAP.values())


def extract_entities(doc_or_text) -> list[dict]:
    """
    Extract named entities from a spaCy Doc (preferred) or a raw string.

    When passed the Doc from preprocessing.preprocess(), no re-parsing occurs —
    the EntityRuler already ran as part of that pipeline.

    When passed a plain str, the shared nlp from preprocessing is used so
    only one spaCy instance is ever loaded per process.

    Returns:
        Deduplicated list of entity dicts:
          [{"text": str, "label": str, "start_char": int, "end_char": int}, ...]
    """
    import spacy  # noqa: PLC0415

    if isinstance(doc_or_text, str):
        from backend.services.preprocessing import _get_nlp  # noqa: PLC0415
        doc = _get_nlp()(doc_or_text)
    elif isinstance(doc_or_text, spacy.tokens.Doc):
        doc = doc_or_text
    else:
        raise TypeError(f"Expected str or spaCy Doc, got {type(doc_or_text)}")

    seen: set[tuple] = set()
    entities: list[dict] = []

    for ent in doc.ents:
        mapped_label = _LABEL_MAP.get(ent.label_, ent.label_)
        if mapped_label not in _KEEP_LABELS:
            continue
        key = (ent.text.strip().lower(), mapped_label)
        if key in seen:
            continue
        seen.add(key)
        entities.append({
            "text":       ent.text.strip(),
            "label":      mapped_label,
            "start_char": ent.start_char,
            "end_char":   ent.end_char,
        })

    logger.info("NER complete — %d entities extracted.", len(entities))
    return entities
