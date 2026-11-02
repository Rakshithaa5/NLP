"""Generate a detailed, implementation-grounded NLP pipeline PDF."""

from __future__ import annotations

import html
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "Detailed_NLP_Pipeline.pdf"

NAVY = colors.HexColor("#15324B")
BLUE = colors.HexColor("#2563EB")
TEAL = colors.HexColor("#0F766E")
SLATE = colors.HexColor("#475569")
LIGHT = colors.HexColor("#F1F5F9")
PALE_BLUE = colors.HexColor("#EFF6FF")
GRID = colors.HexColor("#CBD5E1")


def esc(value: str) -> str:
    return html.escape(value, quote=False)


def p(text: str, style: ParagraphStyle) -> Paragraph:
    value = esc(text).replace("\n", "<br/>")
    value = value.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    value = value.replace("&lt;br/&gt;", "<br/>")
    return Paragraph(value, style)


def rich(text: str, style: ParagraphStyle) -> Paragraph:
    """Render a deliberately small, safe markup subset used by this report."""
    value = esc(text)
    value = value.replace("**", "<b>", 1) if "**" in value else value
    if "<b>" in value:
        value = value.replace("**", "</b>", 1)
    value = value.replace("`", "<font name='Courier'>", 1) if "`" in value else value
    if "<font name='Courier'>" in value:
        value = value.replace("`", "</font>", 1)
    return Paragraph(value, style)


def table(rows, widths, style, repeat_rows=1):
    result = Table(rows, colWidths=widths, repeatRows=repeat_rows)
    result.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, GRID),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return result


