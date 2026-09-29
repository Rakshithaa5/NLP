"""Versioned extraction identity and evidence-checked reconciliation."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import logging
from backend.services.intelligence import deduplicate, evidence_for, norm, legacy_payload, normalize_analysis, _terms

logger = logging.getLogger(__name__)
ANALYSIS_VERSION = "meeting-intelligence-v3"
PROMPT_VERSION = "exhaustive-evidence-v1"
FIELDS = {"action_items": "task", "decisions": "decision", "questions": "question",
          "follow_ups": "task", "topics": "label"}

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()

def manifest(transcript, segments, language, analyzer):
    from backend.services.semantic import SYSTEM, transcript_units
    import os
    config = {"model": getattr(analyzer, "model", "test-double"), "temperature": 0, "top_p": 1,
              "seed_policy": "sha256-request-content", "budget": analyzer.budget,
              "max_output_tokens": getattr(analyzer, "output_tokens", None),
              "response_format": getattr(analyzer, "mode", None),
              "schema_hash": digest(getattr(analyzer, "schema", {})),
              "system_hash": digest(SYSTEM), "base_url": getattr(analyzer, "base_url", None),
              "reasoning_effort": os.getenv("MEETING_LLM_REASONING_EFFORT", "low"),
              "chunk_policy": "ordered-segments-byte-budget-one-turn-overlap-v1",
              "merge_policy": "deterministic-v1", "fallback_model": None}
    return {"analysis_version": ANALYSIS_VERSION, "prompt_version": PROMPT_VERSION,
            "model": config["model"], "config": config, "config_hash": digest(config),
            "input_hash": digest({"language": language, "transcript": transcript_units(transcript, segments)}),
            "created_at": datetime.now(timezone.utc).isoformat()}

def same_pipeline(old, new):
    return bool(old) and all(old.get(k) == new.get(k) for k in
                            ("analysis_version", "prompt_version", "config_hash", "input_hash"))

def merge_reports(reports):
    result = deepcopy(reports[0])
    for key, field in FIELDS.items():
        rows = [deepcopy(item) for report in reports for item in report.get(key, [])]
        rows.sort(key=lambda r: (tuple(r.get("segment_ids", [])), norm(r.get(field)).casefold()))
        result[key] = deduplicate(rows, field)
    result["summary"], result["summary_evidence"] = [], []
    for report in reports:
        for text, evidence in zip(report["summary"], report["summary_evidence"]):
            if text not in result["summary"]:
                result["summary"].append(text)
                result["summary_evidence"].append(deepcopy(evidence))
        for key, values in report["entities"].items():
            result["entities"][key] = sorted(set(result["entities"][key]) | set(values))
    result["extraction_audit"] = {key: {
        **{stage: sum(r.get("extraction_audit", {}).get(key, {}).get(stage, 0) for r in reports)
           for stage in ("generated", "parsed", "validated", "evidence_matched")},
        "deduplicated": len(result[key])} for key in FIELDS}
    return result

def assign_ids(report, meeting_id):
    for key, field in FIELDS.items():
        groups = {}
        for item in report.get(key, []):
            ids = tuple(sorted(set(item.get("segment_ids", []))))
            groups.setdefault(ids, []).append(item)
        for ids, items in groups.items():
            for item in items:
                # Distinct insights can share a single source turn; never collapse them by IDs alone.
                suffix = norm(item[field]).casefold() if len(items) > 1 else None
                item["id"] = digest([meeting_id, key, ids, suffix])[:24]
                item["evidence_segment_ids"] = list(ids)
                item["ai_fields"] = {k: deepcopy(v) for k, v in item.items()
                                     if k not in {"ai_fields", "user_edits", "reconciliation"}}

def valid_evidence(item, transcript, segments):
    quote = norm(item.get("evidence"))
    ids = item.get("segment_ids", [])
    if not quote or not ids or not all(type(i) is int and 0 <= i < len(segments) for i in ids):
        return False
    cited = " ".join(norm(segments[i].get("text")) for i in range(min(ids), max(ids)+1))
    return quote in cited and evidence_for(quote, transcript, segments) is not None

def _matches(a, b, field, unique):
    left, right = set(a.get("segment_ids", [])), set(b.get("segment_ids", []))
    if not left.intersection(right):
        return False
    quotes_overlap = norm(a.get("evidence")) in norm(b.get("evidence")) or norm(b.get("evidence")) in norm(a.get("evidence"))
    if field == "task" and any(a.get(k) and b.get(k) and a[k] != b[k] for k in ("owner", "deadline")):
        return False
    if left == right and unique and quotes_overlap:
        # Same turn may contain multiple tasks: evidence alone is not enough.
        x, y = _terms(a[field]), _terms(b[field])
        return bool(x and y and len(x & y) / len(x | y) >= 0.5)
    return len(deduplicate([deepcopy(a), deepcopy(b)], field)) == 1

def user_edits(item):
    edits = deepcopy(item.get("user_edits", {}))
    if item.get("ai_fields"):
        edits.update({k: deepcopy(item[k]) for k, v in item["ai_fields"].items()
                      if k in item and item[k] != v and k not in {"id", "segment_ids", "evidence_segment_ids"}})
    elif item.get("user_edited") or item.get("confirmed"):
        edits.update({k: deepcopy(v) for k, v in item.items() if k not in {"id", "user_edits", "ai_fields"}})
    for key in ("confirmed", "user_edited"):
        if key in item:
            edits[key] = item[key]
    return edits

def reconcile(previous, candidate, transcript, segments, meeting_id):
    report = deepcopy(candidate["intelligence"])
    old = (previous or {}).get("intelligence") or {}
    prior_manifest = old.get("analysis_manifest", {})
    if old and not prior_manifest:
        # Migrate pre-versioned reports through the current strict evidence validator.
        validated, _ = normalize_analysis(old, transcript, segments)
        assign_ids(validated, meeting_id)
        for key, field in FIELDS.items():
            for item in validated[key]:
                before = next((r for r in old.get(key, []) if r.get(field) == item[field]), {})
                edits = user_edits(before)
                if before.get("status") not in (None, "Pending", "Unresolved", "Not assessed", "Resolved"):
                    edits["status"] = before["status"]
                item["user_edits"] = edits
                item.update(edits)
        validated["manual_review_items"] = deepcopy(old.get("manual_review_items", []))
        old = validated
        prior_manifest = report.get("analysis_manifest", {})
    compatible = same_pipeline(prior_manifest, report.get("analysis_manifest", {}))
    audit = {}
    review = deepcopy(old.get("manual_review_items", []))
    for key, field in FIELDS.items():
        if key == "topics":
            # Topics describe the current report; accumulating broad labels creates duplicates.
            continue
        rows = report.get(key, [])
        counts = {"stable": 0, "retained": 0, "new": len(rows), "removed": 0}
        used = set()
        for before in old.get(key, []):
            ai = before.get("ai_fields", before)
            edits = user_edits(before)
            grounded = valid_evidence(ai, transcript, segments)
            ids = ai.get("segment_ids")
            unique = (sum(r.get("segment_ids") == ids for r in rows) <= 1 and
                      sum(r.get("segment_ids") == ids for r in old.get(key, [])) == 1)
            match = next((i for i, row in enumerate(rows) if grounded and i not in used and _matches(ai, row, field, unique)), None)
            if match is None and (not compatible or not grounded):
                counts["removed"] += 1
                if edits:
                    review.append({"category": key, "item": deepcopy(before), "reason": "source_or_pipeline_changed"})
                continue
            if match is None:
                row = deepcopy(before)
                row["reconciliation"] = "retained"
                rows.append(row)
                used.add(len(rows)-1)
                counts["retained"] += 1
            else:
                row = rows[match]
                used.add(match)
                row["id"] = before.get("id", row["id"])
                row["ai_fields"]["id"] = row["id"]
                row["reconciliation"] = "stable"
                if key == "questions" and ai.get("status") == "Resolved" and row.get("status") != "Resolved" and ai.get("answer_evidence") and valid_evidence(ai["answer_evidence"], transcript, segments):
                    for detail in ("status", "answer", "answer_evidence"):
                        row[detail] = deepcopy(ai[detail])
                        row["ai_fields"][detail] = deepcopy(ai[detail])
                counts["stable"] += 1
                counts["new"] -= 1
            row["user_edits"] = edits
            row.update(edits)
        # Keep old IDs, disambiguating a genuinely new item on an already-used source turn.
        occupied = {r["id"] for r in rows if r.get("reconciliation") in {"stable", "retained"}}
        for row in rows:
            if row.get("reconciliation") not in {"stable", "retained"} and row["id"] in occupied:
                row["id"] = digest([meeting_id, key, row["segment_ids"], norm(row[field]).casefold()])[:24]
                row["ai_fields"]["id"] = row["id"]
            occupied.add(row["id"])
            row.setdefault("reconciliation", "new")
        rows.sort(key=lambda r: (tuple(r.get("segment_ids", [])), r["id"]))
        report[key] = rows
        counts["persisted"] = len(rows)
        audit[key] = counts
        logger.info("Reconciliation category=%s counts=%s", key, counts)
    if compatible and old.get("takeaway_evidence") and valid_evidence(old["takeaway_evidence"], transcript, segments):
        report["key_takeaway"] = old["key_takeaway"]
        report["takeaway_evidence"] = deepcopy(old["takeaway_evidence"])
    report["manual_review_items"] = review
    report["reconciliation_audit"] = audit
    return {**candidate, **legacy_payload(report)}
