"""Tamper-evident hashing and PDF report generation."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..config import settings
from ..models import Inspection

DECISION_LABEL = {"GRADE_A": "Grade A lot", "URS": "URS lot", "REJECTED": "Not eligible"}
DECISION_COLOR = {"GRADE_A": "#2E7D4F", "URS": "#B36B00", "REJECTED": "#B3261E"}


def compute_hash(insp: Inspection) -> str:
    payload = {
        "report_id": insp.report_id,
        "batch": insp.batch.batch_code,
        "quantity_kg": insp.batch.quantity_kg,
        "bag_rate_50kg": insp.bag_rate_50kg,
        "standard": insp.standard_label,
        "standard_snapshot": insp.standard_snapshot,
        "counts": insp.counts,
        "decision": insp.lot_decision,
        "created_at": insp.created_at.replace(tzinfo=None).isoformat(timespec="seconds"),
        "onions": [[o.number, o.image_id, round(o.diameter_mm or 0, 1), o.grade, o.category] for o in insp.onions],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def verify_url(report_id: str) -> str:
    return f"{settings.public_base_url}/#/verify/{report_id}"


def build_pdf(insp: Inspection) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"Onion quality report {insp.report_id}")
    ss = getSampleStyleSheet()
    small = ss["BodyText"].clone("small", fontSize=8.5, leading=11)
    story = [Paragraph("Onion quality inspection report", ss["Title"]), Paragraph(f"Report ID <b>{insp.report_id}</b>", ss["BodyText"]), Spacer(1, 4)]

    b = insp.batch
    info = [
        ["Batch", b.batch_code, "Date", insp.created_at.strftime("%d %b %Y, %H:%M UTC")],
        ["Farmer", f"{b.farmer.name} ({b.farmer.farmer_code})", "Centre", b.centre.name if b.centre else "-"],
        ["Commodity", f"{b.commodity} - {b.variety}", "Quantity", f"{b.quantity_kg:g} kg"],
        ["Operator", insp.operator.full_name if insp.operator else "-", "Standard", insp.standard_label],
    ]
    if insp.bag_rate_50kg is not None:
        info.append(["Rate / 50 kg bag", f"INR {insp.bag_rate_50kg:,.2f}", "Estimated lot value",
                     f"INR {b.quantity_kg / 50 * insp.bag_rate_50kg:,.2f}"])
    t = Table(info, colWidths=[24 * mm, 62 * mm, 22 * mm, 64 * mm])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
                           ("TEXTCOLOR", (2, 0), (2, -1), colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    story += [t, Spacer(1, 8)]

    color = DECISION_COLOR[insp.lot_decision]
    story.append(Paragraph(f'<font color="{color}" size="16"><b>{DECISION_LABEL[insp.lot_decision]}</b></font>', ss["BodyText"]))
    story.append(Paragraph(f"{insp.total_onions} onions analysed ({insp.excluded_onions} cut by the image edge were excluded). "
                           f"Mean detection confidence {insp.avg_confidence:.2f}.", small))
    story.append(Spacer(1, 6))

    rows = [["Category", "Onions", "Share"]]
    labels = {"grade_a": "Grade A", "urs": "URS", "rotten": "Rotten", "damaged": "Damaged", "sprouted": "Sprouted",
              "undersized": "Undersized", "oversized": "Oversized"}
    for k, lab in labels.items():
        rows.append([lab, str(insp.counts.get(k, 0)), f"{insp.percentages.get(k, 0):.1f}%"])
    ct = Table(rows, colWidths=[60 * mm, 30 * mm, 30 * mm], hAlign="LEFT")
    ct.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAE7F0")),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CFCADB")), ("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
    story += [ct, Spacer(1, 8), Paragraph("Why this result", ss["Heading3"])]
    for e in insp.explanation:
        mark = {"pass": "&#10003;", "fail": "&#10007;", "info": "&#8226;"}[e["status"]]
        story.append(Paragraph(f"{mark} {e['text']}", small))
    for w in insp.warnings or []:
        story.append(Paragraph(f"<font color='#B36B00'>Note: {w}</font>", small))

    story += [Spacer(1, 8), Paragraph("Annotated images", ss["Heading3"])]
    for im in insp.images[:3]:
        p = settings.storage_dir / im.annotated_path
        if p.exists():
            story += [Image(str(p), width=120 * mm, height=120 * mm, kind="proportional"),
                      Paragraph(f"Calibration: {im.calibration_method}" + (f", {im.mm_per_pixel:.4f} mm/px" if im.mm_per_pixel else ""), small),
                      Spacer(1, 4)]

    story += [Paragraph("Per-onion measurements", ss["Heading3"])]
    orows = [["#", "Diameter", "Grade", "Category", "Damage", "Notes"]]
    for o in insp.onions[:60]:
        orows.append([str(o.number), f"{o.diameter_mm:.1f} mm" if o.diameter_mm else "-", o.grade.replace("_", " "),
                      o.category, f"{o.damage_pct:.1f}%", "; ".join(o.reasons)[:70]])
    ot = Table(orows, repeatRows=1, colWidths=[10 * mm, 22 * mm, 22 * mm, 24 * mm, 20 * mm, 76 * mm])
    ot.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 7.5), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAE7F0")),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CFCADB"))]))
    story.append(ot)
    if len(insp.onions) > 60:
        story.append(Paragraph(f"Showing the first 60 of {len(insp.onions)} onions. Full data is in the system.", small))

    qr = QrCodeWidget(verify_url(insp.report_id))
    x0, y0, x1, y1 = qr.getBounds()
    d = Drawing(28 * mm, 28 * mm, transform=[28 * mm / (x1 - x0), 0, 0, 28 * mm / (y1 - y0), 0, 0])
    d.add(qr)
    story += [Spacer(1, 10), d,
              Paragraph(f"Scan to verify. Integrity hash (SHA-256): <font size=6>{insp.integrity_hash}</font>", small),
              Paragraph("Generated by an AI-assisted visual inspection. Grades follow the standard version listed above.", small)]
    doc.build(story)
    return buf.getvalue()
