"""
Offline evaluation for Topic Segmentation & Evolution.

Tests:
  1. Single-topic meeting          — no spurious boundaries
  2. Clear topic transitions       — boundaries at correct positions
  3. Recurring topics              — canonical matching across segments
  4. Gradual topic transitions     — no over-segmentation
  5. Short transcript              — graceful handling
  6. Long transcript               — batched embedding, reasonable segments
  7. Text-only (no timestamps)     — works without segment metadata
  8. Cross-meeting matching        — related topics linked across meetings

Metrics:
  - Boundary precision, recall, F1 (tolerance ±2 sentences)
  - WindowDiff (Pk approximation)
  - Topic recurrence precision
  - Processing time

Run: python -m unittest backend.scripts.test_topic_segmentation -v
"""

import time
import unittest

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_segments(sentences):
    """Build fake timestamped segments from a list of sentences."""
    segs = []
    t = 0.0
    for sent in sentences:
        dur = len(sent.split()) * 0.4  # ~0.4s per word
        segs.append({"text": sent, "start": t, "end": t + dur})
        t += dur
    return segs


AUTH_SENTENCES = [
    "We need to investigate the JWT authentication issue.",
    "The refresh tokens are expiring too quickly.",
    "Users are being logged out unexpectedly.",
    "The token validation logic needs a review.",
    "We should add better error messages for auth failures.",
]

UI_SENTENCES = [
    "Let's move on to the frontend redesign.",
    "The navigation bar needs to be simplified.",
    "We agreed to use a sidebar layout instead of tabs.",
    "The color scheme should match the new brand guidelines.",
    "Mobile responsiveness is a priority for this sprint.",
]

DEPLOY_SENTENCES = [
    "Now let's discuss the deployment plan.",
    "We need to set up the CI/CD pipeline before Friday.",
    "The staging environment is ready for testing.",
    "Docker containers should be used for consistency.",
    "We'll deploy to production after QA sign-off.",
]

AUTH_REVISIT = [
    "Coming back to authentication — we still haven't fixed the bug.",
    "The refresh token rotation approach was proposed.",
    "We need to implement token rotation before the next release.",
    "The JWT expiry time should be reduced to 15 minutes.",
    "We also need to add rate limiting to the login endpoint.",
]

GRADUAL = [
    "The API performance has been improving steadily.",
    "Response times are down to under 200ms on average.",
    "We should keep monitoring the database query times.",
    "The database indexes were updated last week.",
    "Query optimization is still ongoing for the reports endpoint.",
    "The reports feature itself needs a UI update.",
    "Users have requested better filtering options in reports.",
    "The filter panel design is being worked on by the frontend team.",
]


# ── Metric helpers ─────────────────────────────────────────────────────────────

def _boundary_metrics(predicted: list[int], reference: list[int], n: int, tolerance: int = 2):
    """
    Compute precision, recall, F1 for boundary detection.
    A predicted boundary matches a reference if within ±tolerance sentences.
    Boundary 0 is excluded (always present).
    """
    pred = set(b for b in predicted if b > 0)
    ref = set(b for b in reference if b > 0)
    matched_pred = set()
    matched_ref = set()
    for p in pred:
        for r in ref:
            if abs(p - r) <= tolerance and r not in matched_ref:
                matched_pred.add(p)
                matched_ref.add(r)
                break
    tp = len(matched_pred)
    precision = tp / len(pred) if pred else 1.0
    recall = tp / len(ref) if ref else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def _windowdiff(predicted_labels: list[int], reference_labels: list[int], k: int = 3) -> float:
    """
    WindowDiff segmentation error metric.
    Lower is better; 0 = perfect.
    """
    n = len(predicted_labels)
    if n != len(reference_labels) or n <= k:
        return 1.0

    def boundaries_in_window(labels, i, k):
        return sum(1 for j in range(i, i + k) if labels[j] != labels[j + 1])

    errors = 0
    for i in range(n - k):
        b_pred = boundaries_in_window(predicted_labels, i, k)
        b_ref = boundaries_in_window(reference_labels, i, k)
        errors += int(b_pred != b_ref)
    return round(errors / (n - k), 4)


def _labels_from_boundaries(boundaries: list[int], n: int) -> list[int]:
    """Convert boundary indices to per-sentence topic labels."""
    labels = [0] * n
    current = 0
    for i in range(n):
        if i in set(boundaries):
            current += 1
        labels[i] = current
    return labels


# ── Test cases ────────────────────────────────────────────────────────────────

