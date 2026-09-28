from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def ensure_schema_compatibility() -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("inspections")}
    if "bag_rate_50kg" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE inspections ADD COLUMN bag_rate_50kg FLOAT"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
