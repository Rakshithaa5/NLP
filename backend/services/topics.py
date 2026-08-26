"""
services/topics.py — Topic extraction service.

Extracts key topics from the preprocessed transcript using:
  1. TF-IDF keyword extraction (fast, explainable baseline)
  2. LDA / NMF topic modeling for thematic grouping

Pipeline position: NLP Preprocess → [Topics] alongside NER & Classification
Phase 2: full implementation.
Phase 0: stub only.
"""


def extract_topics(sentences: list[str], n_topics: int = 5) -> dict:
    """
    [STUB — Phase 2]
    Accept a list of sentences and desired number of topics.

    Returns a dict:
      {
        "keywords": [str, ...],          # top TF-IDF terms
        "topics": [                      # LDA/NMF topic clusters
          {"id": int, "terms": [str, ...], "weight": float},
          ...
        ]
      }
    """
    raise NotImplementedError("topics.extract_topics — implement in Phase 2")
