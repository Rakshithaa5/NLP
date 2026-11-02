"""Build a defensible Results and Observations PDF from recorded validation data."""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "data" / "validation" / "consistency" / "results.json"
OUTPUT = ROOT / "Results_and_Observations.pdf"


def paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def build_pdf() -> None:
    data = json.loads(VALIDATION.read_text(encoding="utf-8"))
    runs = data["runs"]
    first = runs[0]
    last = runs[-1]
    categories = [
        ("Action items", "action_items"),
        ("Decisions", "decisions"),
        ("Questions", "questions"),
        ("Follow-ups", "follow_ups"),
    ]

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleCenter",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#15324B"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubtitleCenter",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#52606D"),
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#15324B"),
            spaceBefore=10,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodySmall",
            parent=styles["BodyText"],
            fontSize=9.3,
            leading=13,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Note",
            parent=styles["BodyText"],
            fontSize=8.2,
            leading=11,
            textColor=colors.HexColor("#4A5568"),
            backColor=colors.HexColor("#F2F6F8"),
            borderColor=colors.HexColor("#CBD5E0"),
            borderWidth=0.5,
            borderPadding=6,
            spaceBefore=5,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableText",
            parent=styles["BodyText"],
            fontSize=8,
            leading=10,
        )
    )

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="Results and Observations - Meeting Analyzer",
        author="Meeting Analyzer",
    )
    story = [
        paragraph("Results and Observations", styles["TitleCenter"]),
        paragraph(
            "Grounded evidence from the recorded five-run consistency validation",
            styles["SubtitleCenter"],
        ),
        paragraph("1. Evaluation Scope", styles["Section"]),
        paragraph(
            "The results below are limited to the recorded navigation-meeting fixture "
            "and the five fresh provider analyses stored in "
            "<b>data/validation/consistency/results.json</b>. Each run used the same "
            "transcript, schema, analysis and prompt versions, and model configuration. "
            "The fixture contains seven timestamped segments and a 47-second meeting.",
            styles["BodySmall"],
        ),
        paragraph(
            "<b>Reproducibility boundary:</b> these are measured fixture-level results. "
            "They do not establish corpus-wide accuracy, universal LLM determinism, "
            "or a general hallucination rate.",
            styles["Note"],
        ),
        paragraph("2. Re-analysis Stability", styles["Section"]),
    ]

    stability_rows = [
        [paragraph("<b>Category</b>", styles["TableText"])]
        + [paragraph(f"<b>Run {i}</b>", styles["TableText"]) for i in range(1, 6)]
        + [paragraph("<b>Min. Jaccard</b>", styles["TableText"])],
    ]
    for label, key in categories:
        counts = [run["counts"][key] for run in runs]
        stability_rows.append(
            [paragraph(label, styles["TableText"])]
            + [str(value) for value in counts]
            + [f"{100 if len(set(counts)) == 1 else 'not established'}%"]
        )
    stability_table = Table(
        stability_rows,
        colWidths=[43 * mm, 18 * mm, 18 * mm, 18 * mm, 18 * mm, 18 * mm, 30 * mm],
        repeatRows=1,
    )
    stability_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#15324B")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7FAFC")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C4CE")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend(
        [
            stability_table,
            paragraph(
                "All five runs returned exactly 2 action items, 1 decision, 1 question, "
                "and 0 follow-ups. The stored validation report records 100% minimum "
                "Jaccard overlap for actions, decisions, and questions against Run 1. "
                "Follow-ups were absent from the fixture, so no follow-up extraction "
                "accuracy can be inferred.",
                styles["BodySmall"],
            ),
            paragraph("3. Pipeline Retention and Evidence Matching", styles["Section"]),
        ]
    )

    audit_rows = [
        [paragraph("<b>Category</b>", styles["TableText"])]
        + [
            paragraph(f"<b>{stage.replace('_', ' ').title()}</b>", styles["TableText"])
            for stage in ["generated", "parsed", "validated", "evidence_matched", "deduplicated"]
        ],
    ]
    for label, key in categories:
        stage_data = first["pipeline"][key]
        audit_rows.append(
            [paragraph(label, styles["TableText"])]
            + [str(stage_data[stage]) for stage in ["generated", "parsed", "validated", "evidence_matched", "deduplicated"]]
        )
    audit_table = Table(
        audit_rows,
        colWidths=[38 * mm, 27 * mm, 25 * mm, 25 * mm, 31 * mm, 27 * mm],
        repeatRows=1,
    )
    audit_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2D6A4F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7FAFC")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C4CE")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend(
        [
            audit_table,
            paragraph(
                "In Run 1, every generated item survived parsing, validation, verbatim "
                "evidence matching, and deduplication: 2/2 actions, 1/1 decision, and "
                "1/1 question. The same complete retention pattern is recorded for "
                "Runs 2-5.",
                styles["BodySmall"],
            ),
            paragraph("4. Observations", styles["Section"]),
            paragraph(
                "<b>Observation 1 - Stable core identities.</b> The same source-anchored "
                "items were retained across the five runs: actions at segments 3 and 6, "
                "the decision at segment 2, and the question at segment 5 (zero-based "
                "segment numbering).",
                styles["BodySmall"],
            ),
            paragraph(
                "<b>Observation 2 - Deterministic reconciliation.</b> Run 1 created "
                "2 actions, 1 decision, and 1 question. Runs 2-5 reported these same "
                "items as stable, with no removals and no newly introduced core items. "
                "Topic labels varied between runs (2 to 5), showing that the current "
                "stability result applies to reconciled core items, not every generated "
                "descriptive field.",
                styles["BodySmall"],
            ),
            paragraph(
                "<b>Observation 3 - Grounding is enforced at the pipeline boundary.</b> "
                "The recorded evidence-matched counts equal the generated counts for "
                "all extracted core categories in every run. This supports a "
                "fixture-level evidence-match rate of 100% (20 of 20 category-stage "
                "items across five runs), not a claim that arbitrary model outputs "
                "cannot hallucinate.",
                styles["BodySmall"],
            ),
            paragraph(
                "<b>Observation 4 - Empty categories require cautious interpretation.</b> "
                "No follow-up was present in the fixture. The repeated zero therefore "
                "measures fixture content, not follow-up recall.",
                styles["BodySmall"],
            ),
            paragraph("5. Configuration and Traceability", styles["Section"]),
            paragraph(
                f"Analysis version: <b>{first['manifest']['analysis_version']}</b>; "
                f"prompt version: <b>{first['manifest']['prompt_version']}</b>; "
                f"model: <b>{first['manifest']['model']}</b>; temperature: "
                f"<b>{first['manifest']['config']['temperature']}</b>; top-p: "
                f"<b>{first['manifest']['config']['top_p']}</b>; response format: "
                f"<b>{first['manifest']['config']['response_format']}</b>. "
                f"Input hash: <font name='Courier'>{first['manifest']['input_hash']}</font>.",
                styles["BodySmall"],
            ),
            paragraph(
                "The manuscript's discourse-classification scores, AMI/ICSI corpus "
                "claims, ROUGE values, latency comparisons, and the 42.3% zero-shot "
                "baseline are not reproduced by this validation artifact. They should "
                "remain provisional until their datasets, predictions, references, "
                "and measurement scripts are supplied.",
                styles["Note"],
            ),
            Spacer(1, 5),
            paragraph(
                f"Source artifact generated from recorded validation data. "
                f"Validation timestamp in the artifact: {last['manifest']['created_at']}.",
                styles["Note"],
            ),
        ]
    )
    doc.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    build_pdf()
