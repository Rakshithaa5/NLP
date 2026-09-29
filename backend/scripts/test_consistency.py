"""Offline invariants; provider responses below are deliberately varied test doubles."""
from copy import deepcopy
import json
import logging
import os
import tempfile
import unittest
from unittest.mock import patch
from backend.scripts.test_semantic import meeting, controlled_response, response
from backend.services.semantic import analyze_transcript, GroqAnalyzer, transcript_units
from backend.services.consistency import reconcile, same_pipeline, valid_evidence
from backend.services.intelligence import normalize_analysis

class ConsistencyTests(unittest.TestCase):
    def candidate(self, raw=None, meeting_id="fixture"):
        m = meeting()
        with patch.object(GroqAnalyzer, "request", return_value=raw or controlled_response()):
            return analyze_transcript(m["full_text"], m["segments"], meeting_id=meeting_id)

    def reconcile(self, old, new):
        m = meeting()
        return reconcile(old, new, m["full_text"], m["segments"], "fixture")

    def test_five_omitting_paraphrasing_runs_preserve_identity_and_edits(self):
        prior = self.candidate()
        original = {r["id"] for r in prior["intelligence"]["action_items"]}
        edited = prior["intelligence"]["action_items"][0]
        edited.update(owner="User owner", deadline="Next Monday", status="Done", confirmed=True)
        edited_id = edited["id"]
        for run in range(5):
            raw = controlled_response()
            if run % 2:
                raw["action_items"] = raw["action_items"][1:]
            else:
                raw["action_items"][0]["task"] = "Create revised wireframes"
            prior = self.reconcile(prior, self.candidate(raw))
            rows = prior["intelligence"]["action_items"]
            self.assertEqual({r["id"] for r in rows}, original)
            row = next(r for r in rows if r["id"] == edited_id)
            self.assertEqual((row["owner"], row["deadline"], row["status"], row["confirmed"]),
                             ("User owner", "Next Monday", "Done", True))

    def test_unsupported_prior_not_retained(self):
        old = self.candidate()
        fake = deepcopy(old["intelligence"]["action_items"][0])
        fake.update(id="fake", evidence="Unsupported promise", segment_ids=[999])
        fake["ai_fields"] = {k: v for k, v in fake.items() if k != "ai_fields"}
        old["intelligence"]["action_items"].append(fake)
        result = self.reconcile(old, self.candidate())
        self.assertNotIn("fake", {r["id"] for r in result["intelligence"]["action_items"]})

    def test_distinct_tasks_in_one_turn_not_collapsed(self):
        text = "Alice will test login and Bob will update documentation."
        raw = response(text)
        raw["action_items"] = [{"task": "Test login", "owner": "Alice", "evidence": text},
                               {"task": "Update documentation", "owner": "Bob", "evidence": text}]
        with patch.object(GroqAnalyzer, "request", return_value=raw):
            out = analyze_transcript(text)
        self.assertEqual(len({r["id"] for r in out["intelligence"]["action_items"]}), 2)

    def test_input_and_configuration_invalidate_cache(self):
        a = self.candidate()["intelligence"]["analysis_manifest"]
        b = deepcopy(a)
        b["input_hash"] = "changed"
        self.assertFalse(same_pipeline(a, b))
        b = deepcopy(a)
        b["config_hash"] = "changed"
        self.assertFalse(same_pipeline(a, b))
        self.assertTrue(same_pipeline(a, self.candidate()["intelligence"]["analysis_manifest"]))

    def test_changed_source_keeps_manual_data_in_review(self):
        old = self.candidate()
        old["intelligence"]["action_items"][0]["owner"] = "User assignment"
        new = self.candidate()
        new["intelligence"]["analysis_manifest"]["input_hash"] = "changed"
        new["intelligence"]["action_items"] = []
        result = self.reconcile(old, new)["intelligence"]
        self.assertEqual(result["action_items"], [])
        self.assertEqual(result["manual_review_items"][0]["item"]["owner"], "User assignment")

    def test_repeated_quote_uses_explicit_source_id(self):
        text = "I will test it. I will test it."
        segments = [{"text": "I will test it.", "start": 0}, {"text": "I will test it.", "start": 5}]
        raw = response("I will test it.")
        raw["action_items"] = [{"task": "Test it", "evidence": "I will test it.", "segment_ids": [1]}]
        report, _ = normalize_analysis(raw, text, segments)
        self.assertEqual(report["action_items"][0]["segment_ids"], [1])
        self.assertEqual(report["action_items"][0]["timestamp"], 5)

    def test_legacy_grounded_omission_is_retained(self):
        old = self.candidate()
        old["intelligence"].pop("analysis_manifest")
        raw = controlled_response()
        raw["action_items"] = []
        result = self.reconcile(old, self.candidate(raw))
        self.assertEqual(len(result["action_items"]), len(old["action_items"]))

    def test_analysis_lock_releases_and_rejects_concurrent_writer(self):
        from backend.services.meeting_store import analysis_lock, AnalysisInProgress
        file_id = "00000000-0000-0000-0000-000000000005"
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"DATA_DIR": directory}):
            with analysis_lock(file_id):
                with self.assertRaises(AnalysisInProgress):
                    with analysis_lock(file_id):
                        pass
            with analysis_lock(file_id):
                pass

    def test_followup_retained_when_new_run_omits_it(self):
        text = "After deployment, Alice will verify the login fix."
        raw = response(text)
        raw["follow_ups"] = [{"task": "Verify login after deployment", "evidence": text, "owner": "Alice"}]
        with patch.object(GroqAnalyzer, "request", return_value=raw):
            first = analyze_transcript(text, [{"text": text}])
        raw["follow_ups"] = []
        with patch.object(GroqAnalyzer, "request", return_value=raw):
            second = analyze_transcript(text, [{"text": text}])
        result = reconcile(first, second, text, [{"text": text}], "transcript")
        self.assertEqual(len(result["intelligence"]["follow_ups"]), 1)
        self.assertEqual(result["intelligence"]["action_items"], [])
        self.assertEqual(result["intelligence"]["follow_ups"][0]["reconciliation"], "retained")

    def test_cannot_resolve_two_different_assignees_to_same_identity(self):
        text = "Alice and Bob will each independently test the release."
        raw = response(text)
        raw["action_items"] = [{"task": "Test release", "owner": "Alice", "evidence": text}]
        with patch.object(GroqAnalyzer, "request", return_value=raw):
            first = analyze_transcript(text, [{"text": text}])
        raw["action_items"][0]["owner"] = "Bob"
        with patch.object(GroqAnalyzer, "request", return_value=raw):
            second = analyze_transcript(text, [{"text": text}])
        result = reconcile(first, second, text, [{"text": text}], "transcript")
        self.assertEqual(len(result["action_items"]), 2)
        self.assertEqual(len({r["id"] for r in result["action_items"]}), 2)

    def test_distinct_tasks_same_turn_across_runs_are_not_matched(self):
        text = "Alice will send the report and delete the backup."
        raw = response(text)
        raw["action_items"] = [{"task": "Send report", "owner": "Alice", "evidence": text}]
        with patch.object(GroqAnalyzer, "request", return_value=raw):
            first = analyze_transcript(text, [{"text": text}])
        raw["action_items"][0]["task"] = "Delete backup"
        with patch.object(GroqAnalyzer, "request", return_value=raw):
            second = analyze_transcript(text, [{"text": text}])
        result = reconcile(first, second, text, [{"text": text}], "transcript")
        self.assertEqual(len(result["action_items"]), 2)
        self.assertEqual(len({r["id"] for r in result["action_items"]}), 2)

    def test_api_cache_force_and_snapshot(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.routes import analysis
        from backend.services.meeting_store import save_local, read_local
        file_id = "00000000-0000-0000-0000-000000000005"
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"DATA_DIR": directory}), \
                patch.object(analysis, "_get_db", return_value=None), \
                patch.object(GroqAnalyzer, "request", return_value=controlled_response()) as request:
            save_local(file_id, "transcript.json", meeting())
            client = TestClient(app)
            first = client.post("/api/analysis/" + file_id)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(client.post("/api/analysis/" + file_id).json(), first.json())
            self.assertEqual(request.call_count, 1)
            raw = controlled_response()
            raw["action_items"] = []
            request.return_value = raw
            second = client.post("/api/analysis/" + file_id + "?force=true")
            self.assertEqual(second.status_code, 200)
            self.assertEqual(request.call_count, 2)
            self.assertEqual(len(second.json()["action_items"]), len(first.json()["action_items"]))
            self.assertEqual(read_local(file_id, "analysis_previous.json"), first.json())
            self.assertEqual(read_local(file_id, "analysis_candidate.json")["action_items"], [])
            self.assertTrue(read_local(file_id, "analysis_input.json"))

if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    unittest.main()
