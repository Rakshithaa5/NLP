"""
Topic Segmentation & Evolution — pure NLP pipeline, no LLM calls.

Pipeline:
  A. Transcript preparation   — sentence windows from segments or plain text
  B. Semantic embeddings       — all-MiniLM-L6-v2 via HuggingFace transformers
  C. Boundary detection        — sliding-window cosine novelty + adaptive peaks
  D. Canonical topic matching  — agglomerative clustering on segment embeddings
  E. Topic labeling            — TF-IDF + spaCy noun phrases
  F. Evidence association      — link actions/decisions/questions by segment overlap

Random seed: 42 throughout for reproducibility.
"""

import hashlib
import logging
import math
import os
import re
from functools import lru_cache
from typing import Optional

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks

logger = logging.getLogger("meeting_analyzer.topic_segmentation")

# ── Configuration (overridable via env) ──────────────────────────────────────
EMBEDDING_MODEL = os.getenv("TOPIC_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
WINDOW_SIZE = int(os.getenv("TOPIC_WINDOW_SIZE", "3"))          # sentences per context window
MIN_SEGMENT_SENTENCES = int(os.getenv("TOPIC_MIN_SEG_SENTENCES", "2"))
CANONICAL_SIM_THRESHOLD = float(os.getenv("TOPIC_CANONICAL_SIM", "0.68"))
BATCH_SIZE = int(os.getenv("TOPIC_EMBED_BATCH", "32"))
SMOOTH_SIGMA = int(os.getenv("TOPIC_SMOOTH_SIGMA", "2"))        # uniform filter half-width
PEAK_PROMINENCE = float(os.getenv("TOPIC_PEAK_PROMINENCE", "0.08"))
MERGE_SIM_THRESHOLD = float(os.getenv("TOPIC_MERGE_SIM", "0.82"))

# ── Embedding model (lazy singleton) ─────────────────────────────────────────
_tokenizer = None
_model = None
_device = None


def _get_model():
    global _tokenizer, _model, _device
    if _model is None:
        import torch
        from transformers import AutoTokenizer, AutoModel
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading embedding model %s on %s", EMBEDDING_MODEL, _device)
        _tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL)
        _model = AutoModel.from_pretrained(EMBEDDING_MODEL).to(_device)
        _model.eval()
        logger.info("Embedding model loaded")
    return _tokenizer, _model, _device


def _mean_pool(token_embeddings, attention_mask):
    """Mean pooling over non-padding tokens."""
    mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return (token_embeddings * mask).sum(1) / mask.sum(1).clamp(min=1e-9)


def embed_texts(texts: list[str]) -> np.ndarray:
    """Return L2-normalized embeddings, shape (N, D). Batched for memory efficiency."""
    import torch
    tokenizer, model, device = _get_model()
    all_embeddings = []
    with torch.no_grad():
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i: i + BATCH_SIZE]
            encoded = tokenizer(batch, padding=True, truncation=True,
                                max_length=128, return_tensors="pt").to(device)
            output = model(**encoded)
            pooled = _mean_pool(output.last_hidden_state, encoded["attention_mask"])
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            all_embeddings.append(pooled.cpu().numpy())
    return np.vstack(all_embeddings)


# ── Stage A: Transcript preparation ──────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """Sentence-split plain text using spaCy, falling back to regex."""
    try:
        from backend.services.preprocessing import _get_nlp
        doc = _get_nlp()(text)
        return [s.text.strip() for s in doc.sents if s.text.strip()]
    except Exception:
        logger.warning("spaCy sentence splitting unavailable; using regex fallback")
        return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]


def prepare_units(transcript: str, segments: list[dict]) -> list[dict]:
    """
    Return a list of sentence-level units:
      {text, seg_index, start, end}
    Preserves original segment timestamps when available.
    Falls back to sentence splitting on plain text.
    """
    units = []
    clean_segs = [s for s in segments if isinstance(s, dict) and s.get("text", "").strip()]

    if clean_segs:
        for idx, seg in enumerate(clean_segs):
            text = re.sub(r"\s+", " ", seg["text"]).strip()
            if not text:
                continue
            units.append({
                "text": text,
                "seg_index": idx,
                "start": seg.get("start"),
                "end": seg.get("end"),
            })
    else:
        sentences = _split_sentences(transcript)
        for idx, sent in enumerate(sentences):
            units.append({"text": sent, "seg_index": idx, "start": None, "end": None})

    return units


# ── Stage B: Contextual window embeddings ────────────────────────────────────

