"""建模建议：列表 / 详情 / 采纳 / 驳回（状态不因重跑被覆盖）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import (
    SUGGESTION_ROLE_LABELS,
    SUGGESTION_STATUS_LABELS,
)
from src.models.model_run import ModelRun
from src.models.model_suggestion import ModelSuggestion
from src.models.source_table import SourceTable
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc, utcnow


def serialize(suggestion: ModelSuggestion, table: SourceTable | None = None, run_no: str | None = None) -> dict:
    return {
        "id": suggestion.id,
        "run_id": suggestion.run_id,
        "run_no": run_no,
        "table_id": suggestion.table_id,
        "table_name": table.name if table else None,
        "table_cn_name": table.cn_name if table else None,
        "target_name": suggestion.target_name,
        "role": suggestion.role,
        "role_label": SUGGESTION_ROLE_LABELS.get(suggestion.role, suggestion.role),
        "grain": suggestion.grain,
        "joins": suggestion.joins or [],
        "measures": suggestion.measures or [],
        "attributes": suggestion.attributes or [],
        "confidence": suggestion.confidence,
        "status": suggestion.status,
        "status_label": SUGGESTION_STATUS_LABELS.get(suggestion.status, suggestion.status),
        "ddl": suggestion.ddl,
        "reason": suggestion.reason,
        "adopted_by": suggestion.adopted_by,
        "adopted_at": iso_utc(suggestion.adopted_at),
        "created_at": iso_utc(suggestion.created_at),
        "updated_at": iso_utc(suggestion.updated_at),
    }


def latest_run_id(db: Session) -> int | None:
    run = db.scalar(select(ModelRun).order_by(ModelRun.id.desc()).limit(1))
    return run.id if run else None


def list_suggestions(
    db: Session,
    *,
    run_id: int | None = None,
    role: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 40,
    offset: int = 0,
) -> dict:
    # 默认只看最新一次剖析：重跑后旧建议仍留档，但界面与导出聚焦当前模型
    run_id = run_id or latest_run_id(db)
    stmt = select(ModelSuggestion)
    count_stmt = select(func.count()).select_from(ModelSuggestion)
    if run_id:
        stmt = stmt.where(ModelSuggestion.run_id == run_id)
        count_stmt = count_stmt.where(ModelSuggestion.run_id == run_id)
    if role:
        stmt = stmt.where(ModelSuggestion.role == role)
        count_stmt = count_stmt.where(ModelSuggestion.role == role)
    if status:
        stmt = stmt.where(ModelSuggestion.status == status)
        count_stmt = count_stmt.where(ModelSuggestion.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(ModelSuggestion.target_name.ilike(like) | ModelSuggestion.grain.ilike(like))
        count_stmt = count_stmt.where(
            ModelSuggestion.target_name.ilike(like) | ModelSuggestion.grain.ilike(like)
        )
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(ModelSuggestion.role, ModelSuggestion.target_name).limit(limit).offset(offset)
    ).all()
    tables = {table.id: table for table in db.scalars(select(SourceTable)).all()}
    runs = {run.id: run.run_no for run in db.scalars(select(ModelRun)).all()}
    return {
        "items": [serialize(row, tables.get(row.table_id), runs.get(row.run_id)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "run_id": run_id,
    }


def get_suggestion(db: Session, suggestion_id: int) -> ModelSuggestion:
    suggestion = db.get(ModelSuggestion, suggestion_id)
    if suggestion is None:
        raise not_found("model_suggestion", suggestion_id)
    return suggestion


def detail(db: Session, suggestion_id: int) -> dict:
    suggestion = get_suggestion(db, suggestion_id)
    table = db.get(SourceTable, suggestion.table_id)
    run = db.get(ModelRun, suggestion.run_id)
    return serialize(suggestion, table, run.run_no if run else None)


def adopt(db: Session, suggestion: ModelSuggestion, actor_email: str) -> ModelSuggestion:
    if suggestion.status == "dismissed":
        raise AppError("CONFLICT", 409, {"reason": "已驳回的建议不能直接采纳"})
    suggestion.status = "adopted"
    suggestion.adopted_by = actor_email
    suggestion.adopted_at = utcnow()
    suggestion.updated_at = utcnow()
    db.flush()
    return suggestion


def dismiss(db: Session, suggestion: ModelSuggestion, actor_email: str) -> ModelSuggestion:
    if suggestion.status == "adopted":
        raise AppError("CONFLICT", 409, {"reason": "已采纳的建议不能驳回"})
    suggestion.status = "dismissed"
    suggestion.adopted_by = actor_email
    suggestion.updated_at = utcnow()
    db.flush()
    return suggestion
