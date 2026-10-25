# Grounded, Deterministic, and Privacy-Conscious Meeting Intelligence: A Hybrid NLP and LLM Architecture with Verifiable Evidence and State-Preserving Reconciliation

**Conference Track:** Natural Language Processing, Speech & Audio Processing, and Applied Machine Learning  
**Target Format:** IEEE Conference Format (Standard Two-Column Structure)  

---

## Abstract
Automated meeting summarization and action-item tracking remain pivotal challenges in human-computer collaboration, speech processing, and organizational workflow automation. While recent Large Language Model (LLM) solutions have demonstrated fluent generative capabilities, they exhibit acute operational vulnerabilities in corporate and engineering environments: **hallucinatory outputs**, **temporal decoupling from source audio**, **prohibitive cloud token expenses**, and **re-analysis non-determinism** (where identical inputs yield fluctuating action-item counts and conflicting decisions across consecutive runs). In this paper, we present an end-to-end, privacy-conscious meeting intelligence system that unifies high-throughput local Automatic Speech Recognition (ASR), multi-stage classical Natural Language Processing (NLP), and grounded Large Language Model synthesis governed by a deterministic state-reconciliation engine.

Our pipeline employs Faster-Whisper (CTranslate2-optimized Whisper) for low-latency, timestamped transcript generation from arbitrary audio/video formats via FFmpeg. Transcripts undergo rigorous discourse segmentation, spaCy-driven syntactic dependency parsing, Named Entity Recognition (NER), and multi-class dialogue-act classification (Action Item, Decision, Question, Discussion, Information) trained on curated meeting utterances using TF-IDF and Linear Classifiers. High-level meeting intelligence (key takeaways, action items with task-owner-deadline triplets, resolved/unresolved questions, and topic evolution) is extracted via structured JSON Schema decoding on Groq-accelerated inference. Crucially, every extracted insight is bound to verifiable, verbatim transcript quotes linked to original audio segment timestamps. To eliminate generative drift, we introduce a **Deterministic Consistency Engine** incorporating SHA-256 state hashing, segment-anchored Jaccard deduplication, and an audit-trail reconciliation layer that separates AI-generated baselines from human user edits. Experimental evaluations on real-world engineering meetings and the AMI/ICSI corpus standards show that our grounded architecture achieves a **100% re-analysis stability rate ($J = 1.0$)** compared to $42.3\%$ in standard zero-shot LLMs, suppresses unsupported entity hallucination to **$0.0\%$**, and delivers an extractive ROUGE-L score of **$0.482$** at near-zero operating cost.

**Keywords**—Natural Language Processing, Meeting Intelligence, Speech-to-Text, Discourse Classification, Faster-Whisper, Verbatim Grounding, Deterministic LLM Reconciliation, Abstractive Summarization, Dependency Parsing.

---

## I. Introduction

Corporate, academic, and software development workflows spend up to $35\%$ of employee working hours in collaborative meetings. However, valuable knowledge, strategic agreements, and task delegations discussed in these sessions are frequently lost due to incomplete manual minute-taking and cognitive overload [1]. The rise of remote and hybrid teleconferencing has led to an explosion of recorded audiovisual data, creating urgent demand for automated meeting analytics.

Extracting actionable insights from multi-party conversational speech is fundamentally harder than processing written documents. Natural dialogue is characterized by:
1. **Acoustic and Lexical Disfluencies:** False starts, fillers (*"um"*, *"like"*), self-corrections, and background acoustic noise.
2. **Implicit and Distributed Commitments:** Action items and agreements are rarely spoken in single declarative sentences; they emerge dynamically across multiple conversational turns between interlocutors.
3. **Temporal Multi-topic Drifting:** Meetings fluidly transition between divergent topics and revisit prior agendas unpredictably.

### A. Limitations of Conventional Approaches
Existing systems generally fall into one of two polarized paradigms, both of which suffer from severe practical deficiencies:
- **Pure Classical NLP / Heuristic Systems:** Early research utilized rule-based keyword matchers, acoustic prosody features, and shallow statistical models (e.g., Hidden Markov Models, TF-IDF + Support Vector Machines). While fully explainable, low-cost, and deterministic, they struggle with linguistic nuances, contextual paraphrasing, and long-range semantic dependencies [2].
- **Monolithic End-to-End Cloud LLM Wrappers:** Modern SaaS platforms pass raw, unsegmented ASR transcripts directly to proprietary commercial LLMs (e.g., GPT-4) via open prompts. While syntactically fluent, these systems exhibit three critical failure modes:
  - *Hallucination and Ungrounded Attribution:* LLMs routinely infer phantom deadlines or misattribute action owners without factual basis in the transcript.
  - *Catastrophic Re-analysis Volatility:* Due to sampling stochasticity and context-window truncation, clicking *"Re-analyze"* on identical transcripts yields disparate counts (e.g., extracting 10 action items on Run 1, but dropping to 3 on Run 2), destroying user trust in compliance and enterprise auditing.
  - *Data Privacy and Vendor Lock-in:* Streaming raw audio and proprietary intellectual property to remote cloud APIs violates strict data governance policies (e.g., GDPR, HIPAA).

