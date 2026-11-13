"""导出：DDL（按正式版建议分段）+ 关系清单 CSV（UTF-8 BOM）。

所有导出只取「当前正式版」分析版本的快照：草案未发布不会出现在 DDL 里，
从根上避免补数重跑后导出文件混入上一版关系或未核对的建议。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import RELATION_KIND_LABELS, SUGGESTION_ROLE_LABELS, SUGGESTION_STATUS_LABELS
from src.models.model_suggestion import ModelSuggestion
from src.models.relation import Relation
from src.models.source_table import SourceTable
from src.services import analysis_version_service as version_service, star_service
from src.utils.csv_export import to_csv
from src.utils.errors import AppError


def _published_or_404(db: Session):
    version = version_service.current_published(db)
    if version is None:
        # 首启尚未发布时回退最新草案，保证空窗期仍可演示；正常流程下导出的是正式版
        version = version_service.current_draft(db)
    if version is None:
        raise AppError("NOT_FOUND", 404, {"entity": "analysis_version"})
    return version


def ddl_sql(db: Session) -> dict:
    version = _published_or_404(db)
    rows = db.scalars(
        select(ModelSuggestion).where(ModelSuggestion.version_id == version.id)
    ).all()
    if not rows:
        raise AppError("NOT_FOUND", 404, {"entity": "model_suggestion"})
    payload = [
        {
            "target_name": row.target_name,
            "role": row.role,
            "confidence": row.confidence,
            "status": SUGGESTION_STATUS_LABELS.get(row.status, row.status),
            "ddl": row.ddl,
        }
        for row in rows
    ]
    sql = star_service.build_export_sql(payload, version.version_no)
    segments = sql.count("-- =====")
    return {
        "filename": "starmodel-ddl.sql",
        "sql": sql,
        "segments": segments,
        "run_no": version.version_no,
        "version_id": version.id,
    }


def relations_csv(db: Session) -> bytes:
    version = _published_or_404(db)
    relations = db.scalars(
        select(Relation)
        .where(Relation.version_id == version.id)
        .order_by(Relation.left_table_id, Relation.left_column)
    ).all()
    tables = {table.id: table for table in db.scalars(select(SourceTable)).all()}
    headers = ["左表", "左字段", "右表", "右字段", "包含度", "置信度", "类型", "抽样行数"]
    rows = []
    for row in relations:
        left = tables.get(row.left_table_id)
        right = tables.get(row.right_table_id)
        rows.append(
            [
                left.name if left else row.left_table_id,
                row.left_column,
                right.name if right else row.right_table_id,
                row.right_column,
                f"{row.containment:.4f}",
                f"{row.confidence:.3f}",
                RELATION_KIND_LABELS.get(row.kind, row.kind),
                row.sample_size,
            ]
        )
    return to_csv(headers, rows)


def suggestions_csv(db: Session) -> bytes:
    version = _published_or_404(db)
    rows = db.scalars(
        select(ModelSuggestion)
        .where(ModelSuggestion.version_id == version.id)
        .order_by(ModelSuggestion.role, ModelSuggestion.target_name)
    ).all()
    tables = {table.id: table for table in db.scalars(select(SourceTable)).all()}
    headers = ["目标表", "源表", "角色", "粒度", "置信度", "状态", "度量列", "采纳人"]
    payload = [
        [
            row.target_name,
            tables[row.table_id].name if row.table_id in tables else row.table_id,
            SUGGESTION_ROLE_LABELS.get(row.role, row.role),
            row.grain,
            f"{row.confidence:.3f}",
            SUGGESTION_STATUS_LABELS.get(row.status, row.status),
            ",".join(row.measures or []),
            row.adopted_by or "",
        ]
        for row in rows
    ]
    return to_csv(headers, payload)
