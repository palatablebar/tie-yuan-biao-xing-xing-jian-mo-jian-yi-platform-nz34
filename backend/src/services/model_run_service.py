"""运行服务：剖析 → 包含依赖 → 星型建议 → 落库（全部由后端计算）。"""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.constants.enums import MODEL_RUN_STATUS_LABELS, TRIGGER_LABELS
from src.models.column_profile import ColumnProfile
from src.models.model_run import ModelRun
from src.models.model_suggestion import ModelSuggestion
from src.models.relation import Relation
from src.models.source_table import SourceTable
from src.services import profiling_service, star_service
from src.utils.errors import AppError
from src.utils.timeutil import iso_utc, local_now, utcnow


def serialize(run: ModelRun) -> dict:
    return {
        "id": run.id,
        "run_no": run.run_no,
        "trigger": run.trigger,
        "trigger_label": TRIGGER_LABELS.get(run.trigger, run.trigger),
        "status": run.status,
        "status_label": MODEL_RUN_STATUS_LABELS.get(run.status, run.status),
        "operator_email": run.operator_email,
        "table_count": run.table_count,
        "profile_count": run.profile_count,
        "relation_count": run.relation_count,
        "suggestion_count": run.suggestion_count,
        "metrics": run.metrics or {},
        "log_text": run.log_text,
        "started_at": iso_utc(run.started_at),
        "finished_at": iso_utc(run.finished_at),
    }


def next_run_no(db: Session) -> str:
    prefix = f"MR{local_now():%Y%m%d}"
    count = db.scalar(select(func.count()).select_from(ModelRun).where(ModelRun.run_no.like(f"{prefix}%"))) or 0
    return f"{prefix}-{count + 1:04d}"


def _persist_profiles(db: Session, table_id: int, profiles: list[dict]) -> None:
    db.execute(delete(ColumnProfile).where(ColumnProfile.table_id == table_id))
    for profile in profiles:
        db.add(
            ColumnProfile(
                table_id=table_id,
                column=profile["column"],
                dtype=profile["dtype"],
                unique_ratio=profile["unique_ratio"],
                null_ratio=profile["null_ratio"],
                cardinality=profile["cardinality"],
                sample_values=profile["sample_values"],
                sample_size=profile["sample_size"],
            )
        )
    db.flush()


def _persist_relations(db: Session, relations: list[dict]) -> None:
    db.execute(delete(Relation))
    for relation in relations:
        db.add(Relation(**relation))
    db.flush()


def _persist_suggestions(db: Session, run_id: int, suggestions: list[dict]) -> None:
    db.execute(delete(ModelSuggestion).where(ModelSuggestion.run_id == run_id))
    for suggestion in suggestions:
        db.add(
            ModelSuggestion(
                run_id=run_id,
                table_id=suggestion["table_id"],
                target_name=suggestion["target_name"],
                role=suggestion["role"],
                grain=suggestion["grain"],
                joins=suggestion["joins"],
                measures=suggestion["measures"],
                attributes=suggestion["attributes"],
                confidence=suggestion["confidence"],
                status="pending",
                ddl=suggestion["ddl"],
                reason=suggestion["reason"],
            )
        )
    db.flush()