def footer(canvas, doc):
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(GRID)
    canvas.line(16 * mm, 12 * mm, width - 16 * mm, 12 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(SLATE)
    canvas.drawString(16 * mm, 7 * mm, "Meeting Analyzer | Detailed NLP Pipeline")
    canvas.drawRightString(width - 16 * mm, 7 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf() -> None:
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle", parent=styles["Title"], alignment=TA_CENTER,
            fontName="Helvetica-Bold", fontSize=24, leading=29,
            textColor=NAVY, spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSubtitle", parent=styles["Normal"], alignment=TA_CENTER,
            fontSize=13, leading=17, textColor=BLUE, spaceAfter=15,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverMeta", parent=styles["Normal"], alignment=TA_CENTER,
            fontSize=9, leading=13, textColor=SLATE,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Lead", parent=styles["BodyText"], alignment=TA_JUSTIFY,
            fontSize=10.5, leading=15, textColor=NAVY, spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body", parent=styles["BodyText"], alignment=TA_JUSTIFY,
            fontSize=9.2, leading=13.2, spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold",
            fontSize=14, leading=18, textColor=NAVY, spaceBefore=12, spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Subsection", parent=styles["Heading3"], fontName="Helvetica-Bold",
            fontSize=10.5, leading=14, textColor=TEAL, spaceBefore=8, spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Table", parent=styles["BodyText"], fontSize=8, leading=10.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Small", parent=styles["BodyText"], fontSize=8.2, leading=11,
            textColor=SLATE,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PipelineCode", parent=styles["Code"], fontName="Courier", fontSize=7.6,
            leading=10, backColor=LIGHT, borderColor=GRID, borderWidth=0.5,
            borderPadding=7, spaceBefore=4, spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Callout", parent=styles["BodyText"], fontSize=8.7, leading=12,
            backColor=PALE_BLUE, borderColor=colors.HexColor("#93C5FD"),
            borderWidth=0.5, borderPadding=7, spaceBefore=4, spaceAfter=8,
        )
    )

    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="Detailed NLP Pipeline - Meeting Analyzer",
        author="Meeting Analyzer",
    )
    story = [
        Spacer(1, 28 * mm),
        p("Meeting Analyzer", styles["CoverTitle"]),
        p("Detailed NLP Pipeline", styles["CoverSubtitle"]),
        p(
            "An implementation-grounded guide to the audio, speech, NLP, semantic "
            "extraction, evidence validation, persistence, and reporting workflow.",
            styles["CoverMeta"],
        ),
        Spacer(1, 18 * mm),
        p("Repository: NLP | Generated from the current backend services", styles["CoverMeta"]),
        p("Pipeline order is preserved from upload to dashboard/PDF export.", styles["CoverMeta"]),
        PageBreak(),
        p("1. Executive overview", styles["Section"]),
        p(
            "Meeting Analyzer converts an existing audio or video recording into a "
            "timestamped transcript and a structured meeting report. The design is "
            "hybrid: deterministic local components handle media normalization, "
            "speech recognition, linguistic preprocessing, classification, topic "
            "signals, and extractive summarization; structured semantic extraction "
            "adds cross-turn interpretation while strict validation prevents "
            "unsupported insights from reaching the dashboard.",
            styles["Lead"],
        ),
        p(
            "The pipeline is not a live transcription system. It processes an uploaded "
            "recording, retains the original transcript evidence, and exposes the "
            "result through the FastAPI backend for the React dashboard and PDF report.",
            styles["Callout"],
        ),
        p("Canonical processing order", styles["Subsection"]),
    ]

    flow = [
        [p("<b>1. Upload</b><br/>recording", styles["Table"]),
         p("<b>2. Validate</b><br/>type and storage", styles["Table"]),
         p("<b>3. Audio</b><br/>FFmpeg", styles["Table"]),
         p("<b>4. ASR</b><br/>Faster-Whisper", styles["Table"]),
         p("<b>5. NLP</b><br/>spaCy + NLTK", styles["Table"])],
        [p("<b>6. Signals</b><br/>NER | classifier | topics", styles["Table"]),
         p("<b>7. Intelligence</b><br/>actions | decisions | questions", styles["Table"]),
         p("<b>8. Summary</b><br/>extractive / optional draft", styles["Table"]),
         p("<b>9. Persist</b><br/>local + Supabase", styles["Table"]),
         p("<b>10. Present</b><br/>dashboard / PDF", styles["Table"])],
    ]
    flow_table = Table(flow, colWidths=[35 * mm] * 5)
    flow_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.extend([flow_table, Spacer(1, 8), p("2. Pipeline stage reference", styles["Section"])])

    stage_rows = [[
        p("<b>Stage</b>", styles["Table"]), p("<b>Implementation</b>", styles["Table"]),
        p("<b>Input</b>", styles["Table"]), p("<b>Output / guarantee</b>", styles["Table"]),
    ]]
    stages = [
        ("Upload and validation", "routes/upload.py; meeting_store.py", "Audio/video file", "Stored meeting ID; supported media and bounded file checks."),
        ("Audio normalization", "services/audio.py", "Original media", "Mono, 16 kHz PCM WAV produced by FFmpeg."),
        ("Transcription", "services/transcription.py", "Normalized WAV", "Segments with start/end seconds, text, language, duration."),
        ("Preprocessing", "services/preprocessing.py", "Full transcript", "spaCy Doc, sentences, tokens, filtered tokens, lemmas."),
        ("NER", "services/ner.py + EntityRuler", "spaCy Doc", "Named people, organizations, dates, locations, products/technologies."),
        ("Classification", "services/classification.py", "Sentences", "Five dialogue-act labels plus model confidence."),
        ("Topics", "services/topics.py", "Sentences / Doc", "TF-IDF keywords, LDA or NMF clusters, noun-phrase topics."),
        ("Semantic extraction", "services/semantic.py", "Transcript units", "Structured summary, actions, decisions, questions, topics and entities."),
        ("Validation/reconciliation", "services/intelligence.py; consistency.py", "Candidate report + evidence", "Only grounded items persist; stable IDs and edits survive re-analysis."),
        ("Summarization", "services/summarization.py", "Transcript", "Chronological TF-IDF/MMR excerpts; optional BART/T5 draft."),
    ]
    for row in stages:
        stage_rows.append([p(row[0], styles["Table"]), p(row[1], styles["Table"]),
                           p(row[2], styles["Table"]), p(row[3], styles["Table"])])
    story.append(table(stage_rows, [32 * mm, 42 * mm, 32 * mm, 72 * mm], styles["Table"]))

    story.extend([
        p("3. Media ingestion and audio preparation", styles["Section"]),
        p(
            "The upload route stores the original recording under a meeting-specific "
            "directory. The audio service accepts common audio extensions (MP3, WAV, "
            "FLAC, OGG, M4A) and video containers (MP4, MOV, MKV, AVI, WEBM). Every "
            "input is passed through the same normalization command so downstream "
            "speech recognition sees a consistent signal.",
            styles["Body"],
        ),
        p(
            "FFmpeg drops video, mixes channels to mono, resamples to 16 kHz, and "
            "writes signed 16-bit PCM WAV. Missing FFmpeg, unsupported extensions, "
            "nonexistent paths, and a ten-minute conversion timeout are explicit "
            "errors rather than silent fallbacks.",
            styles["Body"],
        ),
        p(
            "Command contract: ffmpeg -y -i INPUT -vn -ac 1 -ar 16000 "
            "-acodec pcm_s16le OUTPUT.wav",
            styles["PipelineCode"],
        ),
        p("4. Speech-to-text and transcript representation", styles["Section"]),
        p(
            "Faster-Whisper is loaded lazily and cached per worker. The model size, "
            "device, and compute type are configurable through WHISPER_MODEL_SIZE, "
            "WHISPER_DEVICE, and WHISPER_COMPUTE_TYPE; defaults are base, CPU, and "
            "int8. Transcription uses beam size 5 and voice-activity detection with "
            "a 500 ms minimum silence duration.",
            styles["Body"],
        ),
    ])
    transcript_rows = [[p("<b>Field</b>", styles["Table"]), p("<b>Meaning</b>", styles["Table"]),
                        p("<b>Why it matters</b>", styles["Table"])]]
    for row in [
        ("segments[].start / end", "Rounded time boundaries in seconds.", "Enables source navigation and evidence timestamps."),
        ("segments[].text", "Text for one detected speech segment.", "Preserves the smallest source unit used by later validation."),
        ("full_text", "Segments joined by spaces.", "Canonical text for NLP, hashes, and quote matching."),
        ("language", "Detected or requested language code.", "Controls analysis metadata and reproducibility."),
        ("duration", "Total media duration in seconds.", "Displayed as meeting metadata and used in reports."),
    ]:
        transcript_rows.append([p(row[0], styles["Table"]), p(row[1], styles["Table"]), p(row[2], styles["Table"])])
    story.append(table(transcript_rows, [43 * mm, 65 * mm, 70 * mm], styles["Table"]))

    story.extend([
        p("5. Linguistic preprocessing", styles["Section"]),
        p(
            "Preprocessing uses one spaCy document so sentence boundaries, token "
            "attributes, named entities, and dependency information can be reused. "
            "The original text is retained for evidence: normalization is intentionally "
            "light and does not replace the source transcript.",
            styles["Body"],
        ),
        p("Processing sequence", styles["Subsection"]),
        p(
            "1) spaCy loads en_core_web_sm and adds an EntityRuler; 2) spaCy performs "
            "sentence segmentation and tokenization; 3) stop words are the union of "
            "spaCy and NLTK English stop words; 4) punctuation, spaces, and stop words "
            "are excluded from clean tokens; 5) surviving tokens are lower-cased "
            "lemmas for downstream statistical features.",
            styles["Body"],
        ),
        p(
            "The preprocessing response contains sentences, raw tokens, clean_tokens, "
            "lemmas, and the spaCy Doc. A transcript exceeding spaCy's max_length raises "
            "an explicit error and must be split before analysis.",
            styles["Callout"],
        ),
        p("6. Entity extraction", styles["Section"]),
        p(
            "The NER layer combines spaCy's statistical recognizer with deterministic "
            "EntityRuler patterns for technologies and project identifiers. The "
            "implemented report contract groups normalized entities into people, "
            "organizations, dates, locations, and products. Technology and project "
            "patterns cover terms such as Python, React, FastAPI, Whisper, NLP, "
            "phase 2, sprint 3, and version 1.",
            styles["Body"],
        ),
        p(
            "Entities are signals, not evidence by themselves. A report item still "
            "needs a verbatim transcript quote and valid segment mapping before it "
            "is accepted into meeting intelligence.",
            styles["Body"],
        ),
        p("7. Dialogue-act classification", styles["Section"]),
        p(
            "Each sentence is classified as ACTION ITEM, DECISION, QUESTION, "
            "DISCUSSION, or INFORMATION. The baseline is a persisted scikit-learn "
            "Pipeline trained from data/training_sentences.csv. It uses word TF-IDF "
            "features with unigram-to-trigram ranges, up to 20,000 features, "
            "sublinear term frequency, and balanced multinomial Logistic Regression.",
            styles["Body"],
        ),
        p(
            "The returned confidence is the maximum class probability and is useful "
            "for inspection, but it is not a calibrated factuality score. High-level "
            "rule checks then promote explicit decisions, action patterns, and "
            "questions when the sentence contains stronger evidence than the model "
            "label alone. A Hugging Face classifier can replace the internals later "
            "without changing the public result shape.",
            styles["Body"],
        ),
    ])

    classifier_rows = [[p("<b>Label</b>", styles["Table"]), p("<b>Interpretation</b>", styles["Table"]),
                        p("<b>Downstream use</b>", styles["Table"])]]
    for row in [
        ("ACTION ITEM", "Explicit assignment, commitment, request, or agreed next step.", "Action extraction and status/detail inference."),
        ("DECISION", "Settled choice, approval, rejection, or selected direction.", "Decision statements."),
        ("QUESTION", "Substantive uncertainty or unresolved issue.", "Question resolution tracking."),
        ("DISCUSSION", "Meaningful discussion without a detected commitment.", "Topics and summary context."),
        ("INFORMATION", "Context or factual statement.", "Context and summary candidate."),
    ]:
        classifier_rows.append([p(row[0], styles["Table"]), p(row[1], styles["Table"]), p(row[2], styles["Table"])])
    story.append(table(classifier_rows, [31 * mm, 90 * mm, 57 * mm], styles["Table"]))

    story.extend([
        p("8. Topic discovery", styles["Section"]),
        p(
            "Topic extraction has two complementary levels. Corpus-level TF-IDF "
            "ranks unigrams and bigrams after a meeting-specific stop-word set. "
            "LDA uses count vectors for probabilistic latent topics; NMF is available "
            "as an alternative over TF-IDF vectors and is often sharper for short "
            "documents. Topic count is capped by the number of sentences and "
            "vocabulary size, and a fixed random_state of 42 supports repeatability.",
            styles["Body"],
        ),
        p(
            "The service also ranks noun phrases from the spaCy Doc. These phrases "
            "remain transcript-derived discussion labels, while the semantic report "
            "may provide broader labels only when each label has supporting evidence.",
            styles["Body"],
        ),
        p("9. Grounded meeting intelligence", styles["Section"]),
        p(
            "The semantic stage receives ordered transcript units containing source "
            "segment IDs, speaker labels when available, text, and start times. "
            "Short meetings use one structured extraction request; long meetings "
            "use byte-bounded chunks with adjacent-turn overlap, local extraction, "
            "and deterministic global merging. The schema covers summary bullets, "
            "key takeaway, actions, follow-ups, decisions, questions, topics, "
            "entities, metadata, and limitations.",
            styles["Body"],
        ),
        p(
            "The provider is instructed to treat transcript content as data, extract "
            "all distinct supported items, preserve the original language in evidence, "
            "and never invent owners, deadlines, priorities, answers, or participants. "
            "A first-person commitment may resolve to the labeled speaker, but speaker "
            "identity is not inferred when the recording has no labels.",
            styles["Body"],
        ),
    ])

    contract_rows = [[p("<b>Object</b>", styles["Table"]), p("<b>Required meaning</b>", styles["Table"]),
                      p("<b>Evidence rules</b>", styles["Table"])]]
    for row in [
        ("Action", "task, optional owner/deadline/priority, status (Pending by default)", "Exact quote; owner/deadline evidence when contextual."),
        ("Decision", "settled decision statement", "Exact quote and supporting segment IDs."),
        ("Question", "question, status, optional answer", "Unresolved unless answer and answer evidence are grounded."),
        ("Topic", "label, keywords, optional relevance", "Quote must support the topic concept."),
        ("Summary", "3-6 concise factual bullets", "One summary_evidence object per bullet."),
    ]:
        contract_rows.append([p(row[0], styles["Table"]), p(row[1], styles["Table"]), p(row[2], styles["Table"])])
    story.append(table(contract_rows, [30 * mm, 72 * mm, 76 * mm], styles["Table"]))

    story.extend([
        p("10. Evidence validation and reconciliation", styles["Section"]),
        p(
            "Before persistence, every candidate insight is normalized and checked. "
            "The quote must be a contiguous substring of the canonical transcript "
            "(with a bounded fuzzy-trimming recovery for minor edge-word errors), "
            "segment IDs must be valid integers, and the quote must occur within the "
            "cited source span. Unique matches receive a timestamp from the first "
            "supporting segment and a speaker only when all supporting segments agree.",
            styles["Body"],
        ),
        p(
            "Deduplication merges paraphrases only when semantic terms and source "
            "evidence identify the same event. Actions with conflicting owners or "
            "deadlines remain separate. This prevents a broad similarity threshold "
            "from collapsing distinct work items.",
            styles["Body"],
        ),
        p(
            "Re-analysis is controlled by a SHA-256 manifest containing analysis and "
            "prompt versions, model/configuration hashes, input hash, schema hash, "
            "chunk policy, merge policy, and output settings. Stable IDs are derived "
            "from meeting ID, category, source segment IDs, and a task/decision suffix "
            "when multiple insights share a turn. Existing user edits are carried "
            "forward only when the underlying task and evidence still match.",
            styles["Body"],
        ),
        p("Reconciliation state model", styles["Subsection"]),
        p(
            "complete means a validated report is available; partial means some "
            "fields required recovery or review; empty means no usable intelligence "
            "was produced. Provider or parsing failure is surfaced as an API failure "
            "and saved as a failed attempt rather than converted into a successful "
            "empty report.",
            styles["Callout"],
        ),
        p("11. Summarization", styles["Section"]),
        p(
            "The default extractive summary is source-preserving. It removes duplicate "
            "sentences and low-information greetings, vectorizes substantive sentences "
            "with TF-IDF, scores centroid relevance, boosts actions/decisions and risk "
            "signals, then applies maximal marginal relevance so selected sentences "
            "are diverse. The final sentences are returned in transcript order.",
            styles["Body"],
        ),
        p(
            "Optional abstractive summarization uses a Hugging Face BART/T5-compatible "
            "pipeline on CPU. Text is split at sentence boundaries under a character "
            "budget, each chunk is summarized, and the result is marked as a draft. "
            "The shareable report remains grounded in transcript excerpts; an "
            "abstractive draft must receive human review.",
            styles["Body"],
        ),
        p("12. Persistence, API, and presentation", styles["Section"]),
        p(
            "The analysis route loads a stored transcript, builds the current manifest, "
            "uses a cache hit when the prior complete report has the same pipeline and "
            "input identity, runs analysis under a meeting lock, checkpoints long "
            "analysis, reconciles the candidate, and persists the canonical payload. "
            "Local JSON storage supports recovery; Supabase stores compatible boundary "
            "fields and the canonical intelligence object.",
            styles["Body"],
        ),
        p(
            "The frontend consumes the report through the existing Overview, Transcript, "
            "and Analytics views. Evidence remains navigable to the first matching "
            "timestamp when source mapping is unambiguous. PDF export uses ReportLab "
            "and should display the evidence-backed report rather than independently "
            "re-running extraction.",
            styles["Body"],
        ),
        p("13. Operational configuration", styles["Section"]),
    ])

    config_rows = [[p("<b>Area</b>", styles["Table"]), p("<b>Configuration</b>", styles["Table"]),
                    p("<b>Operational note</b>", styles["Table"])]]
    for row in [
        ("ASR", "WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE", "GPU failure retries once on CPU; model is lazy-loaded."),
        ("Semantic provider", "GROQ_API_KEY / MEETING_LLM_API_KEY and MEETING_LLM_* settings", "Credentials stay server-side; bounded retries handle transient limits."),
        ("NLP model", "en_core_web_sm plus NLTK stopwords", "Install/download resources before first analysis."),
        ("Storage", "Local meeting files and optional Supabase", "No SQL migration is required for the canonical JSONB field."),
        ("Validation", "backend.scripts.test_report_accuracy and related tests", "Regression fixtures are not a production accuracy benchmark."),
    ]:
        config_rows.append([p(row[0], styles["Table"]), p(row[1], styles["Table"]), p(row[2], styles["Table"])])
    story.append(table(config_rows, [31 * mm, 78 * mm, 69 * mm], styles["Table"]))

    story.extend([
        p("14. Limitations and evaluation boundaries", styles["Section"]),
        p(
            "The extraction rules favor precision and may omit implicit commitments, "
            "unusual task verbs, conditional assignments, and cross-sentence resolutions. "
            "Whisper does not perform diarization in the current service, so unlabeled "
            "audio cannot reliably identify speakers. English spaCy/NLTK models are "
            "used for classical NLP, although semantic extraction can process the "
            "original multilingual text without forced translation.",
            styles["Body"],
        ),
        p(
            "Model probability is not factuality. Fixture-level re-analysis stability "
            "does not establish general accuracy, and the regression suite is not a "
            "measured production benchmark. Representative annotated recordings are "
            "required before treating generated reports as authoritative.",
            styles["Callout"],
        ),
        p("15. Reproducible execution checklist", styles["Section"]),
        p(
            "1) Install Python dependencies and FFmpeg. 2) Download en_core_web_sm "
            "and ensure NLTK stopwords are available. 3) Configure server credentials "
            "only in .env when semantic extraction is enabled. 4) Start FastAPI and "
            "the React/Vite frontend. 5) Upload an existing recording. 6) Inspect "
            "the raw timestamped transcript. 7) Run analysis and verify evidence "
            "quotes, segment IDs, actions, decisions, questions, and limitations. "
            "8) Re-analyse the same meeting to verify cache/reconciliation behavior. "
            "9) Run the focused regression tests before sharing a report.",
            styles["Body"],
        ),
        p("Repository implementation map", styles["Subsection"]),
    ])
    map_rows = [[p("<b>Concern</b>", styles["Table"]), p("<b>Primary files</b>", styles["Table"])]]
    for row in [
        ("HTTP orchestration", "backend/main.py; backend/routes/upload.py; backend/routes/analysis.py"),
        ("Media and ASR", "backend/services/audio.py; backend/services/transcription.py"),
        ("Classical NLP", "backend/services/preprocessing.py; ner.py; classification.py; topics.py"),
        ("Semantic intelligence", "backend/services/semantic.py; intelligence.py; consistency.py"),
        ("Summaries", "backend/services/summarization.py"),
        ("Storage and reports", "backend/services/meeting_store.py; backend/db.py; routes/report.py"),
        ("Validation", "backend/scripts/test_*.py; data/training_sentences.csv"),
    ]:
        map_rows.append([p(row[0], styles["Table"]), p(row[1], styles["Table"])])
    story.append(table(map_rows, [40 * mm, 138 * mm], styles["Table"]))
    story.append(Spacer(1, 8))
    story.append(p("End of document", styles["Small"]))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"Generated {OUTPUT}")


if __name__ == "__main__":
    build_pdf()