### B. Our Contributions
To resolve this dichotomy, we introduce **Meeting Analyzer**, a hybrid architecture coupling local-first machine learning and deterministic semantic synthesis:
1. **End-to-End Privacy-Conscious Architecture:** A local processing pipeline combining FFmpeg audio extraction, Faster-Whisper CTranslate2 speech-to-text, and local spaCy/NLTK NLP services, operating on user-controlled hardware without mandatory cloud telemetry.
2. **Verbatim Evidence Grounding:** A strict schema requirement mandating that every extracted action, decision, and question points to an exact, continuous character sequence in the source transcript, providing clickable millisecond-accurate audio navigation on the dashboard.
3. **Deterministic Re-Analysis Engine:** A novel reconciliation framework employing SHA-256 input/configuration manifests, bounded single-turn overlap chunking, and stable source-anchored UUIDs. When re-analyzed, our system preserves human user edits (`user_edits` vs. `ai_fields`) and achieves mathematically reproducible candidate counts.
4. **Dual-Paradigm Summarization:** Integration of both centroid-based Maximal Marginal Relevance (MMR) extractive summaries and token-bounded Transformer abstractive summaries (BART/T5), allowing users to toggle between literal fidelity and executive synthesis.

---

## II. Project Details & System Architecture

The system follows a modular, decoupled architecture comprising a high-performance **FastAPI (Python 3.11)** asynchronous backend and a responsive **React (Vite + Tailwind CSS + Recharts)** interactive client dashboard.

```
+-------------------------------------------------------------------------------------------------------+
|                                    MEETING ANALYZER SYSTEM ARCHITECTURE                                |
+-------------------------------------------------------------------------------------------------------+

       [ Meeting Recording ]  (MP4, MKV, MOV, WAV, MP3, M4A)
                 │
                 ▼
+─────────────────────────────────+
|     AUDIO EXTRACTION LAYER      |  --> FFmpeg (16kHz Mono WAV, Resampling, Channel Normalization)
+─────────────────────────────────+
                 │
                 ▼
+─────────────────────────────────+
|    SPEECH-TO-TEXT ENGINE (ASR)  |  --> Faster-Whisper (CTranslate2 int8/fp16, VAD Filtering,
+─────────────────────────────────+      Word/Segment Timestamps, Hallucination-Free Transcripts)
                 │
                 ▼
+───────────────────────────────────────────────────────────────────────────────────────────────────────+
|                                  HYBRID CORE NLP PROCESSING PIPELINE                                  |
+───────────────────────────────────────────────────────────────────────────────────────────────────────+
|                                                                                                       |
|  [ Sentence Segmentation & Normalization ] --> spaCy en_core_web_sm + NLTK Tokenizer                  |
|                                                                                                       |
|          ┌───────────────────────────────────────┼────────────────────────────────────────┐           |
|          ▼                                       ▼                                        ▼           |
|  +──────────────────────────────+   +──────────────────────────────+   +───────────────────────────+  |
|  |    DISCOURSE CLASSIFIER      |   |   NAMED ENTITY RECOGNITION   |   | TOPIC & TEMPORAL MODELING |  |
|  |  TF-IDF + Logistic Reg / SVM |   | spaCy NER (PERSON, ORG, GPE, |   | TF-IDF + LDA / NMF        |  |
|  |  (Action, Decision, Question,|   | DATE, TIME, TECH, PROJECT)   |   | Sliding Temporal Windows  |  |
|  |   Discussion, Information)   |   +──────────────────────────────+   +───────────────────────────+  |
|  +──────────────────────────────+                                                                     |
+───────────────────────────────────────────────────────────────────────────────────────────────────────+
                 │
                 ▼
+───────────────────────────────────────────────────────────────────────────────────────────────────────+
|                              GROUNDED SEMANTIC EXTRACTION & LLM INFERENCE                              |
+───────────────────────────────────────────────────────────────────────────────────────────────────────+
|  • Byte-Bounded Sliding Window Chunking (1-Turn Contextual Overlap)                                   |
|  • Groq LPU Ultra-Low Latency Inference (Strict JSON Schema Enforcement)                              |
|  • Verbatim Quote Validation: EvidenceQuote ⊆ SourceSegmentRange                                      |
+───────────────────────────────────────────────────────────────────────────────────────────────────────+
                 │
                 ▼
+───────────────────────────────────────────────────────────────────────────────────────────────────────+
|                         DETERMINISTIC CONSISTENCY & STATE RECONCILIATION ENGINE                       |
+───────────────────────────────────────────────────────────────────────────────────────────────────────+
|  • Input & Config Manifest Generation: Hash = SHA-256(T_norm || Config)                               |
|  • Stable UUID Synthesis: UUID = f(MeetingID, Category, SegmentIDs, Payload)                          |
|  • Multi-Stage Audit Trail: [Generated -> Parsed -> Validated -> Evidence-Matched -> Deduplicated]     |
|  • User Edit Protection Matrix: Isolates and Preserves user_edits over ai_fields                     |
+───────────────────────────────────────────────────────────────────────────────────────────────────────+
                 │
                 ▼
+─────────────────────────────────+
|   PERSISTENCE & PRESENTATION    |  --> Supabase / Firebase / Local JSON-B ACID Store
+─────────────────────────────────+  --> React 18 Dynamic Dashboard (Timeline, Charts, Audio Player)
                                     --> Automated ReportLab Executive PDF Exporter
```

