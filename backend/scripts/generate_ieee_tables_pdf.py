"""Generate a standalone IEEE-style tables PDF for the Meeting Analyzer paper."""

from __future__ import annotations

import csv
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "research_evaluation" / "data"
OUTPUT = ROOT / "IEEE_Tables_Separate.pdf"

NAVY = colors.HexColor("#15324B")
SLATE = colors.HexColor("#475569")
GRID = colors.HexColor("#CBD5E1")
LIGHT = colors.HexColor("#F1F5F9")


def load_latency() -> list[dict[str, str]]:
    with (DATA / "transcription_summary.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def table(headers: list[str], values: list[list[str]], widths: list[float], styles) -> Table:
    rows = [[Paragraph(f"<b>{header}</b>", styles["TableText"]) for header in headers]]
    rows.extend([[Paragraph(str(value), styles["TableText"]) for value in row] for row in values])
    result = Table(rows, colWidths=widths, repeatRows=1)
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return result


def footer(canvas, doc) -> None:
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(GRID)
    canvas.line(16 * mm, 12 * mm, width - 16 * mm, 12 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(SLATE)
    canvas.drawString(16 * mm, 7 * mm, "Meeting Analyzer | IEEE Tables")
    canvas.drawRightString(width - 16 * mm, 7 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf() -> None:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TitleCenter", parent=styles["Title"], alignment=TA_CENTER,
        fontName="Helvetica-Bold", fontSize=18, leading=23,
        textColor=NAVY, spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        name="Subtitle", parent=styles["Normal"], alignment=TA_CENTER,
        fontSize=9.5, leading=13, textColor=SLATE, spaceAfter=13,
    ))
    styles.add(ParagraphStyle(
        name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=12, leading=15, textColor=NAVY, spaceBefore=10, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="Body", parent=styles["BodyText"], alignment=TA_JUSTIFY,
        fontSize=9.2, leading=13.2, spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        name="Caption", parent=styles["BodyText"], alignment=TA_CENTER,
        fontSize=8.3, leading=11, textColor=SLATE, spaceBefore=4, spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        name="Note", parent=styles["BodyText"], fontSize=8.4, leading=11.5,
        textColor=colors.HexColor("#334155"), backColor=LIGHT,
        borderColor=GRID, borderWidth=0.5, borderPadding=6,
        spaceBefore=5, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="TableText", parent=styles["BodyText"], fontSize=7.8, leading=9.8,
    ))

    latency = load_latency()
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=15 * mm, bottomMargin=16 * mm,
        title="IEEE Tables - Meeting Analyzer",
        author="Meeting Analyzer",
    )
    story = [
        Paragraph("IEEE Tables for Meeting Analyzer", styles["TitleCenter"]),
        Paragraph(
            "Standalone manuscript-ready tables based on recorded implementation and evaluation data",
            styles["Subtitle"],
        ),
        Paragraph(
            "These tables are separated from the evaluation-graphs PDF so they can be "
            "inserted independently into the IEEE manuscript. Jaccard-overlap results "
            "are intentionally excluded.",
            styles["Note"],
        ),
        Paragraph("TABLE I. SYSTEM TECHNOLOGY STACK", styles["Caption"]),
        table(
            ["Layer", "Technology", "Role"],
            [
                ["Frontend", "React, Vite, Tailwind CSS", "Interactive dashboard"],
                ["Backend", "FastAPI, Python", "API and orchestration"],
                ["Audio", "FFmpeg", "Extraction and normalization"],
                ["Speech recognition", "Faster-Whisper", "Timestamped transcription"],
                ["NLP", "spaCy, NLTK", "Preprocessing and linguistic analysis"],
                ["Classification", "TF-IDF + Logistic Regression", "Dialogue-act classification"],
                ["Topics", "LDA / NMF", "Topic discovery"],
                ["Storage", "Local JSON / Supabase", "Persistence and recovery"],
                ["PDF export", "ReportLab", "Report generation"],
            ],
            [36 * mm, 70 * mm, 72 * mm],
            styles,
        ),
        Spacer(1, 8),
        Paragraph("TABLE II. DATASET AND EVALUATION CONFIGURATION", styles["Caption"]),
        table(
            ["Parameter", "Value"],
            [
                ["Source recordings", "1"],
                ["Clip durations", "30 s, 60 s, 120 s"],
                ["Transcription repeats", "3 per duration"],
                ["Re-analysis runs", "5"],
                ["Whisper model", "Systran/faster-whisper-base"],
                ["Device / compute", "CPU / int8"],
                ["Beam size", "5"],
                ["VAD", "Enabled; 500 ms minimum silence"],
                ["Language", "Automatic detection"],
            ],
            [65 * mm, 113 * mm],
            styles,
        ),
        Spacer(1, 8),
        Paragraph("TABLE III. TRANSCRIPTION LATENCY UNDER CPU/INT8 EXECUTION", styles["Caption"]),
        table(
            ["Duration (s)", "Mean (s)", "SD (s)", "Minimum (s)", "Maximum (s)", "Mean RTF"],
            [
                [
                    row["duration_s"],
                    f"{float(row['mean_s']):.3f}",
                    f"{float(row['sd_s']):.3f}",
                    f"{float(row['min_s']):.3f}",
                    f"{float(row['max_s']):.3f}",
                    f"{float(row['mean_rtf']):.3f}",
                ]
                for row in latency
            ],
            [28 * mm, 30 * mm, 28 * mm, 30 * mm, 30 * mm, 32 * mm],
            styles,
        ),
        PageBreak(),
        Paragraph("TABLE IV. CORE EXTRACTION COUNTS ACROSS FIVE FRESH ANALYSES", styles["Caption"]),
        table(
            ["Category", "Run 1", "Run 2", "Run 3", "Run 4", "Run 5"],
            [
                ["Action items", "2", "2", "2", "2", "2"],
                ["Decisions", "1", "1", "1", "1", "1"],
                ["Questions", "1", "1", "1", "1", "1"],
                ["Follow-ups", "0", "0", "0", "0", "0"],
            ],
            [50 * mm, 25 * mm, 25 * mm, 25 * mm, 25 * mm, 28 * mm],
            styles,
        ),
        Paragraph(
            "Follow-up extraction accuracy is not established by this fixture because "
            "it contains no separate follow-up item.",
            styles["Note"],
        ),
        Paragraph("TABLE V. VALIDATION PIPELINE RETENTION", styles["Caption"]),
        table(
            ["Category", "Generated", "Parsed", "Validated", "Evidence matched", "Deduplicated", "Persisted"],
            [
                ["Action items", "2", "2", "2", "2", "2", "2"],
                ["Decisions", "1", "1", "1", "1", "1", "1"],
                ["Questions", "1", "1", "1", "1", "1", "1"],
                ["Follow-ups", "0", "0", "0", "0", "0", "0"],
            ],
            [31 * mm, 24 * mm, 22 * mm, 25 * mm, 32 * mm, 27 * mm, 24 * mm],
            styles,
        ),
        Spacer(1, 8),
        Paragraph("TABLE VI. SUMMARIZATION METHODS", styles["Caption"]),
        table(
            ["Method", "Algorithm / model", "Output", "Grounding"],
            [
                ["Extractive", "TF-IDF + centroid similarity + MMR", "Source excerpts", "Direct transcript text"],
                ["Abstractive", "BART/T5-compatible Transformer", "Generated draft", "Requires human review"],
                ["Semantic", "Structured evidence extraction", "Evidence-linked bullets", "Verbatim evidence required"],
            ],
            [32 * mm, 68 * mm, 42 * mm, 36 * mm],
            styles,
        ),
        Spacer(1, 8),
        Paragraph("TABLE VII. LIMITATIONS AND SAFEGUARDS", styles["Caption"]),
        table(
            ["Risk", "Safeguard", "Remaining limitation"],
            [
                ["Unsupported insight", "Verbatim evidence matching", "Lexical matching is not full entailment"],
                ["Re-analysis drift", "Versioned manifest and stable IDs", "Fixture-level validation only"],
                ["Speaker identity", "Preserve available labels", "No diarization for unlabeled audio"],
                ["Long transcripts", "Bounded chunks and deterministic merge", "Higher resource requirements"],
                ["Abstractive hallucination", "Extractive default and review", "Generated drafts need human review"],
            ],
            [43 * mm, 66 * mm, 69 * mm],
            styles,
        ),
        Spacer(1, 8),
        Paragraph("Data provenance", styles["Section"]),
        Paragraph(
            "Tables I and VI reflect the implemented system design. Tables II–V use the "
            "recorded benchmark and consistency-validation artifacts in the repository. "
            "The latency benchmark uses one source recording, three clip durations, and "
            "three repeats per duration. The extraction and retention tables describe "
            "a five-run meeting fixture and should not be interpreted as corpus-wide "
            "accuracy claims.",
            styles["Body"],
        ),
    ]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"Generated {OUTPUT}")


if __name__ == "__main__":
    build_pdf()
