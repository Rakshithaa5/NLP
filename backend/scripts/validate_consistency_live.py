"""Five fresh Groq calls through the real persistence/reconciliation route; isolated fixture store."""
import json
import logging
import os
import time
from pathlib import Path
from unittest.mock import patch
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")
from backend.scripts.test_semantic import meeting
from backend.services.consistency import FIELDS, valid_evidence
from backend.services.meeting_store import save_local, read_local
from backend.routes import analysis
from fastapi.testclient import TestClient
from backend.main import app


def run():
    output = Path("data/validation/consistency")
    output.mkdir(parents=True, exist_ok=True)
    logging.getLogger().setLevel(logging.INFO)
    handler = logging.FileHandler(output / "pipeline.log", encoding="utf-8")
    logging.getLogger().handlers = [handler]
    fixture = meeting()
    file_id = "00000000-0000-0000-0000-000000000005"
    records, identity_sets, candidate_sets = [], [], []
    with patch.dict(os.environ, {"DATA_DIR": str(output / "store")}), patch.object(analysis, "_get_db", return_value=None):
        save_local(file_id, "transcript.json", fixture)
        # A separate store per invocation avoids using a prior validation result as run 1.
        from tempfile import TemporaryDirectory
        with TemporaryDirectory(dir=output) as directory, patch.dict(os.environ, {"DATA_DIR": directory}):
            save_local(file_id, "transcript.json", fixture)
            client = TestClient(app)
            for index in range(5):
                if index:
                    time.sleep(25)
                for attempt in range(3):
                    response = client.post("/api/analysis/" + file_id + "?force=true")
                    if response.status_code != 502 or "rate limit" not in response.text.lower():
                        break
                    print("Provider rate limit; waiting before retrying the same run", flush=True)
                    time.sleep(30)
                if response.status_code != 200:
                    raise RuntimeError(response.text)
                result = response.json()
                report = result["intelligence"]
                candidate = read_local(file_id, "analysis_candidate.json")["intelligence"]
                ids = {key: {r["id"] for r in report[key]} for key in FIELDS}
                identity_sets.append(ids)
                candidate_sets.append({key: {r["id"] for r in candidate[key]} for key in FIELDS})
                record = {"run": index + 1, "state": result["analysis_state"],
                          "counts": {key: len(report[key]) for key in FIELDS},
                          "candidate_counts": {key: len(candidate[key]) for key in FIELDS},
                          "pipeline": report["extraction_audit"], "reconciliation": report["reconciliation_audit"],
                          "manifest": report["analysis_manifest"]}
                records.append(record)
                (output / f"run-{index+1}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                (output / f"candidate-{index+1}.json").write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
                print(json.dumps({"run": index+1, "counts": record["counts"], "candidate_counts": record["candidate_counts"], "state": record["state"]}), flush=True)
                for key in FIELDS:
                    for item in report[key]:
                        assert valid_evidence(item, fixture["full_text"], fixture["segments"]), (key, item)
            overlap = {key: min(len(identity_sets[0][key] & ids[key]) / len(identity_sets[0][key] | ids[key])
                        if identity_sets[0][key] | ids[key] else 1.0 for ids in identity_sets[1:]) for key in FIELDS}
            passed = all(r["state"] == "complete" for r in records) and all(overlap[k] == 1 for k in ("action_items", "decisions", "questions", "follow_ups"))
            raw_overlap = {key: min(len(candidate_sets[0][key] & ids[key]) / len(candidate_sets[0][key] | ids[key])
                        if candidate_sets[0][key] | ids[key] else 1.0 for ids in candidate_sets[1:]) for key in FIELDS}
            summary = {"passed": passed, "runs": records, "minimum_jaccard_vs_run1": overlap,
                       "candidate_minimum_jaccard_vs_run1": raw_overlap}
            (output / "results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(json.dumps({"passed": passed, "overlap": overlap}), flush=True)
            assert passed, "Five-run semantic consistency failed; inspect raw candidates and reconciled results"

if __name__ == "__main__":
    run()
