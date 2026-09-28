from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Farmer, User
from ..schemas import FarmerRegisterIn, LoginIn, UserCreateIn
from ..security import create_token, hash_password, verify_password
from ..serializers import user_out
from .farmers import next_farmer_code

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username.strip().lower()).first()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong username or password")
    return {"access_token": create_token(user.id, user.role), "token_type": "bearer", "user": user_out(user)}


@router.post("/register-farmer", status_code=201)
def register_farmer(body: FarmerRegisterIn, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(409, "That username is taken")
    user = User(username=username, full_name=body.full_name, password_hash=hash_password(body.password), role="farmer")
    db.add(user)
    db.flush()
    db.add(Farmer(farmer_code=next_farmer_code(db), name=body.full_name, phone=body.phone, village=body.village, user_id=user.id))
    db.commit()
    return {"access_token": create_token(user.id, user.role), "token_type": "bearer", "user": user_out(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.post("/users", status_code=201)
def create_user(body: UserCreateIn, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    username = body.username.strip().lower()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(409, "That username is taken")
    u = User(username=username, full_name=body.full_name, password_hash=hash_password(body.password), role=body.role, centre_id=body.centre_id)
    db.add(u)
    db.commit()
    return user_out(u)


@router.get("/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    return [user_out(u) for u in db.query(User).order_by(User.id).all()]
