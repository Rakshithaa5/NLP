"""
services/preprocessing.py — NLP preprocessing service.

Uses spaCy and NLTK to clean and normalize the raw transcript
before downstream NER, classification, and topic modeling.

Steps (in order):
  1. Sentence segmentation     — spaCy sentencizer / parser
  2. Tokenization              — spaCy tokenizer
  3. Normalization             — punctuation/spacing cleanup via regex
  4. Stop-word handling        — spaCy + NLTK stopword union
  5. Lemmatization             — spaCy token.lemma_

Pipeline position: Transcribe → [NLP Preprocess] → NER | Classification | Topics
Phase 2: full implementation.
"""

import re
import logging

logger = logging.getLogger("meeting_analyzer.preprocessing")

# ── Lazy-loaded singletons (loaded once per worker process) ───────────────────
_nlp = None
_stop_words = None


def _get_nlp():
    """Lazily load and cache the spaCy English model."""
    global _nlp
    if _nlp is None:
        import spacy  # noqa: PLC0415

        logger.info("Loading spaCy model 'en_core_web_sm' …")
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Friendly error if the model has not been downloaded yet.
            raise RuntimeError(
                "spaCy model 'en_core_web_sm' not found. "
                "Run: python -m spacy download en_core_web_sm"
            )
        logger.info("spaCy model loaded.")
    return _nlp


def _get_stop_words():
    """
    Build and cache the combined stop-word set from spaCy + NLTK.
    The union gives broader coverage without being overly aggressive.
    """
    global _stop_words
    if _stop_words is None:
        import nltk  # noqa: PLC0415
        from nltk.corpus import stopwords  # noqa: PLC0415

        # Ensure the NLTK resource is present (downloads only on first run).
        try:
            nltk.data.find("corpora/stopwords")
        except LookupError:
            logger.info("Downloading NLTK stopwords …")
            nltk.download("stopwords", quiet=True)

        nlp = _get_nlp()
        spacy_stops = nlp.Defaults.stop_words
        nltk_stops = set(stopwords.words("english"))
        _stop_words = spacy_stops | nltk_stops
        logger.info(
            "Stop-word set ready — %d terms (spaCy ∪ NLTK).", len(_stop_words)
        )
    return _stop_words


# ── Helpers ───────────────────────────────────────────────────────────────────

_WS_RE = re.compile(r"\s+")
_FILLER_RE = re.compile(r"\b(um+|uh+|hmm+|like|you know|i mean)\b", re.IGNORECASE)


def _normalize(text: str) -> str:
    """
    Light normalization pass on raw transcript text:
      - Remove disfluency fillers (um, uh, hmm) common in speech transcripts
      - Collapse runs of whitespace / newlines to a single space
      - Strip leading/trailing whitespace
    """
    text = _FILLER_RE.sub("", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


# ── Public API ────────────────────────────────────────────────────────────────

def preprocess(text: str) -> dict:
    """
    Accept raw transcript text. Runs the full preprocessing pipeline and
    returns a dict suitable for downstream NER, classification, and topic
    modeling steps.

    Args:
        text: Full transcript string produced by Faster-Whisper.

    Returns:
        {
          "sentences": list[str]         — segmented sentence strings
          "tokens":    list[list[str]]   — token text per sentence
          "lemmas":    list[list[str]]   — lemma per token (excl. stop words / punct)
          "clean_tokens": list[list[str]]— tokens with stop words & punct removed
          "doc":       spacy.tokens.Doc  — full spaCy Doc (for NER / dep-parse reuse)
        }

    Raises:
        RuntimeError: if the spaCy model is unavailable.
    """
    nlp = _get_nlp()
    stop_words = _get_stop_words()

    # Step 1–3: normalize → parse (sentence segmentation + tokenization happen
    # inside spaCy's pipeline in a single pass; no need to split first).
    cleaned_text = _normalize(text)
    logger.info("Preprocessing transcript (%d chars) …", len(cleaned_text))

    # spaCy max_length guard — increase if transcripts are very long.
    if len(cleaned_text) > nlp.max_length:
        logger.warning(
            "Transcript (%d chars) exceeds spaCy max_length (%d). "
            "Truncating for preprocessing — NLP results may be partial.",
            len(cleaned_text),
            nlp.max_length,
        )
        cleaned_text = cleaned_text[: nlp.max_length]

    doc = nlp(cleaned_text)

    sentences: list[str] = []
    tokens: list[list[str]] = []
    clean_tokens: list[list[str]] = []
    lemmas: list[list[str]] = []

    for sent in doc.sents:
        sent_text = sent.text.strip()
        if not sent_text:
            continue

        # Step 2: tokenize — keep all tokens (including punct) for the raw list
        sent_tokens = [tok.text for tok in sent]

        # Step 4–5: filter stop words and punctuation; lemmatize survivors
        filtered = [
            tok
            for tok in sent
            if not tok.is_stop
            and not tok.is_punct
            and not tok.is_space
            and tok.text.lower() not in stop_words
        ]
        sent_clean = [tok.text for tok in filtered]
        sent_lemmas = [tok.lemma_.lower() for tok in filtered]

        sentences.append(sent_text)
        tokens.append(sent_tokens)
        clean_tokens.append(sent_clean)
        lemmas.append(sent_lemmas)

    logger.info(
        "Preprocessing complete — %d sentences, %d total tokens.",
        len(sentences),
        sum(len(t) for t in tokens),
    )

    return {
        "sentences":    sentences,
        "tokens":       tokens,
        "clean_tokens": clean_tokens,
        "lemmas":       lemmas,
        "doc":          doc,          # spaCy Doc — passed to ner.extract_entities
    }
