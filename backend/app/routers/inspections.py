from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import assert_can_view_inspection, farmer_of, get_current_user, require_roles
from ..models import Batch, Inspection, InspectionImage, User
from ..serializers import inspection_brief, inspection_out
from ..services import inspection_service
from ..services.report import build_pdf, compute_hash
from ..services.vision import decode_image
from ..services.vision.types import Calibration
from .standards import active_standard

router = APIRouter(prefix="/api", tags=["inspections"])


@router.post("/batches/{batch_id}/inspections", status_code=201)
def create_inspection(
    batch_id: int,
    files: list[UploadFile] = File(...),
    mm_per_pixel: float | None = Form(None),
    scene_width_mm: float | None = Form(None),
    marker_size_mm: float | None = Form(None),
    bag_rate_50kg: float | None = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    if not files or len(files) > settings.max_images:
        raise HTTPException(422, f"Upload between 1 and {settings.max_images} images")
    for v, name in ((mm_per_pixel, "mm_per_pixel"), (scene_width_mm, "scene_width_mm"), (marker_size_mm, "marker_size_mm")):
        if v is not None and v <= 0:
            raise HTTPException(422, f"{name} must be greater than 0")
    if bag_rate_50kg is not None and bag_rate_50kg <= 0:
        raise HTTPException(422, "bag_rate_50kg must be greater than 0")
    blobs: list[tuple[str, bytes]] = []
    for f in files:
        data = f.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
        if len(data) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f"{f.filename}: larger than {settings.max_upload_mb} MB")
        try:
            decode_image(data)
        except ValueError:
            raise HTTPException(422, f"{f.filename}: not a readable image")
        blobs.append((f.filename or "image", data))
    insp = inspection_service.run_inspection(
        db, batch, user, blobs, Calibration(mm_per_pixel, scene_width_mm, marker_size_mm), active_standard(db), notes,
        bag_rate_50kg)
    return inspection_out(insp)


@router.get("/inspections")
def list_inspections(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Inspection).join(Batch)
    if user.role == "farmer":
        f = farmer_of(db, user)
        q = q.filter(Batch.farmer_id == (f.id if f else -1))
    return [inspection_brief(i) for i in q.order_by(Inspection.id.desc()).limit(200).all()]


def _get(db: Session, user: User, inspection_id: int) -> Inspection:
    i = db.get(Inspection, inspection_id)
    if not i:
        raise HTTPException(404, "Report not found")
    assert_can_view_inspection(db, user, i)
    return i


@router.get("/inspections/{inspection_id}")
def get_inspection(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return inspection_out(_get(db, user, inspection_id))


@router.get("/inspections/{inspection_id}/images/{image_id}/{kind}")
def get_image(inspection_id: int, image_id: int, kind: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    insp = _get(db, user, inspection_id)
    im = db.get(InspectionImage, image_id)
    if not im or im.inspection_id != insp.id or kind not in ("original", "annotated"):
        raise HTTPException(404, "Image not found")
    path = (Path(settings.storage_dir) / (im.annotated_path if kind == "annotated" else im.original_path)).resolve()
    if not path.is_file() or Path(settings.storage_dir).resolve() not in path.parents:
        raise HTTPException(404, "Image file missing")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/inspections/{inspection_id}/report.pdf")
def report_pdf(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    insp = _get(db, user, inspection_id)
    return Response(build_pdf(insp), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{insp.report_id}.pdf"'})


@router.get("/reports/verify/{report_id}")
def verify_report(report_id: str, db: Session = Depends(get_db)):
    """Public: lets a farmer, buyer or auditor confirm a report is genuine and unmodified."""
    insp = db.query(Inspection).filter(Inspection.report_id == report_id).first()
    if not insp:
        raise HTTPException(404, "No report with that ID")
    return {
        "report_id": insp.report_id, "batch_code": insp.batch.batch_code, "decision": insp.lot_decision,
        "grade_a_pct": insp.percentages.get("grade_a"), "urs_pct": insp.percentages.get("urs"),
        "bag_rate_50kg": insp.bag_rate_50kg,
        "estimated_lot_value": round(insp.batch.quantity_kg / 50 * insp.bag_rate_50kg, 2) if insp.bag_rate_50kg is not None else None,
        "total_onions": insp.total_onions, "standard": insp.standard_label,
        "created_at": insp.created_at.isoformat(), "integrity_ok": compute_hash(insp) == insp.integrity_hash,
        "integrity_hash": insp.integrity_hash,
    }
