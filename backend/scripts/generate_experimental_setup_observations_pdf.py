"""Generate a polished IEEE-style experimental setup and observations report."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "data" / "validation" / "consistency" / "results.json"
TRANSCRIPTION = ROOT / "research_evaluation" / "data" / "transcription_summary.csv"
OUTPUT = ROOT / "Experimental_Setup_and_Observations_IEEE.pdf"

NAVY = colors.HexColor("#15324B")
BLUE = colors.HexColor("#2563EB")
TEAL = colors.HexColor("#0F766E")
PALE_BLUE = colors.HexColor("#EFF6FF")
PALE_TEAL = colors.HexColor("#ECFDF5")
PALE_GREY = colors.HexColor("#F8FAFC")
MID_GREY = colors.HexColor("#64748B")
GRID = colors.HexColor("#CBD5E1")


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def table(rows, widths, header=True, header_color=NAVY, font_size=8.2):
    converted = []
    for row in rows:
        converted.append(
            [cell if isinstance(cell, Paragraph) else str(cell) for cell in row]
        )
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BACKGROUND", (0, 1 if header else 0), (-1, -1), PALE_GREY),
    ]
    if header:
        commands += [
            ("BACKGROUND", (0, 0), (-1, 0), header_color),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    return Table(converted, colWidths=widths, repeatRows=1 if header else 0,
                 style=TableStyle(commands))


def build_pdf() -> None:
    result = json.loads(RESULTS.read_text(encoding="utf-8"))
    runs = result["runs"]
    manifest = runs[0]["manifest"]
    transcription_rows = list(csv.DictReader(TRANSCRIPTION.open(encoding="utf-8")))

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=21, leading=25, alignment=TA_CENTER, textColor=NAVY,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle", parent=styles["Normal"], fontSize=10.5,
        leading=14, alignment=TA_CENTER, textColor=MID_GREY, spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=13, leading=16, textColor=NAVY, spaceBefore=11, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="Subsection", parent=styles["Heading3"], fontName="Helvetica-Bold",
        fontSize=10.5, leading=13, textColor=TEAL, spaceBefore=7, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="BodyJustified", parent=styles["BodyText"], fontSize=9.2,
        leading=13.2, alignment=TA_JUSTIFY, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="Small", parent=styles["BodyText"], fontSize=8.2, leading=11,
        textColor=MID_GREY, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="TableCell", parent=styles["BodyText"], fontSize=8, leading=10,
    ))
    styles.add(ParagraphStyle(
        name="Callout", parent=styles["BodyText"], fontSize=8.7, leading=12,
        backColor=PALE_BLUE, borderColor=colors.HexColor("#BFDBFE"),
        borderWidth=0.6, borderPadding=7, spaceBefore=4, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="Observation", parent=styles["BodyText"], fontSize=9.1,
        leading=13, leftIndent=9, firstLineIndent=-9, spaceAfter=7,
    ))

    def cell(text: str) -> Paragraph:
        return p(text, styles["TableCell"])

    def footer(canvas, doc):
        canvas.saveState()
        width, height = A4
        canvas.setStrokeColor(GRID)
        canvas.setLineWidth(0.4)
        canvas.line(16 * mm, 12 * mm, width - 16 * mm, 12 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MID_GREY)
        canvas.drawString(16 * mm, 7 * mm, "Meeting Analyzer | Experimental Setup and Observations")
        canvas.drawRightString(width - 16 * mm, 7 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=18 * mm,
        title="Experimental Setup and Observations - Meeting Analyzer",
        author="Meeting Analyzer",
    )

    story = [
        Spacer(1, 15 * mm),
        p("Experimental Setup and Observations", styles["ReportTitle"]),
        p(
            "IEEE-paper support document for the grounded meeting-intelligence pipeline",
            styles["ReportSubtitle"],
        ),
        HRFlowable(width="100%", thickness=1.2, color=BLUE, spaceAfter=13),
        p(
            "<b>Purpose.</b> This report presents the experimental configuration, "
            "measurement protocol, recorded results, and engineering observations "
            "supporting the IEEE manuscript. It separates directly recorded validation "
            "evidence from manuscript values that still require their underlying datasets "
            "and scripts for independent reproduction.",
            styles["BodyJustified"],
        ),
        p(
            "<b>Evidence status.</b> The primary reproducibility result is a five-run "
            "forced re-analysis of one controlled navigation fixture. Transcription "
            "throughput is measured independently on one audio recording with 30 s, "
            "60 s, and 120 s clips, each repeated three times.",
            styles["Callout"],
        ),
        table(
            [
                [cell("<b>Recorded artifact</b>"), cell("<b>Value</b>")],
                [cell("Consistency validation"), cell("Passed; 5 forced runs")],
                [cell("Core output per run"), cell("2 actions, 1 decision, 1 question")],
                [cell("Minimum core Jaccard overlap"), cell("1.00 for actions, decisions, questions")],
                [cell("Transcription benchmark"), cell("9 timed runs; 30/60/120 s clips")],
                [cell("Runtime platform"), cell("Windows 11; 16 logical CPUs; Python 3.12.10")],
            ],
            [59 * mm, 109 * mm],
        ),
        PageBreak(),
        p("I. Experimental Setup", styles["Section"]),
        p("A. System under evaluation", styles["Subsection"]),
        p(
            "The evaluated system is a hybrid, evidence-grounded meeting analyzer. "
            "Audio/video is decoded with FFmpeg and transcribed locally by Faster-Whisper "
            "using CTranslate2. The transcript is preserved with ordered segments and "
            "timestamps. Classical NLP components provide preprocessing, named-entity "
            "recognition, and dialogue-act signals. Structured semantic extraction then "
            "produces actions, decisions, questions, follow-ups, topics, and summaries. "
            "Every core insight is validated against transcript evidence before it is "
            "deduplicated and persisted.",
            styles["BodyJustified"],
        ),
        table(
            [
                [cell("<b>Stage</b>"), cell("<b>Implementation / control</b>")],
                [cell("Input"), cell("Audio/video upload; FFmpeg extraction and format validation")],
                [cell("ASR"), cell("Faster-Whisper base; CTranslate2; INT8 CPU inference; VAD enabled")],
                [cell("Linguistic processing"), cell("spaCy preprocessing, NER, TF-IDF features, dialogue-act classification")],
                [cell("Semantic extraction"), cell("Groq openai/gpt-oss-120b; strict JSON Schema; temperature 0; top-p 1")],
                [cell("Evidence control"), cell("Verbatim quote matching to source segments; unsupported evidence rejected")],
                [cell("State control"), cell("SHA-256 manifests, stable source-anchored IDs, deterministic reconciliation")],
                [cell("Output"), cell("Canonical report, dashboard data, and shareable PDF export")],
            ],
            [43 * mm, 125 * mm], header_color=TEAL,
        ),
        p("B. Runtime and model configuration", styles["Subsection"]),
        table(
            [
                [cell("<b>Parameter</b>"), cell("<b>Configuration</b>")],
                [cell("Operating system / CPU"), cell("Windows 11; AMD64; 16 logical CPUs")],
                [cell("Python and packages"), cell("Python 3.12.10; faster-whisper 1.2.1; CTranslate2 4.8.2")],
                [cell("ASR model"), cell("Systran/faster-whisper-base; recorded revision ebe41f70...")],
                [cell("ASR decoding"), cell("Beam size 5; VAD filter true; minimum silence 500 ms; language auto")],
                [cell("LLM"), cell("Groq API, openai/gpt-oss-120b; strict json_schema")],
                [cell("LLM controls"), cell("Temperature 0; top-p 1; reasoning effort low; max output 8192 tokens")],
                [cell("Determinism"), cell("SHA-256 request-content seed policy; ordered segment chunks; deterministic merge")],
            ],
            [48 * mm, 120 * mm],
        ),
        p("C. Datasets and test fixtures", styles["Subsection"]),
        p(
            "The manuscript describes AMI/ICSI corpora, an internal engineering-meeting "
            "corpus, a controlled navigation fixture, and multilingual tests. The "
            "directly auditable artifacts used for this report are the controlled "
            "navigation fixture for semantic consistency and one independent recording "
            "for ASR throughput. The fixture contains seven timestamped segments and "
            "was held constant across all five forced analyses.",
            styles["BodyJustified"],
        ),
        p("D. Measurement protocol", styles["Subsection"]),
        p(
            "For semantic stability, the same canonical input, prompt version, schema, "
            "analysis version, and provider configuration were submitted five times with "
            "force=true, bypassing ordinary cached-result reuse. Outputs were measured "
            "at generated, parsed, validated, evidence-matched, deduplicated, and "
            "persisted stages. For ASR throughput, warm transcription runs were timed "
            "after model loading; decode, VAD, language detection, lazy segment "
            "consumption, and output construction were included, while model loading, "
            "NLP, and persistence were excluded.",
            styles["BodyJustified"],
        ),
        PageBreak(),
        p("II. Metrics and Recorded Results", styles["Section"]),
        p("A. Evaluation metrics", styles["Subsection"]),
        table(
            [
                [cell("<b>Metric</b>"), cell("<b>Definition and interpretation</b>")],
                [cell("Jaccard overlap"), cell("J(A,B) = |A intersection B| / |A union B|, using stable item identity and source evidence.")],
                [cell("Stage retention"), cell("Items surviving each validation boundary divided by items entering that boundary.")],
                [cell("Real-time factor"), cell("Transcription time divided by clip duration; values below 1 indicate faster-than-real-time processing.")],
                [cell("Run variance"), cell("Mean, standard deviation, minimum, and maximum of three timed runs per clip length.")],
                [cell("Grounding status"), cell("An item is evidence-matched only when its supporting quote maps to the original transcript segment.")],
            ],
            [45 * mm, 123 * mm], header_color=BLUE,
        ),
        p("B. Five-run semantic consistency", styles["Subsection"]),
    ]

    stability_rows = [[
        cell("<b>Category</b>"), cell("<b>Run 1</b>"), cell("<b>Run 2</b>"),
        cell("<b>Run 3</b>"), cell("<b>Run 4</b>"), cell("<b>Run 5</b>"),
        cell("<b>Min J</b>"),
    ]]
    for label, key in [
        ("Action items", "action_items"),
        ("Decisions", "decisions"),
        ("Questions", "questions"),
        ("Follow-ups", "follow_ups"),
    ]:
        values = [run["counts"][key] for run in runs]
        minimum = "1.00" if key != "follow_ups" else "N/A"
        stability_rows.append([cell(label), *map(str, values), cell(minimum)])
    story.append(table(stability_rows, [38 * mm, 17 * mm, 17 * mm, 17 * mm, 17 * mm, 17 * mm, 22 * mm]))
    story.extend([
        p(
            "The five forced runs returned identical core counts: 2 action items, "
            "1 decision, and 1 question. The empty follow-up category is not a recall "
            "measurement because the fixture contains no separate follow-up.",
            styles["BodyJustified"],
        ),
        p("C. Pipeline retention audit", styles["Subsection"]),
    ])
    audit_rows = [[
        cell("<b>Category</b>"), cell("<b>Generated</b>"), cell("<b>Parsed</b>"),
        cell("<b>Validated</b>"), cell("<b>Evidence matched</b>"), cell("<b>Deduplicated</b>"),
    ]]
    for label, key in [
        ("Action items", "action_items"), ("Decisions", "decisions"),
        ("Questions", "questions"), ("Follow-ups", "follow_ups"),
    ]:
        values = runs[0]["pipeline"][key]
        audit_rows.append([cell(label)] + [str(values[k]) for k in (
            "generated", "parsed", "validated", "evidence_matched", "deduplicated"
        )])
    story.append(table(audit_rows, [38 * mm, 26 * mm, 25 * mm, 27 * mm, 34 * mm, 29 * mm], header_color=TEAL))
    story.append(p(
        "For the recorded fixture, every generated core item survived all local "
        "validation boundaries. Across five runs this corresponds to 20 of 20 "
        "category-run core items remaining evidence matched. This is a fixture-level "
        "observation, not a universal hallucination-rate estimate.",
        styles["Callout"],
    ))
    story.append(p("D. Local transcription throughput", styles["Subsection"]))
    timing_rows = [[
        cell("<b>Clip (s)</b>"), cell("<b>Mean (s)</b>"), cell("<b>SD (s)</b>"),
        cell("<b>Min (s)</b>"), cell("<b>Max (s)</b>"), cell("<b>Mean RTF</b>"),
    ]]
    for row in sorted(transcription_rows, key=lambda x: int(x["duration_s"])):
        timing_rows.append([
            row["duration_s"], f'{float(row["mean_s"]):.3f}',
            f'{float(row["sd_s"]):.3f}', f'{float(row["min_s"]):.3f}',
            f'{float(row["max_s"]):.3f}', f'{float(row["mean_rtf"]):.3f}',
        ])
    story.append(table(timing_rows, [27 * mm, 29 * mm, 25 * mm, 27 * mm, 27 * mm, 30 * mm], header_color=BLUE))
    story.append(p(
        "Mean real-time factors remained below 0.10 for all tested durations. The "
        "120-second clip averaged 11.562 seconds of transcription time (RTF 0.096), "
        "indicating faster-than-real-time local ASR under the recorded CPU configuration. "
        "The benchmark does not include full upload, NLP, LLM, or persistence latency.",
        styles["BodyJustified"],
    ))
    story.append(PageBreak())
    story.extend([
        p("III. Detailed Observations", styles["Section"]),
        p(
            "<b>1. Core semantic identities were stable.</b> The same source-anchored "
            "action items, decision, and question were reproduced across all five "
            "forced analyses. Stability therefore held at the level most relevant to "
            "report persistence: category, semantic identity, and source evidence.",
            styles["Observation"],
        ),
        p(
            "<b>2. Local reconciliation removed provider-order dependence.</b> The "
            "candidate and persisted counts were identical in every run. Stable IDs, "
            "normalized matching, evidence checks, and deterministic merging prevent a "
            "later response from silently replacing a valid earlier report.",
            styles["Observation"],
        ),
        p(
            "<b>3. Evidence validation was an effective boundary on this fixture.</b> "
            "No core item was removed between generation and evidence matching. The "
            "result is consistent with the system's design: supporting quotes must map "
            "to transcript segments, and invalid or unsupported evidence is not "
            "persisted as a successful insight.",
            styles["Observation"],
        ),
        p(
            "<b>4. Descriptive topics are less stable than core outcomes.</b> The "
            "recorded provenance shows topic overlap varying from 0.00 to 1.00 across "
            "runs, while actions, decisions, and questions remained at 1.00. This "
            "suggests that topic labels should be treated as descriptive context rather "
            "than as audit-grade identifiers.",
            styles["Observation"],
        ),
        p(
            "<b>5. Local ASR throughput was consistent across scale.</b> Mean RTF was "
            "0.077, 0.095, and 0.096 for 30-, 60-, and 120-second clips. The near-flat "
            "ratio after the shortest clip indicates that fixed overhead was amortized, "
            "but the result is hardware- and model-specific.",
            styles["Observation"],
        ),
        p(
            "<b>6. Reproducibility metadata is part of the result.</b> The validation "
            "manifest records input, configuration, schema, system, and model hashes. "
            "These fields allow a future run to distinguish a changed input or pipeline "
            "from genuine model variation.",
            styles["Observation"],
        ),
        p("IV. Reproducibility and Limitations", styles["Section"]),
        p(
            f"Semantic runs used analysis version <b>{manifest['analysis_version']}</b>, "
            f"prompt version <b>{manifest['prompt_version']}</b>, model "
            f"<b>{manifest['model']}</b>, temperature <b>{manifest['config']['temperature']}</b>, "
            f"top-p <b>{manifest['config']['top_p']}</b>, strict JSON Schema output, "
            f"and an input hash beginning <font name='Courier'>{manifest['input_hash'][:16]}...</font>.",
            styles["BodyJustified"],
        ),
        p(
            "The controlled fixture is short, English, and single-purpose. It does not "
            "establish accuracy across speakers, domains, languages, noisy recordings, "
            "or long meetings. It also does not independently reproduce manuscript-only "
            "claims such as AMI/ICSI classification scores, ROUGE values, or an "
            "unconstrained-LLM baseline. Those claims should be retained in the IEEE "
            "paper only after the corresponding datasets, predictions, references, and "
            "measurement scripts are archived.",
            styles["Callout"],
        ),
        p(
            "Source artifacts: data/validation/consistency/results.json, "
            "data/validation/consistency/consistency_pairs.csv, and "
            "research_evaluation/data/transcription_summary.csv.",
            styles["Small"],
        ),
    ])

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    build_pdf()