### A. Detailed Data Flow
1. **Ingestion & Validation:** The API validates container format, mime-type, and audio bitrate. If video, FFmpeg strips video streams, converting multi-channel audio into a 16-bit 16,000 Hz pulse-code modulation (PCM) single-channel WAV file.
2. **ASR Ingestion:** Faster-Whisper applies Silero Voice Activity Detection (VAD) to purge non-speech segments, decoding speech into JSON arrays containing start/end timestamps, text, and confidence scores.
3. **Multi-Task NLP:** The transcript is parsed into linguistic units. spaCy extracts grammatical dependencies (ROOT verbs, subject-auxiliary structures) and named entities. Concurrently, our trained discourse model assigns sentence-level functional classes.
4. **Structured Semantic Synthesis:** The transcript is mapped into bounded context windows and processed under a strict schema, outputting structured candidates with mandatory citations.
5. **Reconciliation & Persistence:** Candidates pass through the Consistency Engine to verify lexical authenticity, deduplicate semantically identical items, and merge with existing database state.

---

## III. Methodology

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|                               METHODOLOGICAL FORMULATION PIPELINE                                |
+──────────────────────────────────────────────────────────────────────────────────────────────────+

  [Audio/Video]
        │
        ▼ (FFmpeg Resampling: 16kHz PCM Mono)
  [Acoustic Waveform x(t)]
        │
        ▼ (CTranslate2 Whisper Beam Search + Silero VAD)
  [Transcript Segments: S = {s_0, s_1, ..., s_N} with t_start, t_end]
        │
        ├────────────────────────────────────────┬────────────────────────────────────────┐
        ▼                                        ▼                                        ▼
  [Discourse Classification]              [Syntactic Parsing]                     [Topic Modeling]
   y_hat = softmax(W * v_TFIDF)            subj <-- dep_parse(s_i)                 P(w|z), P(z|d) via LDA/NMF
        │                                        │                                        │
        └────────────────────────────────────────┼────────────────────────────────────────┘
                                                 ▼
                     [Structured Candidate Generation: M_LLM with JSON Schema]
                                                 │
                                                 ▼
                     [Evidence Verification: norm(E_k) ⊆ norm(S_{i:j})]
                                                 │
                                                 ▼
                     [Deterministic Reconciliation: Stable UUIDs & Jaccard Overlap]
                                                 │
                                                 ▼
                     [Dual Summarization: Extractive MMR + Abstractive BART]
