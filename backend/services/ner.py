"""
services/ner.py — Named Entity Recognition service.

Uses spaCy NER to extract entities from the preprocessed transcript.

Target entity types:
  PERSON, ORG, DATE, TIME, GPE (location), TECHNOLOGY, PROJECT

Note: A transformer-based NER upgrade (Hugging Face) is a planned
      future swap-in — leave a clear interface point here.

Pipeline position: NLP Preprocess → [NER] → Classification | Topics
Phase 2: full implementation.
Phase 0: stub only.
"""


def extract_entities(doc) -> list[dict]:
    """
    [STUB — Phase 2]
    Accept a spaCy Doc object.

    Returns a list of entity dicts:
      [{"text": str, "label": str, "start_char": int, "end_char": int}, ...]

    Extension point: replace spaCy pipeline with a HuggingFace NER model
    by swapping this function's internals while keeping the return signature.
    """
    raise NotImplementedError("ner.extract_entities — implement in Phase 2")