def execute_run(db: Session, run: ModelRun) -> ModelRun:
    run.status = "running"
    try:
        tables = db.scalars(select(SourceTable).order_by(SourceTable.id)).all()
        table_dicts = [
            {
                "id": table.id,
                "name": table.name,
                "cn_name": table.cn_name,
                "subject": table.subject,
                "domain": table.domain,
                "row_count": table.row_count,
                "sample_rows": table.sample_rows or [],
            }
            for table in tables
        ]
        profiling = profiling_service.profile_tables(table_dicts)
        profile_rows: list[dict] = []
        for table in table_dicts:
            profiles = profiling["profiles"][table["id"]]
            _persist_profiles(db, table["id"], profiles)
            source = db.get(SourceTable, table["id"])
            if source is not None:
                source.field_count = len(profiles)
                source.scanned_at = utcnow()
            profile_rows.extend({"table_id": table["id"], **profile} for profile in profiles)

        discovery = profiling_service.discover_relations(profile_rows)
        _persist_relations(db, discovery["relations"])

        rows_by_table = {table["id"]: table["sample_rows"] for table in table_dicts}
        built = star_service.build_suggestions(
            table_dicts, profile_rows, discovery["relations"], rows_by_table
        )
        _persist_suggestions(db, run.id, built["suggestions"])

        classified = built["classified"]
        fact_count = sum(1 for item in classified if item["role"] == star_service.ROLE_FACT)
        dim_count = sum(1 for item in classified if item["role"] == star_service.ROLE_DIM)
        none_count = sum(1 for item in classified if item["role"] == star_service.ROLE_NONE)
        grain = {
            suggestion["target_name"]: suggestion["grain_combos"]
            for suggestion in built["suggestions"]
            if suggestion["role"] == star_service.ROLE_FACT
        }
        confidences = [float(item["confidence"]) for item in discovery["relations"]]
        metrics = {
            "tables": len(table_dicts),
            "profiles": profiling["total"],
            "pk_candidates": len(profiling_service.candidate_keys(profile_rows)),
            "relation_candidates": discovery["rejected"] + len(discovery["relations"]),
            "relations": len(discovery["relations"]),
            "rejected_pairs": discovery["rejected"],
            "unique_columns": discovery["unique_columns"],
            "fact_tables": fact_count,
            "dim_tables": dim_count,
            "unrelated_tables": none_count,
            "secondary_dims": len(built["secondary_dim_tables"]),
            "suggestions": len(built["suggestions"]),
            "avg_relation_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
            "grain_combos": grain,
            "primary_dims": built["primary_dim_tables"],
        }
        run.table_count = len(table_dicts)
        run.profile_count = profiling["total"]
        run.relation_count = len(discovery["relations"])
        run.suggestion_count = len(built["suggestions"])
        run.metrics = metrics
        run.log_text = (
            f"剖析 {len(table_dicts)} 张表 / {profiling['total']} 个字段；"
            f"发现 {metrics['relations']} 条包含依赖（拒绝 {metrics['rejected_pairs']} 对同名候选）；"
            f"判定 {fact_count} 张事实表、{dim_count} 张维表、{none_count} 张无关表；"
            f"生成 {len(built['suggestions'])} 条建模建议（二级维 {len(built['secondary_dim_tables'])} 张不单独建议）。"
        )
        run.status = "success" if built["suggestions"] else "partial"
    except Exception as exc:  # noqa: BLE001 - 运行失败留痕，不抛 500
        run.status = "failed"
        run.log_text = f"剖析失败：{exc}"
        run.metrics = {"error": str(exc)[:300]}
    run.finished_at = utcnow()
    db.flush()
    return run


def create_and_execute(
    db: Session,
    *,
    trigger: str,
    operator_email: str,
    seed_key: str | None = None,
) -> ModelRun:
    if seed_key:
        existing = db.scalar(select(ModelRun).where(ModelRun.seed_key == seed_key))
        if existing is not None:
            return existing
    run = ModelRun(
        run_no=next_run_no(db),
        trigger=trigger,
        status="running",
        operator_email=operator_email,
        seed_key=seed_key,
    )
    db.add(run)
    db.flush()
    return execute_run(db, run)


def list_runs(db: Session, status: str | None, limit: int, offset: int) -> dict:
    stmt = select(ModelRun)
    count_stmt = select(func.count()).select_from(ModelRun)
    if status:
        stmt = stmt.where(ModelRun.status == status)
        count_stmt = count_stmt.where(ModelRun.status == status)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(ModelRun.id.desc()).limit(limit).offset(offset)).all()
    return {"items": [serialize(row) for row in rows], "total": total, "limit": limit, "offset": offset}


def get_run(db: Session, run_id: int) -> ModelRun:
    run = db.get(ModelRun, run_id)
    if run is None:
        raise AppError("NOT_FOUND", 404, {"entity": "model_run", "id": run_id})
    return run
