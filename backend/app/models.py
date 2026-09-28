from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Centre(Base):
    __tablename__ = "centres"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    location: Mapped[str] = mapped_column(String(160), default="")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(16))  # admin | operator | farmer
    centre_id: Mapped[int | None] = mapped_column(ForeignKey("centres.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    centre: Mapped[Centre | None] = relationship()


class Farmer(Base):
    __tablename__ = "farmers"
    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20), default="")
    village: Mapped[str] = mapped_column(String(120), default="")
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QualityStandard(Base):
    __tablename__ = "quality_standards"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer)
    config: Mapped[dict] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id"))
    centre_id: Mapped[int | None] = mapped_column(ForeignKey("centres.id"), nullable=True)
    commodity: Mapped[str] = mapped_column(String(40), default="Onion")
    variety: Mapped[str] = mapped_column(String(60), default="Red Onion")
    quantity_kg: Mapped[float] = mapped_column(Float, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    farmer: Mapped[Farmer] = relationship()
    centre: Mapped[Centre | None] = relationship()
    inspections: Mapped[list["Inspection"]] = relationship(back_populates="batch", order_by="Inspection.id.desc()")


class Inspection(Base):
    __tablename__ = "inspections"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), index=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    standard_id: Mapped[int | None] = mapped_column(ForeignKey("quality_standards.id"), nullable=True)
    standard_label: Mapped[str] = mapped_column(String(200))
    standard_snapshot: Mapped[dict] = mapped_column(JSON)
    bag_rate_50kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    vision_backend: Mapped[str] = mapped_column(String(20))
    total_onions: Mapped[int] = mapped_column(Integer)
    excluded_onions: Mapped[int] = mapped_column(Integer, default=0)
    counts: Mapped[dict] = mapped_column(JSON)
    percentages: Mapped[dict] = mapped_column(JSON)
    lot_decision: Mapped[str] = mapped_column(String(20))  # GRADE_A | URS | REJECTED
    explanation: Mapped[list] = mapped_column(JSON)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0)
    integrity_hash: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    batch: Mapped[Batch] = relationship(back_populates="inspections")
    operator: Mapped[User | None] = relationship()
    images: Mapped[list["InspectionImage"]] = relationship(cascade="all, delete-orphan", order_by="InspectionImage.id")
    onions: Mapped[list["OnionResult"]] = relationship(cascade="all, delete-orphan", order_by="OnionResult.id")


class InspectionImage(Base):
    __tablename__ = "inspection_images"
    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id"), index=True)
    original_path: Mapped[str] = mapped_column(String(300))
    annotated_path: Mapped[str] = mapped_column(String(300))
    mm_per_pixel: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibration_method: Mapped[str] = mapped_column(String(40), default="none")
    onion_count: Mapped[int] = mapped_column(Integer, default=0)


class OnionResult(Base):
    __tablename__ = "onion_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id"), index=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("inspection_images.id"))
    number: Mapped[int] = mapped_column(Integer)
    diameter_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    grade: Mapped[str] = mapped_column(String(12))  # GRADE_A | URS | REJECT
    category: Mapped[str] = mapped_column(String(16))  # healthy|rotten|damaged|sprouted|undersized|oversized
    confidence: Mapped[float] = mapped_column(Float, default=0)
    damage_pct: Mapped[float] = mapped_column(Float, default=0)
    discolouration_pct: Mapped[float] = mapped_column(Float, default=0)
    rot: Mapped[bool] = mapped_column(Boolean, default=False)
    sprouted: Mapped[bool] = mapped_column(Boolean, default=False)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    bbox: Mapped[list] = mapped_column(JSON, default=list)
