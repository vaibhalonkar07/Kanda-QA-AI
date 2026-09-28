from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import QualityStandard, User
from ..schemas import StandardIn
from ..services.grading import validate_standard

router = APIRouter(prefix="/api/standards", tags=["standards"])


def _out(s: QualityStandard) -> dict:
    return {"id": s.id, "name": s.name, "version": s.version, "config": s.config, "is_active": s.is_active,
            "created_at": s.created_at.isoformat()}


def active_standard(db: Session) -> QualityStandard:
    s = db.query(QualityStandard).filter(QualityStandard.is_active.is_(True)).order_by(QualityStandard.id.desc()).first()
    if not s:
        raise HTTPException(409, "No active quality standard. Ask an admin to publish one")
    return s


@router.get("")
def list_standards(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [_out(s) for s in db.query(QualityStandard).order_by(QualityStandard.id.desc()).all()]


@router.get("/active")
def get_active(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return _out(active_standard(db))


@router.post("", status_code=201)
def publish(body: StandardIn, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    try:
        cfg = validate_standard(body.config)
    except ValueError as e:
        raise HTTPException(422, f"Invalid standard: {e}")
    version = (db.query(func.max(QualityStandard.version)).scalar() or 0) + 1
    if body.activate:
        db.query(QualityStandard).update({QualityStandard.is_active: False})
    s = QualityStandard(name=body.name, version=version, config=cfg, is_active=body.activate, created_by=user.id)
    db.add(s)
    db.commit()
    return _out(s)


@router.post("/{standard_id}/activate")
def activate(standard_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    s = db.get(QualityStandard, standard_id)
    if not s:
        raise HTTPException(404, "Standard not found")
    db.query(QualityStandard).update({QualityStandard.is_active: False})
    s.is_active = True
    db.commit()
    return _out(s)
