"""Regression cases for report grounding; uses installed local NLP models."""
import os
import unittest
from unittest.mock import patch
from backend.services.actions import extract_actions, is_action
from backend.services.decisions import extract_decisions, extract_questions
from backend.services.summarization import summarize, summarize_extractive, summarize_abstractive
from backend.routes.analysis import run_nlp_pipeline
from backend.routes.report import _build_pdf


class ReportAccuracyTests(unittest.TestCase):
    def test_decisions_preserve_negation_and_reject_proposals(self):
        sentences = ["We have not approved the launch.", "If we approved the launch, costs would rise.",
                     "We should adopt Redis.", "We decided not to deploy on Monday.",
                     "We rejected the budget."]
        self.assertEqual([d["statement"] for d in extract_decisions(sentences)], sentences[-2:])

    def test_recipient_is_not_owner(self):
        item = extract_actions(["I will send the report to Alice by Friday."])[0]
        self.assertIsNone(item["person"])
        self.assertEqual(item["deadline"], "Friday")

    def test_explicit_owner_and_future_status(self):
        item = extract_actions(["Alice will send the completed report to Bob by Friday."])[0]
        self.assertEqual(item["person"], "Alice")
        self.assertEqual(item["status"], "Pending")
        self.assertIn("to Bob", item["task"])

    def test_forecasts_and_suggestions_are_not_tasks(self):
        for text in ["The security review will finish on Thursday.", "We should review Redis.",
                     "Alice will not send the file.", "If needed, Alice will send the file."]:
            self.assertFalse(is_action(text), text)

    def test_explicit_request(self):
        item = extract_actions(["Bob, can you send the invoice by Thursday?"])[0]
        self.assertEqual(item["person"], "Bob")

    def test_questions_do_not_claim_to_be_unanswered(self):
        question = extract_questions(["When will we launch?"])[0]
        self.assertEqual(question["resolution_status"], "Not assessed")

    def test_default_summary_never_calls_generator(self):
        with patch.dict(os.environ, {"ENABLE_ABSTRACTIVE_SUMMARY": "false"}), patch(
            "backend.services.summarization.summarize_abstractive") as generator:
            result = summarize("Alice will send the report by Friday.")
        generator.assert_not_called()
        self.assertEqual(result["preferred"], "extractive")
        self.assertEqual(result["abstractive"], "")

    def test_summary_keeps_late_outcome_and_removes_duplicates(self):
        text = "The team discussed dashboard colors. " * 30 + "We decided not to launch until security approves."
        summary = summarize_extractive(text, 2)
        self.assertIn("We decided not to launch", summary)
        self.assertEqual(summary.count("dashboard colors"), 1)

    def test_pipeline_and_pdf(self):
        text = "Alice will send the budget by Friday. We have not approved the launch. We decided not to deploy on Monday. When will we launch?"
        with patch.dict(os.environ, {"ENABLE_ABSTRACTIVE_SUMMARY": "false"}):
            result = run_nlp_pipeline(text)
        self.assertEqual(len(result["action_items"]), 1)
        self.assertEqual(len(result["decisions"]), 1)
        analysis = dict(result, summary_extractive=result["summary"]["extractive"])
        pdf = _build_pdf("test", {"meeting": {"filename": "R&D <review>.mp4", "transcript": text + " x < 3 & y > 2"}, "analysis": analysis})
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_token_chunks_preserve_end_of_long_input(self):
        from types import SimpleNamespace
        class Tokenizer:
            model_max_length = 64
            def num_special_tokens_to_add(self, pair=False): return 2
            def encode(self, text, add_special_tokens=False): return text.split()
            def decode(self, ids, skip_special_tokens=True): return " ".join(ids)
        class Pipe:
            tokenizer = Tokenizer()
            model = SimpleNamespace(config=SimpleNamespace(max_position_embeddings=64))
            def __call__(self, chunk, **kwargs):
                self_test.assertLessEqual(len(chunk.split()) + 2, 64)
                self_test.assertFalse(kwargs["truncation"])
                return [{"summary_text": chunk}]
        self_test = self
        text = " ".join("word" + str(i) for i in range(250))
        with patch("backend.services.summarization._load_abstractive_pipeline", return_value=Pipe()):
            output = summarize_abstractive(text)
        self.assertEqual(output.split(), text.split())

    def test_failed_generator_is_not_mislabeled_as_draft(self):
        with patch.dict(os.environ, {"ENABLE_ABSTRACTIVE_SUMMARY": "true"}), patch(
            "backend.services.summarization._load_abstractive_pipeline", side_effect=RuntimeError("offline")):
            result = summarize("Alice will send the report by Friday.")
        self.assertEqual(result["abstractive"], "")
        self.assertTrue(result["extractive"])

    def test_empty_transcript(self):
        with self.assertRaises(RuntimeError):
            run_nlp_pipeline(" ")


if __name__ == "__main__":
    unittest.main()
