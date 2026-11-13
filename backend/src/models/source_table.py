"""贴源表：业务库同步过来的表结构 + 抽样行（24 张：4 事实候选 / 12 维 / 8 无关）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class SourceTable(Base):
    __tablename__ = "source_tables"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    cn_name: Mapped[str] = mapped_column(String(120))
    subject: Mapped[str] = mapped_column(String(40), default="")
    domain: Mapped[str] = mapped_column(String(20), default="sales", index=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    field_count: Mapped[int] = mapped_column(Integer, default=0)
    sample_rows: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
