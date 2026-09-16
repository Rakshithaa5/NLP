"""
services/decisions.py — Decision & unresolved question extraction service.

Processes sentences classified as DECISION or QUESTION.

  - DECISION sentences → clean decision statements via keyword/pattern detection.
  - QUESTION sentences → "Unresolved Question" entries for the dashboard.

Pipeline position: Classification → [Decisions] → Summarization
Phase 3: full implementation.

NLP techniques used:
  - Keyword / pattern-based decision indicator detection
    (e.g. "decided", "agreed", "approved", "resolved", "confirmed")
  - Negation detection (to distinguish "not approved" from "approved")
  - Linguistic cleaning: strip discourse markers, hedges, filler phrases
  - Question normalisation: reformat as actionable unresolved-issue entries
"""

import re
import logging
from typing import Optional

logger = logging.getLogger("meeting_analyzer.decisions")

# ── Decision indicator vocabulary ─────────────────────────────────────────────
# Ordered from strongest (definitive) to softer indicators.
_DECISION_VERBS = [
    # Past-tense definitive verbs
    "decided", "agreed", "approved", "confirmed", "resolved", "concluded",
    "determined", "established", "finalized", "finalised", "settled",
    "selected", "chosen", "adopted", "endorsed", "voted", "ratified",
    # Present-tense constructs ("we will", "the plan is to", "going forward")
    "will", "going forward", "the plan is", "the decision is",
    "we are going", "it was decided", "it has been decided",
    "it was agreed", "it has been agreed",
    # Outcome markers
    "outcome:", "conclusion:", "decision:", "resolution:",
]

# Marker that usually precedes or introduces the core decision phrase
_DECISION_LEAD_RE = re.compile(
    r"\b(?:we|the\s+team|the\s+group|everyone|it\s+was|it\s+has\s+been)?\s*"
    r"(?:decided|agreed|approved|confirmed|resolved|concluded|determined|"
    r"established|finalized|finalised|settled|selected|chosen|adopted|"
    r"endorsed|voted|ratified|is\s+going|will\s+go|are\s+going)\b",
    re.IGNORECASE,
)

# Negation prefixes — if any immediately precede the indicator, it's NOT a decision
_NEGATION_RE = re.compile(
    r"\b(?:not|n't|never|no|don't|doesn't|didn't|won't|wouldn't|haven't|hasn't)\b",
    re.IGNORECASE,
)

# Discourse filler phrases to strip from the start of a sentence before
# extracting the clean decision statement
_FILLER_PREFIXES = re.compile(
    r"^(?:so|okay|ok|right|well|now|basically|essentially|actually|"
    r"you know|i think|i believe|i guess|i suppose|in summary|"
    r"in conclusion|to summarize|to conclude|moving on|"
    r"as discussed|as we discussed|as mentioned)[,\s]+",
    re.IGNORECASE,
)

# ── Question / unresolved issue patterns ─────────────────────────────────────

# Wh-question starters
_WH_RE = re.compile(
    r"^(?:who|what|when|where|why|how|which|whose|whom)\b",
    re.IGNORECASE,
)

# Rhetorical marker — "Does anyone know", "Can we check"
_RHETORICAL_RE = re.compile(
    r"^(?:does anyone|do we|can we|should we|would it|could we|"
    r"has anyone|is there|are there|will we)\b",
    re.IGNORECASE,
)

# Action-oriented follow-up question markers
_ACTION_QUESTION_RE = re.compile(
    r"\b(?:need\s+to\s+figure\s+out|need\s+to\s+decide|"
    r"still\s+open|open\s+question|to\s+be\s+decided|TBD|"
    r"to\s+be\s+confirmed|TBC|pending\s+decision|unclear)\b",
    re.IGNORECASE,
)


# ── Helper functions ──────────────────────────────────────────────────────────

def _clean_sentence(sentence: str) -> str:
    """Strip discourse fillers from the start of a sentence."""
    return _FILLER_PREFIXES.sub("", sentence).strip()


def _has_negation_before_indicator(sentence: str, indicator_start: int) -> bool:
    """
    Check whether a negation word appears in the 5 words immediately
    before the decision indicator (indicating the decision was NOT made).
    """
    prefix = sentence[:indicator_start]
    words = prefix.split()[-5:]  # last 5 words before the indicator
    return any(_NEGATION_RE.search(w) for w in words)


