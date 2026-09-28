from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..models import Farmer
from ..schemas import FarmerIn
from ..serializers import farmer_out

router = APIRouter(prefix="/api/farmers", tags=["farmers"])


def next_farmer_code(db: Session) -> str:
    n = (db.query(func.max(Farmer.id)).scalar() or 0) + 1
    while db.query(Farmer).filter(Farmer.farmer_code == f"FRM{1000 + n}").first():
        n += 1
    return f"FRM{1000 + n}"


@router.post("", status_code=201)
def create_farmer(body: FarmerIn, db: Session = Depends(get_db), _=Depends(require_roles("admin", "operator"))):
    f = Farmer(farmer_code=next_farmer_code(db), name=body.name, phone=body.phone, village=body.village)
    db.add(f)
    db.commit()
    return farmer_out(f)


@router.get("")
def list_farmers(q: str = "", db: Session = Depends(get_db), _=Depends(require_roles("admin", "operator"))):
    query = db.query(Farmer)
    if q:
        like = f"%{q}%"
        query = query.filter(Farmer.name.ilike(like) | Farmer.farmer_code.ilike(like) | Farmer.phone.ilike(like))
    return [farmer_out(f) for f in query.order_by(Farmer.id.desc()).limit(200).all()]
