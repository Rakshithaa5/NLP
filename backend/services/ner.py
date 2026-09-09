"""
services/ner.py — Named Entity Recognition service.

Uses spaCy NER to extract entities from the preprocessed transcript.
An EntityRuler adds custom rule-based patterns for TECHNOLOGY and PROJECT
entities that spaCy's statistical model does not cover reliably.

Target entity types (after label mapping):
  PERSON, ORG, DATE, TIME, LOCATION (mapped from GPE/LOC),
  TECHNOLOGY, PROJECT, MONEY, PERCENT, EVENT

Extension point: replace spaCy pipeline with a HuggingFace NER model by
swapping _extract_with_spacy() internals while keeping extract_entities()
return signature identical.

Pipeline position: NLP Preprocess → [NER] → Classification | Topics
Phase 2: full implementation.
"""

import logging

logger = logging.getLogger("meeting_analyzer.ner")

# ── Label mapping: spaCy labels → readable dashboard labels ──────────────────
_LABEL_MAP: dict[str, str] = {
    "PERSON":   "PERSON",
    "ORG":      "ORG",
    "GPE":      "LOCATION",    # geopolitical entity → LOCATION
    "LOC":      "LOCATION",    # non-GPE location → LOCATION
    "DATE":     "DATE",
    "TIME":     "TIME",
    "MONEY":    "MONEY",
    "PERCENT":  "PERCENT",
    "EVENT":    "EVENT",
    "PRODUCT":  "TECHNOLOGY",  # spaCy's PRODUCT covers some tech items
    "WORK_OF_ART": "PROJECT",  # tools/projects sometimes tagged here
    "TECHNOLOGY": "TECHNOLOGY",
    "PROJECT":    "PROJECT",
}

# Entity labels we want to expose to the dashboard (others are dropped)
_KEEP_LABELS = set(_LABEL_MAP.values())

# ── Custom EntityRuler patterns (TECHNOLOGY & PROJECT) ────────────────────────
# These supplement spaCy's statistical model with reliable keyword matches.
# Add more patterns here as the project grows.
_TECH_PATTERNS = [
    # Programming languages
    {"label": "TECHNOLOGY", "pattern": "Python"},
    {"label": "TECHNOLOGY", "pattern": "JavaScript"},
    {"label": "TECHNOLOGY", "pattern": "TypeScript"},
    {"label": "TECHNOLOGY", "pattern": "Java"},
    {"label": "TECHNOLOGY", "pattern": "Go"},
    {"label": "TECHNOLOGY", "pattern": "Rust"},
    {"label": "TECHNOLOGY", "pattern": "SQL"},
    # Frameworks / platforms
    {"label": "TECHNOLOGY", "pattern": "React"},
    {"label": "TECHNOLOGY", "pattern": "FastAPI"},
    {"label": "TECHNOLOGY", "pattern": "Docker"},
    {"label": "TECHNOLOGY", "pattern": "Kubernetes"},
    {"label": "TECHNOLOGY", "pattern": "AWS"},
    {"label": "TECHNOLOGY", "pattern": "GCP"},
    {"label": "TECHNOLOGY", "pattern": "Azure"},
    {"label": "TECHNOLOGY", "pattern": "Supabase"},
    {"label": "TECHNOLOGY", "pattern": "Firebase"},
    {"label": "TECHNOLOGY", "pattern": "PostgreSQL"},
    {"label": "TECHNOLOGY", "pattern": "MySQL"},
    {"label": "TECHNOLOGY", "pattern": "MongoDB"},
    {"label": "TECHNOLOGY", "pattern": "Redis"},
    {"label": "TECHNOLOGY", "pattern": "Kafka"},
    {"label": "TECHNOLOGY", "pattern": "Terraform"},
    {"label": "TECHNOLOGY", "pattern": "GitHub"},
    {"label": "TECHNOLOGY", "pattern": "Jira"},
    {"label": "TECHNOLOGY", "pattern": "Slack"},
    # AI / ML
    {"label": "TECHNOLOGY", "pattern": "Whisper"},
    {"label": "TECHNOLOGY", "pattern": "spaCy"},
    {"label": "TECHNOLOGY", "pattern": "BERT"},
    {"label": "TECHNOLOGY", "pattern": "GPT"},
    {"label": "TECHNOLOGY", "pattern": "LLM"},
    # Multi-token (list-of-dict patterns)
    {"label": "TECHNOLOGY", "pattern": [{"LOWER": "machine"}, {"LOWER": "learning"}]},
    {"label": "TECHNOLOGY", "pattern": [{"LOWER": "deep"}, {"LOWER": "learning"}]},
    {"label": "TECHNOLOGY", "pattern": [{"LOWER": "natural"}, {"LOWER": "language"}, {"LOWER": "processing"}]},
    {"label": "TECHNOLOGY", "pattern": [{"LOWER": "ci"}, {"LOWER": "/"}, {"LOWER": "cd"}]},
    {"label": "TECHNOLOGY", "pattern": [{"LOWER": "rest"}, {"LOWER": "api"}]},
    # Project keywords (common meeting terms for project names)
    {"label": "PROJECT", "pattern": [{"LOWER": "phase"}, {"IS_DIGIT": True}]},
    {"label": "PROJECT", "pattern": [{"LOWER": "sprint"}, {"IS_DIGIT": True}]},
    {"label": "PROJECT", "pattern": [{"LOWER": "version"}, {"IS_DIGIT": True}]},
    {"label": "PROJECT", "pattern": [{"LOWER": "v"}, {"IS_DIGIT": True}]},
]

