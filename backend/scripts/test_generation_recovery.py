"""Offline regressions for bounded generation recovery."""
import io
import json
import os
import unittest
from copy import deepcopy
from unittest.mock import patch
from urllib.error import HTTPError

from backend.services.semantic import GroqAnalyzer, OutputLimitError, RateLimitError, analyze_transcript
from backend.services.chatbot import ChatbotError, ask_meeting
from backend.scripts.test_semantic import response
from backend.scripts.test_chatbot import MEETING


def envelope(content, finish="stop"):
    return io.StringIO(json.dumps({"choices": [{"finish_reason": finish,
        "message": {"content": json.dumps(content)}}]}))


class RecoveryTests(unittest.TestCase):
    def test_analysis_timeout_recovers(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "test"}), patch(
                "backend.services.semantic.urlopen", side_effect=[TimeoutError(), envelope(response())]) as call, patch(
                "backend.services.semantic.time.sleep"):
            self.assertTrue(GroqAnalyzer().request({}, "Extract.")["summary"])
        self.assertEqual(call.call_count, 2)

    def test_analysis_splits_truncated_output_and_preserves_all_source(self):
        segments = [{"text": "The service processes ten requests per second."},
                    {"text": "The release is scheduled for next Friday."}]
        seen = []
        def extract(payload, instruction):
            rows = payload["transcript"]
            seen.append(rows)
            if len(rows) > 1:
                raise OutputLimitError("incomplete")
            return response(rows[0]["text"])
        with patch.object(GroqAnalyzer, "request", side_effect=extract):
            result = analyze_transcript(" ".join(s["text"] for s in segments), segments)
        self.assertEqual(len(seen), 3)
        self.assertEqual(result["intelligence"]["summary"], [s["text"] for s in segments])
        self.assertEqual(result["analysis_state"], "complete")

    def test_split_recovery_checkpoints_successful_child(self):
        segments = [{"text": "The service processes ten requests per second."},
                    {"text": "The release is scheduled for next Friday."}]
        checkpoint = {}
        fail = True
        seen = []
        def extract(payload, instruction):
            rows = payload["transcript"]
            if len(rows) > 1:
                raise OutputLimitError("incomplete")
            seen.append(rows[0]["text"])
            if fail and rows[0]["text"] == segments[1]["text"]:
                raise RateLimitError(60)
            return response(rows[0]["text"])
        text = " ".join(s["text"] for s in segments)
        with patch.object(GroqAnalyzer, "request", side_effect=extract):
            with self.assertRaises(RateLimitError):
                analyze_transcript(text, segments, checkpoint=checkpoint)
            fail = False
            result = analyze_transcript(text, segments, checkpoint=deepcopy(checkpoint))
        self.assertEqual(seen.count(segments[0]["text"]), 1)
        self.assertEqual(result["analysis_state"], "complete")

    def test_daily_quota_with_short_retry_after_is_not_retried(self):
        error = HTTPError("https://test", 429, "limit", {"Retry-After": "1"},
                          io.BytesIO(b'{"error":{"message":"tokens per day"}}'))
        with patch.dict(os.environ, {"GROQ_API_KEY": "test"}), patch(
                "backend.services.semantic.urlopen", side_effect=error) as call, patch(
                "backend.services.semantic.time.sleep") as sleep:
            with self.assertRaises(RateLimitError) as raised:
                GroqAnalyzer().request({}, "Extract.")
        self.assertEqual(raised.exception.limit_kind, "TPD")
        self.assertEqual(call.call_count, 1)
        sleep.assert_not_called()

    def test_chat_increases_output_budget_after_truncation(self):
        answer = {"answer": "Authentication failed.", "evidence_segment_ids": ["SEG_0"]}
        with patch.dict(os.environ, {"GROQ_CHATBOT_API_KEY": "test"}, clear=True), patch(
                "backend.services.chatbot.urlopen", side_effect=[envelope({}, "length"), envelope(answer)]) as call:
            result = ask_meeting(MEETING, "What failed?")
        self.assertEqual(result["answer"], answer["answer"])
        budgets = [json.loads(c.args[0].data)["max_completion_tokens"] for c in call.call_args_list]
        self.assertEqual(budgets, [2048, 4096])

    def test_chat_persistent_truncation_is_bounded_and_never_accepted(self):
        with patch.dict(os.environ, {"GROQ_CHATBOT_API_KEY": "test"}, clear=True), patch(
                "backend.services.chatbot.urlopen", side_effect=lambda *a, **k: envelope({}, "length")) as call:
            with self.assertRaisesRegex(ChatbotError, "output limit"):
                ask_meeting(MEETING, "Summary")
        self.assertEqual(call.call_count, 3)

    def test_chat_transient_errors_recover(self):
        answer = {"answer": "Authentication failed.", "evidence_segment_ids": ["SEG_0"]}
        errors = [TimeoutError(), HTTPError("https://test", 503, "busy", {}, None),
                  HTTPError("https://test", 429, "limit", {"Retry-After": "1"}, None)]
        for error in errors:
            with self.subTest(error=error), patch.dict(os.environ, {"GROQ_CHATBOT_API_KEY": "test"}, clear=True), patch(
                    "backend.services.chatbot.urlopen", side_effect=[error, envelope(answer)]) as call, patch(
                    "backend.services.chatbot.time.sleep"):
                self.assertEqual(ask_meeting(MEETING, "What failed?")["answer"], answer["answer"])
                self.assertEqual(call.call_count, 2)

    def test_minute_cooldown_recovers_without_manual_resubmission(self):
        for module, content, invoke in [
                ("semantic", response(), lambda: GroqAnalyzer().request({}, "Extract.")),
                ("chatbot", {"answer": "Authentication failed.", "evidence_segment_ids": ["SEG_0"]},
                 lambda: ask_meeting(MEETING, "What failed?"))]:
            error = HTTPError("https://test", 429, "limit", {"Retry-After": "60"}, None)
            with self.subTest(module=module), patch.dict(os.environ,
                    {"GROQ_API_KEY": "test", "GROQ_CHATBOT_API_KEY": "test"}, clear=True), patch(
                    "backend.services." + module + ".urlopen", side_effect=[error, envelope(content)]) as call, patch(
                    "backend.services." + module + ".time.sleep") as sleep:
                self.assertTrue(invoke())
                self.assertEqual(call.call_count, 2)
                sleep.assert_called_once_with(60)
