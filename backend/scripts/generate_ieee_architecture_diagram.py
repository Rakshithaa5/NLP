"""Generate a clean IEEE-style vector architecture diagram for Meeting Analyzer."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "IEEE_Architecture_Diagram.pdf"
PAGE = landscape(A4)

BLACK = colors.HexColor("#111827")
DARK = colors.HexColor("#1F2937")
MID = colors.HexColor("#4B5563")
GRID = colors.HexColor("#9CA3AF")
LIGHT = colors.HexColor("#F3F4F6")
PALE = colors.HexColor("#F9FAFB")
ACCENT = colors.HexColor("#374151")


def centered_text(c: canvas.Canvas, text: str, x: float, y: float, size: float,
                  font: str = "Helvetica", color=BLACK) -> None:
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawCentredString(x, y, text)


def box(c: canvas.Canvas, x: float, y: float, width: float, height: float,
        title: str, lines: list[str], fill=colors.white, title_fill=LIGHT,
        title_size: float = 8.2, body_size: float = 6.8) -> None:
    c.setStrokeColor(DARK)
    c.setLineWidth(0.75)
    c.setFillColor(fill)
    c.roundRect(x, y, width, height, 2.5 * mm, stroke=1, fill=1)
    c.setFillColor(title_fill)
    c.roundRect(x, y + height - 12 * mm, width, 12 * mm, 2.5 * mm, stroke=0, fill=1)
    c.rect(x, y + height - 12 * mm, width, 2.5 * mm, stroke=0, fill=1)
    c.setStrokeColor(DARK)
    c.line(x, y + height - 12 * mm, x + width, y + height - 12 * mm)
    centered_text(c, title, x + width / 2, y + height - 7.7 * mm,
                  title_size, "Helvetica-Bold")
    line_y = y + height - 18 * mm
    for line in lines:
        centered_text(c, line, x + width / 2, line_y, body_size, "Helvetica", MID)
        line_y -= 8 * mm


def arrow(c: canvas.Canvas, x1: float, y1: float, x2: float, y2: float,
          label: str | None = None, dashed: bool = False) -> None:
    c.saveState()
    c.setStrokeColor(DARK)
    c.setFillColor(DARK)
    c.setLineWidth(0.8)
    if dashed:
        c.setDash(3, 2)
    c.line(x1, y1, x2, y2)
    angle = 0.0
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 3.2 * mm
    for offset in (2.55, -2.55):
        c.line(
            x2, y2,
            x2 - size * math.cos(angle + offset),
            y2 - size * math.sin(angle + offset),
        )
    if label:
        centered_text(c, label, (x1 + x2) / 2, (y1 + y2) / 2 + 2.5 * mm,
                      6.1, "Helvetica-Oblique", MID)
    c.restoreState()


def group(c: canvas.Canvas, x: float, y: float, width: float, height: float,
          label: str, fill=PALE, dashed: bool = False) -> None:
    c.saveState()
    c.setStrokeColor(GRID)
    c.setLineWidth(0.7)
    if dashed:
        c.setDash(4, 3)
    c.setFillColor(fill)
    c.roundRect(x, y, width, height, 3 * mm, stroke=1, fill=1)
    c.setDash()
    c.setFillColor(MID)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(x + 5 * mm, y + height - 6 * mm, label.upper())
    c.restoreState()


def build_diagram() -> None:
    c = canvas.Canvas(str(OUTPUT), pagesize=PAGE)
    width, height = PAGE
    c.setTitle("Meeting Analyzer - IEEE System Architecture")
    c.setAuthor("Meeting Analyzer")
    c.setSubject("IEEE-style architecture diagram")

    margin = 15 * mm
    centered_text(c, "MEETING ANALYZER: HYBRID NLP SYSTEM ARCHITECTURE",
                  width / 2, height - 14 * mm, 12, "Helvetica-Bold")
    centered_text(c, "Local-first speech and classical NLP with grounded semantic synthesis",
                  width / 2, height - 21 * mm, 7.5, "Helvetica-Oblique", MID)

    # Main horizontal pipeline.
    top_y = height - 57 * mm
    h = 30 * mm
    gap = 4 * mm
    x = margin
    widths = [25, 25, 26, 26, 30, 33, 30, 30]
    widths = [value * mm for value in widths]
    boxes = [
        ("INPUT", ["Audio / video", "MP4 · WAV · M4A"]),
        ("INGESTION", ["Upload + validate", "Meeting ID"]),
        ("AUDIO", ["FFmpeg", "Mono 16 kHz WAV"]),
        ("ASR", ["Faster-Whisper", "Timestamped segments"]),
        ("NLP SIGNALS", ["spaCy + NLTK", "NER · classifier · topics"]),
        ("INTELLIGENCE", ["Structured extraction", "Actions · decisions · questions"]),
        ("VALIDATION", ["Evidence matching", "Reconciliation + stable IDs"]),
        ("OUTPUT", ["Dashboard", "ReportLab PDF"]),
    ]
    positions = []
    for index, ((title, lines), w) in enumerate(zip(boxes, widths)):
        positions.append((x, top_y))
        fill = colors.white if index not in (5, 6) else LIGHT
        box(c, x, top_y, w, h, title, lines, fill=fill)
        x += w + gap
    for index in range(len(positions) - 1):
        x1 = positions[index][0] + widths[index]
        x2 = positions[index + 1][0]
        arrow(c, x1 + 1.5 * mm, top_y + h / 2, x2 - 1.5 * mm, top_y + h / 2)

    # Backend detail groups.
    backend_x = margin
    backend_y = 32 * mm
    backend_w = width - 2 * margin
    backend_h = 47 * mm
    group(c, backend_x, backend_y, backend_w, backend_h,
          "FASTAPI BACKEND  |  ASYNCHRONOUS ORCHESTRATION", fill=colors.white)

    service_y = backend_y + 10 * mm
    service_h = 25 * mm
    service_gap = 5 * mm
    service_x = backend_x + 7 * mm
    service_widths = [41, 47, 47, 47, 41]
    service_titles = [
        ("MEDIA SERVICES", ["audio.py", "transcription.py"]),
        ("CLASSICAL NLP", ["preprocessing.py", "ner.py · topics.py"]),
        ("ML CLASSIFIER", ["TF-IDF features", "Logistic Regression"]),
        ("SEMANTIC LAYER", ["semantic.py", "JSON schema extraction"]),
        ("STATE SERVICES", ["intelligence.py", "consistency.py"]),
    ]
    service_positions = []
    for (title, lines), service_width in zip(service_titles, service_widths):
        sw = service_width * mm
        service_positions.append((service_x, service_y, sw))
        box(c, service_x, service_y, sw, service_h, title, lines,
            fill=PALE, title_fill=colors.white, title_size=7.2, body_size=6.4)
        service_x += sw + service_gap

    # Persistence row.
    store_y = backend_y + 2.5 * mm
    store_h = 6 * mm
    store_x = backend_x + 7 * mm
    store_w = backend_w - 14 * mm
    c.setStrokeColor(GRID)
    c.setFillColor(LIGHT)
    c.roundRect(store_x, store_y, store_w, store_h, 1.5 * mm, stroke=1, fill=1)
    centered_text(c, "PERSISTENCE  |  Local JSON recovery  ·  Supabase analysis_results  ·  transcript / analysis manifests",
                  store_x + store_w / 2, store_y + 2.1 * mm, 6.2, "Helvetica", MID)

    # Connect top pipeline to relevant backend services.
    arrow(c, positions[2][0] + widths[2] / 2, top_y - 1 * mm,
          service_positions[0][0] + service_positions[0][2] / 2, service_y + service_h + 1 * mm,
          "media")
    arrow(c, positions[4][0] + widths[4] / 2, top_y - 1 * mm,
          service_positions[1][0] + service_positions[1][2] / 2, service_y + service_h + 1 * mm,
          "features")
    arrow(c, positions[5][0] + widths[5] / 2, top_y - 1 * mm,
          service_positions[3][0] + service_positions[3][2] / 2, service_y + service_h + 1 * mm,
          "schema")
    arrow(c, positions[6][0] + widths[6] / 2, top_y - 1 * mm,
          service_positions[4][0] + service_positions[4][2] / 2, service_y + service_h + 1 * mm,
          "state")
    arrow(c, service_positions[4][0] + service_positions[4][2] / 2, store_y + store_h + 0.5 * mm,
          store_x + store_w / 2, store_y + store_h + 0.5 * mm, "persist", dashed=True)

    # Cross-cutting guarantees.
    guarantee_y = 14 * mm
    guarantee_w = (backend_w - 8 * mm) / 3
    guarantees = [
        ("EVIDENCE GROUNDING", "Every insight requires a verbatim transcript quote and valid segment IDs."),
        ("DETERMINISTIC RE-ANALYSIS", "SHA-256 manifests, evidence-aware deduplication, and stable source-anchored IDs."),
        ("PRIVACY + RECOVERY", "Media and reports remain in controlled storage; failures preserve prior successful state."),
    ]
    for i, (title, text) in enumerate(guarantees):
        gx = margin + i * (guarantee_w + 4 * mm)
        c.setStrokeColor(DARK)
        c.setFillColor(colors.white)
        c.roundRect(gx, guarantee_y, guarantee_w, 12 * mm, 2 * mm, stroke=1, fill=1)
        centered_text(c, title, gx + guarantee_w / 2, guarantee_y + 8.2 * mm, 6.5, "Helvetica-Bold")
        centered_text(c, text[:78], gx + guarantee_w / 2, guarantee_y + 3.6 * mm, 5.3, "Helvetica", MID)

    # Figure label suitable for an IEEE paper.
    centered_text(c, "Fig. 1. End-to-end architecture of the grounded meeting intelligence pipeline.",
                  width / 2, 6.5 * mm, 7.2, "Helvetica-Oblique", DARK)
    c.showPage()
    c.save()
    print(f"Generated {OUTPUT}")


if __name__ == "__main__":
    build_diagram()
