"""Live long-transcript acceptance check (Groq calls; no mocked extraction)."""
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")
from backend.services.semantic import GroqAnalyzer, analyze_transcript


def run():
    texts = ["Maya will send the API documentation by Friday."]
    texts.extend(f"The API response for integration check {n} remained stable at two hundred milliseconds."
                 for n in range(170))
    texts.append("We agreed to keep PostgreSQL for the release. Maya will send the release checklist tomorrow.")
    segments = [{"text": text, "start": n * 5, "end": (n + 1) * 5, "speaker": "Speaker 1"}
                for n, text in enumerate(texts)]
    transcript = " ".join(texts)
    cache = Path("data/validation/long-raw-responses.json")
    prior = json.loads(cache.read_text(encoding="utf-8")) if "--resume" in sys.argv and cache.exists() else []
    class CountingAnalyzer(GroqAnalyzer):
        calls = 0
        raw_outputs = []
        def request(self, payload, instruction):
            self.calls += 1
            print("Live long meeting call", self.calls, "synthesis" if "candidates" in payload else "chunk", flush=True)
            if "transcript" in payload and self.calls <= len(prior):
                print("Reusing previously recorded live chunk response", flush=True)
                raw = prior[self.calls - 1]
            else:
                raw = super().request(payload, instruction)
            self.raw_outputs.append(raw)
            Path("data/validation/long-raw-responses.json").write_text(
                json.dumps(self.raw_outputs, ensure_ascii=False, indent=2), encoding="utf-8")
            return raw
    analyzer = CountingAnalyzer()
    result = analyze_transcript(transcript, segments, duration=len(texts) * 5, analyzer=analyzer)
    report = result["intelligence"]
    assert analyzer.calls >= 3
    assert any(a["owner"] == "Maya" and a["deadline"] == "Friday" for a in report["action_items"])
    assert any(a["owner"] == "Maya" and a["deadline"] == "tomorrow" for a in report["action_items"])
    assert any("PostgreSQL" in d["decision"] for d in report["decisions"])
    assert len(report["summary"]) >= 3
    assert any("stable" in s.lower() or "millisecond" in s.lower() for s in report["summary"])
    for group in ("action_items", "decisions", "questions", "topics"):
        for item in report[group]:
            assert item["evidence"] in transcript
    Path("data/validation/long-analysis.json").write_text(json.dumps(
        {"calls": analyzer.calls, "transcript_chars": len(transcript), "analysis": result, "raw_outputs": analyzer.raw_outputs},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS long transcript, early/late tasks, decision, evidence, synthesis;", analyzer.calls, "calls", flush=True)


if __name__ == "__main__":
    run()

