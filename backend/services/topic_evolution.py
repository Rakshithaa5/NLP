"""
Cross-meeting topic evolution service.

Compares canonical topics across stored meetings using semantic similarity
on their label embeddings. Never re-processes full transcripts.
"""

import logging
from typing import Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from backend.services.meeting_store import list_local_meetings, read_local

logger = logging.getLogger("meeting_analyzer.topic_evolution")

CROSS_MEETING_SIM = float(__import__("os").getenv("TOPIC_CROSS_MEETING_SIM", "0.68"))


def _topic_text(ct: dict) -> str:
    """Combine label + keywords into a single text for embedding."""
    parts = [ct.get("label", "")]
    parts.extend(ct.get("keywords", []))
    return " ".join(p for p in parts if p)


def cross_meeting_evolution(meeting_ids: Optional[list[str]] = None) -> dict:
    """
    Load saved topic analyses for the given meetings (or all meetings),
    match canonical topics across meetings by semantic similarity,
    and return a chronological topic history.
    """
    from backend.services.topic_segmentation import embed_texts

    # Collect meetings with saved topic analyses
    if meeting_ids:
        candidates = [{"id": mid} for mid in meeting_ids]
    else:
        candidates = list_local_meetings()

    meeting_data = []
    for m in candidates:
        mid = m["id"]
        saved = read_local(mid, "topic_segments.json")
        if not saved or not saved.get("canonical_topics"):
            continue
        transcript_meta = read_local(mid, "transcript.json") or {}
        meeting_data.append({
            "meeting_id": mid,
            "filename": transcript_meta.get("filename") or mid,
            "uploaded_at": transcript_meta.get("uploaded_at") or "",
            "canonical_topics": saved["canonical_topics"],
        })

    if not meeting_data:
        return {"cross_meeting_topics": [], "meeting_count": 0}

    # Sort chronologically
    meeting_data.sort(key=lambda m: m["uploaded_at"])

    # Flatten all canonical topics with meeting context
    all_topics = []
    for m in meeting_data:
        for ct in m["canonical_topics"]:
            all_topics.append({
                "meeting_id": m["meeting_id"],
                "filename": m["filename"],
                "uploaded_at": m["uploaded_at"],
                "canonical_topic_id": ct["canonical_topic_id"],
                "label": ct["label"],
                "keywords": ct["keywords"],
                "occurrence_count": ct["occurrence_count"],
                "first_start_time": ct.get("first_start_time"),
                "total_sentences": ct.get("total_sentences", 0),
                "segment_indices": ct.get("segment_indices", []),
            })

    if not all_topics:
        return {"cross_meeting_topics": [], "meeting_count": len(meeting_data)}

    # Embed all topic texts
    texts = [_topic_text(t) for t in all_topics]
    embeddings = embed_texts(texts)

    # Greedy grouping: assign each topic to an existing cross-meeting group
    # or create a new one, based on cosine similarity to group centroid
    groups: list[dict] = []  # {label, keywords, centroid, occurrences}

    for i, topic in enumerate(all_topics):
        emb = embeddings[i]
        best_group = None
        best_sim = CROSS_MEETING_SIM - 1e-9

        for g in groups:
            sim = float(cosine_similarity(emb.reshape(1, -1), g["centroid"].reshape(1, -1))[0, 0])
            if sim > best_sim:
                best_sim = sim
                best_group = g

        occurrence = {
            "meeting_id": topic["meeting_id"],
            "filename": topic["filename"],
            "uploaded_at": topic["uploaded_at"],
            "canonical_topic_id": topic["canonical_topic_id"],
            "occurrence_count": topic["occurrence_count"],
            "first_start_time": topic["first_start_time"],
            "total_sentences": topic["total_sentences"],
        }

        if best_group is not None:
            best_group["occurrences"].append(occurrence)
            # Update centroid as running mean
            n = len(best_group["occurrences"])
            best_group["centroid"] = (best_group["centroid"] * (n - 1) + emb) / n
            norm = np.linalg.norm(best_group["centroid"])
            best_group["centroid"] /= norm + 1e-9
        else:
            groups.append({
                "cross_topic_id": len(groups),
                "label": topic["label"],
                "keywords": topic["keywords"],
                "centroid": emb.copy(),
                "occurrences": [occurrence],
            })

    # Build output — strip internal centroid, sort occurrences chronologically
    result = []
    for g in groups:
        occs = sorted(g["occurrences"], key=lambda o: o["uploaded_at"])
        result.append({
            "cross_topic_id": g["cross_topic_id"],
            "label": g["label"],
            "keywords": g["keywords"],
            "meeting_count": len({o["meeting_id"] for o in occs}),
            "occurrences": occs,
        })

    # Sort by number of meetings (most recurring first)
    result.sort(key=lambda g: -g["meeting_count"])

    return {
        "cross_meeting_topics": result,
        "meeting_count": len(meeting_data),
    }