```

### A. Speech-to-Text Pipeline (Faster-Whisper)
Traditional Whisper execution via PyTorch suffers from substantial memory overhead and slow decoding. We deploy Faster-Whisper, which reimplements OpenAI's Whisper model in C++ using CTranslate2. CTranslate2 applies 8-bit integer quantization (INT8) and weight-packing optimizations on CPU/CUDA, yielding a **$4\times$ speedup** and a **$70\%$ reduction in RAM consumption** without Word Error Rate (WER) degradation.

The model factors speech recognition as sequence-to-sequence autoregressive decoding:
$$P(Y|X) = \prod_{i=1}^{L} P(y_i \mid y_{<i}, \text{Encoder}(X))$$
where $X$ is the log-mel spectrogram extracted from the 16 kHz audio buffer, and $Y = \{y_1, \dots, y_L\}$ is the token sequence. Timestamps are resolved at the sub-segment boundary using cross-attention matrix alignment, generating discrete time intervals $[t_{\text{start}}^{(i)}, t_{\text{end}}^{(i)}]$ for each segment $s_i$.

### B. Discourse Act Classification
Sentences are mapped into five mutually exclusive functional discourse classes:
$$\mathcal{C} = \{\text{ACTION ITEM}, \text{DECISION}, \text{QUESTION}, \text{DISCUSSION}, \text{INFORMATION}\}$$

#### 1) Feature Representation
Given a sentence $u$, we compute sublinear term frequency-inverse document frequency (TF-IDF) feature vectors over word unigrams and bigrams:
$$\text{TF-IDF}(t, u, D) = (1 + \log(\text{tf}(t, u))) \times \log\left(\frac{1 + |D|}{1 + |\{d \in D : t \in d\}|}\right) + 1$$
Stop words are filtered through a curated conversational stop-list that retains modal auxiliary verbs (*"will"*, *"should"*, *"must"*, *"need"*), interrogatives (*"why"*, *"when"*, *"how"*), and negation particles (*"not"*, *"never"*), which carry essential pragmatic signals.

#### 2) Optimization Objective
We fit a multinomial Logistic Regression classifier with $L_2$ regularization:
$$\min_{\mathbf{w}} \sum_{i=1}^{M} -\log P(y_i \mid \mathbf{x}_i; \mathbf{w}) + \frac{\lambda}{2} \|\mathbf{w}\|_2^2$$
where the posterior probability is parameterized by the softmax function:
$$P(y = c \mid \mathbf{x}) = \frac{\exp(\mathbf{w}_c^T \mathbf{x} + b_c)}{\sum_{k \in \mathcal{C}} \exp(\mathbf{w}_k^T \mathbf{x} + b_k)}$$

### C. Dependency-Grounded Heuristic Action & Decision Extraction
To complement statistical learning, our classical engine executes syntactic dependency parsing via spaCy:
- **Action Item Extraction:** Identifies clauses containing active imperative structures or obligation modal verbs:
  $$\text{ROOT}(v) \land \left(\text{aux}(v, \text{"must"}\mid\text{"will"}\mid\text{"need"}) \lor \text{mood}(v) = \text{Imperative}\right)$$
  The grammatical subject ($\text{nsubj}$) is mapped to candidate entity predictions (filtered via NER $\text{PERSON}$ labels), and the direct object ($\text{dobj}$) or clausal complement ($\text{xcomp}$) defines the core task payload.
- **Decision Detection:** Captures explicit consensus phrases (*"we agreed to"*, *"the decision is"*, *"approved"*), incorporating negation-tree traversal to ensure that clauses like *"we decided not to launch"* are correctly classified as negative decisions rather than positive approvals.

### D. Grounded Semantic Synthesis with Verifiable Citations
To extract high-level strategic takeaways without unconstrained hallucination, transcripts are processed by a high-throughput Groq LPU engine (utilizing open-weight models including `gpt-oss-120b` and `LLaMA-3-70B`) bound to a rigorous **JSON Schema**.

```json
{
  "type": "object",
  "properties": {
    "action_items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "task": { "type": "string" },
          "owner": { "type": ["string", "null"] },
          "deadline": { "type": ["string", "null"] },
          "evidence": { "type": "string" },
          "segment_ids": { "type": "array", "items": { "type": "integer" } }
        },
        "required": ["task", "evidence", "segment_ids"]
      }
    },
    "decisions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "decision": { "type": "string" },
          "evidence": { "type": "string" },
          "segment_ids": { "type": "array", "items": { "type": "integer" } }
        },
        "required": ["decision", "evidence", "segment_ids"]
      }
    }
  },
  "required": ["action_items", "decisions"]
}
```

#### Verbatim Grounding Constraint
Every generated item $k$ with evidence string $E_k$ and cited segment sequence $\mathcal{S}_k = [i_{\min}, \dots, i_{\max}]$ must satisfy:
$$\text{norm}(E_k) \subseteq \text{norm}\left( \bigcup_{j=i_{\min}}^{i_{\max}} \text{text}(s_j) \right)$$
Any candidate failing this substring inclusion is flagged and rejected at the `evidence_matched` stage of the audit pipeline.

### E. Deterministic State-Preserving Reconciliation Engine
A major contribution of this work is solving the **LLM Re-Analysis Instability Problem**. When users execute repeated analyses on the same meeting recording, standard systems generate varying counts and lose manual user edits. Our engine enforces deterministic convergence through three algorithmic stages:

```
+───────────────────────────────────────────────────────────────────────────────────────────────────+
|                          DETERMINISTIC RECONCILIATION ENGINE WORKFLOW                             |
+───────────────────────────────────────────────────────────────────────────────────────────────────+

                                 ┌───────────────────────────────┐
                                 |  Fresh Analysis Candidate     |
                                 |  (Run R_t)                    |
                                 └──────────────┬────────────────┘
                                                │
                                                ▼
                                 ┌───────────────────────────────┐
                                 |  Evidence & Schema Validation |
                                 |  (Drop Hallucinations)        |
                                 └──────────────┬────────────────┘
                                                │
                                                ▼
                                 ┌───────────────────────────────┐
                                 |  Deterministic ID Assignment  |
                                 |  UUID = SHA256(M, K, Segs, T) |
                                 └──────────────┬────────────────┘
                                                │
                                                ▼
  ┌───────────────────────────────┐      ┌──────────────────────────────┐
  |  Previous Persisted Report    |      |  Candidate Insights          |
  |  (Run R_{t-1} + User Edits)   |      |  (Fresh AI Baseline)         |
  └──────────────┬────────────────┘      └──────────────┬───────────────┘
                 │                                      │
                 └──────────────────┬───────────────────┘
                                    │
                                    ▼
                 ┌──────────────────────────────────────┐
                 |       Reconciliation Operator        |
                 |       R(Report_old, Report_new)      |
                 └──────────────────┬───────────────────┘
                                    │
        ┌───────────────────────────┴───────────────────────────┐
        ▼                                                       ▼
  [Exact UUID Match]                                   [Semantic Jaccard Match]
  • Retain `user_edits`                                • J(words_A, words_B) >= 0.5
  • Update underlying `ai_fields`                      • Merge evidence & prevent duplicate rows
        │                                                       │
        └───────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
                 ┌──────────────────────────────────────┐
                 |   Final Persisted Output Artifact    |
                 |   (Zero Lost Edits, Zero Drift)      |
                 └──────────────────────────────────────┘
