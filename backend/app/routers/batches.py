from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import assert_can_view_batch, farmer_of, get_current_user, require_roles
from ..models import Batch, Centre, Farmer, User
from ..schemas import BatchIn
from ..serializers import batch_out

router = APIRouter(prefix="/api/batches", tags=["batches"])


def next_batch_code(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    n = (db.query(func.max(Batch.id)).scalar() or 0) + 1
    while db.query(Batch).filter(Batch.batch_code == f"ON-{year}-{n:05d}").first():
        n += 1
    return f"ON-{year}-{n:05d}"


@router.post("", status_code=201)
def create_batch(body: BatchIn, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "operator"))):
    if not db.get(Farmer, body.farmer_id):
        raise HTTPException(404, "Farmer not found")
    centre_id = user.centre_id or body.centre_id
    if centre_id and not db.get(Centre, centre_id):
        raise HTTPException(404, "Centre not found")
    b = Batch(batch_code=next_batch_code(db), farmer_id=body.farmer_id, centre_id=centre_id, commodity=body.commodity,
              variety=body.variety, quantity_kg=body.quantity_kg, created_by=user.id)
    db.add(b)
    db.commit()
    db.refresh(b)
    return batch_out(b)


@router.get("")
def list_batches(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Batch)
    if user.role == "farmer":
        f = farmer_of(db, user)
        q = q.filter(Batch.farmer_id == (f.id if f else -1))
    return [batch_out(b) for b in q.order_by(Batch.id.desc()).limit(200).all()]


@router.get("/{batch_id}")
def get_batch(batch_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    b = db.get(Batch, batch_id)
    if not b:
        raise HTTPException(404, "Batch not found")
    assert_can_view_batch(db, user, b)
    return batch_out(b)
