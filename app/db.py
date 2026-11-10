from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.types import JSON

from app.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class AnalysisRecord(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(160), index=True)
    title: Mapped[str] = mapped_column(String(200))
    original_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview: Mapped[str] = mapped_column(String(300))
    reliability_score: Mapped[int] = mapped_column(Integer)
    hallucination_risk_score: Mapped[int] = mapped_column(Integer)
    decision_confidence: Mapped[int] = mapped_column(Integer)
    total_claims: Mapped[int] = mapped_column(Integer)
    supported_claims: Mapped[int] = mapped_column(Integer)
    contradicted_claims: Mapped[int] = mapped_column(Integer)
    uncertain_claims: Mapped[int] = mapped_column(Integer)
    unverifiable_claims: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40))
    source_type: Mapped[str] = mapped_column(String(80))
    verification_mode: Mapped[str] = mapped_column(String(40))
    score_type: Mapped[str] = mapped_column(String(30), default="heuristic")
    claims: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def db_session() -> Session:
    return SessionLocal()
