"""Offline tests for current-meeting-only chatbot grounding."""
import os
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from backend.services.chatbot import ChatbotClient, ChatbotError, ChatbotRateLimitError, NOT_FOUND, ask_meeting, retrieve_segments


MEETING = {
    "full_text": "Authentication failed in the new flow. The older approach remains in use.",
    "segments": [
        {"start": 10, "end": 12, "text": "Authentication failed in the new flow."},
        {"start": 20, "end": 22, "text": "The older approach remains in use."},
    ],
}


class StubClient:
    def __init__(self, evidence):
        self.evidence = evidence
        self.context = None
        self.history = None

    def answer(self, question, history, context):
        self.history = history
        self.context = context
        return {"answer": "The older approach remains in use.", "evidence_segment_ids": self.evidence}


class ChatbotTests(unittest.TestCase):
    def test_foreign_or_unprovided_evidence_is_refused(self):
        result = ask_meeting(MEETING, "What about authentication?", client=StubClient(["SEG_1", "SEG_999"]))
        self.assertEqual(result, {"answer": NOT_FOUND, "evidence_segment_ids": []})

    def test_retrieval_is_current_meeting_only_and_followup_uses_history(self):
        client = StubClient(["SEG_0"])
        result = ask_meeting(MEETING, "Why?", [{"role": "user", "content": "What happened with authentication?"}], client)
        self.assertEqual(result["evidence_segment_ids"], ["SEG_0"])
        self.assertEqual([row["segment_id"] for row in client.context], ["SEG_0", "SEG_1"])
        self.assertEqual(client.history[0]["content"], "What happened with authentication?")

    def test_paraphrase_reaches_provider_with_transcript(self):
        client = StubClient(["SEG_0"])
        ask_meeting(MEETING, "Why couldn't people log in?", client=client)
        self.assertEqual(len(client.context), 2)

    def test_summary_includes_late_decisions(self):
        meeting = {"segments": [
            {"text": f"Discussion point {index}"} for index in range(40)
        ] + [{"text": "We agreed to launch on Friday."}]}
        client = StubClient(["SEG_40"])
        result = ask_meeting(meeting, "What decisions were made?", client=client)
        self.assertEqual(len(client.context), 41)
        self.assertEqual(result["evidence"][0]["text"], "We agreed to launch on Friday.")

    def test_topic_change_keeps_new_topic_available(self):
        meeting = {"segments": [
            {"text": "Authentication failed."} for _ in range(20)
        ] + [{"text": "The budget is five thousand dollars."}]}
        client = StubClient(["SEG_20"])
        result = ask_meeting(meeting, "How much can we spend?", [
            {"role": "user", "content": "What happened with authentication?"}
        ], client)
        self.assertEqual(result["evidence_segment_ids"], ["SEG_20"])
        self.assertIn("budget", client.context[-1]["text"])

    def test_empty_transcript_refuses_without_provider_call(self):
        client = StubClient([])
        self.assertEqual(ask_meeting({}, "Summarize this meeting", client=client)["answer"], NOT_FOUND)
        self.assertIsNone(client.context)

    def test_full_text_only_meeting_is_available_for_paraphrases(self):
        client = StubClient(["SEG_0"])
        ask_meeting({"full_text": "Authentication failed."}, "Could users log in?", client=client)
        self.assertEqual(client.context[0]["text"], "Authentication failed.")

    def test_provider_unsupported_answer_and_invalid_citations_are_refused(self):
        responses = [
            {"answer": NOT_FOUND, "evidence_segment_ids": []},
            {"answer": "It will rain.", "evidence_segment_ids": []},
            {"answer": "It will rain.", "evidence_segment_ids": ["SEG_0", "SEG_999"]},
            {"answer": "  ", "evidence_segment_ids": ["SEG_0"]},
        ]
        for response in responses:
            with self.subTest(response=response):
                body = io.StringIO(json.dumps({"choices": [{"message": {
                    "content": json.dumps(response)
                }}]}))
                with patch("backend.services.chatbot.urlopen", return_value=body), patch.dict(
                        os.environ, {"GROQ_CHATBOT_API_KEY": "test-only"}, clear=True):
                    result = ask_meeting(MEETING, "What is the weather?")
                self.assertEqual(result["answer"], NOT_FOUND)
                self.assertEqual(result["evidence_segment_ids"], [])

    def test_large_multilingual_context_is_bounded_and_covers_end(self):
        meeting = {"segments": [{"text": "Discussion " * 40} for _ in range(100)]
                   + [{"text": "Final budget approved."}]}
        with patch.dict(os.environ, {"GROQ_CHATBOT_CONTEXT_BYTES": "10000"}):
            rows = retrieve_segments(meeting, "What budget was approved?")
        self.assertLessEqual(len(json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()), 10000)
        self.assertIn("SEG_100", [row["segment_id"] for row in rows])
        meeting = {"full_text": "\u0905" * 20000}
        rows = retrieve_segments(meeting, "Summary")
        self.assertTrue(rows)
        self.assertLessEqual(len(json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()), 10000)

    def test_rate_limit_preserves_retry_timing_and_daily_quota(self):
        error = HTTPError("https://example.test", 429, "limit", {"Retry-After": "91.2"},
                          io.BytesIO(b'{"error":{"message":"tokens per day private-org"}}'))
        with patch("backend.services.chatbot.urlopen", side_effect=error) as provider, patch.dict(
                os.environ, {"GROQ_CHATBOT_API_KEY": "test-only"}, clear=True):
            with self.assertRaises(ChatbotRateLimitError) as raised:
                ask_meeting(MEETING, "Summarize")
        self.assertEqual(raised.exception.retry_after, 92)
        self.assertIn("daily", str(raised.exception))
        self.assertNotIn("private-org", str(raised.exception))
        self.assertEqual(provider.call_count, 1)

    def test_endpoint_returns_retry_after_header(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.routes.chatbot import router
        app = FastAPI()
        app.include_router(router)
        with patch("backend.routes.chatbot._meeting", return_value=MEETING), patch(
                "backend.routes.chatbot.ask_meeting", side_effect=ChatbotRateLimitError(92)):
            response = TestClient(app).post("/meeting", json={"question": "Summary"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "92")

    def test_chatbot_key_is_separate_and_never_falls_back(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "analysis-only"}, clear=True):
            with self.assertRaisesRegex(Exception, "GROQ_CHATBOT_API_KEY"):
                ChatbotClient().answer("question", [], [{"segment_id": "SEG_0", "text": "context"}])

    def test_request_identifies_application_to_provider(self):
        body = io.StringIO(json.dumps({"choices": [{"message": {"content": json.dumps({
            "answer": "Authentication failed.", "evidence_segment_ids": ["SEG_0"]
        })}}]}))
        with patch("backend.services.chatbot.urlopen", return_value=body) as provider, patch.dict(
                os.environ, {"GROQ_CHATBOT_API_KEY": "test-only"}, clear=True):
            result = ask_meeting(MEETING, "What failed?")
        request = provider.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "MeetingAnalyzer/1.0")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(result["answer"], "Authentication failed.")

    def test_forbidden_response_does_not_diagnose_invalid_key(self):
        error = HTTPError("https://example.test", 403, "forbidden", {}, None)
        with patch("backend.services.chatbot.urlopen", side_effect=error), patch.dict(
                os.environ, {"GROQ_CHATBOT_API_KEY": "test-only"}, clear=True):
            with self.assertRaisesRegex(ChatbotError, "account/model permissions or network filtering"):
                ask_meeting(MEETING, "What failed?")

    def test_rejected_chatbot_key_has_actionable_error(self):
        error = HTTPError("https://api.groq.com", 401, "unauthorized", {}, None)
        with patch("backend.services.chatbot.urlopen", side_effect=error), patch.dict(
                os.environ, {"GROQ_CHATBOT_API_KEY": "chatbot-only"}, clear=True):
            with self.assertRaisesRegex(ChatbotError, "GROQ_CHATBOT_API_KEY"):
                ChatbotClient().answer("question", [], [{"segment_id": "SEG_0", "text": "context"}])


if __name__ == "__main__":
    unittest.main()