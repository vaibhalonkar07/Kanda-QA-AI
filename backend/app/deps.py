import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import Batch, Farmer, Inspection, User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue")
    try:
        payload = decode_token(cred.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Sign in again")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or disabled")
    return user


def require_roles(*roles: str):
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this action")
        return user
    return dep


def farmer_of(db: Session, user: User) -> Farmer | None:
    return db.query(Farmer).filter(Farmer.user_id == user.id).first()


def assert_can_view_batch(db: Session, user: User, batch: Batch) -> None:
    if user.role == "farmer":
        f = farmer_of(db, user)
        if not f or f.id != batch.farmer_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")


def assert_can_view_inspection(db: Session, user: User, insp: Inspection) -> None:
    assert_can_view_batch(db, user, insp.batch)
