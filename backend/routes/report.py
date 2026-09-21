"""
routes/report.py — PDF report generation endpoint.

GET  /api/report/{file_id}/pdf
  Fetches the stored analysis results for file_id from Supabase,
  generates a comprehensive PDF report using ReportLab, and returns
  it as a downloadable file response.

Report sections:
  1. Cover page — meeting title, date, metadata stats
  2. Executive Summary — abstractive (preferred) or extractive fallback
  3. Action Items — person / task / deadline / status table
  4. Decisions — numbered list of clean decision statements
  5. Questions raised — numbered list
  6. Key Topics — TF-IDF keywords + topic cluster overview
  7. Named Entities — grouped by type (PERSON, ORG, DATE, …)
  8. Full Transcript — paginated raw text appendix

Phase 4: full implementation.
"""

import logging
from datetime import datetime, timezone
from io import BytesIO
from html import escape

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger("meeting_analyzer.report")

router = APIRouter()


# ── DB helper ──────────────────────────────────────────────────────────────────

def _get_db():
    """Return Supabase client or None if not configured."""
    try:
        from backend.db import get_client  # noqa: PLC0415
        return get_client()
    except Exception as exc:
        logger.warning("DB unavailable: %s", exc)
        return None


def _fetch_report_data(file_id: str) -> dict:
    """
    Fetch meeting metadata + full analysis payload from Supabase.
    Raises HTTPException(404) if meeting or analysis not found.
    """
    from backend.services.meeting_store import load_meeting, read_local
    meeting = load_meeting(file_id, _get_db())
    local = read_local(file_id, "analysis.json")
    if meeting and local:
        return {"meeting": {**meeting, "duration_sec": meeting.get("duration"), "transcript": meeting.get("full_text", "")},
                "analysis": {**local, "summary_extractive": local.get("summary", {}).get("extractive", ""),
                             "summary_abstractive": local.get("summary", {}).get("abstractive", "")}}
    db = _get_db()
    if not db:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable — cannot generate report.",
        )

    # Meeting metadata
    try:
        m_row = (
            db.table("meetings")
            .select("filename, duration_sec, language, uploaded_at, transcript")
            .eq("id", file_id)
            .single()
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Meeting '{file_id}' not found: {exc}",
        )

    if not m_row.data:
        raise HTTPException(status_code=404, detail=f"Meeting '{file_id}' not found.")

    # Analysis results
    try:
        a_row = (
            db.table("analysis_results")
            .select(
                "entities, topics, classifications, "
                "action_items, decisions, questions, "
                "summary_extractive, summary_abstractive, analyzed_at"
            )
            .eq("id", file_id)
            .single()
            .execute()
        )
    except Exception:
        a_row = type("_", (), {"data": None})()

    return {
        "meeting":  m_row.data,
        "analysis": a_row.data or {},
    }


# ── ReportLab PDF builder ──────────────────────────────────────────────────────

