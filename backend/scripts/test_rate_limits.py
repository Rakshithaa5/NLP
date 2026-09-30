"""Provider cooldown regressions; no real Groq calls."""
import logging
import os
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from backend.services.semantic import GroqAnalyzer, RateLimitError, retry_delay
from backend.scripts.test_semantic import meeting, controlled_response

class RateLimitTests(unittest.TestCase):
    def test_retry_after_parsing(self):
        self.assertEqual(retry_delay({"Retry-After": "21.2"}), 22)
        for value in (None, "bad", "nan", "inf"):
            self.assertEqual(retry_delay({"Retry-After": value}), 60)
        with patch("backend.services.semantic.time.time", return_value=0):
            self.assertEqual(retry_delay({"Retry-After": "Thu, 01 Jan 1970 00:02:00 GMT"}), 120)

    def test_provider_preserves_long_retry_after_without_sleep(self):
        error = HTTPError("https://example.test", 429, "limit", {"Retry-After": "90"}, None)
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-only"}), patch(
                "backend.services.semantic.urlopen", side_effect=error), patch("backend.services.semantic.time.sleep") as sleep:
            with self.assertRaises(RateLimitError) as raised:
                GroqAnalyzer().request({}, "Extract.")
            self.assertEqual(raised.exception.retry_after, 90)
            sleep.assert_not_called()

    def test_daily_token_limit_is_identified_without_exposing_body(self):
        from io import BytesIO
        import json
        error = HTTPError("https://example.test", 429, "limit", {"Retry-After": "900"},
                          BytesIO(json.dumps({"error": {"message": "Limit on tokens per day (TPD) for private-org"}}).encode()))
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-only"}), patch(
                "backend.services.semantic.urlopen", side_effect=error):
            with self.assertRaises(RateLimitError) as raised:
                GroqAnalyzer().request({}, "Extract.")
        self.assertEqual(raised.exception.limit_kind, "TPD")
        self.assertIn("daily quota", str(raised.exception))
        self.assertNotIn("private-org", str(raised.exception))

    def test_interrupted_chunks_resume_and_completed_attempt_starts_fresh(self):
        from backend.services.semantic import analyze_transcript
        from backend.scripts.test_semantic import response
        from copy import deepcopy
        text = " ".join(f"Milestone {i} is ready for review." for i in range(70))
        checkpoint, saved = {}, []
        class Analyzer:
            budget = 2500
            def __init__(self, fail=False):
                self.calls = 0
                self.fail = fail
            def request(self, payload, instruction):
                self.calls += 1
                if self.fail and self.calls == 2:
                    raise RateLimitError(60)
                return response(payload["transcript"][-1]["text"])
        first = Analyzer(fail=True)
        with self.assertRaises(RateLimitError):
            analyze_transcript(text, analyzer=first, checkpoint=checkpoint,
                               on_checkpoint=lambda value: saved.append(deepcopy(value)))
        self.assertEqual(len(saved[-1]["reports"]), 1)
        resumed = Analyzer()
        output = analyze_transcript(text, analyzer=resumed, checkpoint=saved[-1])
        chunks = len(output["intelligence"]["analysis_manifest"]["chunks"])
        self.assertEqual(resumed.calls, chunks - 1)
        self.assertTrue(any("Milestone 69" in point for point in output["intelligence"]["summary"]))
        saved[-1]["state"] = "complete"
        fresh = Analyzer()
        analyze_transcript(text, analyzer=fresh, checkpoint=saved[-1])
        self.assertEqual(fresh.calls, chunks)
        changed = Analyzer()
        analyze_transcript(text + " New information.", analyzer=changed, checkpoint=checkpoint)
        self.assertGreater(changed.calls, 1)

    def test_cooldown_survives_refresh_and_cached_post(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.routes import analysis
        from backend.services.meeting_store import save_local
        file_id = "00000000-0000-0000-0000-000000000007"
        url = "/api/analysis/" + file_id
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"DATA_DIR": directory}), \
                patch.object(analysis, "_get_db", return_value=None), \
                patch.object(GroqAnalyzer, "request", return_value=controlled_response()) as request:
            save_local(file_id, "transcript.json", meeting())
            client = TestClient(app)
            initial = client.post(url)
            self.assertEqual(initial.status_code, 200)
            request.side_effect = RateLimitError(70)
            limited = client.post(url + "?force=true", headers={"Origin": "http://localhost:5173"})
            self.assertEqual(limited.status_code, 429)
            self.assertEqual(limited.headers["Retry-After"], "70")
            self.assertIn("Retry-After", limited.headers["access-control-expose-headers"])
            saved = client.get(url).json()
            self.assertEqual(saved["intelligence"], initial.json()["intelligence"])
            self.assertEqual(saved["analysis_attempt"]["state"], "rate_limited")
            self.assertEqual(client.post(url).status_code, 200)
            self.assertEqual(client.post(url + "?force=true").status_code, 429)
            self.assertEqual(request.call_count, 2)
            request.side_effect = None
            save_local(file_id, "analysis_state.json", {"state": "rate_limited", "retry_at": time.time() - 1})
            self.assertEqual(client.post(url + "?force=true").status_code, 200)
            self.assertEqual(request.call_count, 3)

    def test_no_saved_report_returns_cooldown_on_reload(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.routes import analysis
        from backend.services.meeting_store import save_local
        file_id = "00000000-0000-0000-0000-000000000008"
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"DATA_DIR": directory}), \
                patch.object(analysis, "_get_db", return_value=None), \
                patch.object(GroqAnalyzer, "request", side_effect=RateLimitError(90)) as request:
            save_local(file_id, "transcript.json", meeting())
            client = TestClient(app)
            url = "/api/analysis/" + file_id
            self.assertEqual(client.post(url).status_code, 429)
            reload = client.get(url)
            self.assertEqual(reload.status_code, 429)
            self.assertGreater(int(reload.headers["Retry-After"]), 0)
            self.assertEqual(client.post(url).status_code, 429)
            self.assertEqual(request.call_count, 1)

if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    unittest.main()
