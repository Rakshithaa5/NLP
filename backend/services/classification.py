"""
services/classification.py — Sentence classification service.

Classifies each sentence in the transcript into one of:
  ACTION ITEM | DECISION | QUESTION | DISCUSSION | INFORMATION

Baseline implementation: TF-IDF + Logistic Regression (scikit-learn).
The model is trained on data/training_sentences.csv and persisted to
  models/tfidf_vectorizer.pkl
  models/sentence_classifier.pkl

Extension point: swap classifier internals for a BERT/DistilBERT
(Hugging Face Transformers) model while keeping the same public interface.
See _classify_with_hf() stub at the bottom of this file.

Pipeline position: NLP Preprocess → [Classification] → Actions | Decisions | Topics
Phase 2: full implementation.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger("meeting_analyzer.classification")

LABELS = ["ACTION ITEM", "DECISION", "QUESTION", "DISCUSSION", "INFORMATION"]

# Paths for serialised artefacts
_PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", Path(__file__).resolve().parents[2]))
_MODELS_DIR   = _PROJECT_ROOT / "models"
_DATA_DIR     = _PROJECT_ROOT / "data"
_VECTORIZER_PATH   = _MODELS_DIR / "tfidf_vectorizer.pkl"
_CLASSIFIER_PATH   = _MODELS_DIR / "sentence_classifier.pkl"
_TRAINING_CSV_PATH = _DATA_DIR   / "training_sentences.csv"

# Module-level cached pipeline (vectorizer + classifier)
_pipeline = None   # sklearn Pipeline object after training / loading


# ── Model persistence ─────────────────────────────────────────────────────────

def _save_pipeline(pipeline) -> None:
    """Serialise the fitted sklearn Pipeline to disk using joblib."""
    import joblib  # noqa: PLC0415

    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, _CLASSIFIER_PATH)
    logger.info("Classifier pipeline saved → %s", _CLASSIFIER_PATH)


def _load_pipeline():
    """Load a previously serialised pipeline from disk. Returns None if not found."""
    import joblib  # noqa: PLC0415

    if _CLASSIFIER_PATH.exists():
        logger.info("Loading classifier pipeline from %s …", _CLASSIFIER_PATH)
        return joblib.load(_CLASSIFIER_PATH)
    return None


# ── Training ──────────────────────────────────────────────────────────────────

def train_classifier(training_data: list[dict] | None = None) -> None:
    """
    Train and persist the TF-IDF + Logistic Regression pipeline.

    Args:
        training_data: Optional list of {"sentence": str, "label": str} dicts.
                       If None (default), the CSV at data/training_sentences.csv
                       is used.

    The trained pipeline is written to models/sentence_classifier.pkl and
    cached in the module-level _pipeline variable.
    """
    global _pipeline

    import pandas as pd  # noqa: PLC0415
    from sklearn.pipeline import Pipeline  # noqa: PLC0415
    from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: PLC0415
    from sklearn.linear_model import LogisticRegression  # noqa: PLC0415
    from sklearn.preprocessing import LabelEncoder  # noqa: PLC0415

    # ── Load training data ────────────────────────────────────────────────────
    if training_data is not None:
        df = pd.DataFrame(training_data)          # [{"sentence": ..., "label": ...}]
    elif _TRAINING_CSV_PATH.exists():
        df = pd.read_csv(_TRAINING_CSV_PATH)
        logger.info("Loaded %d training samples from CSV.", len(df))
    else:
        raise FileNotFoundError(
            f"Training data not found at {_TRAINING_CSV_PATH}. "
            "Provide training_data argument or place training_sentences.csv "
            "in the data/ directory."
        )

    if "sentence" not in df.columns or "label" not in df.columns:
        raise ValueError("Training CSV must have 'sentence' and 'label' columns.")

    # Drop unknowns
    df = df[df["label"].isin(LABELS)].dropna(subset=["sentence", "label"])
    X = df["sentence"].tolist()
    y = df["label"].tolist()

    logger.info(
        "Training on %d samples, %d classes: %s",
        len(X),
        len(set(y)),
        sorted(set(y)),
    )

    # ── Build sklearn Pipeline ────────────────────────────────────────────────
    # TF-IDF with character n-grams (1–3 words) captures action-item phrasing
    # such as "needs to", "will handle", "should prepare" effectively.
    pipe = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 3),
                    max_features=20_000,
                    sublinear_tf=True,      # log-TF scaling — helps skewed corpora
                    strip_accents="unicode",
                    analyzer="word",
                    token_pattern=r"\b[a-zA-Z][a-zA-Z0-9]*\b",
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",  # handles class imbalance in small datasets
                    solver="lbfgs",           # lbfgs handles multinomial natively (sklearn >= 1.5)
                    C=1.0,
                ),
            ),
        ]
    )

    pipe.fit(X, y)
    logger.info("Classifier trained successfully.")

    _pipeline = pipe
    _save_pipeline(pipe)


def _get_pipeline():
    """
    Return the fitted pipeline, loading from disk or training from scratch
    if it has not been initialised yet.
    """
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    loaded = _load_pipeline()
    if loaded is not None:
        _pipeline = loaded
        return _pipeline

    # No saved model — train now using the bundled CSV
    logger.info("No saved classifier found — training from data/training_sentences.csv …")
    train_classifier()
    return _pipeline


# ── Public API ────────────────────────────────────────────────────────────────

def classify_sentences(sentences: list[str]) -> list[dict]:
    """
    Classify each sentence into one of the five meeting-content categories.

    Args:
        sentences: List of sentence strings (from preprocessing.preprocess).

    Returns:
        A list of classification dicts in the same order as the input:
          [{"sentence": str, "label": str, "confidence": float}, ...]

        confidence is the max softmax probability (0.0–1.0) from the
        Logistic Regression model.

    Extension point:
        To upgrade to a HuggingFace BERT/DistilBERT classifier, replace the
        body of this function with _classify_with_hf(sentences) while keeping
        the return schema identical.
    """
    if not sentences:
        return []

    pipeline = _get_pipeline()

    # predict_proba gives us per-class probabilities for confidence scoring
    probs = pipeline.predict_proba(sentences)
    labels = pipeline.predict(sentences)

    results = []
    for sentence, label, prob_row in zip(sentences, labels, probs):
        confidence = float(prob_row.max())
        results.append(
            {
                "sentence":   sentence,
                "label":      label,
                "confidence": round(confidence, 4),
            }
        )

    label_counts = {}
    for r in results:
        label_counts[r["label"]] = label_counts.get(r["label"], 0) + 1
    logger.info(
        "Classification complete — %d sentences classified: %s",
        len(results),
        label_counts,
    )

    return results


# ── Extension point (HuggingFace upgrade) ─────────────────────────────────────
# def _classify_with_hf(sentences: list[str]) -> list[dict]:
#     """
#     Future upgrade: replace TF-IDF + LR with a fine-tuned DistilBERT classifier.
#     from transformers import pipeline as hf_pipeline
#     classifier = hf_pipeline("text-classification",
#                              model="distilbert-base-uncased-finetuned-sst-2-english")
#     # Fine-tune on LABELS and replace above model path.
#     results = classifier(sentences, truncation=True, max_length=512)
#     return [{"sentence": s, "label": r["label"], "confidence": round(r["score"], 4)}
#             for s, r in zip(sentences, results)]
#     """
#     raise NotImplementedError("HuggingFace classifier upgrade — implement when needed")