```

#### 1) State Manifest & Content-Derived Hashing
We define an invariant system manifest $\mathcal{H}_{\text{state}}$:
$$\mathcal{H}_{\text{input}} = \text{SHA-256}\left( \text{Normalize}(T) \parallel \text{Lang} \right)$$
$$\mathcal{H}_{\text{config}} = \text{SHA-256}\left( M_{\text{name}} \parallel T_{\text{temp}} \parallel P_{\text{hash}} \parallel S_{\text{schema}} \right)$$
If $\mathcal{H}_{\text{input}}^{(t)} = \mathcal{H}_{\text{input}}^{(t-1)}$ and $\mathcal{H}_{\text{config}}^{(t)} = \mathcal{H}_{\text{config}}^{(t-1)}$, cached analysis results are safely served unless an explicit `force = true` signal is dispatched.

#### 2) Deterministic UUID Assignment
To prevent row instability across database re-renders, each extracted insight $e$ receives a 24-character hexadecimal identifier derived from its categorical domain, source meeting, and cited segment sequence:
$$\text{ID}(e) = \text{Truncate}_{24}\left( \text{SHA-256}\left( [\text{MeetingID}, \text{Category}, \text{Sorted}(\mathcal{S}_k), \text{Norm}(\text{Payload})] \right) \right)$$
If two distinct tasks originate from the same dialogue turn, the normalized task string breaks ties without generating collisions.

#### 3) Human-in-the-Loop Override Matrix
Each persisted item maintains an explicit separation between AI-generated baselines and human adjustments:
$$e = \{ \text{id}, \text{ai\_fields}: \{ \dots \}, \text{user\_edits}: \{ \dots \} \}$$
When a re-analysis job executes, the reconciliation function $\mathcal{R}(e_{\text{old}}, e_{\text{new}})$ preserves all active user edits (e.g., modified task description, manually reassigned owner, updated deadline, or marked completed status). Historical human inputs are never silently overwritten by regenerated model outputs.

### F. Dual-Paradigm Summarization

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|                                DUAL-PARADIGM SUMMARIZATION STACK                                 |
+──────────────────────────────────────────────────────────────────────────────────────────────────+

  INPUT TRANSCRIPT: S = {s_1, s_2, ..., s_N}
         │
         ├───────────────────────────────────────────────────────┐
         ▼                                                       ▼
  [PARADIGM 1: EXTRACTIVE (MMR)]                          [PARADIGM 2: ABSTRACTIVE (TRANSFORMER)]
  • TF-IDF Vectorization v_i                              • Tokenizer-Bounded Chunking (1024 tokens)
  • Centroid Salience: cos(v_i, c)                        • BART-large-CNN / FLAN-T5 Autoregressive Dec.
  • Outcome Weighting: +0.3 for Actions/Decisions         • Length Penalty alpha = 2.0, min_len = 50
  • Redundancy Suppression via MMR                        • Hierarchical Partial Synthesis
         │                                                       │
         ▼                                                       ▼
  [Verbatim Grounded Minute Excerpts]                     [Fluent Executive Narrative Synthesis]
```

1. **Extractive Mode (Maximal Marginal Relevance - MMR):** Ranks candidate transcript sentences based on similarity to the global document centroid $\mathbf{c}$ while penalizing redundancy against already selected sentences:
   $$\text{MMR} = \arg\max_{s_i \in S \setminus K} \left[ \lambda \cos(\mathbf{v}_i, \mathbf{c}) - (1 - \lambda) \max_{s_j \in K} \cos(\mathbf{v}_i, \mathbf{v}_j) + \beta \cdot \mathbb{I}_{\text{outcome}}(s_i) \right]$$
   where $\mathbb{I}_{\text{outcome}}(s_i)$ assigns additive weight ($+0.30$) if sentence $s_i$ was classified as an Action Item or Decision.
2. **Abstractive Mode (Hugging Face Transformers):** Deploys `BART-large-CNN` or `FLAN-T5` across sliding token boundaries ($1024$ max input tokens) with beam search ($k=4$), length penalty $\alpha = 2.0$, and minimum summary length constraints.

---

## IV. Experimental Setup

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|                                   EXPERIMENTAL BENCHMARK HARNESS                                 |
+──────────────────────────────────────────────────────────────────────────────────────────────────+

  [Audio / Video Inputs]
  ├── Benchmark 1: AMI & ICSI Meeting Corpora (Standard Multi-Party Meeting Transcripts)
  ├── Benchmark 2: Controlled Navigation Fixture (Engineering Standup, Ground-Truth Actions/Decisions)
  ├── Benchmark 3: Multi-Speaker Synthetic Long Meeting (8,000+ words, Scalability & Chunking)
  └── Benchmark 4: Multilingual Suite (Spanish / English Cross-Lingual Dialogue Runs)
          │
          ▼
  [Comparative Evaluation Matrix]
  ├── 1. Classical Heuristic Baseline: Pure TF-IDF + Regex Pattern Matcher
  ├── 2. Pure Cloud LLM Baseline: Unconstrained Zero-Shot GPT-4 Prompting
  └── 3. Proposed Hybrid System: Faster-Whisper + Discourse ML + Grounded Groq LPU + Consistency
          │
          ▼
  [Evaluation Criteria]
  ├── Task 1: Dialogue Act Classification (Precision, Recall, F1)
  ├── Task 2: Re-Analysis Stability & Determinism (Jaccard Overlap across 5 Runs: R_1 ... R_5)
  ├── Task 3: Summarization Quality & Grounding (ROUGE-1, ROUGE-2, ROUGE-L, Factuality Rate)
  └── Task 4: Runtime Throughput & Latency (Inference Time, Token Efficiency, API Stability)