def _window_texts(units: list[dict], window: int) -> list[str]:
    """Concatenate a sliding window of sentences around each position."""
    texts = [u["text"] for u in units]
    result = []
    for i in range(len(texts)):
        lo = max(0, i - window)
        hi = min(len(texts), i + window + 1)
        result.append(" ".join(texts[lo:hi]))
    return result


# ── Stage C: Adaptive boundary detection ─────────────────────────────────────

def _novelty_signal(embeddings: np.ndarray, window: int) -> np.ndarray:
    """
    For each position i, compute cosine similarity between the mean of the
    left-window embeddings and the mean of the right-window embeddings.
    Novelty = 1 - similarity (high novelty = likely topic boundary).
    """
    n = len(embeddings)
    novelty = np.zeros(n)
    for i in range(window, n - window):
        left = embeddings[max(0, i - window): i].mean(axis=0)
        right = embeddings[i: min(n, i + window)].mean(axis=0)
        left /= np.linalg.norm(left) + 1e-9
        right /= np.linalg.norm(right) + 1e-9
        novelty[i] = 1.0 - float(np.dot(left, right))
    return novelty


def detect_boundaries(units: list[dict], embeddings: np.ndarray) -> list[int]:
    """
    Return sorted list of boundary indices (first unit of each new segment).
    Always includes 0.
    """
    n = len(units)
    if n < 2 * MIN_SEGMENT_SENTENCES + 1:
        return [0]

    novelty = _novelty_signal(embeddings, WINDOW_SIZE)
    # Smooth to suppress local noise
    smoothed = uniform_filter1d(novelty.astype(float), size=max(1, SMOOTH_SIGMA * 2 + 1))

    # Adaptive threshold: mean + fraction of std
    threshold = smoothed.mean() + PEAK_PROMINENCE * smoothed.std()

    peaks, _ = find_peaks(smoothed, height=threshold, distance=MIN_SEGMENT_SENTENCES)

    # Merge oversegmented adjacent peaks where semantic coherence is high
    filtered = []
    for peak in peaks:
        if filtered:
            prev = filtered[-1]
            sim = float(cosine_similarity(
                embeddings[prev].reshape(1, -1),
                embeddings[peak].reshape(1, -1)
            )[0, 0])
            if sim >= MERGE_SIM_THRESHOLD:
                continue  # skip — same topic continues
        filtered.append(int(peak))

    boundaries = sorted({0} | set(filtered))
    return boundaries


# ── Stage D: Canonical topic identification ───────────────────────────────────

def _segment_embedding(units: list[dict], embeddings: np.ndarray,
                        start: int, end: int) -> np.ndarray:
    """Mean embedding for a contiguous range of units."""
    chunk = embeddings[start:end]
    mean = chunk.mean(axis=0)
    norm = np.linalg.norm(mean)
    return mean / (norm + 1e-9)


def assign_canonical_topics(segments: list[dict], seg_embeddings: np.ndarray) -> list[int]:
    """
    Cluster segment embeddings into canonical topics using agglomerative
    clustering with cosine distance threshold. Returns canonical_id per segment.
    """
    n = len(segments)
    if n == 1:
        return [0]

    # Distance matrix (1 - cosine_similarity)
    sim = cosine_similarity(seg_embeddings)
    dist = np.clip(1.0 - sim, 0.0, 2.0)

    # Use distance threshold: segments within (1 - CANONICAL_SIM_THRESHOLD) are same topic
    distance_threshold = 1.0 - CANONICAL_SIM_THRESHOLD

    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=distance_threshold,
        metric="precomputed",
        linkage="average",
    )
    labels = clustering.fit_predict(dist)

    # Post-process: merge clusters whose centroids are very similar
    # Build centroid per cluster
    unique = sorted(set(labels))
    centroids = {}
    for cid in unique:
        idxs = [i for i, l in enumerate(labels) if l == cid]
        centroids[cid] = seg_embeddings[idxs].mean(axis=0)

    # Remap similar clusters to the same canonical id
    remap = {cid: cid for cid in unique}
    for i, a in enumerate(unique):
        for b in unique[i + 1:]:
            if remap[b] != b:
                continue
            sim_ab = float(np.dot(centroids[a], centroids[b]) /
                           (np.linalg.norm(centroids[a]) * np.linalg.norm(centroids[b]) + 1e-9))
            if sim_ab >= CANONICAL_SIM_THRESHOLD:
                remap[b] = remap[a]

    # Normalize to 0-based contiguous IDs
    seen, counter = {}, 0
    final = []
    for lbl in labels:
        mapped = remap[lbl]
        if mapped not in seen:
            seen[mapped] = counter
            counter += 1
        final.append(seen[mapped])
    return final


