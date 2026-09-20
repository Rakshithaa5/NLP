"""
services/topics.py — Topic extraction service.

Extracts key topics from the preprocessed transcript using two methods:

  1. TF-IDF keyword extraction — fast, fully explainable baseline.
     Computes a term-level TF-IDF matrix over the sentence corpus and
     returns the highest-scoring terms as "keywords".

  2. LDA (Latent Dirichlet Allocation) topic modeling — probabilistic
     thematic grouping of sentences into n_topics clusters.
     NMF (Non-negative Matrix Factorization) is available as an alternative
     via the `method` argument and tends to be sharper for short documents.

Pipeline position: NLP Preprocess → [Topics] alongside NER & Classification
Phase 2: full implementation.
"""

import logging
import re
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

TOPIC_STOP = set(ENGLISH_STOP_WORDS) | set("yeah yes okay ok right meeting meetings let lets um uh actually basically really just like know think thanks thank hello hi going got things thing today everyone people said say sure well gonna want need look bit sort kind".split())

logger = logging.getLogger("meeting_analyzer.topics")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_tfidf_keywords(sentences: list[str], top_n: int = 20) -> list[str]:
    """
    Compute per-corpus TF-IDF scores and return the top-N terms.

    Uses a word-level TF-IDF vectorizer.  Stop words are removed at the
    vectorizer level (English built-in list) so no external resource is needed.

    Args:
        sentences: List of sentence strings.
        top_n:     Number of keywords to return.

    Returns:
        Ordered list of keyword strings (highest TF-IDF score first).
    """
    import numpy as np  # noqa: PLC0415
    from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: PLC0415

    if not sentences:
        return []

    vectorizer = TfidfVectorizer(
        stop_words=sorted(TOPIC_STOP),
        ngram_range=(1, 2),    # unigrams + bigrams catch "action item", "sprint velocity" etc.
        max_features=5_000,
        sublinear_tf=True,
        token_pattern=r"(?u)\b[^\W\d_][^\W_]+\b",
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(sentences)
    except ValueError:
        # Corpus is empty or all stop words — return nothing
        return []

    # Sum TF-IDF scores across all documents to get corpus-level importance
    feature_names = vectorizer.get_feature_names_out()
    scores = np.asarray(tfidf_matrix.sum(axis=0)).flatten()

    # Sort descending and pick top-N
    top_indices = scores.argsort()[::-1][:top_n]
    keywords = [str(feature_names[i]) for i in top_indices]

    return keywords


def _build_topic_model(
    sentences: list[str],
    n_topics: int,
    method: str = "lda",
) -> list[dict]:
    """
    Run LDA or NMF on the sentence corpus.

    Args:
        sentences: List of sentence strings.
        n_topics:  Number of latent topics to discover.
        method:    "lda" (default) or "nmf".

    Returns:
        List of topic dicts:
          [{"id": int, "terms": [str, ...], "weight": float}, ...]
        "terms" contains the top words for that topic.
        "weight" is the normalised average document-topic probability.
    """
    import numpy as np  # noqa: PLC0415
    from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer  # noqa: PLC0415
    from sklearn.decomposition import LatentDirichletAllocation, NMF  # noqa: PLC0415

    if not sentences:
        return []

    # LDA requires raw counts; NMF works best with TF-IDF
    if method == "lda":
        vectorizer = CountVectorizer(
            stop_words=sorted(TOPIC_STOP),
            max_features=3_000,
            token_pattern=r"(?u)\b[^\W\d_][^\W_]+\b",
        )
    else:
        vectorizer = TfidfVectorizer(
            stop_words=sorted(TOPIC_STOP),
            max_features=3_000,
            sublinear_tf=True,
            token_pattern=r"(?u)\b[^\W\d_][^\W_]+\b",
        )

    try:
        doc_term_matrix = vectorizer.fit_transform(sentences)
    except ValueError:
        return []

    # Guard: can't have more topics than documents or vocabulary size
    n_vocab = doc_term_matrix.shape[1]
    n_docs  = doc_term_matrix.shape[0]
    actual_topics = min(n_topics, n_docs, n_vocab)
    if actual_topics < 1:
        return []

    if method == "lda":
        model = LatentDirichletAllocation(
            n_components=actual_topics,
            max_iter=20,
            learning_method="online",
            random_state=42,
        )
    else:
        model = NMF(
            n_components=actual_topics,
            max_iter=300,
            random_state=42,
            init="nndsvda",
        )

    doc_topic_matrix = model.fit_transform(doc_term_matrix)

    feature_names = vectorizer.get_feature_names_out()
    N_TOP_WORDS = 8  # words per topic returned to the dashboard

    topics = []
    for topic_idx, topic_vec in enumerate(model.components_):
        top_word_indices = topic_vec.argsort()[::-1][:N_TOP_WORDS]
        terms = [str(feature_names[i]) for i in top_word_indices]

        # weight = mean document-topic probability for this topic
        weight = float(doc_topic_matrix[:, topic_idx].mean())

        topics.append(
            {
                "id":     topic_idx,
                "terms":  terms,
                "weight": round(weight, 4),
            }
        )

    # Sort topics by weight descending so the most prominent appears first
    topics.sort(key=lambda t: t["weight"], reverse=True)
    return topics


# ── Public API ────────────────────────────────────────────────────────────────

def extract_topics(
    sentences: list[str],
    n_topics: int = 5,
    method: str = "lda",
    doc=None,
) -> dict:
    """
    Extract key topics from the preprocessed transcript.

    Args:
        sentences: List of sentence strings (from preprocessing.preprocess).
        n_topics:  Desired number of latent topic clusters (default 5).
                   Automatically capped at min(n_topics, n_sentences).
        method:    Topic modeling algorithm — "lda" (default) or "nmf".

    Returns:
        {
          "keywords": [str, ...],          # top TF-IDF terms (corpus-level)
          "topics": [                      # LDA/NMF topic clusters
            {"id": int, "terms": [str, ...], "weight": float},
            ...
          ]
        }
    """
    if not sentences:
        logger.warning("extract_topics called with empty sentence list.")
        return {"keywords": [], "topics": []}

    logger.info(
        "Extracting topics from %d sentences (method=%s, n_topics=%d) …",
        len(sentences),
        method,
        n_topics,
    )

    keywords = _build_tfidf_keywords(sentences, top_n=20)
    topics   = _build_topic_model(sentences, n_topics=n_topics, method=method)

    logger.info(
        "Topics extracted — %d keywords, %d topic clusters.",
        len(keywords),
        len(topics),
    )

    return {"keywords": keywords, "topics": topics, "discussion": discussion_topics(doc, sentences, n_topics)}


def discussion_topics(doc, sentences, limit=5):
    """Rank real noun phrases; labels are transcript spans, not invented titles."""
    if doc is None:
        from backend.services.preprocessing import _get_nlp
        doc = _get_nlp()(" ".join(sentences))
    phrases = {}
    for chunk in doc.noun_chunks:
        tokens = list(chunk)
        while tokens and (tokens[0].is_stop or tokens[0].pos_ in {"DET", "PRON", "ADJ", "CCONJ"}):
            tokens.pop(0)
        if not 2 <= len(tokens) <= 5 or not any(t.pos_ == "NOUN" for t in tokens):
            continue
        if any(not t.is_alpha or len(t.text) < 2 or t.lower_ in TOPIC_STOP for t in tokens):
            continue
        if tokens[-1].lower_ in {"owner", "team", "coach", "people", "participant", "participants", "case", "context", "benefit", "outcome", "thing", "company", "partnership", "fragment", "detail", "user", "users"}:
            continue
        phrase = doc[tokens[0].i:tokens[-1].i + 1].text
        key = phrase.casefold()
        phrases.setdefault(key, {"label": phrase, "keywords": [t.lower_ for t in tokens],
                                 "evidence": chunk.sent.text.strip(), "count": 0})["count"] += 1
    ranked = sorted(phrases.values(), key=lambda x: (-x["count"], -len(x["keywords"]), x["label"]))
    selected = []
    for item in ranked:
        if any(set(item["keywords"]) <= set(other["keywords"]) for other in selected):
            continue
        item["relevance"] = round(item.pop("count") / max(1, len(sentences)), 4)
        selected.append(item)
        if len(selected) == limit:
            break
    return selected
