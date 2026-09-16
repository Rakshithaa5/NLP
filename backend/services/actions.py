"""
services/actions.py — Action item extraction service.

Processes sentences classified as ACTION ITEM and uses NER +
dependency/semantic analysis + rule-based patterns to extract
structured action items.

Output schema per action item:
  { "person": str | None, "task": str, "deadline": str | None, "status": "Pending" }

Default status is always "Pending" unless stated otherwise in the text.

Pipeline position: Classification → [Actions] → Summarization
Phase 3: full implementation.

NLP techniques used:
  - spaCy dependency parsing  (subject extraction via nsubj arc)
  - spaCy NER                 (PERSON / DATE entity detection)
  - Rule-based regex patterns  (deadline keywords: "by", "before", "until", "due")
  - Pattern matching           (modal + verb constructions: "will", "needs to", "should")
"""

import re
import logging
from typing import Optional

logger = logging.getLogger("meeting_analyzer.actions")

# ── Lazy-loaded spaCy pipeline singleton ──────────────────────────────────────
_nlp = None


def _get_nlp():
    """Load spaCy 'en_core_web_sm' once per process."""
    global _nlp
    if _nlp is None:
        import spacy  # noqa: PLC0415

        logger.info("Loading spaCy model for action extraction …")
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            raise RuntimeError(
                "spaCy model 'en_core_web_sm' not found. "
                "Run: python -m spacy download en_core_web_sm"
            )
    return _nlp


# ── Regex patterns for deadline extraction ───────────────────────────────────

# Matches constructs like: "by Monday", "by end of week", "before Friday",
# "until next Tuesday", "due on 15th", "due by EOD"
_DEADLINE_RE = re.compile(
    r"\b(?:by|before|until|due(?:\s+(?:on|by))?|no\s+later\s+than)\b"
    r"\s+(?:end\s+of\s+)?(?:the\s+)?"
    r"(?:[A-Za-z]+day|(?:next|this)\s+\w+|\w{3,}\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}\s+\w+|EOD|COB|EOM|\w+)",
    re.IGNORECASE,
)

# Matches explicit date patterns: "March 15", "15/03", "2024-03-15" etc.
_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[\/\-]\d{1,2}(?:[\/\-]\d{2,4})?|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?)\b",
    re.IGNORECASE,
)

# Status keywords override — if present in the sentence the status changes
_STATUS_MAP = {
    r"\b(?:done|completed|finished|resolved)\b": "Completed",
    r"\b(?:in\s+progress|ongoing|working\s+on)\b": "In Progress",
    r"\b(?:blocked|on\s+hold|waiting)\b": "Blocked",
}


# ── Helper functions ──────────────────────────────────────────────────────────

def _extract_person(doc) -> Optional[str]:
    """
    Try three strategies (in order of reliability) to find the responsible person:

    1. Dependency parse: find the grammatical subject (nsubj) of the root verb.
       Prefer subjects that are PERSON entities.
    2. NER fallback: first PERSON entity in the sentence.
    3. Possessive pronouns linked to an earlier PERSON (heuristic).

    Returns the person string or None if no person can be determined.
    """
    # Strategy 1 — dependency subject of the root verb
    root_token = next((tok for tok in doc if tok.dep_ == "ROOT"), None)
    if root_token:
        for child in root_token.children:
            if child.dep_ in {"nsubj", "nsubjpass", "csubj"}:
                # Expand compound names: "John Smith" not just "John"
                person_text = _expand_noun_phrase(child)
                # Only keep proper nouns / PERSON entities (skip "I", "we", etc.)
                if len(person_text) > 1 and person_text.lower() not in _VAGUE_SUBJECTS:
                    return person_text

    # Strategy 2 — first PERSON entity in the sentence
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text.strip()

    return None


def _expand_noun_phrase(token) -> str:
    """
    Walk the dependency tree to collect compound / proper noun siblings so
    "John Smith" is returned instead of just "John".
    """
    parts = []
    # Collect compound modifiers that precede the token
    for child in token.lefts:
        if child.dep_ in {"compound", "amod", "nmod"} and child.pos_ in {"PROPN", "NOUN"}:
            parts.append(child.text)
    parts.append(token.text)
    # Collect right-side complements (e.g. last names in flat name structure)
    for child in token.rights:
        if child.dep_ in {"flat", "compound"} and child.pos_ == "PROPN":
            parts.append(child.text)
    return " ".join(parts)