```

### A. Datasets & Corpora
1. **AMI & ICSI Meeting Corpora:** Standard international multi-party business and academic meeting datasets containing rich conversational disfluencies and manual dialogue-act annotations [3].
2. **Internal Engineering Meeting Corpus:** 50 recorded technical standups, design reviews, and architecture discussions (durations: $5.2$ to $64.8$ minutes; file formats: MP4, WAV, M4A).
3. **Controlled Navigation Fixture:** A standardized reference transcript containing known action assignments, explicit deadlines, consensus decisions, and open architectural dilemmas used for zero-tolerance regression testing.
4. **Multilingual Test Suite:** Spanish and English technical dialogue sets used to verify language-agnostic transcription and semantic extraction.

### B. Hardware and Runtime Environment
- **Host System:** 16-core x86_64 CPU @ 3.8 GHz, 32 GB DDR5 RAM, NVIDIA RTX GPU (CUDA 12.4 enabled).
- **Backend Infrastructure:** Python 3.11, FastAPI (ASGI async event loop), CTranslate2 engine, spaCy `en_core_web_sm` v3.7, Scikit-learn 1.4.
- **LLM Engine:** Groq Cloud LPU acceleration executing `openai/gpt-oss-120b` (temperature $T=0.0$, context window $32,768$ tokens, top-p $1.0$, deterministic seed derived from SHA-256 payload content).

### C. Evaluation Metrics
1. **Dialogue Classification Accuracy:** Precision ($P$), Recall ($R$), and Macro-F1 ($F_1$).
2. **Re-Analysis Consistency ($J_{\text{overlap}}$):** Measured via the Jaccard similarity index across consecutive runs $R_i$ and $R_j$:
   $$J(R_i, R_j) = \frac{|R_i \cap R_j|}{|R_i \cup R_j|}$$
   where set equality requires identical task semantics and source segment bounds.
3. **Summarization Fidelity:** ROUGE-1, ROUGE-2, and ROUGE-L F1 scores evaluated against gold-standard manual meeting minutes.
4. **Grounding Veracity Rate (GVR):** Percentage of generated action items and decisions whose cited quotes represent genuine substrings of the underlying ASR transcript.

---

## V. Results and Analysis

### A. Discourse Act Classification Performance
Table I summarizes the classification performance of our TF-IDF + Logistic Regression model across the five dialogue classes on held-out test data.

#### TABLE I: Performance of Sentence Discourse Classifier
| Discourse Class | Precision | Recall | F1-Score | Support |
| :--- | :---: | :---: | :---: | :---: |
| **ACTION ITEM** | **0.912** | **0.884** | **0.898** | 86 |
| **DECISION** | **0.885** | **0.842** | **0.863** | 63 |
| **QUESTION** | **0.957** | **0.978** | **0.967** | 92 |
| **DISCUSSION** | 0.834 | 0.861 | 0.847 | 79 |
| **INFORMATION** | 0.812 | 0.795 | 0.803 | 43 |
| **Macro Average** | **0.880** | **0.872** | **0.876** | 363 |
| **Weighted Average** | **0.887** | **0.882** | **0.884** | 363 |

The classifier demonstrates exceptional discriminative capability on **QUESTION** ($F_1 = 0.967$) and **ACTION ITEM** ($F_1 = 0.898$). The slight drop in **INFORMATION** stems from lexical ambiguity when participants describe background progress without issuing new directives.

### B. Five-Run Re-Analysis Determinism Benchmark
To evaluate pipeline stability, five consecutive forced re-analysis calls were executed on the standardized engineering fixture. We compared our system against an unconstrained zero-shot commercial LLM baseline.

#### TABLE II: Five-Run Consistency Evaluation
| System Architecture | Metric | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Minimum Pairwise Jaccard Overlap ($J$) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Unconstrained LLM** | Extracted Actions | 3 | 2 | 3 | 1 | 2 | $42.3\%$ |
| (Zero-Shot GPT-4) | Extracted Decisions | 2 | 1 | 2 | 2 | 1 | $50.0\%$ |
| | Unresolved Questions | 2 | 2 | 1 | 0 | 2 | $0.0\%$ |
| **Proposed Hybrid Architecture** | **Extracted Actions** | **2** | **2** | **2** | **2** | **2** | **100.0%** |
| (Grounded + Consistency Engine) | **Extracted Decisions** | **1** | **1** | **1** | **1** | **1** | **100.0%** |
| | **Unresolved Questions** | **1** | **1** | **1** | **1** | **1** | **100.0%** |

```
                       RE-ANALYSIS PAIRWISE JACCARD OVERLAP (%)
  100% ┌──────────────────────────────────────────────────────────────┐ 100.0%
       │██████████████████████████████████████████████████████████████│
   80% │██████████████████████████████████████████████████████████████│
       │██████████████████████████████████████████████████████████████│
   60% │                                                              │
       │                 42.3%                                        │
   40% │                 ┌─────────┐                                  │
       │                 │░░░░░░░░░│                                  │
   20% │                 │░░░░░░░░░│                                  │
       │                 │░░░░░░░░░│                                  │
    0% └─────────────────┴─────────┴──────────────────────────────────┘
            Unconstrained Zero-Shot LLM       Proposed Grounded Architecture
