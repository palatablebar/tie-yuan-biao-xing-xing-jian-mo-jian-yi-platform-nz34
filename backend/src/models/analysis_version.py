"""分析版本：一次剖析产出的可比较、可重跑草案；通过核对后发布为正式版。

- draft：草案，剖析/补数的产物，页面可查看差异与本版依据，但不进入关系图与 DDL 导出。
- published：正式版，同一时刻至多一个；发布在单个事务内完成，失败回滚到上一正式版。
- validation_failed：草案在关系与粒度核对环节未通过，保留留档，不影响当前正式版。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class AnalysisVersion(Base):
    __tablename__ = "analysis_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    trigger: Mapped[str] = mapped_column(String(20), default="manual")
    operator_email: Mapped[str] = mapped_column(String(160), default="system")
    base_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_versions.id", ondelete="SET NULL"), nullable=True
    )
    # 链式增量时的直接上一草案（血缘链）；base_version_id 始终锚定被替换的正式版
    parent_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_versions.id", ondelete="SET NULL"), nullable=True
    )
    # 补数增量场景：本版只重算受影响的源表，其余对象沿用上一版快照
    affected_table_ids: Mapped[list] = mapped_column(JSON, default=list)
    # 全部贴源表（name + row_count + sample_rows）的内容指纹：输入不变时重跑直接复用草案
    input_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    table_count: Mapped[int] = mapped_column(Integer, default=0)
    profile_count: Mapped[int] = mapped_column(Integer, default=0)
    relation_count: Mapped[int] = mapped_column(Integer, default=0)
    suggestion_count: Mapped[int] = mapped_column(Integer, default=0)
    # 关系与粒度核对结果：{passed, checks: [...], failed_checks: [...]}
    validation: Mapped[dict] = mapped_column(JSON, default=dict)
    # 与上一正式版的差异摘要：{suggestions: {added, changed, removed, unchanged}, relations: {...}}
    diff_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    log_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
