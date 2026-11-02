"""Generate measured IEEE-style evaluation graphs and an explanatory PDF."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "research_evaluation" / "data"
OUT_DIR = ROOT / "paper_graphs" / "ieee_evaluation"
OUTPUT = ROOT / "IEEE_Evaluation_Graphs_and_Explanations.pdf"

NAVY = "#15324B"
BLUE = "#2563EB"
TEAL = "#0F766E"
GRAY = "#64748B"
GRID = "#CBD5E1"
LIGHT = "#F1F5F9"


def load_latency() -> dict:
    rows = []
    with (DATA / "transcription_summary.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {
        "duration": np.array([float(row["duration_s"]) for row in rows]),
        "mean": np.array([float(row["mean_s"]) for row in rows]),
        "sd": np.array([float(row["sd_s"]) for row in rows]),
        "rtf": np.array([float(row["mean_rtf"]) for row in rows]),
        "n": [int(row["n"]) for row in rows],
    }


def configure_plot(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_xlabel(xlabel, fontsize=8.5, color="#1F2937")
    ax.set_ylabel(ylabel, fontsize=8.5, color="#1F2937")
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(labelsize=7.5, colors="#374151")


def save_figure(fig, path: Path) -> Path:
    """Write both a reviewable PNG and a vector PDF for paper insertion."""
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", dpi=300)
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    return path


def save_latency_graph(data: dict) -> Path:
    path = OUT_DIR / "01_transcription_latency.png"
    fig, ax = plt.subplots(figsize=(7.0, 4.2), dpi=220)
    ax.errorbar(
        data["duration"], data["mean"], yerr=data["sd"], marker="o",
        markersize=6, linewidth=2, capsize=4, color=BLUE,
        markerfacecolor="white", markeredgewidth=1.5,
    )
    configure_plot(ax, "Transcription latency by audio duration",
                   "Input audio duration (s)", "Mean transcription time (s)")
    ax.set_xticks(data["duration"])
    ax.text(
        0.02, 0.95,
        "Mean ± standard deviation; n = 3 runs per duration",
        transform=ax.transAxes, fontsize=7.5, va="top", color=GRAY,
    )
    return save_figure(fig, path)


def save_rtf_graph(data: dict) -> Path:
    path = OUT_DIR / "02_real_time_factor.png"
    fig, ax = plt.subplots(figsize=(7.0, 4.2), dpi=220)
    bars = ax.bar(data["duration"], data["rtf"], width=17, color=TEAL,
                  edgecolor="white", linewidth=0.7)
    configure_plot(ax, "Speech-to-text real-time factor",
                   "Input audio duration (s)", "Real-time factor (×)")
    ax.set_xticks(data["duration"])
    for bar, value in zip(bars, data["rtf"]):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.002,
                f"{value:.3f}", ha="center", va="bottom", fontsize=7.5, color=NAVY)
    return save_figure(fig, path)


def save_jaccard_graph() -> Path:
    path = OUT_DIR / "03_jaccard_overlap.png"
    labels = ["Actions", "Decisions", "Questions"]
    values = [1.0, 1.0, 1.0]
    fig, ax = plt.subplots(figsize=(7.0, 4.2), dpi=220)
    bars = ax.bar(labels, values, color=[BLUE, TEAL, "#B45309"],
                  width=0.58)
    configure_plot(ax, "Minimum Jaccard overlap against Run 1",
                   "Insight category", "Minimum Jaccard overlap")
    ax.set_ylim(0, 1.12)
    ax.set_yticks(np.arange(0, 1.01, 0.2))
    ax.set_yticklabels([f"{value:.0%}" for value in np.arange(0, 1.01, 0.2)])
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.035,
                f"{value:.0%}", ha="center", va="bottom", fontsize=8,
                fontweight="bold", color=NAVY)
    ax.text(0.02, 0.06,
            "Four pairwise comparisons against Run 1 per category; topic labels excluded.",
            transform=ax.transAxes, fontsize=7.2, color=GRAY)
    return save_figure(fig, path)


def footer(canvas, doc) -> None:
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(colors.HexColor(GRID))
    canvas.line(16 * mm, 12 * mm, width - 16 * mm, 12 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor(GRAY))
    canvas.drawString(16 * mm, 7 * mm, "Meeting Analyzer | IEEE Evaluation Graphs")
    canvas.drawRightString(width - 16 * mm, 7 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf(graphs: list[Path], data: dict) -> None:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TitleCenter", parent=styles["Title"], alignment=TA_CENTER,
        fontName="Helvetica-Bold", fontSize=18, leading=23, textColor=colors.HexColor(NAVY),
        spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        name="Subtitle", parent=styles["Normal"], alignment=TA_CENTER,
        fontSize=9.5, leading=13, textColor=colors.HexColor(GRAY), spaceAfter=13,
    ))
    styles.add(ParagraphStyle(
        name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=12, leading=15, textColor=colors.HexColor(NAVY),
        spaceBefore=10, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="Body", parent=styles["BodyText"], alignment=TA_JUSTIFY,
        fontSize=9.2, leading=13.2, spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        name="Caption", parent=styles["BodyText"], alignment=TA_CENTER,
        fontSize=8.3, leading=11, textColor=colors.HexColor(GRAY),
        spaceBefore=4, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="Note", parent=styles["BodyText"], fontSize=8.4, leading=11.5,
        textColor=colors.HexColor("#334155"), backColor=colors.HexColor("#F1F5F9"),
        borderColor=colors.HexColor(GRID), borderWidth=0.5, borderPadding=6,
        spaceBefore=5, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="TableText", parent=styles["BodyText"], fontSize=8, leading=10,
    ))

    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=15 * mm, bottomMargin=16 * mm,
        title="IEEE Evaluation Graphs and Explanations - Meeting Analyzer",
        author="Meeting Analyzer",
    )
    story = [
        Paragraph("Evaluation Graphs and Explanations", styles["TitleCenter"]),
        Paragraph(
            "IEEE-style figures generated from recorded transcription and consistency-validation data",
            styles["Subtitle"],
        ),
        Paragraph("Purpose and evidence boundary", styles["Section"]),
        Paragraph(
            "This document contains publication-ready graphs for the Meeting Analyzer "
            "evaluation. The figures use the measured transcription benchmark in "
            "research_evaluation/data and the recorded five-run consistency audit "
            "described in REANALYSIS_CONSISTENCY_REPORT.md. Values are not inferred "
            "from the architecture diagram and no unsupported accuracy values are added.",
            styles["Body"],
        ),
        Paragraph(
            "The transcription benchmark contains one source recording, three clip "
            "durations (30, 60, and 120 seconds), and three repeated runs per duration. "
            "The consistency fixture contains five fresh analyses of the same meeting. "
            "These are engineering validation results, not a corpus-wide accuracy study.",
            styles["Note"],
        ),
    ]

    def data_table(headers: list[str], values: list[list[str]], widths: list[float]) -> Table:
        rows = [[Paragraph(f"<b>{header}</b>", styles["TableText"]) for header in headers]]
        rows.extend([[Paragraph(str(value), styles["TableText"]) for value in row] for row in values])
        result = Table(rows, colWidths=widths, repeatRows=1)
        result.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor(GRID)),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT)]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return result

    story.extend([
        Paragraph("Tables for the IEEE manuscript", styles["Section"]),
        Paragraph(
            "The following tables report configuration and measured results directly. "
            "Jaccard overlap has been removed from this PDF.",
            styles["Body"],
        ),
        Paragraph("TABLE I. SYSTEM TECHNOLOGY STACK", styles["Caption"]),
        data_table(
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
        ),
        Spacer(1, 7),
        Paragraph("TABLE II. DATASET AND EVALUATION CONFIGURATION", styles["Caption"]),
        data_table(
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
        ),
        Spacer(1, 7),
        Paragraph("TABLE III. TRANSCRIPTION LATENCY UNDER CPU/INT8 EXECUTION", styles["Caption"]),
        data_table(
            ["Duration (s)", "Mean (s)", "SD (s)", "Minimum (s)", "Maximum (s)", "Mean RTF"],
            [
                [str(int(duration)), f"{mean:.3f}", f"{sd:.3f}", f"{minimum:.3f}",
                 f"{maximum:.3f}", f"{rtf:.3f}"]
                for duration, mean, sd, minimum, maximum, rtf in zip(
                    data["duration"], data["mean"], data["sd"],
                    [1.757, 5.065, 11.063], [2.614, 6.041, 12.130], data["rtf"]
                )
            ],
            [28 * mm, 30 * mm, 28 * mm, 30 * mm, 30 * mm, 32 * mm],
        ),
        Spacer(1, 7),
    ])

    captions = [
        (
            "Fig. 1. Mean transcription latency with one-standard-deviation error bars. "
            "Latency increases approximately linearly with clip duration for the measured "
            "CPU/int8 Faster-Whisper benchmark.",
            "The graph reports wall-clock time for warm transcription, including decode, "
            "VAD, language detection, segment consumption, and output construction. "
            "Model loading, NLP, persistence, and PDF generation are excluded.",
        ),
        (
            "Fig. 2. Speech-to-text real-time factor for the three measured input durations. "
            "Values below 1.0 indicate processing faster than the duration of the audio.",
            "The measured mean real-time factor remains near 0.08–0.10×, indicating that "
            "the tested CPU configuration processed each clip substantially faster than "
            "real time. This result is specific to the tested hardware and model settings.",
        ),
    ]
    for index, (graph, (caption, explanation)) in enumerate(zip(graphs, captions)):
        story.append(Image(str(graph), width=170 * mm, height=101 * mm))
        story.append(Paragraph(caption, styles["Caption"]))
        story.append(Paragraph("<b>Interpretation.</b> " + explanation, styles["Body"]))

    story.append(PageBreak())
    story.extend([
        Paragraph("Results reported as tables", styles["Section"]),
        Paragraph(
            "The repeated extraction counts and validation-stage counts are constant "
            "for this fixture. Plotting constant series would add visual weight without "
            "adding information, so they are reported as compact tables instead.",
            styles["Body"],
        ),
    ])
    stability_rows = [
        [Paragraph("<b>Run</b>", styles["TableText"]),
         Paragraph("<b>Actions</b>", styles["TableText"]),
         Paragraph("<b>Decisions</b>", styles["TableText"]),
         Paragraph("<b>Questions</b>", styles["TableText"])],
    ]
    for run in range(1, 6):
        stability_rows.append([str(run), "2", "1", "1"])
    stability_table = Table(stability_rows, colWidths=[35 * mm] * 4, repeatRows=1)
    stability_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor(GRID)),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT)]),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.extend([
        Paragraph("TABLE IV. CORE EXTRACTION COUNTS ACROSS FIVE FRESH ANALYSES", styles["Caption"]),
        stability_table,
        Spacer(1, 8),
        Paragraph(
            "The recorded Runs 1–2 retention audit also reported 2 actions, 1 decision, "
            "and 1 question at each of Generated, Parsed, Validated, Evidence matched, "
            "Deduplicated, and Persisted stages. This supports the retention claim without "
            "representing a single fixture as a general production guarantee.",
            styles["Body"],
        ),
        Paragraph("TABLE V. VALIDATION PIPELINE RETENTION", styles["Caption"]),
        data_table(
            ["Category", "Generated", "Parsed", "Validated", "Evidence matched", "Deduplicated", "Persisted"],
            [
                ["Action items", "2", "2", "2", "2", "2", "2"],
                ["Decisions", "1", "1", "1", "1", "1", "1"],
                ["Questions", "1", "1", "1", "1", "1", "1"],
                ["Follow-ups", "0", "0", "0", "0", "0", "0"],
            ],
            [31 * mm, 24 * mm, 22 * mm, 25 * mm, 32 * mm, 27 * mm, 24 * mm],
        ),
        Spacer(1, 7),
        Paragraph("TABLE VI. SUMMARIZATION METHODS", styles["Caption"]),
        data_table(
            ["Method", "Algorithm / model", "Output", "Grounding"],
            [
                ["Extractive", "TF-IDF + centroid similarity + MMR", "Source excerpts", "Direct transcript text"],
                ["Abstractive", "BART/T5-compatible Transformer", "Generated draft", "Requires human review"],
                ["Semantic", "Structured evidence extraction", "Evidence-linked bullets", "Verbatim evidence required"],
            ],
            [32 * mm, 68 * mm, 42 * mm, 36 * mm],
        ),
        Spacer(1, 7),
        Paragraph("TABLE VII. LIMITATIONS AND SAFEGUARDS", styles["Caption"]),
        data_table(
            ["Risk", "Safeguard", "Remaining limitation"],
            [
                ["Unsupported insight", "Verbatim evidence matching", "Lexical matching is not full entailment"],
                ["Re-analysis drift", "Versioned manifest and stable IDs", "Fixture-level validation only"],
                ["Speaker identity", "Preserve available labels", "No diarization for unlabeled audio"],
                ["Long transcripts", "Bounded chunks and deterministic merge", "Higher resource requirements"],
                ["Abstractive hallucination", "Extractive default and review", "Generated drafts need human review"],
            ],
            [43 * mm, 66 * mm, 69 * mm],
        ),
        Spacer(1, 7),
        Paragraph("Data provenance and reproducibility", styles["Section"]),
        Paragraph(
            "The latency and real-time-factor figures are generated directly from "
            "research_evaluation/data/transcription_summary.csv. The source benchmark "
            "records the Faster-Whisper base model, CPU execution, int8 compute, beam "
            "size 5, VAD enabled, and three repeated runs per duration. The consistency "
            "figures use the documented recorded values: five stable core extraction "
            "runs and the stored action/decision/question overlap results.",
            styles["Body"],
        ),
    ])
    rows = [[Paragraph("<b>Figure</b>", styles["TableText"]),
             Paragraph("<b>Primary source</b>", styles["TableText"]),
             Paragraph("<b>Sample</b>", styles["TableText"])]]
    for row in [
        ("Figs. 1–2", "research_evaluation/data/transcription_summary.csv", "3 durations × 3 runs"),
        ("Stability table", "REANALYSIS_CONSISTENCY_REPORT.md", "5 fresh analyses"),
        ("Tables IV–V", "REANALYSIS_CONSISTENCY_REPORT.md", "5 runs; Runs 1–2 audit"),
        ("Retention table", "REANALYSIS_CONSISTENCY_REPORT.md", "Recorded Runs 1–2 audit"),
    ]:
        rows.append([Paragraph(row[0], styles["TableText"]),
                     Paragraph(row[1], styles["TableText"]),
                     Paragraph(row[2], styles["TableText"])])
    table = Table(rows, colWidths=[30 * mm, 100 * mm, 48 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor(GRID)),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT)]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Recommended paper placement: use Figs. 1–2 in the efficiency subsection and "
        "Tables IV–VII in the evaluation and discussion subsections, and retain "
        "the full explanations in an evaluation appendix if page limits are strict.",
        styles["Note"],
    ))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = load_latency()
    graphs = [
        save_latency_graph(data),
        save_rtf_graph(data),
    ]
    build_pdf(graphs, data)
    print(f"Generated {OUTPUT}")
    print(f"Generated {len(graphs)} figures in {OUT_DIR}")


if __name__ == "__main__":
    main()
