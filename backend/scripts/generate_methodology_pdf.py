"""Generate a clean, detailed PDF of the IEEE paper methodology section."""

from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "IEEE_RESEARCH_PAPER.md"
OUTPUT = ROOT / "Methodology_IEEE_Paper.pdf"


def inline_markup(text: str) -> str:
    """Convert the small Markdown subset used in the paper to ReportLab markup."""
    escaped = html.escape(text, quote=False)
    escaped = re.sub(
        r"\$(.+?)\$",
        lambda match: "<font name='Courier'>" + math_text(match.group(1)) + "</font>",
        escaped,
    )
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<i>\1</i>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<font name='Courier'>\1</font>", escaped)
    return escaped


def math_text(value: str) -> str:
    """Make common LaTeX notation readable in a PDF without exposing source syntax."""
    replacements = {
        r"\operatorname{": "",
        r"\mathrm{": "",
        r"\text{": "",
        r"\mathcal{": "",
        r"\left": "",
        r"\right": "",
        r"\Vert": " || ",
        r"\subseteq": " subset ",
        r"\in": " in ",
        r"\geq": " >= ",
        r"\leq": " <= ",
        r"\times": " x ",
        r"\sum": "sum ",
        r"\cos": "cos ",
        r"\max": "max ",
        r"\operatorname{Trunc}": "Trunc",
        "_{": "_",
        "^{": "^",
        "}": "",
        "{": "",
        r"\,": " ",
        r"\ ": " ",
    }
    result = value
    for source, target in replacements.items():
        result = result.replace(source, target)
    return html.escape(re.sub(r"\s+", " ", result).strip(), quote=False)


def equation_text(value: str) -> str:
    """Render a display equation as readable plain text rather than raw LaTeX."""
    return math_text(value.replace("$$", "").replace(r"\[", "").replace(r"\]", ""))


def footer(canvas, doc) -> None:
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.setLineWidth(0.5)
    canvas.line(16 * mm, 12 * mm, width - 16 * mm, 12 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(16 * mm, 7 * mm, "Meeting Analyzer | IEEE Methodology")
    canvas.drawRightString(width - 16 * mm, 7 * mm, f"Page {doc.page}")
    canvas.restoreState()


def read_methodology() -> list[str]:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "## III. Methodology")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## IV. "))
    return lines[start:end]


