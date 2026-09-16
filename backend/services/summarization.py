"""
services/summarization.py — Summarization service.

Implements two summarization strategies:
  1. Extractive  — TF-IDF sentence scoring with TextRank-style graph reranking
                   (fast, explainable, no GPU required — ideal for jury demo).
  2. Abstractive — BART / T5 / FLAN-T5 via Hugging Face Transformers pipeline,
                   optionally routed through a local LLM via Ollama.

The dashboard defaults to abstractive, with extractive as fallback/comparison.

Pipeline position: Actions | Decisions → [Summarization] → Dashboard
Phase 3: full implementation.

NLP techniques used (extractive):
  - TF-IDF sentence scoring (scikit-learn TfidfVectorizer)
  - Cosine-similarity graph (sentence-to-sentence TextRank-style scoring)
  - Sentence positional bias (first/last sentences carry more information)

NLP techniques used (abstractive):
  - Pretrained seq2seq transformer (facebook/bart-large-cnn or google/flan-t5-base)
  - HuggingFace Transformers pipeline ("summarization" task)
  - Chunk-and-merge strategy for transcripts exceeding the model's token limit
"""

import logging
import re
from typing import Optional

logger = logging.getLogger("meeting_analyzer.summarization")

# ── Lazy-loaded singletons ────────────────────────────────────────────────────
_abstractive_pipeline = None   # HuggingFace pipeline instance
_abstractive_model_name = None  # Track which model is currently loaded


# ── Shared text helpers ───────────────────────────────────────────────────────

