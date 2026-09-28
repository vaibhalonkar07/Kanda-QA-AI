from sqlalchemy.orm import Session

from .config import settings
from .models import Centre, Farmer, QualityStandard, User
from .security import hash_password
from .services.grading import default_standard


def seed(db: Session) -> None:
    if not db.query(QualityStandard).first():
        db.add(QualityStandard(name="Onion procurement standard (illustrative)", version=1, config=default_standard(), is_active=True))
    if settings.seed_demo and not db.query(User).first():
        c = Centre(name="Demo Procurement Centre", location="Nashik, Maharashtra")
        db.add(c)
        db.flush()
        db.add_all([
            User(username="admin", full_name="Centre Admin", password_hash=hash_password("Admin@12345"), role="admin", centre_id=c.id),
            User(username="operator1", full_name="Demo Operator", password_hash=hash_password("Operator@12345"), role="operator", centre_id=c.id),
        ])
        fu = User(username="farmer1", full_name="Rahul Patil", password_hash=hash_password("Farmer@12345"), role="farmer")
        db.add(fu)
        db.flush()
        db.add(Farmer(farmer_code="FRM1001", name="Rahul Patil", phone="9000000001", village="Niphad", user_id=fu.id))
    db.commit()
