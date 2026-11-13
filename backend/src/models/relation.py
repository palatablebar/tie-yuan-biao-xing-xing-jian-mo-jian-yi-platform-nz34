"""关系：同名列包含依赖发现出的主外键边（seed 稳定 18 条）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Relation(Base):
    __tablename__ = "relations"
    __table_args__ = (
        UniqueConstraint("left_table_id", "left_column", "right_table_id", "right_column", name="uq_relations_edge"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    left_table_id: Mapped[int] = mapped_column(ForeignKey("source_tables.id", ondelete="CASCADE"), index=True)
    left_column: Mapped[str] = mapped_column(String(80))
    right_table_id: Mapped[int] = mapped_column(ForeignKey("source_tables.id", ondelete="CASCADE"), index=True)
    right_column: Mapped[str] = mapped_column(String(80))
    containment: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    kind: Mapped[str] = mapped_column(String(12), default="pk-fk", index=True)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