def build_story(styles) -> list:
    lines = read_methodology()
    story = [
        Spacer(1, 25 * mm),
        Paragraph("Meeting Analyzer", styles["CoverTitle"]),
        Paragraph("Detailed Methodology", styles["CoverSubtitle"]),
        Spacer(1, 8 * mm),
        Paragraph(
            "Grounded, deterministic, and privacy-conscious meeting intelligence "
            "using hybrid NLP and structured semantic extraction",
            styles["CoverDescription"],
        ),
        Spacer(1, 18 * mm),
        Paragraph(
            "IEEE Paper Methodology Section",
            styles["CoverMeta"],
        ),
        PageBreak(),
        Paragraph("III. Methodology", styles["PaperTitle"]),
        Paragraph(
            "This section describes the complete processing pipeline, mathematical "
            "formulation, evidence-grounding strategy, deterministic reconciliation "
            "engine, summarization methods, and reproducibility controls used by "
            "the proposed Meeting Analyzer system.",
            styles["Lead"],
        ),
    ]

    paragraph_lines: list[str] = []
    bullet_items: list[str] = []
    numbered_items: list[str] = []
    code_lines: list[str] = []
    equation_lines: list[str] = []
    in_code = False
    in_equation = False

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            text = " ".join(line.strip() for line in paragraph_lines)
            story.append(Paragraph(inline_markup(text), styles["Body"]))
            paragraph_lines = []

    def flush_lists() -> None:
        nonlocal bullet_items, numbered_items
        if bullet_items:
            story.append(
                ListFlowable(
                    [ListItem(Paragraph(inline_markup(item), styles["Body"])) for item in bullet_items],
                    bulletType="bullet",
                    bulletFontName="Helvetica",
                    bulletFontSize=7,
                    leftIndent=16,
                    bulletOffsetY=2,
                )
            )
            story.append(Spacer(1, 2))
            bullet_items = []
        if numbered_items:
            story.append(
                ListFlowable(
                    [ListItem(Paragraph(inline_markup(item), styles["Body"])) for item in numbered_items],
                    bulletType="1",
                    start="1",
                    leftIndent=19,
                )
            )
            story.append(Spacer(1, 2))
            numbered_items = []

    for raw in lines[1:]:
        line = raw.rstrip()
        if line.startswith("```"):
            flush_paragraph()
            flush_lists()
            if in_code:
                story.append(Preformatted("\n".join(code_lines), styles["PdfCode"]))
                story.append(Spacer(1, 4))
                code_lines = []
            in_code = not in_code
            continue
        if in_equation:
            equation_lines.append(line)
            if line.endswith("$$") or line.endswith(r"\]"):
                story.append(
                    Preformatted(
                        equation_text(" ".join(equation_lines)),
                        styles["PdfEquation"],
                    )
                )
                story.append(Spacer(1, 3))
                equation_lines = []
                in_equation = False
            continue
        if in_code:
            code_lines.append(line)
            continue

        if not line.strip():
            flush_paragraph()
            flush_lists()
            continue
        if line.startswith("### "):
            flush_paragraph()
            flush_lists()
            story.append(Paragraph(inline_markup(line[4:]), styles["Section"]))
            continue
        if line.startswith("#### "):
            flush_paragraph()
            flush_lists()
            story.append(Paragraph(inline_markup(line[5:]), styles["Subsection"]))
            continue
        if re.match(r"^\d+\.\s+", line):
            flush_paragraph()
            numbered_items.append(re.sub(r"^\d+\.\s+", "", line))
            continue
        if line.startswith("- "):
            flush_paragraph()
            bullet_items.append(line[2:])
            continue
        if line.startswith("$$") or line.startswith(r"\["):
            flush_paragraph()
            flush_lists()
            equation_lines = [line]
            if not (line.endswith("$$") or line.endswith(r"\]")):
                in_equation = True
            else:
                story.append(Preformatted(equation_text(line), styles["PdfEquation"]))
            continue
        if line.startswith("|"):
            flush_paragraph()
            flush_lists()
            story.append(Paragraph(inline_markup(line.replace("|", "  |  ")), styles["TableLine"]))
            continue
        if numbered_items:
            numbered_items[-1] += " " + line.strip()
        elif bullet_items:
            bullet_items[-1] += " " + line.strip()
        else:
            paragraph_lines.append(line)

    flush_paragraph()
    flush_lists()
    return story


def build_pdf() -> None:
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=32,
            textColor=colors.HexColor("#123B5D"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSubtitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontName="Helvetica",
            fontSize=20,
            leading=25,
            textColor=colors.HexColor("#256D85"),
            spaceAfter=16,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverDescription",
            parent=styles["BodyText"],
            alignment=TA_CENTER,
            fontSize=11,
            leading=17,
            textColor=colors.HexColor("#475569"),
            leftIndent=25 * mm,
            rightIndent=25 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverMeta",
            parent=styles["BodyText"],
            alignment=TA_CENTER,
            fontSize=10,
            textColor=colors.HexColor("#64748B"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="PaperTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=22,
            textColor=colors.HexColor("#123B5D"),
            spaceBefore=4,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=16,
            textColor=colors.HexColor("#123B5D"),
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Subsection",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#256D85"),
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Lead",
            parent=styles["BodyText"],
            alignment=TA_JUSTIFY,
            fontSize=10.2,
            leading=15,
            textColor=colors.HexColor("#334155"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            alignment=TA_JUSTIFY,
            fontName="Helvetica",
            fontSize=9.4,
            leading=13.7,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=6,
            splitLongWords=False,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfCode",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=7.1,
            leading=9.2,
            leftIndent=8,
            rightIndent=8,
            borderColor=colors.HexColor("#CBD5E1"),
            borderWidth=0.5,
            borderPadding=6,
            backColor=colors.HexColor("#F8FAFC"),
            spaceBefore=4,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfEquation",
            parent=styles["PdfCode"],
            fontName="Courier",
            fontSize=8,
            leading=10,
            leftIndent=14,
            textColor=colors.HexColor("#334155"),
            spaceBefore=3,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableLine",
            parent=styles["BodyText"],
            fontName="Courier",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#334155"),
            spaceAfter=1,
        )
    )

    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=17 * mm,
        bottomMargin=18 * mm,
        title="Meeting Analyzer - Detailed Methodology",
        author="Meeting Analyzer",
        subject="IEEE paper methodology",
    )
    document.build(build_story(styles), onFirstPage=footer, onLaterPages=footer)
    print(f"Generated {OUTPUT}")


if __name__ == "__main__":
    build_pdf()
