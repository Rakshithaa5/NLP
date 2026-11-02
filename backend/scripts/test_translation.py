"""Offline regression tests for the English display toggle."""
import io
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.routes.translation import router
from backend.services.translation import translate_batch, translate_texts, TranslationError
from backend.services.meeting_store import read_local, save_local
from backend.services.semantic import RateLimitError
from backend.services.chatbot import ask_meeting


class TranslationTests(unittest.TestCase):
    def test_cached_translations_do_not_modify_sources_and_changed_content_is_retranslated(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"DATA_DIR": directory}):
            file_id = str(uuid4())
            original = {"language": "fr", "segments": [{"text": "Bonjour", "start": 1.2}]}
            save_local(file_id, "transcript.json", original)
            provider = Mock(side_effect=[["Hello"], ["Goodbye"]])
            self.assertEqual(translate_texts(file_id, ["Bonjour"], provider), ["Hello"])
            self.assertEqual(translate_texts(file_id, ["Bonjour"], provider), ["Hello"])
            self.assertEqual(translate_texts(file_id, ["Au revoir"], provider), ["Goodbye"])
            self.assertEqual(provider.call_count, 2)
            self.assertEqual(read_local(file_id, "transcript.json"), original)

    def test_provider_translation_contract_and_invalid_responses(self):
        for values, finish, valid in [(["Hello"], "stop", True), ([], "stop", False),
                                       ([""], "stop", False), (["Hello"], "length", False)]:
            body = io.StringIO(json.dumps({"choices": [{"finish_reason": finish,
                "message": {"content": json.dumps({"translations": values})}}]}))
            with self.subTest(values=values, finish=finish), patch.dict(os.environ, {"GROQ_API_KEY": "test"}, clear=True), patch(
                    "backend.services.translation.urlopen", return_value=body) as provider:
                if valid:
                    self.assertEqual(translate_batch(["Bonjour"]), ["Hello"])
                    payload = json.loads(provider.call_args.args[0].data)
                    self.assertIn("untrusted data", payload["messages"][0]["content"])
                else:
                    with self.assertRaises(TranslationError):
                        translate_batch(["Bonjour"])

    def test_provider_rate_limit_keeps_retry_after(self):
        error = HTTPError("https://example.test", 429, "limit", {"Retry-After": "12"},
                          io.BytesIO(b'{"error":{"message":"tokens per minute"}}'))
        with patch.dict(os.environ, {"GROQ_API_KEY": "test"}, clear=True), patch(
                "backend.services.translation.urlopen", side_effect=error):
            with self.assertRaises(RateLimitError) as raised:
                translate_batch(["Bonjour"])
        self.assertEqual(raised.exception.retry_after, 12)

    def test_endpoint_validation_and_quota_response(self):
        app = FastAPI(); app.include_router(router)
        client = TestClient(app); path = "/" + str(uuid4())
        self.assertEqual(client.post("/invalid", json={"texts": ["Bonjour"]}).status_code, 400)
        for texts in [[], [""], [" "], ["a" * 2001], ["x"] * 65, ["a" * 2000] * 6]:
            self.assertEqual(client.post(path, json={"texts": texts}).status_code, 422)
        with patch("backend.routes.translation.read_local", return_value={"language": "fr"}), patch(
                "backend.routes.translation.translate_texts", side_effect=RateLimitError(12)):
            response = client.post(path, json={"texts": ["Bonjour"]})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "12")

    def test_english_chat_uses_original_evidence_and_does_not_change_source_language(self):
        meeting = {"language": "fr", "segments": [{"text": "Bonjour", "start": 1.2}]}
        body = io.StringIO(json.dumps({"choices": [{"message": {"content": json.dumps({
            "answer": "They said hello.", "evidence_segment_ids": ["SEG_0"]})}}]}))
        with patch.dict(os.environ, {"GROQ_CHATBOT_API_KEY": "test"}, clear=True), patch(
                "backend.services.chatbot.urlopen", return_value=body) as provider:
            result = ask_meeting(meeting, "What was said?", response_language="en")
        payload = json.loads(provider.call_args.args[0].data)
        self.assertIn("meeting language (en)", payload["messages"][0]["content"])
        self.assertIn("Bonjour", payload["messages"][-1]["content"])
        self.assertEqual(result["evidence"][0]["start"], 1.2)
        self.assertEqual(meeting["language"], "fr")

    def test_chat_endpoint_accepts_only_supported_display_override(self):
        from backend.routes.chatbot import router as chat_router
        app = FastAPI(); app.include_router(chat_router)
        client = TestClient(app)
        with patch("backend.routes.chatbot._meeting", return_value={"language": "fr"}), patch(
                "backend.routes.chatbot.ask_meeting", return_value={"answer": "Hello"}) as ask:
            response = client.post("/meeting", json={"question": "Hello", "response_language": "en"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(ask.call_args.kwargs["response_language"], "en")
            self.assertEqual(client.post("/meeting", json={"question": "Hello", "response_language": "arbitrary"}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