# ── Stage E: Topic labeling ───────────────────────────────────────────────────

_LABEL_STOP = set(
    "yeah yes okay ok right meeting meetings let lets um uh actually basically "
    "really just like know think thanks thank hello hi going got things thing "
    "today everyone people said say sure well gonna want need look bit sort kind "
    "going going going sorry worries works fair sounds great perfect good deal "
    "understood talk load stress totally exactly connect push haven ask hold "
    "ahead boring bye hey promise urgent honestly thought way".split()
)


def _tfidf_keywords(texts: list[str], top_n: int = 6) -> list[str]:
    if not texts or not any(t.strip() for t in texts):
        return []
    try:
        vec = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=2000,
            sublinear_tf=True,
            token_pattern=r"(?u)\b[^\W\d_][^\W_]+\b",
        )
        mat = vec.fit_transform(texts)
        scores = np.asarray(mat.sum(axis=0)).flatten()
        names = vec.get_feature_names_out()
        top = scores.argsort()[::-1]
        keywords = []
        for i in top:
            w = str(names[i])
            if w.casefold() not in _LABEL_STOP and len(w) > 2:
                keywords.append(w)
            if len(keywords) == top_n:
                break
        return keywords
    except ValueError:
        return []


def _noun_phrase_label(texts: list[str]) -> Optional[str]:
    """Extract the most frequent meaningful noun phrase as a label."""
    try:
        from backend.services.preprocessing import _get_nlp
        from backend.services.topics import TOPIC_STOP
        nlp = _get_nlp()
        combined = " ".join(texts)[:4000]  # cap for speed
        doc = nlp(combined)
        counts: dict[str, int] = {}
        for chunk in doc.noun_chunks:
            tokens = [t for t in chunk if not t.is_stop and t.is_alpha and len(t.text) > 2
                      and t.lower_ not in TOPIC_STOP]
            if len(tokens) < 2:
                continue
            phrase = " ".join(t.text for t in tokens).strip()
            if phrase:
                counts[phrase.casefold()] = counts.get(phrase.casefold(), 0) + 1
        if not counts:
            return None
        best = max(counts, key=lambda k: (counts[k], len(k)))
        return " ".join(w.capitalize() for w in best.split())
    except Exception:
        logger.warning("Noun phrase labeling unavailable; falling back to TF-IDF keywords")
        return None


def label_topic(texts: list[str]) -> tuple[str, list[str]]:
    """Return (label, keywords) for a set of sentences."""
    keywords = _tfidf_keywords(texts, top_n=6)
    label = _noun_phrase_label(texts)
    if not label and keywords:
        # Fallback: capitalize top 2 TF-IDF keywords
        label = " & ".join(w.title() for w in keywords[:2])
    if not label:
        label = "General Discussion"
    return label, keywords


# ── Groq intelligence topic mapping ──────────────────────────────────────────

def _groq_topics(analysis: Optional[dict]) -> list[dict]:
    """Extract validated Groq topics from analysis, sorted by first segment id."""
    if not analysis:
        return []
    intel = (analysis.get("topics") or {}).get("intelligence") or analysis.get("intelligence") or {}
    topics = [t for t in (intel.get("topics") or []) if isinstance(t, dict) and t.get("label") and t.get("segment_ids")]
    return sorted(topics, key=lambda t: min(t["segment_ids"]))


def _assign_groq_labels(
    out_segments: list[dict],
    groq_topics: list[dict],
    seg_embeddings: np.ndarray,
) -> None:
    """
    For each output segment, assign the best-matching Groq topic label.
    Matching is by segment_id overlap first, then by embedding similarity
    to the Groq topic's evidence text.
    Mutates out_segments in place.
    """
    # Build a unit_index -> groq_topic_id map from segment_ids overlap
    unit_to_groq: dict[int, int] = {}
    for gid, gt in enumerate(groq_topics):
        for sid in gt["segment_ids"]:
            unit_to_groq[sid] = gid

    # Embed Groq topic evidence texts for similarity fallback
    groq_evidence_texts = [t.get("evidence") or t["label"] for t in groq_topics]
    groq_embeddings = embed_texts(groq_evidence_texts) if groq_topics else np.empty((0, 1))

    for i, seg in enumerate(out_segments):
        unit_indices = set(seg.get("unit_indices") or [])
        # Count votes from overlapping unit->groq mappings
        votes: dict[int, int] = {}
        for uid in unit_indices:
            if uid in unit_to_groq:
                gid = unit_to_groq[uid]
                votes[gid] = votes.get(gid, 0) + 1

        if votes:
            best_gid = max(votes, key=lambda g: votes[g])
        elif groq_topics:
            # Fallback: cosine similarity between segment embedding and groq topic embeddings
            sims = cosine_similarity(seg_embeddings[i].reshape(1, -1), groq_embeddings)[0]
            best_gid = int(np.argmax(sims))
        else:
            continue

        gt = groq_topics[best_gid]
        seg["label"] = gt["label"]
        seg["keywords"] = gt.get("keywords") or seg.get("keywords") or []
        seg["canonical_topic_id"] = best_gid


