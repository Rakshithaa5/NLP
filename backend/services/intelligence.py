"""Canonical meeting analysis and transcript-grounded field validation."""
import logging
import math
import re
from typing import Literal
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class Evidence(BaseModel):
    evidence: str
    timestamp: float | None = None
    segment_ids: list[int] = Field(default_factory=list)
    speaker: str | None = None


class Action(Evidence):
    task: str
    owner: str | None = None
    deadline: str | None = None
    priority: Literal["high", "medium", "low"] | None = None
    status: str = "Pending"
    owner_evidence: str | None = None
    deadline_evidence: str | None = None
    priority_evidence: str | None = None


class Decision(Evidence):
    decision: str


class Question(Evidence):
    question: str
    status: Literal["Resolved", "Unresolved", "Not assessed"] = "Unresolved"
    answer: str | None = None
    answer_evidence: Evidence | None = None


class Topic(Evidence):
    label: str
    keywords: list[str] = Field(default_factory=list)
    relevance: float | None = None


class Metadata(BaseModel):
    language: str | None = None
    duration: float | None = None
    speaker_count: int | None = None


class Intelligence(BaseModel):
    version: int = 2
    summary: list[str] = Field(default_factory=list)
    summary_evidence: list[Evidence] = Field(default_factory=list)
    key_takeaway: str | None = None
    takeaway_evidence: Evidence | None = None
    action_items: list[Action] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)
    entities: dict[str, list[str]] = Field(default_factory=lambda: {
        key: [] for key in ("people", "organizations", "dates", "locations", "products")})
    metadata: Metadata = Field(default_factory=Metadata)
    limitations: list[str] = Field(default_factory=list)


def norm(text):
    return re.sub(r"\s+", " ", text).strip() if isinstance(text, str) else ""


def evidence_for(quote, transcript, segments):
    quote = norm(quote)
    parts = [norm(s.get("text")) for s in segments]
    joined = " ".join(parts)
    if not quote or quote not in norm(transcript):
        return None
    result = {"evidence": quote, "timestamp": None, "segment_ids": [], "speaker": None}
    if joined != norm(transcript) or joined.count(quote) != 1:
        return result
    start, cursor = joined.index(quote), 0
    for index, part in enumerate(parts):
        if cursor < start + len(quote) and cursor + len(part) > start:
            result["segment_ids"].append(index)
        cursor += len(part) + 1
    if result["segment_ids"]:
        first = segments[result["segment_ids"][0]]
        value = first.get("start")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
            result["timestamp"] = value
        speakers = {norm(segments[i].get("speaker") or segments[i].get("speaker_id"))
                    for i in result["segment_ids"]}
        if len(speakers) == 1:
            result["speaker"] = speakers.pop() or None
    return result


def _contains(value, context):
    return bool(value and re.search(r"(?<!\w)" + re.escape(value.casefold()) + r"(?!\w)",
                                    norm(context).casefold()))


def _terms(value):
    value = re.sub(r"\bdocs?\b", "documentation", norm(value).casefold())
    return set(re.findall(r"\w+", value)) - {"the", "a", "an", "to", "should", "will"}


def deduplicate(items, field):
    """Merge paraphrases only when their evidence identifies the same event."""
    result = []
    for item in items:
        duplicate = None
        for other in result:
            if field == "task" and any(item.get(k) and other.get(k) and
                                      item[k] != other[k] for k in ("owner", "deadline")):
                continue
            a, b = _terms(item[field]), _terms(other[field])
            similar = a == b or (a and b and len(a & b) / len(a | b) >= .72)
            same_event = (item["evidence"] in other["evidence"] or
                          other["evidence"] in item["evidence"])
            if similar and same_event:
                duplicate = other
                break
        if duplicate is None:
            result.append(item)
        else:
            for key, value in item.items():
                if not duplicate.get(key) and value:
                    duplicate[key] = value
            if len(item["evidence"]) > len(duplicate["evidence"]):
                for key in ("evidence", "timestamp", "speaker", "segment_ids"):
                    duplicate[key] = item[key]
            if field == "question" and item.get("status") == "Resolved":
                for key in ("status", "answer", "answer_evidence"):
                    duplicate[key] = item[key]
    return result


