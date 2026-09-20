"""Validated, additive dashboard contract. All insight text must have source evidence."""
import math
import re
from typing import Literal
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    evidence: str
    timestamp: float | None = None
    segment_ids: list[int] = Field(default_factory=list)


class Action(Evidence):
    task: str
    owner: str | None = None
    deadline: str | None = None
    priority: Literal["high", "medium", "low"] | None = None
    status: str = "Pending"


class Decision(Evidence):
    decision: str


class Question(Evidence):
    question: str
    status: Literal["Resolved", "Unresolved", "Not assessed"] = "Not assessed"
    answer: str | None = None
    answer_evidence: Evidence | None = None


class Topic(Evidence):
    label: str
    keywords: list[str] = Field(default_factory=list)
    relevance: float | None = None


class Intelligence(BaseModel):
    version: int = 2
    summary: list[str] = Field(default_factory=list)
    key_takeaway: str | None = None
    action_items: list[Action] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)
    entities: dict[str, list[str]] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


def norm(text):
    return re.sub(r"\s+", " ", text or "").strip()


def evidence_for(quote, transcript, segments):
    quote = norm(quote)
    if not quote or quote not in norm(transcript):
        return None
    # Exact normalized substring only. Ambiguous repeated excerpts stay unmapped.
    parts = [norm(s.get("text", "")) for s in segments]
    joined = " ".join(parts)
    result = {"evidence": quote, "timestamp": None, "segment_ids": []}
    if joined.count(quote) != 1:
        return result
    start = joined.index(quote)
    end = start + len(quote)
    cursor = 0
    for index, part in enumerate(parts):
        if cursor < end and cursor + len(part) > start:
            result["segment_ids"].append(index)
        cursor += len(part) + 1
    if result["segment_ids"]:
        value = segments[result["segment_ids"][0]].get("start")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
            result["timestamp"] = value
    return result


def build_intelligence(result, transcript, segments=None, language="en"):
    segments = segments if isinstance(segments, list) else []
    segments = [s if isinstance(s, dict) else {} for s in segments]
    report = Intelligence()
    if language and language.lower().split("-")[0] != "en":
        report.limitations.append("Original-language transcript is preserved. Reliable semantic extraction is currently available for English; other languages show source excerpts only.")
        report.summary = [norm(s.get("text", "")) for s in segments if norm(s.get("text", ""))][:6]
        if not report.summary and transcript.strip():
            report.summary = [transcript.strip()]
        return report.model_dump()
    from backend.services.summarization import _sentence_split
    report.summary = [s for s in _sentence_split(result.get("summary", {}).get("extractive", ""))
                      if evidence_for(s, transcript, segments)][:6]
    for item in result.get("action_items", []) or []:
        source = evidence_for(item.get("original", ""), transcript, segments)
        if not source:
            continue
        owner = item.get("person")
        deadline = item.get("deadline")
        # Ownership/deadline must literally occur in the supporting source.
        owner = owner if owner and owner in source["evidence"] else None
        deadline = deadline if deadline and deadline in source["evidence"] else None
        priority_match = re.search(r"\b(high|medium|low)[ -]priority\b", source["evidence"], re.I)
        report.action_items.append(Action(task=source["evidence"], owner=owner, deadline=deadline,
            priority=priority_match.group(1).lower() if priority_match else None, **source))
    for item in result.get("decisions", []) or []:
        source = evidence_for(item.get("original", ""), transcript, segments)
        if source:
            report.decisions.append(Decision(decision=source["evidence"], **source))
    # Last explicit outcome is a traceable takeaway; no invented overall conclusion.
    if report.decisions:
        report.key_takeaway = report.decisions[-1].decision
        report.summary = [s for s in report.summary if s != report.key_takeaway]
    sentences = result.get("sentences", []) or [c.get("sentence", "") for c in result.get("classifications", [])]
    from backend.services.decisions import _is_unresolved
    for item in result.get("questions", []) or []:
        source = evidence_for(item.get("original", ""), transcript, segments)
        if not source:
            continue
        question = Question(question=source["evidence"], **source)
        # Only explicit unresolved language establishes unresolved status.
        if _is_unresolved(question.question):
            question.status = "Unresolved"
        # An explicit adjacent answer marker is supported; topical guesses are not.
        try:
            index = sentences.index(item["original"])
            following = sentences[index + 1] if index + 1 < len(sentences) else ""
        except ValueError:
            following = ""
        if re.match(r"^(?:the answer is|answer:)\s*", following, re.I):
            answer_source = evidence_for(following, transcript, segments)
            if answer_source and not re.search(r"\b(?:unknown|unclear|not sure|TBD)\b", following, re.I):
                question.status = "Resolved"
                question.answer = following
                question.answer_evidence = Evidence(**answer_source)
        report.questions.append(question)
    for item in (result.get("topics") or {}).get("discussion", []) or []:
        source = evidence_for(item.get("evidence", ""), transcript, segments)
        if source and item.get("label", "") in source["evidence"]:
            report.topics.append(Topic(label=item["label"], keywords=item.get("keywords", []), relevance=item.get("relevance"), **source))
    groups = {"PERSON": "people", "ORG": "organizations", "DATE": "dates", "TIME": "dates",
              "TECHNOLOGY": "products", "PROJECT": "products", "LOCATION": "locations"}
    for entity in result.get("entities", []) or []:
        group = groups.get(entity.get("label"))
        text = entity.get("text", "")
        if group and text and text in transcript:
            values = report.entities.setdefault(group, [])
            if text not in values:
                values.append(text)
    return report.model_dump()
