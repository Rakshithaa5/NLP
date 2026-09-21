"""Opt-in live Groq/Whisper/API acceptance checks; outputs stay under validation/."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")
from backend.services.semantic import analyze_transcript, GroqAnalyzer
from backend.services.intelligence import norm
from backend.scripts.test_semantic import meeting


def grounded(report, transcript):
    for group in ("action_items", "decisions", "questions", "topics", "summary_evidence"):
        for row in report[group]:
            assert row["evidence"] in norm(transcript), (group, row["evidence"])
    for item in report["questions"]:
        if item["answer_evidence"]:
            assert item["answer_evidence"]["evidence"] in norm(transcript)


def run():
    output = Path("data/validation")
    output.mkdir(exist_ok=True)
    prior = output / "semantic-live.json"
    results = json.loads(prior.read_text(encoding="utf-8")) if "--resume" in sys.argv and prior.exists() else {}
    cases = {
        "informational": "The API serves ten thousand requests daily. Its documentation describes the current endpoints. The service runs in two regions.",
        "suggestion": "I think we could use PostgreSQL.",
        "confirmed": "Let's use PostgreSQL. Agreed.",
        "missing_owner": "We need to update the documentation.",
        "missing_deadline": "John will update the documentation.",
        "rhetorical": "Does that make sense?",
        "resolved": "Should we deploy Friday? Yes, Friday works.",
        "implicit_question": "We still need to figure out who owns authentication.",
        "duplicate": "John will update the API documentation by Friday. To confirm, John will update the API docs by Friday.",
        "spanish": "Ana: Enviaré el informe mañana. Luis: De acuerdo, usaremos PostgreSQL.",
    }
    for name, transcript in cases.items():
        if name in results:
            print("Previously passed", name, flush=True)
            continue
        segments = []
        language = "en"
        if name == "spanish":
            language = "es"
            segments = [{"speaker": "Ana", "start": 0, "text": "Enviaré el informe mañana."},
                        {"speaker": "Luis", "start": 5, "text": "De acuerdo, usaremos PostgreSQL."}]
            transcript = " ".join(s["text"] for s in segments)
        result = analyze_transcript(transcript, segments, language)
        i = result["intelligence"]
        grounded(i, transcript)
        if name == "informational":
            assert i["summary"] and not i["action_items"] and not i["decisions"]
        elif name == "suggestion":
            assert not i["decisions"]
        elif name == "confirmed":
            assert any("postgresql" in d["decision"].lower() for d in i["decisions"])
        elif name == "missing_owner":
            assert i["action_items"] and all(a["owner"] is None for a in i["action_items"])
        elif name == "missing_deadline":
            assert i["action_items"][0]["owner"] == "John"
            assert i["action_items"][0]["deadline"] is None
        elif name == "rhetorical":
            assert not i["questions"]
        elif name == "resolved":
            assert any(q["status"] == "Resolved" and q["answer"] for q in i["questions"])
        elif name == "implicit_question":
            assert any(q["status"] == "Unresolved" for q in i["questions"])
        elif name == "duplicate":
            assert len(i["action_items"]) == 1
        elif name == "spanish":
            assert i["action_items"] and i["action_items"][0]["owner"] == "Ana"
            assert i["decisions"]
        results[name] = result
        (output / "semantic-live.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print("PASS", name, result["analysis_state"], flush=True)
        time.sleep(5)

    # Real API, saved transcript, Groq request, refresh and PDF. No model mocks.
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.routes import analysis, upload, report
    from backend.services.meeting_store import save_local
    store = output / "e2e_store"
    store.mkdir(exist_ok=True)
    with patch.dict(os.environ, {"DATA_DIR": str(store.resolve())}), \
            patch.object(analysis, "_get_db", return_value=None), \
            patch.object(upload, "_get_db", return_value=None), \
            patch.object(report, "_get_db", return_value=None), \
            patch.object(upload, "_DATA_DIR", store.resolve()):
        client = TestClient(app)
        file_id = "00000000-0000-0000-0000-000000000024"
        m = meeting()
        save_local(file_id, "transcript.json", {**m, "filename": "Controlled navigation meeting", "file_id": file_id})
        r = client.post("/api/analysis/" + file_id)
        assert r.status_code == 200, r.text
        result = r.json()
        i = result["intelligence"]
        grounded(i, m["full_text"])
        assert i["summary"] and i["key_takeaway"]
        assert any(a["owner"] == "John" and a["deadline"] == "Friday" and a["timestamp"] == 22
                   for a in i["action_items"])
        assert i["decisions"] and any(q["status"] == "Unresolved" for q in i["questions"])
        assert set(i["entities"]["people"]) == {"Sarah", "John", "Alex"}
        assert client.get("/api/analysis/" + file_id).json()["intelligence"] == i
        pdf = client.get("/api/report/" + file_id + "/pdf")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        (output / "controlled-analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "controlled-report.pdf").write_bytes(pdf.content)
        print("PASS controlled live API, persistence, refresh, PDF", flush=True)

        source = Path("data/0b11c60d-3dc0-4eaa-b8ba-9f7301fb692f/audio.wav")
        if source.exists():
            sample = output / "real-sample.wav"
            subprocess.run(["ffmpeg", "-y", "-i", str(source), "-t", "60", "-ac", "1",
                            "-ar", "16000", str(sample)], check=True, capture_output=True)
            with sample.open("rb") as audio:
                uploaded = client.post("/api/upload/", files={"file": ("real-sample.wav", audio, "audio/wav")})
            assert uploaded.status_code == 200, uploaded.text
            m = uploaded.json()
            assert m["full_text"] and m["segments"]
            response = client.post("/api/analysis/" + m["file_id"])
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["intelligence"]["summary"]
            grounded(result["intelligence"], m["full_text"])
            (output / "real-flow.json").write_text(json.dumps({"meeting": m, "analysis": result},
                                                            ensure_ascii=False, indent=2), encoding="utf-8")
            print("PASS real audio upload -> FFmpeg -> Whisper -> Groq -> saved API", m["file_id"], flush=True)


if __name__ == "__main__":
    run()

