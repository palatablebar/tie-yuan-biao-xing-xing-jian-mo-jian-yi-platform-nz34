"""字段剖析：每列的唯一率 / 空值率 / 基数 / 样本值。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class ColumnProfile(Base):
    __tablename__ = "column_profiles"
    __table_args__ = (UniqueConstraint("table_id", "column_name", name="uq_profiles_table_column"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("source_tables.id", ondelete="CASCADE"), index=True)
    column: Mapped[str] = mapped_column("column_name", String(80))
    dtype: Mapped[str] = mapped_column(String(16), default="string")
    unique_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    null_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    cardinality: Mapped[int] = mapped_column(Integer, default=0)
    sample_values: Mapped[list] = mapped_column(JSON, default=list)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