# Module-level nlp singleton with ruler already injected
_nlp_with_ruler = None


def _get_nlp():
    """
    Return a spaCy pipeline with a custom EntityRuler injected before the
    NER component so that rule-based patterns take priority.
    Loaded once per worker process.
    """
    global _nlp_with_ruler
    if _nlp_with_ruler is None:
        import spacy  # noqa: PLC0415

        logger.info("Loading spaCy NER pipeline …")
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            raise RuntimeError(
                "spaCy model 'en_core_web_sm' not found. "
                "Run: python -m spacy download en_core_web_sm"
            )

        # Add the EntityRuler *before* the ner component so rules take priority.
        # "ner" is the last component in en_core_web_sm; last_before_ner = True
        # puts the ruler just before it.
        ruler = nlp.add_pipe(
            "entity_ruler",
            before="ner",
            config={"overwrite_ents": False},  # statistical NER wins on conflicts
        )
        ruler.add_patterns(_TECH_PATTERNS)
        logger.info("EntityRuler added with %d custom patterns.", len(_TECH_PATTERNS))
        _nlp_with_ruler = nlp

    return _nlp_with_ruler


# ── Public API ────────────────────────────────────────────────────────────────

def extract_entities(doc_or_text) -> list[dict]:
    """
    Extract named entities from a spaCy Doc (preferred) or a raw string.

    Accepts either:
      - A spaCy ``Doc`` object produced by preprocessing.preprocess() — zero
        re-parsing cost, the doc is used directly.
      - A plain ``str`` — will be parsed fresh (slightly slower).

    Returns:
        A deduplicated list of entity dicts:
          [{"text": str, "label": str, "start_char": int, "end_char": int}, ...]

        Labels are mapped to the dashboard vocabulary defined in _LABEL_MAP.
        Entity types not in _KEEP_LABELS are silently dropped.

    Extension point:
        To upgrade to a HuggingFace transformer NER model, replace the
        _extract_with_spacy() call below with _extract_with_hf() while keeping
        this function's return signature unchanged.
    """
    return _extract_with_spacy(doc_or_text)


def _extract_with_spacy(doc_or_text) -> list[dict]:
    """Internal: run spaCy NER and map labels."""
    import spacy  # noqa: PLC0415

    if isinstance(doc_or_text, str):
        # Fresh parse — uses the ruler-augmented pipeline
        nlp = _get_nlp()
        doc = nlp(doc_or_text)
    elif isinstance(doc_or_text, spacy.tokens.Doc):
        # Reuse the Doc from preprocessing — BUT the ruler may not have run on
        # this doc (preprocessing uses a separate nlp instance).  We re-parse
        # the text so that the ruler-augmented pipeline processes it too.
        nlp = _get_nlp()
        doc = nlp(doc_or_text.text)
    else:
        raise TypeError(f"Expected str or spaCy Doc, got {type(doc_or_text)}")

    seen: set[tuple] = set()
    entities: list[dict] = []

    for ent in doc.ents:
        mapped_label = _LABEL_MAP.get(ent.label_, ent.label_)
        if mapped_label not in _KEEP_LABELS:
            continue

        # Deduplicate by (normalised text, label) — case-insensitive
        key = (ent.text.strip().lower(), mapped_label)
        if key in seen:
            continue
        seen.add(key)

        entities.append(
            {
                "text":       ent.text.strip(),
                "label":      mapped_label,
                "start_char": ent.start_char,
                "end_char":   ent.end_char,
            }
        )

    logger.info("NER complete — %d entities extracted.", len(entities))
    return entities


# ── Extension point ───────────────────────────────────────────────────────────
# def _extract_with_hf(text: str) -> list[dict]:
#     """
#     Future: replace spaCy with a HuggingFace transformer NER model.
#     from transformers import pipeline as hf_pipeline
#     ner = hf_pipeline("ner", model="dslim/bert-base-NER", aggregation_strategy="simple")
#     results = ner(text)
#     return [{"text": r["word"], "label": r["entity_group"],
#              "start_char": r["start"], "end_char": r["end"]} for r in results]
#     """
#     raise NotImplementedError("HuggingFace NER upgrade — implement when needed")
