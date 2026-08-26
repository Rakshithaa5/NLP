# AI-Based NLP System for Automated Meeting Analysis — Implementation Plan

> **Purpose of this document:** A phase-by-phase build plan for AI coding assistants (Claude Code, Copilot, Cursor, etc.) to follow while implementing this project. It preserves the exact workflow, pipeline order, and technology stack defined in the original project details. **No library or stack substitutions are permitted** unless explicitly instructed by the user.

---

## 0. Non-Negotiable Constraints

These apply across every phase. An AI assistant must not deviate from them without explicit user approval.

- **Do not swap, "upgrade," or substitute any library/tool** listed in the Technology Stack table below (e.g. no swapping Faster-Whisper for OpenAI Whisper API, no swapping spaCy for a different NLP toolkit, no swapping Firebase/Supabase for another DB unless the user specifies which of the two).
- **RAG / semantic Q&A ("Ask Your Meeting") is explicitly OUT OF SCOPE** for the initial build. It belongs only to the Future Enhancement phase (Phase 6) and must not be implemented early, even if it seems convenient.
- **Input is always an existing, already-recorded audio/video file** — this is not a live/real-time transcription system.
- The pipeline order defined in the Overall Workflow (Section 4 of the source doc) must be preserved exactly:
  `Upload → Validate → Extract Audio (FFmpeg) → Transcribe (Faster-Whisper) → NLP Preprocess → [NER | Classification | Topics] → Meeting Info → [Actions | Decisions | Questions] → Summarization → Dashboard`
- Prefer **open-source / local-first tools** — avoid paid AI APIs, per the project's cost goal.
- Keep the **ML + rule-based components genuinely present** (TF-IDF, Logistic Regression/SVM, spaCy NER, dependency parsing) — the project is explicitly designed to be more than "an LLM wrapper," since it will be evaluated by an NLP jury.

### Technology Stack (fixed — do not change)

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
| Summarization | BART / T5 / FLAN-T5 (optionally a local LLM via Ollama for abstractive) |
| Database | Firebase or Supabase |
| PDF export | ReportLab |
| Version control | Git + GitHub |

### Fixed Project Structure (do not restructure)

