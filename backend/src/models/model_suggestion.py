"""星型建模建议：每张事实 / 维度表一条，含粒度、关联、置信度与 DDL。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class ModelSuggestion(Base):
    __tablename__ = "model_suggestions"
    __table_args__ = (UniqueConstraint("run_id", "table_id", name="uq_suggestions_run_table"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("model_runs.id", ondelete="CASCADE"), index=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("source_tables.id", ondelete="CASCADE"), index=True)
    target_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(8), default="dim", index=True)
    grain: Mapped[str] = mapped_column(String(200), default="")
    joins: Mapped[list] = mapped_column(JSON, default=list)
    measures: Mapped[list] = mapped_column(JSON, default=list)
    attributes: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    ddl: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    adopted_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    adopted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
