"""字段剖析查询（锚定当前正式版分析版本，避免跨版本返回同一列的多份快照）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.column_profile import ColumnProfile
from src.models.source_table import SourceTable
from src.services import analysis_version_service as version_service
from src.services.source_table_service import serialize_profile


def list_profiles(
    db: Session,
    *,
    table_id: int | None = None,
    q: str | None = None,
    dtype: str | None = None,
    limit: int = 40,
    offset: int = 0,
) -> dict:
    version = version_service.current_published(db) or version_service.current_draft(db)
    stmt = select(ColumnProfile)
    count_stmt = select(func.count()).select_from(ColumnProfile)
    if version is not None:
        stmt = stmt.where(ColumnProfile.version_id == version.id)
        count_stmt = count_stmt.where(ColumnProfile.version_id == version.id)
    if table_id:
        stmt = stmt.where(ColumnProfile.table_id == table_id)
        count_stmt = count_stmt.where(ColumnProfile.table_id == table_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(ColumnProfile.column.ilike(like))
        count_stmt = count_stmt.where(ColumnProfile.column.ilike(like))
    if dtype:
        stmt = stmt.where(ColumnProfile.dtype == dtype)
        count_stmt = count_stmt.where(ColumnProfile.dtype == dtype)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(ColumnProfile.table_id, ColumnProfile.id).limit(limit).offset(offset)).all()
    names = {table.id: table.cn_name for table in db.scalars(select(SourceTable)).all()}
    return {
        "items": [{**serialize_profile(row), "table_name": names.get(row.table_id)} for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "version_id": version.id if version else None,
    }
