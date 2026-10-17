"""Manual action edits persist without changing transcript evidence."""
import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from pydantic import ValidationError
from backend.routes import analysis
from backend.services.meeting_store import save_local, read_local

ID = "12345678-1234-1234-1234-123456789abc"

class ActionDetailsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        env = patch.dict(os.environ, {"DATA_DIR": temp.name})
        env.start()
        self.addCleanup(env.stop)
        db = patch.object(analysis, "_get_db", return_value=None)
        db.start()
        self.addCleanup(db.stop)
        intelligence = {"action_items": [{"task": "Send notes", "owner": None,
                         "deadline": None, "evidence": "Please send notes", "segment_ids": [0]}]}
        save_local(ID, "analysis.json", {"intelligence": intelligence, "topics": {"intelligence": intelligence},
                   "analyzed_at": "revision-1", "analysis_state": "complete", "analysis_issues": []})

    def update(self, **kwargs):
        return analysis.ActionDetailsUpdate(**dict({"owner": " Alex ", "deadline": " Friday ",
                                                   "task": "Send notes", "analyzed_at": "revision-1"}, **kwargs))

    def test_edit_survives_reload_and_preserves_evidence(self):
        analysis.update_action_details(ID, 0, self.update())
        stored = analysis._fetch_stored_analysis(ID)
        item = stored["intelligence"]["action_items"][0]
        self.assertEqual((item["owner"], item["deadline"]), ("Alex", "Friday"))
        self.assertTrue(item["manually_edited"])
        self.assertEqual(item["evidence"], "Please send notes")
        self.assertEqual(item["segment_ids"], [0])
        self.assertEqual(item, stored["topics"]["intelligence"]["action_items"][0])
        self.assertEqual(asyncio.run(analysis.get_analysis(ID)).status_code, 200)

    def test_blank_values_clear_fields(self):
        analysis.update_action_details(ID, 0, self.update(owner=" ", deadline=""))
        item = read_local(ID, "analysis.json")["intelligence"]["action_items"][0]
        self.assertIsNone(item["owner"])
        self.assertIsNone(item["deadline"])

    def test_stale_edit_and_missing_item_are_rejected(self):
        for index, update, code in [(0, self.update(analyzed_at="old"), 409),
                                    (0, self.update(task="Different task"), 409),
                                    (-1, self.update(), 404), (9, self.update(), 404)]:
            with self.assertRaises(HTTPException) as raised:
                analysis.update_action_details(ID, index, update)
            self.assertEqual(raised.exception.status_code, code)
        self.assertIsNone(read_local(ID, "analysis.json")["intelligence"]["action_items"][0]["owner"])

    def test_validation_rejects_unexpected_and_oversized_fields(self):
        for extra in ({"owner": "x" * 201}, {"status": "Done"}, {"deadline": None}):
            with self.assertRaises(ValidationError):
                self.update(**extra)

    def test_storage_failure_is_reported(self):
        with patch.object(analysis, "_persist_analysis", side_effect=RuntimeError("failed")):
            with self.assertRaises(HTTPException) as raised:
                analysis.update_action_details(ID, 0, self.update())
        self.assertEqual(raised.exception.status_code, 503)

if __name__ == "__main__":
    unittest.main()