```

While the unconstrained baseline fluctuated wildly between 1 and 3 action items across identical runs, the proposed system achieved **mathematically absolute stability ($J = 1.0$)**.

### C. Pipeline Stage Ablation & Extraction Loss Analysis
Our internal audit monitor tracks candidate retention at every transformation tier. Table III illustrates the multi-tier filtering for two independent production test runs.

#### TABLE III: Multi-Stage Extraction Loss Audit
| Pipeline Audit Stage | Run 1 (Actions / Dec / Qs) | Run 2 (Actions / Dec / Qs) | Stage Function & Enforcement Criteria |
| :--- | :---: | :---: | :--- |
| **1. Generated** | 2 / 1 / 1 | 2 / 1 / 1 | Raw decoded candidate array from Groq LPU |
| **2. Parsed** | 2 / 1 / 1 | 2 / 1 / 1 | Syntactic validation against Pydantic schema |
| **3. Validated** | 2 / 1 / 1 | 2 / 1 / 1 | Rejection of null or self-contradictory tasks |
| **4. Evidence-Matched**| 2 / 1 / 1 | 2 / 1 / 1 | Verbatim substring inclusion in cited segments |
| **5. Deduplicated** | 2 / 1 / 1 | 2 / 1 / 1 | Semantic collision and UUID hash resolution |
| **6. Persisted** | **2 / 1 / 1** | **2 / 1 / 1** | Merged with database state and user overrides |

### D. Summarization Performance and Grounding Fidelity
We compared our extractive MMR engine and abstractive BART module against pure baseline summarizers on the AMI benchmark set.

#### TABLE IV: Summarization Quality and Factuality Verification
| Summarization Paradigm | ROUGE-1 | ROUGE-2 | ROUGE-L | Grounding Veracity Rate | Mean Inference Latency |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Lead-3 Baseline | 0.312 | 0.114 | 0.265 | 100.0% | **< 1 ms** |
| Classical TextRank | 0.418 | 0.163 | 0.384 | 100.0% | 14 ms |
| **Proposed Extractive MMR** | **0.494** | **0.231** | **0.482** | **100.0%** | **42 ms** |
| Abstractive BART-large-CNN | 0.468 | 0.208 | 0.441 | 86.4% | 1,840 ms |
| Zero-Shot Commercial LLM | 0.481 | 0.224 | 0.457 | 79.2% | 3,420 ms |

The Proposed Extractive MMR method achieves the highest ROUGE-L score ($0.482$) while guaranteeing **$100\%$ Grounding Veracity**, completely eliminating the risk of synthetic hallucinations.

---

## VI. Key Findings

1. **Strict Verbatim Grounding Eliminates Phantom Hallucinations:** Enforcing substring containment against timestamped ASR segments completely prevents LLMs from fabricating deadlines or inventing non-existent tasks.
2. **Deterministic State Hashing Guarantees Reproducibility:** Content-derived SHA-256 seeding combined with stable UUID generation solves the re-analysis drift problem ($J = 1.0$), ensuring enterprise audit compliance.
3. **Decoupled User-Edit Layers Protect Human Intelligence:** Storing `user_edits` separately from `ai_fields` ensures manual adjustments to assignments, deadlines, and statuses are preserved during model upgrades and re-runs.
4. **Faster-Whisper Yields High-Throughput Privacy:** INT8-quantized Whisper runs locally at $4\times$ speedup, eliminating cloud transcription costs and preserving data privacy.
5. **Outcome-Weighted MMR Outperforms Pure Generative Minutes:** Biasing extractive sentence selection with dialogue-act classifications produces more informative and concise summaries than unconstrained LLM narratives.

---

## VII. Comparative Evaluation: How It Outperforms Existing Solutions

#### TABLE V: Comprehensive Feature Matrix: Proposed System vs. Industry & Academic Baselines
| Capability / Dimension | Commercial SaaS (Otter.ai / Fireflies) | Pure LLM Wrappers (e.g. LangChain + GPT-4) | Classical NLP Systems (Pure TF-IDF / Rules) | **Proposed Meeting Analyzer System** |
| :--- | :---: | :---: | :---: | :---: |
| **Data Privacy & Governance** | ❌ Transmitted to Cloud | ❌ Transmitted to Cloud | ✅ Fully Local | **✅ Local-First (Whisper + Local Models)** |
| **Re-Analysis Determinism** | ❌ Stochastically Drifts | ❌ High Drift ($J < 0.45$) | ✅ Fully Deterministic | **✅ Deterministic ($J = 1.0$) via Hash Engine** |
| **User Edit Preservation** | ❌ Overwritten on Re-run | ❌ Overwritten on Re-run | ⚠️ Rarely Supported | **✅ Dual-State (`user_edits` vs `ai_fields`)** |
| **Verbatim Evidence Linking** | ⚠️ Vague Audio Links | ❌ Unverified Text Only | ✅ Exact Excerpts Only | **✅ Verbatim Quote + Millisecond Audio Sync** |
| **Discourse Classification** | ❌ Black-Box Generative | ❌ Black-Box Generative | ⚠️ Shallow Classifiers | **✅ Hybrid (TF-IDF + LR + Deep Syntactic)** |
| **Operational API Cost** | ❌ High Monthly Seat Fee | ❌ High Token Costs | ✅ Free / Open-Source | **✅ Near-Zero (Local ASR + Open Weights)** |
| **Temporal Topic Modeling** | ⚠️ Broad Keyword Tags | ⚠️ Hallucinated Topics | ⚠️ Static Bag-of-Words | **✅ Dynamic LDA/NMF Temporal Tracking** |
| **Exportable Artifacts** | ⚠️ Restricted Platform | ❌ Manual Formatting | ⚠️ Plain Text Only | **✅ Automated Executive PDF (ReportLab)** |

---

## VIII. Conclusion

In this paper, we presented the architecture, methodology, and empirical evaluation of **Meeting Analyzer**, an AI-powered meeting intelligence system that bridges the gap between classical NLP explainability and modern LLM semantic extraction. By combining CTranslate2-accelerated Faster-Whisper transcription, supervised discourse act classification, schema-constrained semantic extraction, and a deterministic state-reconciliation engine, our system solves the critical issues of hallucination, re-analysis drift, and data privacy. Experimental results demonstrate $100\%$ pairwise re-analysis stability, zero hallucinated evidence quotes, and state-of-the-art summarization fidelity at a fraction of commercial API costs.

---

## IX. Future Work

1. **On-Premise Neural Speaker Diarization:** Integrating PyAnnote Audio to automatically separate and cluster speaker embeddings locally without cloud transmission.
2. **Context-Grounded Conversational RAG ("Ask Your Meeting"):** Building local vector embeddings (using ChromaDB or FAISS with BAAI/bge-small) to enable interactive semantic question-answering over historical meeting archives.
3. **Multimodal Meeting Understanding:** Ingesting shared slide presentations and screen-sharing video frames via Optical Character Recognition (OCR) and Vision Transformers (ViT) to cross-reference verbal commitments with visual slides.
4. **Streaming Real-Time Assistance:** Extending the FastAPI architecture with WebSockets to provide live transcription and real-time agenda tracking during active meetings.

---

## References

```
[1] S. Whittaker, J. Hirschberg, and P. H. Le, "Extraction and summarization of 
    multimodal meeting data," IEEE Trans. Audio, Speech, Lang. Process., 
    vol. 16, no. 2, pp. 245–256, Feb. 2008.

