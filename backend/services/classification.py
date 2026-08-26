"""
services/classification.py — Sentence classification service.

Classifies each sentence in the transcript into one of:
  ACTION ITEM | DECISION | QUESTION | DISCUSSION | INFORMATION

Baseline implementation: TF-IDF + Logistic Regression / SVM (Scikit-learn).

Extension point: swap classifier internals for a BERT/DistilBERT
(Hugging Face Transformers) model while keeping the same interface.
The interface is defined here; the transformer upgrade is optional/later.

Pipeline position: NLP Preprocess → [Classification] → Actions | Decisions | Topics
Phase 2: full implementation.
Phase 0: stub only.
"""

LABELS = ["ACTION ITEM", "DECISION", "QUESTION", "DISCUSSION", "INFORMATION"]


def classify_sentences(sentences: list[str]) -> list[dict]:
    """
    [STUB — Phase 2]
    Accept a list of sentence strings.

    Returns a list of classification dicts:
      [{"sentence": str, "label": str, "confidence": float}, ...]

    Baseline: TF-IDF vectorizer → Logistic Regression or SVM.
    Extension point: replace model internals with HuggingFace pipeline
    while preserving this return signature.
    """
    raise NotImplementedError("classification.classify_sentences — implement in Phase 2")


def train_classifier(training_data: list[dict]) -> None:
    """
    [STUB — Phase 2]
    Train and persist the TF-IDF + classifier pipeline.
    training_data: list of {"sentence": str, "label": str}
    """
    raise NotImplementedError("classification.train_classifier — implement in Phase 2")
