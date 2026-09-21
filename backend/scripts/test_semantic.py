"""Offline contract/integration tests. Model responses are explicit test doubles."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.services.intelligence import Intelligence, normalize_analysis, evidence_for, deduplicate
from backend.services.semantic import (AnalysisError, GroqAnalyzer, analyze_transcript,
                                      chunk_units, parse_response, transcript_units)

FIXTURE = Path(__file__).parent / "fixtures"


def meeting():
    return json.loads((FIXTURE / "navigation_meeting.json").read_text(encoding="utf-8-sig"))


def response(text="The service processes ten requests per second."):
    raw = Intelligence().model_dump()
    raw["summary"] = [text]
    raw["summary_evidence"] = [{"evidence": text}]
    return raw


def controlled_response():
    return json.loads((FIXTURE / "navigation_response.json").read_text(encoding="utf-8-sig"))


class SemanticTests(unittest.TestCase):
    def test_controlled_contract_and_real_timestamps(self):
        m = meeting()
        with patch.object(GroqAnalyzer, "request", return_value=controlled_response()) as request:
            result = analyze_transcript(m["full_text"], m["segments"], "en", 47)
        request.assert_called_once()
        i = Intelligence.model_validate(result["intelligence"])
        self.assertEqual(result["analysis_state"], "complete")
        self.assertGreaterEqual(len(i.summary), 3)
        action = next(a for a in i.action_items if "wireframe" in a.task)
        self.assertEqual((action.owner, action.deadline, action.timestamp), ("John", "Friday", 22))
        self.assertIsNone(action.priority)
        self.assertTrue(i.decisions)
        self.assertEqual(i.questions[0].status, "Unresolved")
        self.assertEqual(set(i.entities["people"]), {"Sarah", "John", "Alex"})
        self.assertEqual(i.metadata.speaker_count, 3)

    def test_empty_needs_no_provider(self):
        with patch.object(GroqAnalyzer, "request") as request:
            result = analyze_transcript(" ")
        request.assert_not_called()
        self.assertEqual(result["analysis_state"], "empty")

    def test_paraphrase_does_not_require_exact_keywords_or_confidence(self):
        text = "Agreed. Let's use PostgreSQL."
        raw = response(text)
        raw["decisions"] = [{"decision": "PostgreSQL is selected.", "evidence": text, "confidence": .01}]
        raw["topics"] = [{"label": "Database selection", "evidence": text, "keywords": []}]
        report, _ = normalize_analysis(raw, text)
        self.assertEqual(report["decisions"][0]["decision"], "PostgreSQL is selected.")
        self.assertEqual(report["topics"][0]["label"], "Database selection")

    def test_no_fabricated_evidence_or_timestamps(self):
        raw = response()
        raw["action_items"] = [{"task": "Send report", "evidence": "Alice will send it.", "timestamp": 42}]
        report, issues = normalize_analysis(raw, raw["summary"][0])
        self.assertEqual(report["action_items"], [])
        self.assertIn("action_items", issues)
        self.assertIsNone(evidence_for("Agreed.", "Agreed. Agreed.",
            [{"text": "Agreed.", "start": 0}, {"text": "Agreed.", "start": 5}])["timestamp"])

    def test_first_person_owner_from_speaker_and_unknown_details_null(self):
        text = "I'll send the report tomorrow."
        raw = response(text)
        raw["action_items"] = [{"task": "Send report", "evidence": text, "owner": "Speaker 2",
                               "deadline": "Friday", "priority": "high"}]
        report, _ = normalize_analysis(raw, text, [{"text": text, "speaker": "Speaker 2", "start": 0}])
        action = report["action_items"][0]
        self.assertEqual(action["owner"], "Speaker 2")
        self.assertIsNone(action["deadline"])
        self.assertIsNone(action["priority"])
        self.assertEqual(action["timestamp"], 0)

    def test_confirmation_does_not_erase_named_assignment(self):
        text = "John, prepare the wireframes by Friday. Yes, I'll have them ready."
        raw = response(text)
        raw["action_items"] = [{"task": "Prepare wireframes", "owner": "John", "deadline": "Friday",
            "evidence": text, "owner_evidence": "Yes, I'll have them ready."}]
        report, _ = normalize_analysis(raw, text)
        self.assertEqual(report["action_items"][0]["owner"], "John")

    def test_partial_bad_field_preserves_summary_actions(self):
        m, raw = meeting(), controlled_response()
        raw["topics"] = "broken"
        raw["action_items"].append({"task": 123})
        with patch.object(GroqAnalyzer, "request", return_value=raw):
            result = analyze_transcript(m["full_text"], m["segments"])
        self.assertTrue(result["intelligence"]["summary"])
        self.assertTrue(result["intelligence"]["action_items"])
        self.assertEqual(result["analysis_state"], "partial")

    def test_json_fences_trailing_comma_preserve_quote(self):
        raw = parse_response('```json\n{"summary":["a, } quoted string"], "topics":[],}\n```')
        self.assertEqual(raw["summary"], ["a, } quoted string"])
        for content in ('not json', '{"summary":', '[]', '{}'):
            with self.assertRaises(AnalysisError):
                parse_response(content)

    def test_incomplete_field_preserves_complete_json_sections(self):
        raw = parse_response('{"summary":["A useful meeting fact."],"summary_evidence":[{"evidence":"A useful meeting fact."}],"topics":[')
        report, issues = normalize_analysis(raw, "A useful meeting fact.")
        self.assertEqual(report["summary"], ["A useful meeting fact."])
        self.assertIn("json", issues)

    def test_entity_names_are_not_substrings_or_common_nouns(self):
        text = "Johnson explained the benefit to the developer."
        raw = response(text)
        raw["entities"]["people"] = ["John", "Johnson", "benefit", "developer"]
        report, _ = normalize_analysis(raw, text)
        self.assertEqual(report["entities"]["people"], ["Johnson"])

    def test_source_references_recover_original_quote_without_fabrication(self):
        text = "We agreed to keep PostgreSQL."
        raw = response(text)
        raw["decisions"] = [{"decision": "Keep PostgreSQL", "evidence": "We selected PostgreSQL.",
                             "segment_ids": [0]}]
        report, _ = normalize_analysis(raw, text, [{"text": text, "start": 5}])
        self.assertEqual(report["decisions"][0]["evidence"], text)
        self.assertEqual(report["decisions"][0]["timestamp"], 5)
        raw["decisions"][0]["segment_ids"] = [99]
        report, _ = normalize_analysis(raw, text, [{"text": text, "start": 5}])
        self.assertEqual(report["decisions"], [])

    def test_disjoint_references_include_real_intervening_transcript(self):
        segments = [{"text": "Let's use PostgreSQL.", "start": 0},
                    {"text": "It supports our requirements.", "start": 5},
                    {"text": "Agreed.", "start": 10}]
        text = " ".join(s["text"] for s in segments)
        raw = response(text)
        raw["decisions"] = [{"decision": "Use PostgreSQL", "evidence": "",
                             "segment_ids": [0, 2]}]
        report, _ = normalize_analysis(raw, text, segments)
        self.assertEqual(report["decisions"][0]["evidence"], text)
        self.assertEqual(report["decisions"][0]["segment_ids"], [0, 1, 2])

    def test_stale_segment_evidence_cannot_create_quotes_or_timestamps(self):
        self.assertIsNone(evidence_for("Invented.", "Real.", [{"text": "Invented.", "start": 3}]))
        evidence = evidence_for("Real.", "Real. Other.", [{"text": "Real.", "start": 999}])
        self.assertIsNone(evidence["timestamp"])

    def test_rate_limit_retries_are_bounded(self):
        from io import StringIO
        from urllib.error import HTTPError
        from unittest.mock import MagicMock
        success = MagicMock()
        success.__enter__.return_value = StringIO(json.dumps({"choices": [
            {"finish_reason": "stop", "message": {"content": json.dumps(response())}}]}))
        error = HTTPError("https://example.test", 429, "rate limit", {"Retry-After": "1"}, None)
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-only"}), patch(
                "backend.services.semantic.urlopen", side_effect=[error, success]) as call, patch(
                "backend.services.semantic.time.sleep") as sleep:
            self.assertTrue(GroqAnalyzer().request({}, "Extract.")["summary"])
            self.assertEqual(call.call_count, 2)
            sleep.assert_called_once_with(1.0)

    def test_dedup_same_event_but_not_separate_owners(self):
        quote = "John will update the API docs by Friday."
        a = {"task": "Update API documentation", "evidence": quote, "owner": "John", "deadline": "Friday"}
        b = {**a, "task": "Update the API docs"}
        c = {**b, "owner": "Alex"}
        self.assertEqual(len(deduplicate([a, b, c], "task")), 2)

    def test_resolved_question_requires_answer_evidence(self):
        text = "Should we deploy Friday? Yes, Friday works."
        raw = response(text)
        raw["questions"] = [{"question": "Should we deploy Friday?", "status": "resolved",
            "evidence": "Should we deploy Friday?", "answer": "Deploy Friday.",
            "answer_evidence": {"evidence": "Yes, Friday works."}}]
        report, _ = normalize_analysis(raw, text)
        self.assertEqual(report["questions"][0]["status"], "Resolved")
        raw["questions"][0]["answer_evidence"] = {"evidence": "Invented"}
        report, issues = normalize_analysis(raw, text)
        self.assertIsNone(report["questions"][0]["answer"])
        self.assertIn("questions.answer", issues)

    def test_multilingual_keeps_original_evidence(self):
        text = "Mañana enviaré el informe."
        raw = response(text)
        raw["action_items"] = [{"task": "Enviar el informe", "evidence": text,
                               "owner": "Ana", "deadline": "Mañana"}]
        with patch.object(GroqAnalyzer, "request", return_value=raw):
            result = analyze_transcript(text, [{"text": text, "start": 0, "speaker": "Ana"}], "es")
        self.assertEqual(result["intelligence"]["action_items"][0]["owner"], "Ana")
        self.assertEqual(result["intelligence"]["action_items"][0]["evidence"], text)

    def test_chunk_budget_and_all_text_preserved(self):
        units = [{"text": "word" + str(n) + " " + "अ" * 15, "speaker": "A", "start": n} for n in range(40)]
        chunks = chunk_units(units, 400)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(json.dumps(chunk, ensure_ascii=False, separators=(",", ":")).encode()), 400)
        self.assertEqual({u["text"] for chunk in chunks for u in chunk}, {u["text"] for u in units})
        long = [{"text": "अ" * 1000, "speaker": "A"}]
        chunks = chunk_units(long, 300)
        # Oversized split pieces may overlap across chunks; count at least the
        # complete source size and verify every piece is a source substring.
        self.assertGreaterEqual(sum(len(u["text"]) for c in chunks for u in c), 1000)
        self.assertTrue(all(u["text"] in long[0]["text"] for c in chunks for u in c))

    def test_stale_segments_never_replace_transcript(self):
        units = transcript_units("Start. Important late decision.", [{"text": "Start.", "start": 0}])
        self.assertIn("Important late decision.", " ".join(u["text"] for u in units))

    def test_chunk_pipeline_synthesizes_and_keeps_late_evidence(self):
        transcript = " ".join(f"Milestone {n} is ready for review." for n in range(70))
        calls = []
        class Analyzer:
            budget = 2500
            def request(self, payload, instruction):
                calls.append(payload)
                if "transcript" in payload:
                    return response(payload["transcript"][-1]["text"])
                raw = response(payload["candidates"][-1]["summary"][0])
                return raw
        result = analyze_transcript(transcript, analyzer=Analyzer())
        self.assertIn("Milestone 69", result["intelligence"]["summary"][0])
        self.assertTrue(any("candidates" in c for c in calls))
        for call in calls:
            if "candidates" in call:
                self.assertNotIn("transcript", call)

    def test_synthesis_uses_source_references_not_repeated_transcript(self):
        from backend.services.semantic import synthesis_candidates
        quote = "A long source passage. " * 100
        raw = [{"summary": ["Discussed the service"], "summary_evidence": [
            {"evidence": quote, "segment_ids": [0]}]}]
        compact = synthesis_candidates(raw)
        self.assertEqual(compact[0]["summary_evidence"][0]["segment_ids"], [0])
        self.assertEqual(compact[0]["summary_evidence"][0]["evidence"], "")
        self.assertEqual(raw[0]["summary_evidence"][0]["evidence"], quote)

    def test_synthesis_compacts_long_spans_without_losing_evidence(self):
        from backend.services.semantic import synthesis_candidates
        segments = [{"text": f"Discussion point {i}.", "start": i} for i in range(240)]
        transcript = " ".join(s["text"] for s in segments)
        raw = response("The team discussed the project.")
        raw["summary_evidence"] = [{"evidence": transcript, "segment_ids": list(range(240))}]
        compact = synthesis_candidates([raw])[0]
        self.assertEqual(compact["summary_evidence"][0]["segment_ids"], [0, 239])
        self.assertLess(len(json.dumps(compact)), len(json.dumps(raw)) / 2)
        report, issues = normalize_analysis(compact, transcript, segments)
        self.assertEqual(report["summary_evidence"][0]["evidence"], transcript)
        self.assertEqual(report["summary_evidence"][0]["segment_ids"], list(range(240)))
        self.assertEqual(raw["summary_evidence"][0]["segment_ids"], list(range(240)))

    def test_synthesis_preserves_unreferenced_quotes_and_assignment_details(self):
        from backend.services.semantic import synthesis_candidates
        raw = [{"evidence": "Alice will send it Friday.", "segment_ids": [],
                "owner": "Alice", "deadline": "Friday", "priority": None,
                "owner_evidence": "Alice accepted the task."}]
        compact = synthesis_candidates(raw)[0]
        self.assertEqual(compact["evidence"], raw[0]["evidence"])
        self.assertEqual(compact["owner"], "Alice")
        self.assertEqual(compact["deadline"], "Friday")
        self.assertEqual(compact["owner_evidence"], raw[0]["owner_evidence"])
        self.assertNotIn("priority", compact)

    def test_request_budget_respects_account_limit_and_model_context(self):
        with patch.dict(os.environ, {"MEETING_LLM_CONTEXT_TOKENS": "32768",
                "MEETING_LLM_MAX_OUTPUT_TOKENS": "8192", "MEETING_LLM_MAX_INPUT_BYTES": "4096"}):
            analyzer = GroqAnalyzer()
            self.assertEqual(analyzer.budget, 4096)
            self.assertEqual(analyzer.output_tokens, 8192)
            chunks = chunk_units([{"text": "Discussion. " * 1000}], analyzer.budget - 1024)
            self.assertGreater(len(chunks), 1)
        with patch.dict(os.environ, {"MEETING_LLM_MAX_INPUT_BYTES": "0"}):
            with self.assertRaises(AnalysisError):
                GroqAnalyzer()

    def test_reasoning_budget_is_model_specific_and_configurable(self):
        from io import StringIO
        from unittest.mock import MagicMock
        for model, effort, expected in [("openai/gpt-oss-120b", "low", "low"),
                ("openai/gpt-oss-20b", "medium", "medium"), ("another-model", "low", None)]:
            with self.subTest(model=model, effort=effort):
                success = MagicMock()
                success.__enter__.return_value = StringIO(json.dumps({"choices": [
                    {"finish_reason": "stop", "message": {"content": json.dumps(response())}}]}))
                with patch.dict(os.environ, {"GROQ_API_KEY": "test-only", "MEETING_LLM_MODEL": model,
                        "MEETING_LLM_REASONING_EFFORT": effort}), patch(
                        "backend.services.semantic.urlopen", return_value=success) as call:
                    GroqAnalyzer().request({}, "Extract.")
                    body = json.loads(call.call_args.args[0].data)
                    self.assertEqual(body.get("reasoning_effort"), expected)

    def test_synthesis_budget_allows_merge_without_enlarging_transcript_chunks(self):
        from io import StringIO
        from unittest.mock import MagicMock
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-only",
                "MEETING_LLM_MAX_INPUT_BYTES": "4096", "MEETING_LLM_SYNTHESIS_BYTES": "8192",
                "MEETING_LLM_CONTEXT_TOKENS": "32768", "MEETING_LLM_MAX_OUTPUT_TOKENS": "8192"}):
            analyzer = GroqAnalyzer()
            self.assertEqual(analyzer.budget, 4096)
            self.assertEqual(analyzer.synthesis_budget, 8192)
            text = "x" * 5000
            with self.assertRaises(AnalysisError):
                analyzer.request({"transcript": text}, "Extract.")
            success = MagicMock()
            success.__enter__.return_value = StringIO(json.dumps({"choices": [
                {"finish_reason": "stop", "message": {"content": json.dumps(response())}}]}))
            with patch("backend.services.semantic.urlopen", return_value=success):
                self.assertTrue(analyzer.request({"candidates": text}, "Merge.")["summary"])

    def test_missing_key_and_transport_failure_raise(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "", "MEETING_LLM_API_KEY": ""}):
            with self.assertRaises(AnalysisError):
                analyze_transcript("The service processes ten requests per second.")
        with patch.object(GroqAnalyzer, "request", side_effect=AnalysisError("offline")):
            with self.assertRaises(AnalysisError):
                analyze_transcript("The service processes ten requests per second.")

    def test_provider_truncated_output_not_accepted(self):
        from unittest.mock import MagicMock
        import io
        fake = MagicMock()
        fake.__enter__.return_value = io.StringIO(json.dumps({
            "choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}))
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-only"}), patch(
                "backend.services.semantic.urlopen", return_value=fake):
            with self.assertRaisesRegex(AnalysisError, "incomplete"):
                GroqAnalyzer().request({}, "Extract.")

    def test_malformed_provider_envelopes_raise_analysis_error(self):
        from unittest.mock import MagicMock
        import io
        envelopes = [
            None, [], {}, {"choices": []}, {"choices": [None]},
            {"choices": [{"finish_reason": "stop", "message": None}]},
        ]
        envelopes.extend({"choices": [{"finish_reason": "stop", "message": {
            "content": content}}]} for content in (None, [], {}, 42, "", "  "))
        for envelope in envelopes:
            with self.subTest(envelope=envelope):
                fake = MagicMock()
                fake.__enter__.return_value = io.StringIO(json.dumps(envelope))
                with patch.dict(os.environ, {"GROQ_API_KEY": "test-only"}), patch(
                        "backend.services.semantic.urlopen", return_value=fake):
                    with self.assertRaises(AnalysisError):
                        GroqAnalyzer().request({}, "Extract.")

    def test_schema_is_strict_and_derived(self):
        from backend.services.semantic import extraction_schema
        schema = extraction_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
        self.assertNotIn("metadata", schema["properties"])


class ApiIntegrationTests(unittest.TestCase):
    def test_upload_analysis_refresh_pdf_failure_retry(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.routes import upload, analysis, report
        m = meeting()
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"DATA_DIR": directory}), \
                patch.object(upload, "_DATA_DIR", Path(directory)), \
                patch.object(upload, "_get_db", return_value=None), \
                patch.object(analysis, "_get_db", return_value=None), \
                patch.object(report, "_get_db", return_value=None), \
                patch.object(upload, "extract_audio"), patch.object(upload, "transcribe", return_value=m), \
                patch.object(GroqAnalyzer, "request", return_value=controlled_response()):
            client = TestClient(app)
            uploaded = client.post("/api/upload/", files={"file": ("meeting.wav", b"test-audio", "audio/wav")})
            self.assertEqual(uploaded.status_code, 200, uploaded.text)
            file_id = uploaded.json()["file_id"]
            generated = client.post("/api/analysis/" + file_id)
            self.assertEqual(generated.status_code, 200, generated.text)
            self.assertEqual(generated.json()["analysis_state"], "complete")
            saved = client.get("/api/analysis/" + file_id)
            self.assertEqual(saved.json()["intelligence"], generated.json()["intelligence"])
            transcript = client.get("/api/upload/" + file_id).json()
            self.assertEqual(transcript["segments"][0]["speaker"], "Sarah")
            pdf = client.get("/api/report/" + file_id + "/pdf")
            self.assertEqual(pdf.status_code, 200, pdf.text[:100] if pdf.status_code != 200 else "")
            self.assertTrue(pdf.content.startswith(b"%PDF"))
            with patch.object(GroqAnalyzer, "request", side_effect=AnalysisError("offline")):
                failed = client.post("/api/analysis/" + file_id)
            self.assertEqual(failed.status_code, 502)
            prior = client.get("/api/analysis/" + file_id).json()
            self.assertEqual(prior["analysis_attempt"]["state"], "failed")
            self.assertEqual(prior["intelligence"], saved.json()["intelligence"])
            self.assertEqual(client.post("/api/analysis/" + file_id).status_code, 200)

    def test_failure_without_previous_result_survives_reload(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.routes import analysis
        from backend.services.meeting_store import save_local
        file_id = "00000000-0000-0000-0000-000000000002"
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"DATA_DIR": directory}), \
                patch.object(analysis, "_get_db", return_value=None), \
                patch.object(GroqAnalyzer, "request", side_effect=AnalysisError("offline")):
            save_local(file_id, "transcript.json", meeting())
            client = TestClient(app)
            self.assertEqual(client.post("/api/analysis/" + file_id).status_code, 502)
            self.assertEqual(client.get("/api/analysis/" + file_id).status_code, 502)


if __name__ == "__main__":
    unittest.main()