def _sentence_split(text: str) -> list[str]:
    """
    Split *text* into sentences using a simple regex rule.
    We avoid re-importing spaCy here to keep summarization self-contained;
    the preprocessing module already handles spaCy sentence segmentation.
    """
    # Split on ". " or "! " or "? " boundaries, but keep the delimiter
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _clean_text(text: str) -> str:
    """Light cleanup: collapse whitespace, remove lone punctuation lines."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ── Extractive summarization ─────────────────────────────────────────────────

def summarize_extractive(text: str, n_sentences: int = 5) -> str:
    """
    Produce an extractive summary using TF-IDF sentence scoring with a
    TextRank-inspired cosine-similarity reranking pass.

    Algorithm:
      1. Split transcript into sentences.
      2. Vectorize sentences with TF-IDF (scikit-learn).
      3. Build sentence-to-sentence cosine similarity matrix.
      4. Score each sentence as the sum of its similarity column (PageRank
         intuition: sentences similar to many others are more central).
      5. Apply a positional bias boost to the first and last sentences
         (meeting openings and closing summaries are typically informative).
      6. Select the top n_sentences by score, reordered by original position
         so the summary reads naturally.

    Args:
        text:        Full transcript string.
        n_sentences: Number of sentences to include in the extractive summary.

    Returns:
        A string containing the top n_sentences joined with spaces.

    NLP techniques: TF-IDF, cosine similarity, TextRank-style graph scoring.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: PLC0415
    from sklearn.metrics.pairwise import cosine_similarity        # noqa: PLC0415
    import numpy as np                                            # noqa: PLC0415

    text = _clean_text(text)
    sentences = _sentence_split(text)

    # Guard: if transcript is very short, return as-is
    if len(sentences) <= n_sentences:
        logger.info(
            "Extractive summary: transcript has only %d sentences — returning full text.",
            len(sentences),
        )
        return " ".join(sentences)

    # ── Step 1: TF-IDF vectorization ──────────────────────────────────────────
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=10_000,
        sublinear_tf=True,
        stop_words="english",
    )
    try:
        tfidf_matrix = vectorizer.fit_transform(sentences)  # (n_sents, n_features)
    except ValueError as exc:
        logger.warning("TF-IDF vectorization failed (%s) — returning first %d sentences.", exc, n_sentences)
        return " ".join(sentences[:n_sentences])

    # ── Step 2: Cosine similarity matrix ─────────────────────────────────────
    sim_matrix = cosine_similarity(tfidf_matrix, tfidf_matrix)  # (n_sents, n_sents)

    # ── Step 3: Sentence scores — sum of similarity column ───────────────────
    scores = sim_matrix.sum(axis=1)  # shape: (n_sents,)

    # ── Step 4: Positional bias ───────────────────────────────────────────────
    # First 10 % and last 10 % of sentences get a 20 % score boost
    n = len(sentences)
    boundary = max(1, n // 10)
    scores[:boundary] *= 1.2
    scores[max(0, n - boundary):] *= 1.2

    # ── Step 5: Pick top-n, restore reading order ─────────────────────────────
    top_indices = sorted(
        sorted(range(n), key=lambda i: scores[i], reverse=True)[:n_sentences]
    )

    summary = " ".join(sentences[i] for i in top_indices)
    logger.info(
        "Extractive summary complete — selected %d / %d sentences.",
        len(top_indices),
        n,
    )
    return summary


# ── Abstractive summarization ─────────────────────────────────────────────────

# Tokens reserved for the model's generated output (not the input prompt)
_GENERATION_RESERVE = 200

# Soft limit for input length before chunking kicks in (in characters)
# facebook/bart-large-cnn has a 1024-token input window ≈ ~3500 chars.
_CHUNK_CHAR_LIMIT = 3000


def _load_abstractive_pipeline(model_name: str):
    """
    Load (or reuse) the HuggingFace summarization pipeline.
    Cached at module level so the model is only loaded once per worker.
    """
    global _abstractive_pipeline, _abstractive_model_name
    if _abstractive_pipeline is not None and _abstractive_model_name == model_name:
        return _abstractive_pipeline

    from transformers import pipeline as hf_pipeline  # noqa: PLC0415

    logger.info("Loading abstractive summarization model: %s …", model_name)
    # device=-1 forces CPU; change to device=0 if a GPU is available
    _abstractive_pipeline = hf_pipeline(
        "summarization",
        model=model_name,
        device=-1,
        # Explicitly set tokenizer alongside model to suppress warnings
        tokenizer=model_name,
    )
    _abstractive_model_name = model_name
    logger.info("Abstractive model '%s' loaded.", model_name)
    return _abstractive_pipeline


def _chunk_text(text: str, max_chars: int = _CHUNK_CHAR_LIMIT) -> list[str]:
    """
    Split *text* into chunks of at most *max_chars* characters, breaking
    only at sentence boundaries to avoid truncating mid-sentence.
    """
    sentences = _sentence_split(text)
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_len = 0

    for sent in sentences:
        if current_len + len(sent) > max_chars and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sent]
            current_len = len(sent)
        else:
            current_chunk.append(sent)
            current_len += len(sent) + 1  # +1 for the space

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def summarize_abstractive(
    text: str,
    model_name: str = "facebook/bart-large-cnn",
) -> str:
    """
    Produce an abstractive summary using a pretrained seq2seq transformer.

    For long transcripts that exceed the model's token limit, a
    chunk-and-merge strategy is applied:
      1. Split transcript into chunks of ≤ _CHUNK_CHAR_LIMIT characters.
      2. Summarize each chunk individually.
      3. Concatenate chunk summaries and run a final summarization pass
         over the merged intermediate summary.

    Args:
        text:       Full transcript string.
        model_name: HuggingFace model ID to use.
                    Defaults to "facebook/bart-large-cnn".
                    Can be set to "google/flan-t5-base" or any compatible model.
                    For Ollama local LLM, set model_name = "ollama:<model>" and
                    the caller should handle routing externally (see note below).

    Returns:
        The generated abstractive summary string.

    Note on Ollama:
        If you want to route through a local LLM via Ollama, set up an Ollama
        server locally and call its REST API separately. This function uses
        HuggingFace only; Ollama routing can be added as an alternative branch
        in routes/analysis.py by checking model_name.startswith("ollama:").

    NLP techniques: seq2seq transformer, beam search decoding, chunk-and-merge.
    """
    text = _clean_text(text)
    if not text:
        return ""

    try:
        pipe = _load_abstractive_pipeline(model_name)
    except Exception as exc:
        logger.warning(
            "Failed to load abstractive model '%s': %s. "
            "Falling back to extractive summary.",
            model_name,
            exc,
        )
        return summarize_extractive(text)

    # ── Chunk-and-merge for long transcripts ──────────────────────────────────
    chunks = _chunk_text(text)
    logger.info(
        "Abstractive summarization: %d chunk(s) for text of %d chars.",
        len(chunks),
        len(text),
    )

    chunk_summaries: list[str] = []
    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        try:
            result = pipe(
                chunk,
                max_length=200,
                min_length=40,
                do_sample=False,
                truncation=True,
            )
            chunk_summaries.append(result[0]["summary_text"].strip())
            logger.debug("Chunk %d/%d summarized.", i + 1, len(chunks))
        except Exception as exc:
            logger.warning("Chunk %d summarization failed: %s", i + 1, exc)
            # Fall back to the extractive summary of this chunk
            chunk_summaries.append(summarize_extractive(chunk, n_sentences=3))

    if not chunk_summaries:
        return summarize_extractive(text)

    if len(chunk_summaries) == 1:
        final_summary = chunk_summaries[0]
    else:
        # ── Final merge pass ─────────────────────────────────────────────────
        merged = " ".join(chunk_summaries)
        logger.info("Running final merge pass over %d chunk summaries …", len(chunk_summaries))
        try:
            result = pipe(
                merged,
                max_length=300,
                min_length=60,
                do_sample=False,
                truncation=True,
            )
            final_summary = result[0]["summary_text"].strip()
        except Exception as exc:
            logger.warning("Final merge summarization failed: %s — using chunk summaries.", exc)
            final_summary = merged

    logger.info(
        "Abstractive summary complete — %d chars → %d chars.",
        len(text),
        len(final_summary),
    )
    return final_summary


# ── Combined entry-point (used by analysis pipeline) ─────────────────────────

def summarize(
    text: str,
    n_extractive_sentences: int = 5,
    abstractive_model: str = "facebook/bart-large-cnn",
) -> dict:
    """
    Run both extractive and abstractive summarization and return both results.

    This is the single entry-point called by routes/analysis.py so that the
    dashboard can display both variants side-by-side or prefer abstractive
    with extractive as a fallback.

    Args:
        text:                    Full transcript string.
        n_extractive_sentences:  Number of sentences for extractive summary.
        abstractive_model:       HuggingFace model ID for abstractive summary.

    Returns:
        {
          "extractive":  str  — TF-IDF / TextRank extractive summary,
          "abstractive": str  — BART / T5 abstractive summary (or extractive
                                if the model fails to load),
          "preferred":   str  — "abstractive" (always; consumer can override),
        }
    """
    extractive = summarize_extractive(text, n_sentences=n_extractive_sentences)

    try:
        abstractive = summarize_abstractive(text, model_name=abstractive_model)
    except Exception as exc:
        logger.warning("Abstractive summarization failed: %s — using extractive.", exc)
        abstractive = extractive

    return {
        "extractive":  extractive,
        "abstractive": abstractive,
        "preferred":   "abstractive",
    }
