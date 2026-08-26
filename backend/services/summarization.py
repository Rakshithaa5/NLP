"""
services/summarization.py — Summarization service.

Implements two summarization strategies:
  1. Extractive  — TF-IDF or TextRank over the transcript (fast, explainable).
  2. Abstractive — BART / T5 / FLAN-T5 via Hugging Face Transformers,
                   optionally routed through a local LLM via Ollama.

The dashboard defaults to abstractive, with extractive as fallback/comparison.

Pipeline position: Actions | Decisions → [Summarization] → Dashboard
Phase 3: full implementation.
Phase 0: stub only.
"""


def summarize_extractive(text: str, n_sentences: int = 5) -> str:
    """
    [STUB — Phase 3]
    Produce an extractive summary using TF-IDF or TextRank.
    Returns a string containing the top n_sentences sentences.
    """
    raise NotImplementedError("summarization.summarize_extractive — implement in Phase 3")


def summarize_abstractive(text: str, model_name: str = "facebook/bart-large-cnn") -> str:
    """
    [STUB — Phase 3]
    Produce an abstractive summary using BART / T5 / FLAN-T5
    via Hugging Face Transformers pipeline.

    model_name can be swapped for a local Ollama model endpoint if configured.
    Returns the generated summary string.
    """
    raise NotImplementedError("summarization.summarize_abstractive — implement in Phase 3")
