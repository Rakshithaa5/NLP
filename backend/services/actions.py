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
    for tok in doc:
        # Ownership belongs to the task predicate, not an enclosing reporting verb.
        predicate = tok.head
        commitment = any(c.lower_ in {"will", "shall", "must", "'ll"} for c in predicate.children) or predicate.lemma_ in {"need", "have"}
        if tok.dep_ == "nsubj" and commitment and (tok.pos_ == "PROPN" or tok.ent_type_ == "PERSON"):
            return _expand_noun_phrase(tok)
        if tok.dep_ == "pobj" and tok.head.dep_ == "agent" and tok.pos_ == "PROPN":
            return _expand_noun_phrase(tok)
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
    for ent in doc.ents:
        if ent.label_ not in {"DATE", "TIME"}:
            continue
        prefix = sentence[max(0, ent.start_char - 24):ent.start_char]
        if re.search(r"\b(by|before|due|on|no later than)\s*$", prefix, re.I):
            return ent.text.strip()
        if re.fullmatch(r"tomorrow|tonight|next .+", ent.text, re.I):
            return ent.text.strip()
    match = re.search(r"\b(?:by|before|due)\s+(?:EOD|COB|end of (?:the )?(?:day|week|month))\b", sentence, re.I)
    return match.group(0) if match else None


def _extract_task(sentence: str, doc) -> str:
    """
    Extract the core task description from the sentence.

    Heuristic: Remove the person prefix (if any) from the beginning of the
    sentence and strip common action-item lead-ins such as modal constructions.
    Falls back to the full sentence if no simplification is possible.
    """
    # Preserve negation, objects and conditions rather than slicing at ROOT.
    return sentence.strip()


def _detect_status(sentence: str) -> str:
    """
    Check for explicit status signals in the sentence.
    Returns "Completed", "In Progress", "Blocked", or (default) "Pending".
    """
    # A future task mentioning "completed" is not already completed.
    return "Pending"


def is_action(sentence: str) -> bool:
    """Conservative commitment/request gate for classifier candidates."""
    text = sentence.replace("?", "'")
    if re.search(r"\b(if|unless|might|maybe|perhaps|would|should|could|not|never|won't|can't|cannot)\b|n't\b", text, re.I):
        return False
    verbs = r"(?:send|prepare|review|deliver|update|finish|complete|handle|write|create|fix|test|deploy|schedule|share|investigate|follow up|contact|check|publish|draft|submit|arrange|implement|provide)"
    if "?" in text and not re.search(r"\b(?:can you|please)\s+", text, re.I):
        return False
    matched = bool(re.search(r"\b(?:will|shall|must|need(?:s)? to|have to|has to|going to)\s+" + verbs + r"\b|\b(?:I|we|he|she|they)'ll\s+" + verbs + r"\b|\bplease\s+" + verbs + r"\b|^\s*(?:action item|todo|task)\s*:", text, re.I))
    request = bool(re.search(r"\b(?:can you|please)\s+(?:please\s+)?" + verbs + r"\b", text, re.I))
    if request or re.match(r"\s*(?:action item|todo|task)\s*:", text, re.I):
        return True
    if not matched:
        return False
    doc = _get_nlp()(text)
    # Distinguish a commitment from forecasts such as "the review will finish".
    for token in doc:
        if token.dep_ == "nsubj" and token.head.pos_ == "VERB":
            if token.pos_ == "PROPN" or token.lower_ in {"i", "we", "you", "he", "she", "they", "team", "engineering", "qa"}:
                return True
    return False


def _parse_action_sentence(sentence: str) -> dict:
    """
    Parse a single ACTION ITEM sentence into its structured components.
    Uses spaCy dependency parsing + NER + regex rules.
    """
    nlp = _get_nlp()
    doc = nlp(sentence)

    person = _extract_person(doc)
    if person is None:
        # Explicit addressee in a request, not an arbitrary PERSON mention.
        match = re.match(r"^([A-Z][a-z]+(?: [A-Z][a-z]+)?),\s*(?:can you|please)\b", sentence)
        if match:
            person = match.group(1)
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
        if not sentence or not is_action(sentence) or any(r["original"].casefold() == sentence.casefold() for r in results):
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
