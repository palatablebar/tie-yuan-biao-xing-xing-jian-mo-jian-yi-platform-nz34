"""建模建议：按分析版本读取；采纳 / 驳回写入只追加的 suggestion_decisions。

关键行为：
- 默认读「当前正式版」建议（关系图、导出、总览口径一致）；可传 version_id 看草案。
- 人工决定落在 suggestion_decisions（按 table_id 跟随业务对象），新版本构建时自动迁移，
  因此重跑 / 补数 / 发布都不会重置或删除人工结论。
- 采纳驳回只允许作用在「当前草案」上（对正式版的历史快照只读），保证正式版不可被悄悄改写。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import (
    SUGGESTION_ROLE_LABELS,
    SUGGESTION_STATUS_LABELS,
)
from src.models.analysis_version import AnalysisVersion
from src.models.model_suggestion import ModelSuggestion
from src.models.source_table import SourceTable
from src.models.suggestion_decision import SuggestionDecision
from src.services import analysis_version_service as version_service
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc, utcnow


def serialize(suggestion: ModelSuggestion, table: SourceTable | None = None, version_no: str | None = None) -> dict:
    return {
        "id": suggestion.id,
        "version_id": suggestion.version_id,
        "version_no": version_no,
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
        "change_kind": suggestion.change_kind,
        "evidence": suggestion.evidence or {},
        "ddl": suggestion.ddl,
        "reason": suggestion.reason,
        "adopted_by": suggestion.adopted_by,
        "adopted_at": iso_utc(suggestion.adopted_at),
        "created_at": iso_utc(suggestion.created_at),
        "updated_at": iso_utc(suggestion.updated_at),
    }


def _resolve_scope_version(db: Session, version_id: int | None) -> AnalysisVersion | None:
    if version_id is not None:
        return version_service.get_version(db, version_id)
    # 默认正式版；系统尚未发布任何版本时回退到最新草案（首启 seed 前的空窗）
    published = version_service.current_published(db)
    if published is not None:
        return published
    draft = version_service.current_draft(db)
    return draft


def list_suggestions(
    db: Session,
    *,
    version_id: int | None = None,
    role: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 40,
    offset: int = 0,
) -> dict:
    scope = _resolve_scope_version(db, version_id)
    stmt = select(ModelSuggestion)
    count_stmt = select(func.count()).select_from(ModelSuggestion)
    if scope is not None:
        stmt = stmt.where(ModelSuggestion.version_id == scope.id)
        count_stmt = count_stmt.where(ModelSuggestion.version_id == scope.id)
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
    return {
        "items": [serialize(row, tables.get(row.table_id), scope.version_no if scope else None) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "version_id": scope.id if scope else None,
        "version_no": scope.version_no if scope else None,
        "version_status": scope.status if scope else None,
    }


def get_suggestion(db: Session, suggestion_id: int) -> ModelSuggestion:
    suggestion = db.get(ModelSuggestion, suggestion_id)
    if suggestion is None:
        raise not_found("model_suggestion", suggestion_id)
    return suggestion


def detail(db: Session, suggestion_id: int) -> dict:
    suggestion = get_suggestion(db, suggestion_id)
    table = db.get(SourceTable, suggestion.table_id)
    version = db.get(AnalysisVersion, suggestion.version_id)
    return serialize(suggestion, table, version.version_no if version else None)


def _draft_for_decision(db: Session, suggestion: ModelSuggestion) -> AnalysisVersion:
    draft = version_service.current_draft(db)
    if draft is None or draft.id != suggestion.version_id:
        raise AppError(
            "CONFLICT",
            409,
            {"reason": "只能对当前草案里的建议采纳/驳回；正式版为只读快照，请先重新剖析生成草案"},
        )
    return draft


def _record_decision(
    db: Session,
    suggestion: ModelSuggestion,
    *,
    decision: str,
    actor_email: str,
) -> ModelSuggestion:
    _draft_for_decision(db, suggestion)
    # 只追加：每次人工操作新增一行决定记录，历史永不覆盖
    db.add(
        SuggestionDecision(
            table_id=suggestion.table_id,
            version_id=suggestion.version_id,
            target_name=suggestion.target_name,
            decision=decision,
            source="manual",
            decided_by=actor_email,
        )
    )
    suggestion.status = decision
    suggestion.adopted_by = actor_email
    if decision == "adopted":
        suggestion.adopted_at = utcnow()
    suggestion.updated_at = utcnow()
    db.flush()
    return suggestion


def adopt(db: Session, suggestion: ModelSuggestion, actor_email: str) -> ModelSuggestion:
    if suggestion.status == "dismissed":
        raise AppError("CONFLICT", 409, {"reason": "已驳回的建议不能直接采纳"})
    return _record_decision(db, suggestion, decision="adopted", actor_email=actor_email)


def dismiss(db: Session, suggestion: ModelSuggestion, actor_email: str) -> ModelSuggestion:
    if suggestion.status == "adopted":
        raise AppError("CONFLICT", 409, {"reason": "已采纳的建议不能驳回"})
    return _record_decision(db, suggestion, decision="dismissed", actor_email=actor_email)