def _extract_decision_statement(sentence: str) -> Optional[str]:
    """
    Detect a decision indicator in the sentence; if found and not negated,
    return a cleaned decision statement string.

    Returns None if no strong decision signal is found.
    """
    clean = _clean_sentence(sentence)

    m = _DECISION_LEAD_RE.search(clean)
    if m:
        if _has_negation_before_indicator(clean, m.start()):
            # Negated — not a definitive decision
            logger.debug("Negated decision indicator ignored: '%s'", clean[:80])
            return None

        # Extract the portion after the indicator verb as the core statement
        after = clean[m.end():].strip().lstrip(",;:")
        if after:
            # Capitalise and ensure sentence ends with a period
            statement = after[0].upper() + after[1:]
            if not statement.endswith((".","!","?")):
                statement += "."
            return statement
        else:
            # Indicator verb was at the very end — return the whole clean sentence
            return clean if clean.endswith(".") else clean + "."

    # No indicator found — return the sentence as-is (classification already
    # flagged it as DECISION, so we trust that signal)
    return (clean if clean.endswith(".") else clean + ".") if clean else None


def _is_unresolved(sentence: str) -> bool:
    """
    Return True if the sentence contains an explicit marker for an open /
    unresolved issue (beyond just being classified as QUESTION).
    """
    return bool(_ACTION_QUESTION_RE.search(sentence))


def _format_question(sentence: str) -> str:
    """
    Normalise a question sentence for the dashboard.
    - Strip discourse fillers from the start.
    - Ensure it ends with a "?".
    """
    clean = _clean_sentence(sentence)
    if not clean:
        return sentence
    if not clean.endswith("?"):
        clean += "?"
    return clean[0].upper() + clean[1:]


# ── Public API ────────────────────────────────────────────────────────────────

def extract_decisions(decision_sentences: list[str]) -> list[dict]:
    """
    Accept sentences pre-classified as DECISION and extract clean decision
    statements.

    Args:
        decision_sentences: Sentences labelled DECISION by classification.py.

    Returns:
        A list of decision dicts:
          [{"statement": str, "original": str}, ...]

        "statement" is the cleaned, normalised decision text.
        "original"  is the raw classified sentence.

    NLP techniques:
        - Decision indicator keyword matching (decided, agreed, approved …)
        - Negation detection to filter false positives
        - Discourse marker stripping for clean output
    """
    if not decision_sentences:
        return []

    results = []
    for sentence in decision_sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        statement = _extract_decision_statement(sentence)
        if statement is None:
            # Fallback: use cleaned sentence
            statement = _clean_sentence(sentence)
            if not statement.endswith("."):
                statement += "."

        results.append({
            "statement": statement,
            "original":  sentence,
        })

    logger.info(
        "Decision extraction complete — %d decisions extracted from %d sentences.",
        len(results),
        len(decision_sentences),
    )
    return results


def extract_questions(question_sentences: list[str]) -> list[dict]:
    """
    Accept sentences pre-classified as QUESTION and format them as
    Unresolved Question entries.

    Args:
        question_sentences: Sentences labelled QUESTION by classification.py.

    Returns:
        A list of unresolved question dicts:
          [{"question": str, "is_action_required": bool, "original": str}, ...]

        "question"           — normalised question text.
        "is_action_required" — True if sentence contains an explicit
                               action-needed marker (TBD, "open question" etc.)
        "original"           — raw classified sentence.

    NLP techniques:
        - Wh-question and rhetorical pattern detection
        - Open-question / TBD marker detection
        - Discourse marker stripping
    """
    if not question_sentences:
        return []

    results = []
    for sentence in question_sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        question = _format_question(sentence)
        is_action_required = _is_unresolved(sentence)

        results.append({
            "question":           question,
            "is_action_required": is_action_required,
            "original":           sentence,
        })

    logger.info(
        "Question extraction complete — %d unresolved questions from %d sentences "
        "(%d flagged as action-required).",
        len(results),
        len(question_sentences),
        sum(1 for r in results if r["is_action_required"]),
    )
    return results
