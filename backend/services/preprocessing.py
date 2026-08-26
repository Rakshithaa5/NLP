"""
services/preprocessing.py — NLP preprocessing service.

Uses spaCy and NLTK to clean and normalize the raw transcript
before downstream NER, classification, and topic modeling.

Steps (in order):
  1. Sentence segmentation
  2. Tokenization
  3. Normalization (punctuation/spacing cleanup)
  4. Stop-word handling
  5. Lemmatization

Pipeline position: Transcribe → [NLP Preprocess] → NER | Classification | Topics
Phase 2: full implementation.
Phase 0: stub only.
"""


def preprocess(text: str) -> dict:
    """
    [STUB — Phase 2]
    Accept raw transcript text. Return a dict with:
      - "sentences": list of sentence strings
      - "tokens": list of token lists per sentence
      - "lemmas": list of lemma lists per sentence
      - "doc": spaCy Doc object (for downstream NER/dep-parse reuse)
    """
    raise NotImplementedError("preprocessing.preprocess — implement in Phase 2")