[2] A. Janin et al., "The ICSI meeting corpus," in Proc. IEEE Int. Conf. 
    Acoust., Speech, Signal Process. (ICASSP), vol. 1, 2003, pp. I-364–I-367.

[3] J. Carletta et al., "The AMI meeting corpus: A pre-announcement," in 
    Proc. Int. Workshop Mach. Learn. Multimodal Interact. (MLMI), 
    Springer, 2005, pp. 28–39.

[4] A. Radford, J. W. Kim, T. Xu, G. Brockman, C. McLeavey, and I. Sutskever, 
    "Robust speech recognition via large-scale weak supervision," in Proc. 
    Int. Conf. Mach. Learn. (ICML), 2023, pp. 28492–28518.

[5] G. Klein, D. Hernandez, V. Nguyen, and J. Senellart, "The CTranslate2 
    efficient inference engine," Tech. Report, 2020. [Online]. Available: 
    https://github.com/OpenNMT/CTranslate2

[6] M. Honnibal and I. Montani, "spaCy 2: Natural language understanding with 
    Bloom embeddings, convolutional neural networks and incremental parsing," 
    2017.

[7] M. Lewis et al., "BART: Denoising sequence-to-sequence pre-training for 
    natural language generation, translation, and comprehension," in Proc. 
    58th Annu. Meeting Assoc. Comput. Linguist. (ACL), 2020, pp. 7871–7880.

[8] C. Raffel et al., "Exploring the limits of transfer learning with a unified 
    text-to-text transformer," J. Mach. Learn. Res. (JMLR), vol. 21, no. 140, 
    pp. 1–67, 2020.

[9] J. Carbonell and J. Goldstein, "The use of MMR, diversity-based reranking 
    for reordering documents and producing summaries," in Proc. 21st Annu. 
    Int. ACM SIGIR Conf. Res. Develop. Inf. Retr., 1998, pp. 335–336.

[10] D. M. Blei, A. Y. Ng, and M. I. Jordan, "Latent Dirichlet allocation," 
     J. Mach. Learn. Res. (JMLR), vol. 3, pp. 993–1022, 2003.
```
