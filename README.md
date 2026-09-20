# Meeting Analyzer — AI-Based NLP System for Automated Meeting Analysis

An end-to-end NLP pipeline that takes a recorded meeting (audio or video),
transcribes it, extracts entities, classifies sentences, identifies action items
and decisions, and generates both extractive and abstractive summaries —
presented in an interactive React dashboard.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite |
| UI | Tailwind CSS |
| Charts | Recharts |
| Backend | Python + FastAPI |
| Audio/Video processing | FFmpeg |
| Speech-to-Text | Faster-Whisper |
| NLP | spaCy, NLTK |
| ML (classification) | Scikit-learn |
| Transformers | Hugging Face Transformers |
| Summarization | BART / T5 / FLAN-T5 |
| Database | Firebase or Supabase |
| PDF export | ReportLab |

---

## Project Structure

```
NLP/
├── frontend/
│   ├── src/
│   ├── components/
│   ├── pages/
│   └── services/
├── backend/
│   ├── main.py
│   ├── routes/
│   │   ├── upload.py
│   │   └── analysis.py
│   ├── services/
│   │   ├── audio.py
│   │   ├── transcription.py
│   │   ├── preprocessing.py
│   │   ├── ner.py
│   │   ├── classification.py
│   │   ├── topics.py
│   │   ├── actions.py
│   │   ├── decisions.py
│   │   └── summarization.py
│   └── models/
├── data/
├── models/
├── requirements.txt
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- FFmpeg installed and on PATH

### Backend

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Copy env template and fill in credentials
cp .env.example .env

# Run dev server
uvicorn backend.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # starts Vite at http://localhost:5173
```

### Verify

- Backend health: `GET http://localhost:8000/health` → `{"status": "ok"}`
- Frontend: open `http://localhost:5173`

---

## Pipeline

```
Upload → Validate → Extract Audio (FFmpeg) → Transcribe (Faster-Whisper)
  → NLP Preprocess (spaCy + NLTK)
  → NER | Classification (TF-IDF + LR/SVM) | Topics (TF-IDF + LDA/NMF)
  → Actions | Decisions | Questions
  → Summarization (Extractive + Abstractive BART/T5)
  → Dashboard
```

---

## License

MIT


## Meeting report accuracy

Reports default to chronological transcript excerpts selected with TF-IDF relevance,
diversity, and outcome weighting. Explicit actions and decisions are validated with
rules and spaCy dependencies; the classifier's original label and probability remain
available for inspection. Model probability is not a calibrated factuality score.
Unknown owners/deadlines are left unspecified. Questions are listed as raised; an
explicit open marker describes that excerpt, not a verified end-of-meeting status.

Optional transformer drafts can be enabled with `ENABLE_ABSTRACTIVE_SUMMARY=true`.
They use tokenizer-bounded chunks without a truncating final merge and require human
review. Shareable PDFs use transcript excerpts. No paid API or stack change is required.

Restart the backend after updating, then click **Re-analyse** on existing dashboards;
stored analyses are not retroactively changed. New uploads use the revised pipeline.
Run regression checks with `python -m unittest backend.scripts.test_report_accuracy -v`.

The extraction rules favor precision and may omit implicit commitments, unusual task
verbs, conditional assignments, and cross-sentence resolutions. Speaker identity is
not inferred from first-person pronouns. English NLP models are used. Validate with
representative, annotated team recordings before treating reports as authoritative;
the regression suite is not a measured production accuracy benchmark.


## Meeting intelligence dashboard (v2)

The results route `/dashboard/:fileId` now offers Overview, Transcript, and Analytics.
Overview contains source-backed summary bullets, an explicit outcome when present,
actions, decisions, follow-up questions, phrase-based topics, and validated entities.
Transcript search, category filters, and evidence links use original Whisper segments.
Analytics contains composition, topic relevance, entity counts, and recording statistics.
Speaker filtering/talk-time appears only for segments that actually have speaker labels;
the current Whisper pipeline does not perform diarization. Mentioned people are never
counted as participants. Uploaded date is not presented as the date of the meeting.

The analysis API retains its existing fields and adds a Pydantic-validated `intelligence`
object (version 2). For database compatibility, this object is stored inside the existing
`topics` JSONB column as `topics.intelligence`; no SQL migration is required. Existing
reports need **Re-analyse**. Exact, unambiguous source matches provide `segment_ids` and
a timestamp at the first segment boundary, not word-level audio alignment. When mapping
is unavailable, evidence is readable without a misleading navigation button.

Unknown owner, deadline, and priority remain null. Question resolution is `Not assessed`
unless explicitly marked open or followed by an explicit answer. This avoids claiming
that every question is unanswered. TF-IDF + classifier + spaCy and LDA/NMF are retained;
raw topic clusters are no longer shown as user-facing discussion topics. Topic labels
are actual noun phrases, not generated titles. No paid service has been added.

Multilingual transcription and original text are preserved. English-only semantic models
are not run on recordings detected as other languages: those reports expose original
excerpts plus a clear capability notice. Multilingual semantic analysis and diarization
require suitable models and remain future extensions, not simulated capabilities.

Recovery copies (`transcript.json`, `analysis.json`) stay in each recording's existing
local data directory so a Supabase outage does not discard a freshly processed report.
They contain meeting content and should follow the same retention policy as recordings.
Supabase remains the primary shared database; local copies only cover that server.

Validation commands:

```powershell
python -m unittest backend.scripts.test_report_accuracy backend.scripts.test_intelligence -v
cd frontend
npm run build
npm run lint
node --test src/components/meeting/data.test.js
```

Optional browser validation uses Playwright with installed Edge and existing processed
data, not application demo fixtures. With API on port 8011 and Vite on port 5174:
`python -m backend.scripts.check_dashboard_browser`. Override `TEST_API_URL`, `TEST_UI_URL`,
and `TEST_MEETING_ID` for your environment. Playwright is a development-only test tool.