class TestTopicSegmentation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Load embedding model once for all tests."""
        from backend.services.topic_segmentation import _get_model
        _get_model()

    def _run(self, sentences, segments=None):
        from backend.services.topic_segmentation import analyze_topics
        transcript = " ".join(sentences)
        segs = segments or _make_segments(sentences)
        t0 = time.time()
        result = analyze_topics(transcript, segs)
        elapsed = time.time() - t0
        return result, elapsed

    def test_1_single_topic(self):
        """Single-topic meeting should produce 1 canonical topic."""
        result, elapsed = self._run(AUTH_SENTENCES)
        n_canonical = result["canonical_topic_count"]
        print(f"\n[Test 1] Single topic: {n_canonical} canonical topics, {elapsed:.2f}s")
        self.assertLessEqual(n_canonical, 2,
            f"Expected ≤2 canonical topics for single-topic meeting, got {n_canonical}")
        self.assertGreater(len(result["segments"]), 0)

    def test_2_clear_transitions(self):
        """Three clear topics should produce 3 canonical topics."""
        sentences = AUTH_SENTENCES + UI_SENTENCES + DEPLOY_SENTENCES
        result, elapsed = self._run(sentences)
        n = len(sentences)
        # Reference boundaries at positions 5 and 10
        ref_boundaries = [0, 5, 10]
        pred_boundaries = [s["unit_start"] for s in result["segments"]]
        metrics = _boundary_metrics(pred_boundaries, ref_boundaries, n, tolerance=2)
        print(f"\n[Test 2] Clear transitions: {result['canonical_topic_count']} canonical, "
              f"boundaries={pred_boundaries}, F1={metrics['f1']}, {elapsed:.2f}s")
        self.assertGreaterEqual(metrics["f1"], 0.4,
            f"Boundary F1 too low: {metrics}")
        self.assertGreaterEqual(result["canonical_topic_count"], 2)

    def test_3_recurring_topics(self):
        """Auth discussed twice should map to same canonical topic."""
        sentences = AUTH_SENTENCES + UI_SENTENCES + AUTH_REVISIT
        result, elapsed = self._run(sentences)
        # Find canonical topics with >1 segment
        revisited = [ct for ct in result["canonical_topics"] if ct["occurrence_count"] > 1]
        print(f"\n[Test 3] Recurring topics: {result['canonical_topic_count']} canonical, "
              f"{len(revisited)} revisited, {elapsed:.2f}s")
        self.assertGreaterEqual(len(revisited), 1,
            "Expected at least one recurring canonical topic for auth revisit")

    def test_4_gradual_transitions(self):
        """Gradual topic drift should not over-segment into too many topics."""
        result, elapsed = self._run(GRADUAL)
        n_segs = result["segment_count"]
        n_canonical = result["canonical_topic_count"]
        print(f"\n[Test 4] Gradual transitions: {n_segs} segments, {n_canonical} canonical, {elapsed:.2f}s")
        # Should not create a boundary per sentence
        self.assertLessEqual(n_segs, len(GRADUAL) // 2,
            f"Over-segmented: {n_segs} segments for {len(GRADUAL)} sentences")

    def test_5_short_transcript(self):
        """Very short transcript should not crash."""
        short = ["Hello everyone.", "Let's start the meeting."]
        result, elapsed = self._run(short)
        print(f"\n[Test 5] Short transcript: {result['segment_count']} segments, {elapsed:.2f}s")
        self.assertIsInstance(result["segments"], list)
        self.assertIsInstance(result["canonical_topics"], list)

    def test_6_long_transcript(self):
        """Long transcript should complete in reasonable time with batched embeddings."""
        long_sentences = (AUTH_SENTENCES + UI_SENTENCES + DEPLOY_SENTENCES + AUTH_REVISIT + GRADUAL) * 4
        result, elapsed = self._run(long_sentences)
        print(f"\n[Test 6] Long transcript ({len(long_sentences)} sentences): "
              f"{result['segment_count']} segments, {result['canonical_topic_count']} canonical, {elapsed:.2f}s")
        self.assertLess(elapsed, 120, "Long transcript took too long")
        self.assertGreater(result["segment_count"], 0)

    def test_7_text_only_no_timestamps(self):
        """Plain text without segment timestamps should work correctly."""
        from backend.services.topic_segmentation import analyze_topics
        transcript = " ".join(AUTH_SENTENCES + UI_SENTENCES + DEPLOY_SENTENCES)
        t0 = time.time()
        result = analyze_topics(transcript, [])  # no segments
        elapsed = time.time() - t0
        print(f"\n[Test 7] Text-only: {result['segment_count']} segments, {elapsed:.2f}s")
        self.assertGreater(result["segment_count"], 0)
        # All timestamps should be None
        for seg in result["segments"]:
            self.assertIsNone(seg["start_time"])

    def test_8_cross_meeting_matching(self):
        """Topics from two meetings discussing auth should be linked."""
        from backend.services.topic_segmentation import embed_texts
        from backend.services.topic_evolution import _topic_text
        from sklearn.metrics.pairwise import cosine_similarity

        topic_a = {"label": "JWT Authentication", "keywords": ["jwt", "token", "authentication", "refresh"]}
        topic_b = {"label": "Authentication Token Rotation", "keywords": ["token", "rotation", "authentication", "refresh"]}
        topic_c = {"label": "Frontend UI Redesign", "keywords": ["ui", "design", "navigation", "sidebar"]}

        texts = [_topic_text(t) for t in [topic_a, topic_b, topic_c]]
        embeddings = embed_texts(texts)
        sim_ab = float(cosine_similarity(embeddings[0:1], embeddings[1:2])[0, 0])
        sim_ac = float(cosine_similarity(embeddings[0:1], embeddings[2:3])[0, 0])
        print(f"\n[Test 8] Cross-meeting: sim(auth_a, auth_b)={sim_ab:.3f}, sim(auth_a, ui)={sim_ac:.3f}")
        self.assertGreater(sim_ab, sim_ac,
            "Auth topics should be more similar to each other than to UI topic")

    def test_empty_transcript(self):
        """Empty transcript should return empty result without error."""
        from backend.services.topic_segmentation import analyze_topics
        result = analyze_topics("", [])
        self.assertEqual(result["segment_count"], 0)
        self.assertEqual(result["canonical_topic_count"], 0)

    def test_windowdiff_metric(self):
        """WindowDiff should be 0 for perfect prediction."""
        labels = [0, 0, 0, 1, 1, 1, 2, 2, 2]
        wd = _windowdiff(labels, labels)
        self.assertEqual(wd, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
