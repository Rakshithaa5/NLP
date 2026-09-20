"""Local meeting summaries: grounded TF-IDF excerpts and optional transformer drafts."""

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

def summarize_extractive(text: str, n_sentences: int = 5, focus_sentences=None) -> str:
    """Select diverse, relevant source sentences in transcript order.

    TF-IDF centroid similarity ranks discussion; explicit commitments, decisions
    and risks receive additional weight. Maximal marginal relevance reduces
    repetition without allocating an all-pairs sentence matrix.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: PLC0415
    from sklearn.metrics.pairwise import cosine_similarity        # noqa: PLC0415
    import numpy as np                                            # noqa: PLC0415

    text = _clean_text(text)
    sentences = list(dict.fromkeys(_sentence_split(text)))
    substantive = [s for s in sentences if len(s.split()) >= 5 and not re.match(
        r"^(?:hello|hi everyone|good morning|thanks|thank you|can you hear|bye|if|namely|because|and then i|feel free|that was the end|with a demo|there are hundreds|not a demo|and this is)\b", s, re.I)
        and not s.endswith("?")]
    sentences = substantive
    if not sentences:
        return ""
    n_sentences = max(1, n_sentences)

    # Guard: if transcript is very short, return as-is
    if len(sentences) <= n_sentences:
        logger.info(
            "Extractive summary: transcript has only %d sentences — returning full text.",
            len(sentences),
        )
        return " ".join(sentences)

    # ── Step 1: TF-IDF vectorization ──────────────────────────────────────────
    from backend.services.topics import TOPIC_STOP
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=10_000,
        sublinear_tf=True,
        stop_words=sorted(TOPIC_STOP),
    )
    try:
        tfidf_matrix = vectorizer.fit_transform(sentences)  # (n_sents, n_features)
    except ValueError as exc:
        logger.warning("TF-IDF vectorization failed (%s) — returning first %d sentences.", exc, n_sentences)
        return " ".join(sentences[:n_sentences])

    # ── Step 2: Cosine similarity matrix ─────────────────────────────────────
    # Centroid relevance and diversity without a quadratic similarity matrix.
    centroid = np.asarray(tfidf_matrix.mean(axis=0))
    scores = cosine_similarity(tfidf_matrix, centroid).ravel()
    from backend.services.actions import is_action
    from backend.services.decisions import _extract_decision_statement
    for i, sentence in enumerate(sentences):
        if sentence in (focus_sentences or []):
            scores[i] += 0.3
        if is_action(sentence) or _extract_decision_statement(sentence):
            scores[i] += 0.35
        if re.search(r"\b(blocked|risk|delay|deadline|unresolved|limit|limits|missing|problem|issue)\b", sentence, re.I):
            scores[i] += 0.2
        if len(sentence.split()) < 8 and not (is_action(sentence) or _extract_decision_statement(sentence)):
            scores[i] *= 0.35
    n = len(sentences)
    selected = []
    redundancy = np.zeros(n)
    for _ in range(min(n_sentences, n)):
        ranking = scores - 0.65 * redundancy
        ranking[selected] = -np.inf
        index = int(ranking.argmax())
        selected.append(index)
        redundancy = np.maximum(redundancy, cosine_similarity(tfidf_matrix, tfidf_matrix[index]).ravel())
    top_indices = sorted(selected)

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

    Raises ImportError immediately if PyTorch is not installed so that
    the caller falls back to extractive summarization gracefully.
    """
    global _abstractive_pipeline, _abstractive_model_name
    if _abstractive_pipeline is not None and _abstractive_model_name == model_name:
        return _abstractive_pipeline

    # ── Early torch check ──────────────────────────────────────────────────────
    # Torch is required for HuggingFace summarization models. If it's not
    # installed (e.g. blocked by Application Control policy), fall back early
    # with a clear message rather than a confusing DLL error.
    try:
        import torch  # noqa: PLC0415
        _ = torch.__version__   # force DLL load now so we catch the error here
    except (ImportError, OSError) as exc:
        raise ImportError(
            f"PyTorch not available ({exc}). "
            "Abstractive summarization is disabled — using extractive fallback."
        ) from exc

    from transformers import pipeline as hf_pipeline  # noqa: PLC0415

    logger.info("Loading abstractive summarization model: %s …", model_name)
    # device=-1 forces CPU; change to device=0 if a GPU is available
    _abstractive_pipeline = hf_pipeline(
        "summarization",
        model=model_name,
        device=-1,
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
    """Generate an optional draft over every tokenizer-bounded chunk.

    Chunk outputs are retained in order, without a truncating merge pass.
    Generation failures propagate to summarize, which retains source excerpts.
    These paraphrases are not automatically verified meeting facts.
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
        return ""

    # ── Chunk-and-merge for long transcripts ──────────────────────────────────
    # Count actual model tokens. Never truncate late-meeting decisions.
    tokenizer = pipe.tokenizer
    limits = [getattr(tokenizer, "model_max_length", 1024),
              getattr(pipe.model.config, "max_position_embeddings", 1024)]
    valid_limits = [int(v) for v in limits if isinstance(v, (int, float)) and 32 < v < 100000]
    limit = min(valid_limits or [512])
    budget = limit - tokenizer.num_special_tokens_to_add(pair=False) - 16
    ids = tokenizer.encode(text, add_special_tokens=False)
    summaries = []
    for offset in range(0, len(ids), budget):
        chunk = tokenizer.decode(ids[offset:offset + budget], skip_special_tokens=True)
        result = pipe(chunk, max_length=min(200, max(24, len(ids[offset:offset + budget]) // 2)),
                      min_length=0, do_sample=False, truncation=False)
        summaries.append(result[0]["summary_text"].strip())
    return "\n\n".join(summaries)


def summarize(
    text: str,
    n_extractive_sentences: int = 5,
    abstractive_model: str = "facebook/bart-large-cnn",
    focus_sentences=None,
) -> dict:
    """Return source excerpts and an optional generated draft.

    ENABLE_ABSTRACTIVE_SUMMARY=true enables the draft; excerpts stay preferred.
    A failed generator returns no draft rather than relabeling excerpts.
    """
    import os
    extractive = summarize_extractive(text, n_sentences=n_extractive_sentences, focus_sentences=focus_sentences)
    abstractive = ""
    # Generated paraphrases are optional drafts, not verified meeting facts.
    if os.getenv("ENABLE_ABSTRACTIVE_SUMMARY", "false").lower() == "true":
        try:
            candidate = summarize_abstractive(text, model_name=abstractive_model)
            if candidate != extractive:
                abstractive = candidate
        except Exception as exc:
            logger.warning("Abstractive draft unavailable: %s", exc)
    return {"extractive": extractive, "abstractive": abstractive,
            "preferred": "extractive"}
