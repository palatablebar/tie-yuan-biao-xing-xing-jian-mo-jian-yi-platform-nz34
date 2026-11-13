"""星型建模建议（版本快照）：每张事实 / 维度表一条，含粒度、关联、置信度与 DDL。

建议从属于分析版本而非运行：同一业务对象在不同版本各有一条快照，
人工采纳 / 驳回状态由 suggestion_decisions 迁移而来（status 为缓存值，
发布与重跑时按业务对象 table_id 重新套用，不会被重置）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class ModelSuggestion(Base):
    __tablename__ = "model_suggestions"
    __table_args__ = (UniqueConstraint("version_id", "table_id", name="uq_suggestions_version_table"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_versions.id", ondelete="CASCADE"), index=True
    )
    table_id: Mapped[int] = mapped_column(ForeignKey("source_tables.id", ondelete="CASCADE"), index=True)
    target_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(8), default="dim", index=True)
    grain: Mapped[str] = mapped_column(String(200), default="")
    joins: Mapped[list] = mapped_column(JSON, default=list)
    measures: Mapped[list] = mapped_column(JSON, default=list)
    attributes: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    # pending / adopted / dismissed：由 suggestion_decisions 按 table_id 迁移的缓存值
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    ddl: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    # 相对上一正式版的差异：added / changed / removed / unchanged（发布时落定）
    change_kind: Mapped[str] = mapped_column(String(12), default="unchanged", index=True)
    # 本版依据：粒度去重计数、外键包含度等量化口径（与 reason 互补，供页面展示）
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    adopted_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    adopted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
