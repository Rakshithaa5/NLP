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
