# Meeting Analyzer — AI-Based NLP System for Automated Meeting Analysis

An end-to-end NLP pipeline that takes a recorded meeting (audio or video),
transcribes it, extracts grounded actions, decisions, questions and entities,
and generates a semantic meeting summary —
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
| Meeting intelligence | Groq structured semantic extraction |
| Academic baselines | spaCy, TF-IDF/LDA, BART / T5 |
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


## Meeting intelligence

The existing Overview / Transcript / Analytics dashboard uses one canonical
Pydantic contract in `backend/services/intelligence.py`. It contains a concise
summary, key takeaway, actions, decisions, resolved/unresolved questions, semantic
topics, entities, and deterministic meeting metadata. Evidence remains in the
original transcript language. Missing owners, deadlines, and priorities are null.

### Groq configuration

Set `GROQ_API_KEY` (or `MEETING_LLM_API_KEY`) in the root `.env`; restart the
backend after changing it. Keys stay on the backend and must never use a `VITE_`
prefix. No additional SDK dependency is needed.

Defaults, also shown in `.env.example`:

```dotenv
MEETING_LLM_BASE_URL=https://api.groq.com/openai/v1
MEETING_LLM_MODEL=openai/gpt-oss-120b
MEETING_LLM_RESPONSE_FORMAT=json_schema
MEETING_LLM_CONTEXT_TOKENS=32768
MEETING_LLM_MAX_OUTPUT_TOKENS=8192
MEETING_LLM_TIMEOUT_SECONDS=120
```

The default Groq model supports strict schema output. For a different compatible
model that only supports JSON mode, explicitly set the response format to
`json_object`. Context/output settings must stay within that model's limits.
Provider reference: https://console.groq.com/docs/structured-outputs

### Extraction and persistence

Upload -> FFmpeg -> Faster-Whisper -> original transcript/segments -> one structured
Groq extraction -> field-level validation and evidence mapping -> canonical report
-> saved API response -> dashboard/PDF.

Long transcripts use byte-bounded chunks with adjacent-turn overlap, local
extraction, then compact global synthesis. Exceptionally large intermediate sets
reduce in additional bounded tiers. Nothing is silently truncated; an oversized
or incomplete response produces a failure. No separate summary/actions/topics
model calls are made. Legacy academic services remain available for their
standalone tests, but cannot overwrite the semantic meeting report.

Paraphrases are allowed; supporting quotes must match the original transcript.
Unambiguous matching segments provide source navigation at the first segment's
timestamp, not word-level audio alignment. Repeated or stale segment matches
remain untimed. Stored speaker labels are preserved; the current Whisper service
does not perform diarization, so it cannot identify speakers from unlabeled audio.
Multilingual extraction runs on the original text; there is no forced English
translation or English-only extraction gate.

The API preserves its existing boundary fields for clients/database compatibility.
Those fields are derived from `intelligence`, not independently extracted.
Supabase stores the canonical object in the existing `topics.intelligence` JSONB
field, so no SQL migration is required. Local recovery copies contain the same
canonical data. Re-analyze old reports to use semantic extraction.

`analysis_state` distinguishes `complete`, `partial`, and `empty`. Field-level
recovery is reported as partial, with technical `analysis_issues` for diagnostics.
Provider/parsing failure returns HTTP 502 and saves a failed attempt separately,
preserving any earlier successful report. The dashboard exposes Retry analysis.
Groq rate limits/transient errors receive at most two bounded retries; technical
errors are logged without logging credentials or raw transcript response bodies.

### Validation

Offline regression tests use explicit model/audio test doubles, never application
demo data:

```powershell
python -m unittest backend.scripts.test_report_accuracy backend.scripts.test_intelligence backend.scripts.test_semantic -v
cd frontend
npm run build
npm run lint
node --test src/components/meeting/data.test.js
```

Opt-in live tests require the configured Groq key:

```powershell
python -m backend.scripts.validate_semantic_live
python -m backend.scripts.validate_long_semantic
```

The first script validates the controlled navigation meeting, semantic edge cases,
Spanish extraction, API persistence, PDF, and (when the existing sample recording
is present) a real 60-second FFmpeg/Whisper upload flow. Use `--resume` to resume
completed case results after a rate-limit interruption. Outputs and isolated
recordings are saved under `data/validation/`; they are not served as demo content.

Browser validation uses installed Edge/Playwright with a running API/UI:
`python -m backend.scripts.check_dashboard_browser`. Configure `TEST_API_URL`,
`TEST_UI_URL`, `TEST_MEETING_ID`, and `TEST_SEARCH` for a saved meeting containing
decisions and evidence links. Browser checks cover the real API, evidence
navigation, search/filtering, refresh, PDF download, mobile overflow, malformed
responses, and retry. Playwright is a development-only test tool.

Provider throughput limits are separate from the model context window. The
MEETING_LLM_MAX_INPUT_BYTES setting defaults to 8192 and bounds each extraction
payload. Compact synthesis has a separate MEETING_LLM_SYNTHESIS_BYTES ceiling
(default 12288). Lower these if Groq returns HTTP 413 for your account token
limit; increasing context size does not fix that limit. Compact synthesis uses
source-span endpoints to preserve evidence without repeating every segment ID.
GPT-OSS requests default to low reasoning effort to reduce output-token usage;
MEETING_LLM_REASONING_EFFORT can override this with low, medium or high. This
option is sent only for the supported GPT-OSS models. Provider references:
https://console.groq.com/docs/rate-limits and https://console.groq.com/docs/reasoning.
