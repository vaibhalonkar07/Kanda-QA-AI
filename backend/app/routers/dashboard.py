from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import farmer_of, get_current_user
from ..models import Batch, Inspection, User
from ..serializers import inspection_brief

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    bq, iq = db.query(Batch), db.query(Inspection).join(Batch)
    if user.role == "farmer":
        f = farmer_of(db, user)
        fid = f.id if f else -1
        bq, iq = bq.filter(Batch.farmer_id == fid), iq.filter(Batch.farmer_id == fid)
    inspections = iq.order_by(Inspection.id.desc()).all()
    n = len(inspections)
    onions = sum(i.total_onions for i in inspections)
    grade_a = sum(i.counts.get("grade_a", 0) for i in inspections)
    urs = sum(i.counts.get("urs", 0) for i in inspections)
    return {
        "batches": bq.count(), "inspections": n, "onions_analysed": onions,
        "grade_a_pct": round(100 * grade_a / onions, 1) if onions else 0,
        "urs_pct": round(100 * urs / onions, 1) if onions else 0,
        "defective_pct": round(100 * (onions - grade_a - urs) / onions, 1) if onions else 0,
        "decisions": dict(Counter(i.lot_decision for i in inspections)),
        "recent": [inspection_brief(i) for i in inspections[:8]],
    }