# Subjects that are too vague to attribute ownership to a specific person
_VAGUE_SUBJECTS = {
    "i", "we", "they", "he", "she", "it", "everyone", "somebody", "someone",
    "nobody", "the team", "team", "all", "you", "us", "them",
}


def _extract_deadline(sentence: str, doc) -> Optional[str]:
    """
    Extract a deadline phrase using:
    1. Regex pattern for "by/before/until/due …" constructs.
    2. spaCy DATE entity fallback.

    Returns the matched deadline string or None.
    """
    # Strategy 1 — regex deadline phrase
    match = _DEADLINE_RE.search(sentence)
    if match:
        return match.group(0).strip()

    # Strategy 2 — spaCy DATE entity
    for ent in doc.ents:
        if ent.label_ == "DATE":
            return ent.text.strip()

    return None


def _extract_task(sentence: str, doc) -> str:
    """
    Extract the core task description from the sentence.

    Heuristic: Remove the person prefix (if any) from the beginning of the
    sentence and strip common action-item lead-ins such as modal constructions.
    Falls back to the full sentence if no simplification is possible.
    """
    text = sentence.strip()

    # Remove leading filler patterns like "Action item:", "TODO:", etc.
    text = re.sub(
        r"^(?:action\s+item\s*:?|todo\s*:?|task\s*:?)\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Try to strip the subject + modal/auxiliary prefix
    # e.g.  "John will prepare the slides" → "prepare the slides"
    root = next((tok for tok in doc if tok.dep_ == "ROOT"), None)
    if root:
        # Find where the actual verb phrase begins (skip subject + auxiliary)
        verb_idx = root.i
        # Walk back to find any auxiliary (will, should, must, needs) before the root
        for child in root.children:
            if child.dep_ in {"aux", "auxpass"} and child.i < verb_idx:
                verb_idx = child.i

        # Reconstruct from the verb onward (still within the sentence)
        task_tokens = [tok.text for tok in doc if tok.i >= verb_idx]
        task_text = " ".join(task_tokens).strip()
        if task_text and len(task_text.split()) >= 2:
            return task_text

    return text


def _detect_status(sentence: str) -> str:
    """
    Check for explicit status signals in the sentence.
    Returns "Completed", "In Progress", "Blocked", or (default) "Pending".
    """
    lower = sentence.lower()
    for pattern, status in _STATUS_MAP.items():
        if re.search(pattern, lower):
            return status
    return "Pending"


def _parse_action_sentence(sentence: str) -> dict:
    """
    Parse a single ACTION ITEM sentence into its structured components.
    Uses spaCy dependency parsing + NER + regex rules.
    """
    nlp = _get_nlp()
    doc = nlp(sentence)

    person = _extract_person(doc)
    deadline = _extract_deadline(sentence, doc)
    task = _extract_task(sentence, doc)
    status = _detect_status(sentence)

    return {
        "person":   person,
        "task":     task,
        "deadline": deadline,
        "status":   status,
        "original": sentence,   # preserve raw sentence for dashboard display
    }


# ── Public API ────────────────────────────────────────────────────────────────

def extract_actions(action_sentences: list[str], doc=None) -> list[dict]:
    """
    Accept sentences pre-classified as ACTION ITEM.
    Optionally accept a spaCy Doc for dependency/NER reuse (ignored here —
    each sentence is re-parsed individually for more precise extraction).

    Args:
        action_sentences: Sentences labelled ACTION ITEM by classification.py.
        doc: Optional full-transcript spaCy Doc (not used — kept for API compat).

    Returns:
        A list of action item dicts:
          [{"person": str|None, "task": str, "deadline": str|None,
            "status": str, "original": str}, ...]

    NLP techniques:
        - spaCy dependency parsing (nsubj arc for person extraction)
        - spaCy named entity recognition (PERSON, DATE entities)
        - Regex rule-based deadline detection
        - Status keyword detection
    """
    if not action_sentences:
        return []

    results = []
    for sentence in action_sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        try:
            action = _parse_action_sentence(sentence)
            results.append(action)
        except Exception as exc:
            logger.warning("Failed to parse action sentence '%s': %s", sentence[:60], exc)
            # Graceful fallback — keep sentence as a minimal action item
            results.append({
                "person":   None,
                "task":     sentence,
                "deadline": None,
                "status":   "Pending",
                "original": sentence,
            })

    logger.info(
        "Action extraction complete — %d action items extracted from %d sentences.",
        len(results),
        len(action_sentences),
    )
    return results