```
meeting-analyzer/
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

## Phase 0 — Project Bootstrap

**Goal:** Repo, environments, and skeleton in place. No NLP logic yet.

1. Initialize Git repo; create `.gitignore` (Python, Node, data/models artifacts).
2. Scaffold `frontend/` with **React + Vite**; install **Tailwind CSS** and **Recharts**.
3. Scaffold `backend/` with **FastAPI**; set up virtualenv and `requirements.txt`.
4. Create the exact folder structure above (empty `services/`, `routes/`, `models/` files with stub docstrings).
5. Verify FastAPI (`/health` endpoint) and Vite dev server both run and can talk to each other (basic CORS-enabled fetch).
6. Set up Firebase or Supabase project; store credentials via `.env` (never commit secrets).

**Exit criteria:** Frontend renders a blank shell page; backend `/health` returns 200; DB connection verified with a trivial write/read.

---

## Phase 1 — Basic Pipeline (Upload → Transcript)

Maps to source doc "Phase 1 — Basic Pipeline" and Implementation Pipeline Steps 1–3.

1. **Frontend:** Build the upload UI (accepts MP4, MP3, WAV, M4A, and MOV if FFmpeg supports it). Sends file via REST call to FastAPI (`services/` in frontend).
2. **Backend `routes/upload.py`:** Receive file, validate type/size (File Validation step), store to `data/`.
3. **Backend `services/audio.py`:** If input is video, extract audio via **FFmpeg** → `.wav`.
4. **Backend `services/transcription.py`:** Run **Faster-Whisper** on the extracted/uploaded audio to produce a full transcript.
5. Persist raw transcript + meeting metadata (filename, duration, upload timestamp) to the database.
6. Return transcript to frontend for a simple "raw transcript" preview view (no analysis yet).

**Exit criteria:** A user can upload a real meeting recording and see the raw Faster-Whisper transcript end-to-end.

---

## Phase 2 — Core NLP (Preprocessing → NER → Topics → Classification)

Maps to source doc "Phase 2 — Core NLP" and Implementation Pipeline Step 4–5 (first half).

1. **Backend `services/preprocessing.py`** (spaCy + NLTK):
   - Sentence segmentation
   - Tokenization
   - Normalization (punctuation/spacing cleanup)
   - Stop-word handling (where relevant to downstream tasks)
   - Lemmatization
2. **Backend `services/ner.py`:** Run **spaCy NER** over the cleaned transcript; extract PERSON, ORGANIZATION, DATE, TIME, LOCATION, TECHNOLOGY, PROJECT entities. (Note in code comments: transformer-based NER is a possible later swap-in, not part of this phase.)
3. **Backend `services/topics.py`:** Implement topic extraction using **TF-IDF**, then layer **LDA/NMF** for topic modeling as described in the source doc.
4. **Backend `services/classification.py`:** Implement the sentence classifier for categories `ACTION ITEM / DECISION / QUESTION / DISCUSSION / INFORMATION`.
   - Baseline: **TF-IDF + Logistic Regression/SVM** (Scikit-learn).
   - Leave a clear extension point/interface for a BERT/DistilBERT (Hugging Face Transformers) classifier upgrade — implement the interface now, the transformer swap can come later if time allows, but ship the baseline first.
5. Wire these into `routes/analysis.py` as a single "analyze transcript" pipeline step, run in the fixed order: preprocessing → NER → classification → topics.
6. Persist NLP outputs (entities, topics, per-sentence classifications) to the database alongside the transcript.

**Exit criteria:** Given a stored transcript, the backend can produce and persist entities, topics, and per-sentence category labels.

---

## Phase 3 — Meeting Intelligence (Actions, Decisions, Questions, Summarization)

Maps to source doc "Phase 3 — Meeting Intelligence" and Implementation Pipeline Step 5 (second half) & Step 6.

1. **Backend `services/actions.py`:**
   - Input: sentences classified as `ACTION ITEM`.
   - Apply NER + dependency/semantic analysis + rule-based extraction to pull out `{person, task, deadline, status}`.
   - Default `status = "Pending"` when not stated otherwise.
2. **Backend `services/decisions.py`:**
   - Input: sentences classified as `DECISION`.
   - Use classification output + keyword/pattern detection to phrase a clean decision statement.
3. **Question/unresolved issue detection:** implement within `classification.py`/`decisions.py` scope (or a small helper) — sentences classified as `QUESTION` become "Unresolved Question" entries.
4. **Backend `services/summarization.py`:**
   - Implement **extractive** summarization first (TF-IDF or TextRank over the transcript) — cheapest, most explainable to a jury.
   - Implement **abstractive** summarization using **BART/T5/FLAN-T5** (Hugging Face Transformers), optionally routed through a local LLM via Ollama, per the source doc's flexibility on this point.
   - Keep both available; the dashboard can default to abstractive with extractive as a fallback/comparison.
5. Persist action items, decisions, unresolved questions, and both summary types to the database.

**Exit criteria:** For a processed meeting, the backend returns a structured payload: action items (with person/task/deadline/status), decisions, unresolved questions, and a summary.

---

## Phase 4 — UI & Reporting

Maps to source doc "Phase 4 — UI & Reporting" and Implementation Pipeline Steps 7–9.

1. **Frontend dashboard** (React + Tailwind + Recharts), matching the source doc's dashboard layout:
   - Header stats: duration, speaker count (if available), action item count, decision count, question count.
   - Summary panel.
   - Key topics panel.
   - Action items panel (`Person → Task → Deadline`).
   - Decisions panel.
   - (Optional) Questions/unresolved issues panel.
2. **Meeting history view:** list of previously analyzed meetings (from DB), with basic analytics (e.g. counts over time) via Recharts.
3. **PDF export (`ReportLab`):** backend endpoint that generates a downloadable meeting report (transcript + summary + action items + decisions) as PDF.
4. **Testing pass:**
   - Backend: unit tests per service module (`audio`, `transcription`, `preprocessing`, `ner`, `classification`, `topics`, `actions`, `decisions`, `summarization`).
   - Frontend: component-level tests for upload flow and dashboard rendering.
   - End-to-end: one full run on a real sample recording, verifying each pipeline stage's output is persisted and displayed correctly.

**Exit criteria:** A user can upload a recording, watch it move through the pipeline, view the full dashboard, browse meeting history, and download a PDF report.

---

## Phase 5 — Hardening & Jury-Readiness (recommended addition, not in original phase list)

This phase isn't in the source doc's five phases but is implied by Section 21 ("What Makes This an NLP Project?") — use it to make the NLP work presentable and defensible.

1. Document, per module, which NLP/ML technique is used and why (tokenization/preprocessing, NER, classification, topic modeling, extractive summarization, abstractive summarization) — this becomes jury-facing documentation.
2. Add basic evaluation/inspection artifacts: sample transcripts with annotated classification outputs, confusion-matrix-style sanity checks for the classifier if labeled data is available.
3. Confirm no paid AI API keys are required for the core pipeline (cost goal from Section 17).
4. Finalize `README.md` with setup instructions matching the fixed project structure and stack.

**Exit criteria:** Project is demoable end-to-end, and each pipeline stage's technique can be explained and justified independently.

---

## Phase 6 — Future Enhancement (out of scope for initial build)

Do **not** implement during the main build unless the user explicitly asks. Listed here only so an AI assistant doesn't accidentally pull these forward:

- Speaker diarization
- RAG (retrieval-augmented generation)
- Semantic search
- "Ask the meeting" Q&A functionality

---

## Quick Reference: Phase → Source Doc Mapping

| This plan | Source doc section |
|---|---|
| Phase 0 | §16 Technical Architecture, §18 Project Structure |
| Phase 1 | §20 Phase 1, §19 Steps 1–3 |
| Phase 2 | §20 Phase 2, §19 Step 4–5 (NER/Classification/Topics) |
| Phase 3 | §20 Phase 3, §19 Step 5 (Actions/Decisions/Questions)–6 |
| Phase 4 | §20 Phase 4, §19 Steps 7–9 |
| Phase 5 | §21 What Makes This an NLP Project |
| Phase 6 | §20 Phase 5 (Future Enhancement) |

**Reminder for AI assistants building this project:** at the start of each phase, re-read this file's "Non-Negotiable Constraints" section before writing any code.