def _rebuild_canonical_from_groq(
    out_segments: list[dict],
    groq_topics: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Rebuild canonical_topics and evolution lists using Groq labels."""
    canonical_topics = []
    for gid, gt in enumerate(groq_topics):
        occurrences = [s for s in out_segments if s.get("canonical_topic_id") == gid]
        if not occurrences:
            continue
        first = occurrences[0]
        canonical_topics.append({
            "canonical_topic_id": gid,
            "label": gt["label"],
            "keywords": gt.get("keywords") or [],
            "occurrence_count": len(occurrences),
            "first_segment_index": first["segment_index"],
            "first_start_time": first["start_time"],
            "total_sentences": sum(s["sentence_count"] for s in occurrences),
            "segment_indices": [s["segment_index"] for s in occurrences],
        })

    evolution = [
        {
            "canonical_topic_id": ct["canonical_topic_id"],
            "label": ct["label"],
            "occurrences": [
                {
                    "segment_index": s["segment_index"],
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                    "excerpt": s["excerpt"],
                    "related_actions": s.get("related_actions", []),
                    "related_decisions": s.get("related_decisions", []),
                    "related_questions": s.get("related_questions", []),
                }
                for s in out_segments if s.get("canonical_topic_id") == ct["canonical_topic_id"]
            ],
        }
        for ct in canonical_topics
    ]
    return canonical_topics, evolution


# ── Stage F: Evidence association ─────────────────────────────────────────────

def _seg_ids_for_range(units: list[dict], start_unit: int, end_unit: int) -> set[int]:
    return {u["seg_index"] for u in units[start_unit:end_unit]}


def associate_evidence(topic_segments: list[dict], analysis: dict) -> dict[int, dict]:
    """
    For each topic segment, find related actions/decisions/questions from
    the existing analysis by checking segment_ids overlap.
    Returns {segment_index: {actions, decisions, questions}}.
    """
    intel = (analysis.get("topics") or {}).get("intelligence") or analysis.get("intelligence") or {}

    def items_for(key):
        return [item for item in (intel.get(key) or []) if isinstance(item, dict)]

    result = {}
    for seg in topic_segments:
        seg_id_set = set(seg.get("unit_indices") or [])
        if not seg_id_set:
            continue
        matched = {"actions": [], "decisions": [], "questions": []}
        for item in items_for("action_items"):
            ids = set(item.get("segment_ids") or [])
            if ids & seg_id_set:
                matched["actions"].append(item.get("task", ""))
        for item in items_for("decisions"):
            ids = set(item.get("segment_ids") or [])
            if ids & seg_id_set:
                matched["decisions"].append(item.get("decision", ""))
        for item in items_for("questions"):
            ids = set(item.get("segment_ids") or [])
            if ids & seg_id_set:
                matched["questions"].append(item.get("question", ""))
        result[seg["segment_index"]] = matched
    return result


# ── Main pipeline ─────────────────────────────────────────────────────────────

def _transcript_hash(transcript: str, segments: list[dict]) -> str:
    content = transcript + str(len(segments))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def analyze_topics(
    transcript: str,
    segments: list[dict],
    analysis: Optional[dict] = None,
) -> dict:
    """
    Full topic segmentation pipeline.

    Returns a dict with:
      - segments: list of topic segment dicts
      - canonical_topics: list of canonical topic dicts
      - evolution: per-canonical-topic occurrence timeline
      - model: embedding model name
      - transcript_hash: for cache invalidation
    """
    if not transcript or not transcript.strip():
        return _empty_result(transcript, segments)

    units = prepare_units(transcript, segments)
    if len(units) < 2:
        return _empty_result(transcript, segments)

    logger.info("Topic segmentation: %d units from transcript (%d chars)", len(units), len(transcript))

    # Stage B: embed all units with context windows
    window_texts = _window_texts(units, WINDOW_SIZE)
    unit_embeddings = embed_texts(window_texts)

    # Stage C: detect boundaries
    boundaries = detect_boundaries(units, unit_embeddings)
    boundaries_set = set(boundaries)

    # Build contiguous topic segments
    raw_segments = []
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(units)
        seg_units = units[start:end]
        raw_segments.append({
            "segment_index": i,
            "unit_start": start,
            "unit_end": end,
            "units": seg_units,
            "texts": [u["text"] for u in seg_units],
            "start_time": seg_units[0]["start"],
            "end_time": seg_units[-1]["end"],
        })

    logger.info("Detected %d topic segments from %d boundaries", len(raw_segments), len(boundaries))

    # Stage D: segment-level embeddings for canonical matching
    seg_embeddings = np.vstack([
        _segment_embedding(units, unit_embeddings, s["unit_start"], s["unit_end"])
        for s in raw_segments
    ])
    canonical_ids = assign_canonical_topics(raw_segments, seg_embeddings)

    # Stage E: label each canonical topic (TF-IDF fallback)
    canonical_texts: dict[int, list[str]] = {}
    for seg, cid in zip(raw_segments, canonical_ids):
        canonical_texts.setdefault(cid, []).extend(seg["texts"])

    canonical_labels: dict[int, tuple[str, list[str]]] = {}
    for cid, texts in canonical_texts.items():
        canonical_labels[cid] = label_topic(texts)

    # Build output segments
    out_segments = []
    for seg, cid in zip(raw_segments, canonical_ids):
        label, keywords = canonical_labels[cid]
        excerpt = " ".join(seg["texts"][:2])[:300]
        out_seg = {
            "segment_index": seg["segment_index"],
            "canonical_topic_id": cid,
            "label": label,
            "keywords": keywords,
            "start_time": seg["start_time"],
            "end_time": seg["end_time"],
            "unit_start": seg["unit_start"],
            "unit_end": seg["unit_end"],
            "unit_indices": [u["seg_index"] for u in seg["units"]],
            "excerpt": excerpt,
            "sentence_count": len(seg["texts"]),
        }
        out_segments.append(out_seg)

    # Stage F: associate evidence
    if analysis:
        evidence_map = associate_evidence(out_segments, analysis)
        for seg in out_segments:
            ev = evidence_map.get(seg["segment_index"], {})
            seg["related_actions"] = ev.get("actions", [])
            seg["related_decisions"] = ev.get("decisions", [])
            seg["related_questions"] = ev.get("questions", [])

    # Stage G: override labels with Groq intelligence topics when available
    groq_topics = _groq_topics(analysis)
    if groq_topics:
        logger.info("Applying %d Groq topic labels to %d segments", len(groq_topics), len(out_segments))
        _assign_groq_labels(out_segments, groq_topics, seg_embeddings)
        canonical_topics, evolution = _rebuild_canonical_from_groq(out_segments, groq_topics)
    else:
        # Build canonical topic summaries from TF-IDF labels
        canonical_topics = []
        for cid in sorted(canonical_texts.keys()):
            label, keywords = canonical_labels[cid]
            occurrences = [s for s in out_segments if s["canonical_topic_id"] == cid]
            first = occurrences[0]
            canonical_topics.append({
                "canonical_topic_id": cid,
                "label": label,
                "keywords": keywords,
                "occurrence_count": len(occurrences),
                "first_segment_index": first["segment_index"],
                "first_start_time": first["start_time"],
                "total_sentences": sum(s["sentence_count"] for s in occurrences),
                "segment_indices": [s["segment_index"] for s in occurrences],
            })
        evolution = [
            {
                "canonical_topic_id": ct["canonical_topic_id"],
                "label": ct["label"],
                "occurrences": [
                    {
                        "segment_index": s["segment_index"],
                        "start_time": s["start_time"],
                        "end_time": s["end_time"],
                        "excerpt": s["excerpt"],
                        "related_actions": s.get("related_actions", []),
                        "related_decisions": s.get("related_decisions", []),
                        "related_questions": s.get("related_questions", []),
                    }
                    for s in out_segments if s["canonical_topic_id"] == ct["canonical_topic_id"]
                ],
            }
            for ct in canonical_topics
        ]

    return {
        "segments": out_segments,
        "canonical_topics": canonical_topics,
        "evolution": evolution,
        "model": EMBEDDING_MODEL,
        "transcript_hash": _transcript_hash(transcript, segments),
        "segment_count": len(out_segments),
        "canonical_topic_count": len(canonical_topics),
    }


def _empty_result(transcript: str, segments: list[dict]) -> dict:
    return {
        "segments": [],
        "canonical_topics": [],
        "evolution": [],
        "model": EMBEDDING_MODEL,
        "transcript_hash": _transcript_hash(transcript or "", segments or []),
        "segment_count": 0,
        "canonical_topic_count": 0,
    }
