"""人工决定：对某业务对象（贴源表）建模建议的采纳 / 驳回，独立于版本长期保存。

关键约束：
1. 决定跟随业务对象迁移——重跑 / 补数产生新版本时，按 table_id 把最近一次决定
   套用到新版本的建议上，人工结论不丢、不被重置为 pending。
2. 只追加不覆盖：每次人工操作新增一行（版本留痕），查询取该 table_id 最新一条；
   因此重复剖析、草案发布、回滚都不会误删任何历史决定。同一版本同一表允许
   先迁移后人工改判（多条记录，id 最大者生效），迁移逻辑自行去重。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class SuggestionDecision(Base):
    __tablename__ = "suggestion_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("source_tables.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_versions.id", ondelete="CASCADE"), index=True
    )
    # 产生该决定时建议的目标表名，留痕用
    target_name: Mapped[str] = mapped_column(String(80), default="")
    decision: Mapped[str] = mapped_column(String(16), index=True)  # adopted / dismissed
    # manual：页面人工操作；migrated：新版本构建时按业务对象迁移的历史决定
    source: Mapped[str] = mapped_column(String(12), default="manual")
    decided_by: Mapped[str] = mapped_column(String(160))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
