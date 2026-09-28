"""Orchestrates one inspection: vision -> per-onion grading -> lot decision -> persistence."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path

import cv2
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Batch, Inspection, InspectionImage, OnionResult, QualityStandard, User
from . import grading
from .report import compute_hash
from .vision import analyse_image, annotate, backend_name, decode_image
from .vision.types import Calibration


def new_report_id() -> str:
    return f"RPT-{datetime.now(timezone.utc):%y%m}-{secrets.token_hex(3).upper()}"


def run_inspection(db: Session, batch: Batch, operator: User, files: list[tuple[str, bytes]],
                   cal: Calibration, standard: QualityStandard, notes: str = "",
                   bag_rate_50kg: float | None = None) -> Inspection:
    std = standard.config
    report_id = new_report_id()
    out_dir = Path(settings.storage_dir) / report_id
    out_dir.mkdir(parents=True, exist_ok=True)

    insp = Inspection(
        report_id=report_id, batch_id=batch.id, operator_id=operator.id, standard_id=standard.id,
        standard_label=f"{standard.name} v{standard.version}", standard_snapshot=std,
        bag_rate_50kg=bag_rate_50kg,
        vision_backend=backend_name(), total_onions=0, counts={}, percentages={}, lot_decision="REJECTED",
        explanation=[], integrity_hash="", notes=notes,
    )
    db.add(insp)
    db.flush()

    all_grades: list[grading.OnionGrade] = []
    confs: list[float] = []
    warnings: list[str] = []
    excluded = 0
    number = 0

    for n, (filename, data) in enumerate(files, start=1):
        bgr = decode_image(data)
        analysis = analyse_image(bgr, cal)
        warnings += [f"Image {n}: {w}" for w in analysis.warnings]
        rel_orig, rel_ann = f"{report_id}/img{n}_original.jpg", f"{report_id}/img{n}_annotated.jpg"
        cv2.imwrite(str(Path(settings.storage_dir) / rel_orig), analysis.image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        img_row = InspectionImage(
            inspection_id=insp.id, original_path=rel_orig, annotated_path=rel_ann,
            mm_per_pixel=analysis.mm_per_pixel, calibration_method=analysis.calibration_method,
        )
        db.add(img_row)
        db.flush()

        draw_items = []
        counted_here = 0
        for obs in analysis.observations:
            number += 1
            if obs.truncated:
                excluded += 1
                draw_items.append({"contour": obs.contour, "number": number, "grade": "REJECT", "diameter_mm": obs.diameter_mm, "excluded": True})
                continue
            g = grading.grade_onion(
                grading.OnionMeasurement(obs.diameter_mm, obs.rot, obs.sprouted, obs.damage_pct, obs.discolouration_pct), std)
            all_grades.append(g)
            confs.append(obs.confidence)
            counted_here += 1
            db.add(OnionResult(
                inspection_id=insp.id, image_id=img_row.id, number=number,
                diameter_mm=round(obs.diameter_mm, 1) if obs.diameter_mm else None,
                grade=g.grade, category=g.category, confidence=obs.confidence,
                damage_pct=obs.damage_pct, discolouration_pct=obs.discolouration_pct,
                rot=obs.rot, sprouted=obs.sprouted, reasons=g.reasons, bbox=list(obs.bbox),
            ))
            draw_items.append({"contour": obs.contour, "number": number, "grade": g.grade, "diameter_mm": obs.diameter_mm, "excluded": False})
        img_row.onion_count = counted_here
        cv2.imwrite(str(Path(settings.storage_dir) / rel_ann), annotate(analysis.image, draw_items), [cv2.IMWRITE_JPEG_QUALITY, 90])

    counts, pct = grading.summarise(all_grades)
    decision, explanation, lot_warnings = grading.grade_lot(counts, pct, std)
    if excluded:
        warnings.append(f"{excluded} onion(s) touching the image edge were excluded. Keep onions fully inside the frame.")
    insp.total_onions = len(all_grades)
    insp.excluded_onions = excluded
    insp.counts, insp.percentages = counts, pct
    insp.lot_decision, insp.explanation = decision, explanation
    insp.warnings = warnings + lot_warnings
    insp.avg_confidence = round(sum(confs) / len(confs), 2) if confs else 0.0
    db.flush()
    db.refresh(insp)
    insp.integrity_hash = compute_hash(insp)
    db.commit()
    return insp
