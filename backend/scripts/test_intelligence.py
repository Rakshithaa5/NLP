"""Contract, evidence, and precision regressions for the meeting dashboard."""
import tempfile
import unittest
from unittest.mock import patch
from backend.services.intelligence import build_intelligence, evidence_for, Intelligence
from backend.services.meeting_store import save_local, read_local, load_meeting
from backend.services.preprocessing import _get_nlp
from backend.services.ner import extract_entities
from backend.services.topics import extract_topics
from backend.services.decisions import extract_questions
from backend.services.actions import extract_actions, is_action
from backend.routes.analysis import run_nlp_pipeline

class IntelligenceTests(unittest.TestCase):
    def test_selected_noun_is_not_decision(self):
        from backend.services.decisions import extract_decisions
        text = "Because when you let people have that video or the selected, they will have every see orders from students program."
        self.assertEqual(extract_decisions([text]), [])

    def test_explicit_present_tense_decision(self):
        from backend.services.decisions import extract_decisions
        self.assertEqual(len(extract_decisions(["The development team decides not to implement the old feature."])), 1)

    def test_filler_summary_is_empty(self):
        from backend.services.summarization import summarize_extractive
        self.assertEqual(summarize_extractive("Yeah. Okay. Um. Right."), "")

    def test_filler_topics(self):
        result = extract_topics(["yeah okay let s um uh actually basically really meeting"])
        self.assertEqual(result["keywords"], [])
        self.assertEqual(result["discussion"], [])

    def test_topic_labels_are_real_phrases(self):
        text = "Customer feedback highlighted navigation problems. Customer feedback informs product usability."
        result = extract_topics([text])
        self.assertTrue(result["discussion"])
        for topic in result["discussion"]:
            self.assertIn(topic["label"], text)
            self.assertGreaterEqual(len(topic["label"].split()), 2)

    def test_suspicious_person_predictions(self):
        from spacy.tokens import Span
        doc = _get_nlp()("This benefit helps Sarah.")
        doc.ents = [Span(doc, 0, 1, label="PERSON"), Span(doc, 1, 2, label="PERSON"), Span(doc, 3, 4, label="PERSON")]
        names = [e["text"] for e in extract_entities(doc)]
        self.assertNotIn("This", names)
        self.assertNotIn("benefit", names)

    def test_no_fake_deadline_or_owner(self):
        item = extract_actions(["I will update the report by highlighting the risks."])[0]
        self.assertIsNone(item["deadline"])
        self.assertIsNone(item["person"])

    def test_owner_is_not_reporting_subject(self):
        item = extract_actions(["Alice said Bob will send the report by Friday."])[0]
        self.assertEqual(item["person"], "Bob")

    def test_modal_question_is_not_commitment(self):
        self.assertFalse(is_action("Will Alice send the report?"))

    def test_rhetorical_questions_filtered(self):
        self.assertEqual(extract_questions(["Do you know what I mean?", "Right?", "Okay?", "Can you hear me?"]), [])

    def test_cross_segment_evidence_and_zero_timestamp(self):
        segments = [{"start": 0, "text": "Alice will send"}, {"start": 3, "text": "the budget by Friday."}]
        result = evidence_for("Alice will send the budget by Friday.", "Alice will send the budget by Friday.", segments)
        self.assertEqual(result["segment_ids"], [0, 1])
        self.assertEqual(result["timestamp"], 0)
        self.assertIsNone(evidence_for("Fake task", "Real transcript", segments))

    def test_ambiguous_evidence_has_no_timestamp(self):
        result = evidence_for("Agreed.", "Agreed. Agreed.", [{"start": 0, "text": "Agreed."}, {"start": 3, "text": "Agreed."}])
        self.assertEqual(result["segment_ids"], [])
        self.assertIsNone(result["timestamp"])

    def test_contract_and_explicit_answer(self):
        from backend.scripts.test_semantic import response
        from backend.services.semantic import GroqAnalyzer
        text = "Who will own the redesign? The answer is Sarah."
        raw = response(text)
        raw["questions"] = [{"question": "Who will own the redesign?", "evidence": "Who will own the redesign?",
                            "status": "Resolved", "answer": "The answer is Sarah.",
                            "answer_evidence": {"evidence": "The answer is Sarah."}}]
        with patch.object(GroqAnalyzer, "request", return_value=raw):
            result = run_nlp_pipeline(text)
        report = build_intelligence(result, text)
        Intelligence.model_validate(report)
        self.assertEqual(report["questions"][0]["status"], "Resolved")
        self.assertEqual(report["questions"][0]["answer"], "The answer is Sarah.")
        self.assertEqual(report["action_items"], [])
        self.assertEqual(report["decisions"], [])

    def test_non_english_preserves_original(self):
        from backend.scripts.test_semantic import response
        from backend.services.semantic import GroqAnalyzer
        text = "La reunion porte sur le budget."
        with patch.object(GroqAnalyzer, "request", return_value=response(text)) as model:
            result = run_nlp_pipeline(text, language="fr")
        report = build_intelligence(result, text, language="fr")
        self.assertEqual(report["summary"], [text])
        self.assertEqual(report["action_items"], [])
        self.assertEqual(report["metadata"]["language"], "fr")
        model.assert_called_once()

    def test_local_refresh_and_path_validation(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"DATA_DIR": directory}):
            file_id = "00000000-0000-0000-0000-000000000001"
            save_local(file_id, "transcript.json", {"full_text": "Original", "segments": []})
            self.assertEqual(load_meeting(file_id)["full_text"], "Original")
            from backend.services.meeting_store import list_local_meetings
            self.assertEqual(list_local_meetings()[0]["id"], file_id)
            self.assertIsNone(read_local("../../outside", "transcript.json"))

if __name__ == "__main__": unittest.main()