def normalize_analysis(raw, transcript, segments=None, language="en", duration=None, source_transcript=None):
    """Validate sections independently. Return canonical data and diagnostic fields."""
    segments = [s for s in (segments or []) if isinstance(s, dict)]
    report = Intelligence()
    issues = list(raw.get("_parse_issues", [])) if isinstance(raw, dict) else []
    speakers = {norm(s.get("speaker") or s.get("speaker_id")) for s in segments}
    speakers.discard("")
    report.metadata = Metadata(language=language, duration=duration,
                               speaker_count=len(speakers) or None)
    if not isinstance(raw, dict):
        raise ValueError("Analysis response must be a JSON object")
    def rows(key):
        value = raw.get(key)
        if not isinstance(value, list):
            issues.append(key)
            return []
        return value
    def source(value):
        quote = value.get("evidence") if isinstance(value, dict) else value
        matched = (evidence_for(quote, source_transcript or transcript, segments)
                   if norm(quote) and norm(quote) in norm(transcript) else None)
        if matched:
            return matched
        # Exact numbered source references recover quotes without generating text.
        # Include intervening turns for disjoint references: never concatenate
        # separate quotes and pretend they were contiguous transcript text.
        ids = value.get("segment_ids") if isinstance(value, dict) else None
        if (isinstance(ids, list) and ids and
                all(type(i) is int and 0 <= i < len(segments) for i in ids)):
            original = " ".join(norm(segments[i].get("text"))
                                for i in range(min(ids), max(ids) + 1))
            return (evidence_for(original, source_transcript or transcript, segments)
                    if original in norm(transcript) else None)
        return None

    summary = raw.get("summary", [])
    if isinstance(summary, str):
        summary = [summary]
        issues.append("summary")
    if not isinstance(summary, list):
        summary = []
        issues.append("summary")
    quotes = rows("summary_evidence")
    for index, point in enumerate(summary):
        evidence = source(quotes[index]) if index < len(quotes) else source(point)
        if norm(point) and evidence:
            if norm(point) not in report.summary:
                report.summary.append(norm(point))
                report.summary_evidence.append(Evidence(**evidence))
        else:
            issues.append("summary")
    takeaway = norm(raw.get("key_takeaway"))
    if takeaway:
        evidence = source(raw.get("takeaway_evidence"))
        if evidence:
            report.key_takeaway = takeaway
            report.takeaway_evidence = Evidence(**evidence)
        else:
            issues.append("key_takeaway")

    for key, field, model in (("action_items", "task", Action), ("decisions", "decision", Decision),
                              ("questions", "question", Question), ("topics", "label", Topic)):
        valid = []
        for item in rows(key):
            if not isinstance(item, dict) or not norm(item.get(field)):
                issues.append(key)
                continue
            evidence = source(item)
            if not evidence:
                issues.append(key)
                continue
            value = {field: norm(item[field]), **evidence}
            if model is Action:
                for detail in ("owner", "deadline", "priority"):
                    candidate = norm(item.get(detail))
                    if candidate.casefold() in {"null", "none", "unknown", "unassigned", "not specified"}:
                        candidate = ""
                    extra = source(item.get(detail + "_evidence"))
                    supporting = evidence["evidence"] + (" " + extra["evidence"] if extra else "")
                    # Name/deadline may be in adjacent contextual evidence. Speaker
                    # attribution is supplied by the transcript, never by the model.
                    supported = candidate and (_contains(candidate, supporting) or
                                               (detail == "owner" and candidate == evidence["speaker"]))
                    if detail == "priority":
                        supported = candidate in {"high", "medium", "low"} and extra is not None
                    value[detail] = candidate if supported else None
                    value[detail + "_evidence"] = extra["evidence"] if supported and extra else None
                value["status"] = "Pending"
            elif model is Question:
                status = norm(item.get("status")).capitalize()
                value["status"] = status if status in {"Resolved", "Unresolved"} else "Not assessed"
                answer_source = source(item.get("answer_evidence"))
                answer = norm(item.get("answer"))
                if value["status"] == "Resolved" and answer and answer_source:
                    value["answer"], value["answer_evidence"] = answer, answer_source
                elif value["status"] == "Resolved":
                    value["status"] = "Not assessed"
                    issues.append("questions.answer")
            elif model is Topic:
                if norm(item[field]).casefold() in {"yeah", "okay", "meeting", "let", "s",
                                                     "review", "actually", "basically"} or len(norm(item[field])) < 2:
                    issues.append("topics")
                    continue
                value["keywords"] = [norm(v) for v in item.get("keywords", [])
                                     if norm(v)] if isinstance(item.get("keywords"), list) else []
            try:
                valid.append(model.model_validate(value).model_dump())
            except ValidationError:
                issues.append(key)
        setattr(report, key, [model.model_validate(v) for v in deduplicate(valid, field)])

    entities = raw.get("entities")
    if not isinstance(entities, dict):
        entities = {}
        issues.append("entities")
    context = norm(transcript) + " " + " ".join(speakers)
    for group in report.entities:
        values = entities.get(group, [])
        if not isinstance(values, list):
            issues.append("entities." + group)
            continue
        seen = set()
        for value in values:
            value = norm(value)
            common_word = value.casefold() in {"this", "that", "benefit", "developer", "limit", "okay", "yeah"}
            established_name = value in speakers or bool(re.search(
                r"(?:my name is|named|called)\s+" + re.escape(value) + r"\b", context, re.I))
            if group == "people" and common_word and not established_name:
                continue
            generic_component = value.casefold() in {"navigation", "sidebar", "authentication system",
                "report", "wireframes", "documentation", "backend team"}
            if group == "products" and generic_component and not established_name:
                continue
            if value and _contains(value, context) and value.casefold() not in seen:
                seen.add(value.casefold())
                report.entities[group].append(value)
    if not report.summary and norm(transcript):
        # Recover useful source excerpts, but mark the response partial.
        from backend.services.summarization import summarize_extractive, _sentence_split
        excerpts = _sentence_split(summarize_extractive(transcript, 6))
        for excerpt in excerpts:
            evidence = source(excerpt)
            if evidence:
                report.summary.append(excerpt)
                report.summary_evidence.append(Evidence(**evidence))
        if excerpts:
            issues.append("summary")
    if issues:
        logger.warning("Analysis fields needing recovery: %s", sorted(set(issues)))
    return report.model_dump(), sorted(set(issues))


def build_intelligence(result, transcript, segments=None, language="en"):
    """Compatibility entry point; never reinterpret already validated semantics."""
    if isinstance(result.get("intelligence"), dict):
        return result["intelligence"]
    raise ValueError("Legacy report requires semantic re-analysis")


def legacy_payload(report):
    """One-way boundary adapter for existing database columns and PDF clients."""
    groups = {"people": "PERSON", "organizations": "ORG", "dates": "DATE",
              "locations": "LOCATION", "products": "TECHNOLOGY"}
    return {
        "intelligence": report, "sentences": [], "classifications": [],
        "summary": {"extractive": " ".join(report["summary"]), "abstractive": "", "preferred": "semantic"},
        "action_items": [{**a, "person": a["owner"], "original": a["evidence"]} for a in report["action_items"]],
        "decisions": [{**d, "statement": d["decision"], "original": d["evidence"]} for d in report["decisions"]],
        "questions": [{**q, "resolution_status": q["status"], "original": q["evidence"]} for q in report["questions"]],
        "topics": {"discussion": report["topics"], "intelligence": report},
        "entities": [{"text": v, "label": groups[k]} for k, values in report["entities"].items()
                     for v in values if k in groups],
    }