def _build_pdf(file_id: str, data: dict) -> bytes:
    """
    Build a multi-section PDF report using ReportLab.

    Returns raw PDF bytes.
    """
    from reportlab.lib.pagesizes import A4                              # noqa: PLC0415
    from reportlab.lib.units import mm                                  # noqa: PLC0415
    from reportlab.lib import colors                                    # noqa: PLC0415
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # noqa: PLC0415
    from reportlab.platypus import (                                    # noqa: PLC0415
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak,
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER                  # noqa: PLC0415

    meeting  = data["meeting"]
    analysis = data["analysis"]

    filename    = meeting.get("filename") or "Meeting Recording"
    duration    = meeting.get("duration_sec", 0)
    language    = (meeting.get("language") or "").upper()
    uploaded_at = meeting.get("uploaded_at", "")
    transcript  = meeting.get("transcript", "")

    action_items = analysis.get("action_items", []) or []
    decisions    = analysis.get("decisions", [])    or []
    questions    = analysis.get("questions", [])    or []
    entities     = analysis.get("entities", [])     or []
    topics       = analysis.get("topics", {})       or {}
    summary_abs  = analysis.get("summary_abstractive", "")
    summary_ext  = analysis.get("summary_extractive",  "")
    analyzed_at  = analysis.get("analyzed_at", "")

    intelligence = analysis.get("intelligence") or topics.get("intelligence")
    if isinstance(intelligence, dict) and intelligence.get("version") == 2:
        action_items = [{**item, "person": item.get("owner"), "original": item.get("evidence", "")}
                        for item in intelligence.get("action_items", [])]
        decisions = [{**item, "statement": item.get("decision", ""), "original": item.get("evidence", "")}
                     for item in intelligence.get("decisions", [])]
        questions = [{**item, "resolution_status": item.get("status", "Not assessed"), "original": item.get("evidence", "")}
                     for item in intelligence.get("questions", [])]
        highlights = list(intelligence.get("summary", []))
        if intelligence.get("key_takeaway"):
            highlights.append("Key takeaway: " + intelligence["key_takeaway"])
        summary_ext = " ".join(highlights)

    if isinstance(intelligence, dict):
        topics = {"discussion": intelligence.get("topics", [])}
        labels = {"people": "PERSON", "organizations": "ORG", "dates": "DATE",
                  "locations": "LOCATION", "products": "TECHNOLOGY"}
        entities = [{"text": text, "label": labels[group]}
                    for group, values in intelligence.get("entities", {}).items()
                    if group in labels for text in values]

    summary = summary_ext or "No transcript excerpt summary available. Re-analyse this meeting."

    # ── Style setup ───────────────────────────────────────────────────────────
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    base = getSampleStyleSheet()

    def style(name, **kw):
        s = base[name].clone(name + "_custom")
        for k, v in kw.items():
            setattr(s, k, v)
        return s

    # Colour palette
    INDIGO  = colors.HexColor("#6366f1")
    CYAN    = colors.HexColor("#06b6d4")
    SLATE   = colors.HexColor("#0f172a")
    MUTED   = colors.HexColor("#94a3b8")
    SURFACE = colors.HexColor("#1e293b")
    TEXT    = colors.HexColor("#f1f5f9")
    AMBER   = colors.HexColor("#f59e0b")
    GREEN   = colors.HexColor("#10b981")
    RED     = colors.HexColor("#ef4444")

    title_style  = style("Title",  textColor=INDIGO,  fontSize=26, spaceAfter=6, alignment=TA_CENTER)
    h1_style     = style("h1",     textColor=INDIGO,  fontSize=16, spaceBefore=14, spaceAfter=6)
    h2_style     = style("h2",     textColor=CYAN,    fontSize=12, spaceBefore=10, spaceAfter=4)
    body_style   = style("Normal", textColor=MUTED,   fontSize=10, leading=15)
    label_style  = style("Normal", textColor=TEXT,    fontSize=9,  fontName="Helvetica-Bold")
    muted_style  = style("Normal", textColor=MUTED,   fontSize=9)
    center_style = style("Normal", textColor=MUTED,   fontSize=10, alignment=TA_CENTER)

    def hr():
        return HRFlowable(width="100%", thickness=0.5, color=SURFACE, spaceAfter=8, spaceBefore=4)

    def section(title):
        return [Spacer(1, 6), Paragraph(title, h1_style), hr()]

    def fmtdur(s):
        if not s:
            return "—"
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = int(s % 60)
        return f"{h}h {m:02d}m {sec:02d}s" if h else f"{m}m {sec:02d}s"

    def fmtdate(iso):
        if not iso:
            return "—"
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return dt.strftime("%d %b %Y, %H:%M UTC")
        except Exception:
            return iso

    # ── Story (content elements) ──────────────────────────────────────────────
    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph("Meeting Intelligence Report", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(escape(filename), style("Normal", textColor=TEXT, fontSize=13, alignment=TA_CENTER)))
    story.append(Spacer(1, 10))

    meta_data = [
        ["File ID",      file_id[:24] + "…" if len(file_id) > 24 else file_id],
        ["Duration",     fmtdur(duration)],
        ["Language",     language or "—"],
        ["Uploaded",     fmtdate(uploaded_at)],
        ["Analysed",     fmtdate(analyzed_at)],
        ["Action Items", str(len(action_items))],
        ["Decisions",    str(len(decisions))],
        ["Questions",    str(len(questions))],
    ]
    meta_table = Table(meta_data, colWidths=[50 * mm, 110 * mm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (0, -1), SURFACE),
        ("TEXTCOLOR",    (0, 0), (0, -1), CYAN),
        ("TEXTCOLOR",    (1, 0), (1, -1), TEXT),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("FONTNAME",     (0, 0), (0, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#0f172a"), colors.HexColor("#0c1527")]),
        ("ROUNDEDCORNERS", [4]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#1e293b")),
    ]))
    story.append(meta_table)
    story.append(PageBreak())

    # ── Executive Summary ──────────────────────────────────────────────────────
    story += section("Executive Summary")
    story.append(Paragraph(escape(summary), body_style))
    story.append(Spacer(1, 8))


    # ── Action Items ──────────────────────────────────────────────────────────
    story += section(f"Action Items ({len(action_items)})")
    if not action_items:
        story.append(Paragraph("No action items detected.", muted_style))
    else:
        tbl_data = [["Person", "Task", "Deadline", "Status"]]
        for a in action_items:
            status = a.get("status", "Pending")
            status_color = {"Completed": GREEN, "In Progress": AMBER, "Blocked": RED}.get(status, MUTED)
            tbl_data.append([
                a.get("person") or "—",
                Paragraph(escape(a.get("task") or a.get("original", "")), body_style),
                a.get("deadline") or "—",
                status,
            ])
        tbl = Table(tbl_data, colWidths=[35 * mm, 80 * mm, 35 * mm, 20 * mm])
        tbl_style = [
            ("BACKGROUND",   (0, 0), (-1, 0),  INDIGO),
            ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#0f172a"), colors.HexColor("#0c1527")]),
            ("TEXTCOLOR",    (0, 1), (-1, -1), MUTED),
            ("GRID",         (0, 0), (-1, -1), 0.3, colors.HexColor("#1e293b")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ]
        # Colour status column per value
        for i, a in enumerate(action_items, start=1):
            status = a.get("status", "Pending")
            c = {"Completed": GREEN, "In Progress": AMBER, "Blocked": RED}.get(status, MUTED)
            tbl_style.append(("TEXTCOLOR", (3, i), (3, i), c))
        tbl.setStyle(TableStyle(tbl_style))
        story.append(tbl)

    story.append(Spacer(1, 10))

    # ── Decisions ─────────────────────────────────────────────────────────────
    story += section(f"Decisions ({len(decisions)})")
    if not decisions:
        story.append(Paragraph("No decisions detected.", muted_style))
    else:
        for i, d in enumerate(decisions, 1):
            stmt = d.get("statement", d.get("original", ""))
            story.append(Paragraph(f"<b>{i}.</b> {escape(stmt)}", body_style))
            story.append(Spacer(1, 3))

    # ── Questions raised ───────────────────────────────────────────────────
    story += section(f"Questions raised ({len(questions)})")
    if not questions:
        story.append(Paragraph("No questions detected.", muted_style))
    else:
        for i, q in enumerate(questions, 1):
            q_text = q.get("question", q.get("original", ""))
            flag = " ⚡ <i>Action required</i>" if q.get("is_action_required") else ""
            story.append(Paragraph(f"<b>{i}.</b> {escape(q_text)} (Resolution: {escape(q.get('resolution_status', 'Not assessed'))}){flag}", body_style))
            if q.get("answer"):
                story.append(Paragraph("Answer: " + escape(q["answer"]), body_style))
            story.append(Spacer(1, 3))

    # ── Key Topics ────────────────────────────────────────────────────────────
    story += section("Key Topics")
    discussion = topics.get("discussion", [])
    for topic in discussion:
        story.append(Paragraph(escape(topic.get("label", "")), body_style))
    if not discussion:
        story.append(Paragraph("No reliable discussion topics identified.", muted_style))

    # ── Named Entities ────────────────────────────────────────────────────────
    story += section("Named Entities")
    if not entities:
        story.append(Paragraph("No entities detected.", muted_style))
    else:
        # Group by label
        grouped: dict[str, list[str]] = {}
        for e in entities:
            grouped.setdefault(e["label"], []).append(e["text"])

        for label, texts in sorted(grouped.items()):
            story.append(Paragraph(f"<b>{label}:</b> {escape(', '.join(texts))}", body_style))
            story.append(Spacer(1, 3))

    # ── Full Transcript ───────────────────────────────────────────────────────
    if transcript:
        story.append(PageBreak())
        story += section("Full Transcript")
        # Chunk to avoid single huge paragraph
        chunks = [transcript[i:i+2000] for i in range(0, len(transcript), 2000)]
        for chunk in chunks:
            story.append(Paragraph(escape(chunk), muted_style))
            story.append(Spacer(1, 6))

    # ── Build ─────────────────────────────────────────────────────────────────
    doc.build(story)
    return buf.getvalue()


# ── GET /api/report/{file_id}/pdf ─────────────────────────────────────────────

@router.get(
    "/{file_id}/pdf",
    summary="Download meeting intelligence report as PDF",
)
async def download_pdf(file_id: str):
    """
    Generate and stream a comprehensive PDF report for the analysed meeting.

    The report includes:
      - Cover page with meeting metadata
      - Executive summary (abstractive preferred, extractive fallback)
      - Action items table (person / task / deadline / status)
      - Decisions list
      - Unresolved questions list
      - Key topics (TF-IDF keywords + topic clusters)
      - Named entities grouped by type
      - Full transcript appendix

    Requires ReportLab to be installed (pip install reportlab).
    Requires the meeting to have been uploaded AND analysed first.
    """
    logger.info("PDF report requested for meeting [%s]", file_id)

    # Fetch data
    data = _fetch_report_data(file_id)

    # Build PDF
    try:
        pdf_bytes = _build_pdf(file_id, data)
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="ReportLab not installed. Run: pip install reportlab",
        )
    except Exception as exc:
        logger.exception("PDF generation failed for [%s]: %s", file_id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation error: {exc}",
        )

    filename = (data["meeting"].get("filename") or "meeting").rsplit(".", 1)[0]
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in filename)
    disposition = f'attachment; filename="{safe_name}_report.pdf"'

    logger.info("PDF generated for [%s] — %d bytes", file_id, len(pdf_bytes))

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": disposition},
    )
