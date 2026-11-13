"""运行服务：执行剖析并产出分析版本（草案），运行本身只做执行台账。

历史上 run 直接覆盖 profiles/relations/suggestions；现在改为：
run → analysis_version（草案）→ 核对通过后发布为正式版。
本模块保留 run_no / seed_key 幂等等对外契约，内部委托 analysis_version_service。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import MODEL_RUN_STATUS_LABELS, TRIGGER_LABELS
from src.models.analysis_version import AnalysisVersion
from src.models.model_run import ModelRun
from src.services import analysis_version_service as version_service
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
        "version_id": run.version_id,
        "metrics": run.metrics or {},
        "log_text": run.log_text,
        "started_at": iso_utc(run.started_at),
        "finished_at": iso_utc(run.finished_at),
    }


def next_run_no(db: Session) -> str:
    prefix = f"MR{local_now():%Y%m%d}"
    count = db.scalar(select(func.count()).select_from(ModelRun).where(ModelRun.run_no.like(f"{prefix}%"))) or 0
    return f"{prefix}-{count + 1:04d}"


def create_and_execute(
    db: Session,
    *,
    trigger: str,
    operator_email: str,
    seed_key: str | None = None,
    affected_table_ids: list[int] | None = None,
    auto_publish: bool = False,
) -> ModelRun:
    # seed 幂等：同一 seed_key 直接返回既有运行
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
    try:
        version = version_service.build_version(
            db,
            trigger=trigger,
            operator_email=operator_email,
            run_id=run.id,
            affected_table_ids=affected_table_ids,
            auto_publish=auto_publish,
        )
        run.version_id = version.id
        run.table_count = version.table_count
        run.profile_count = version.profile_count
        run.relation_count = version.relation_count
        run.suggestion_count = version.suggestion_count
        run.metrics = version.metrics or {}
        run.log_text = version.log_text
        # 复用既有草案（幂等重跑）也算成功；核对未过的版本对应 partial，便于台账区分
        if version.status == "validation_failed":
            run.status = "partial"
        elif version.suggestion_count:
            run.status = "success"
        else:
            run.status = "partial"
    except Exception as exc:  # noqa: BLE001 - 运行失败留痕，不抛 500
        run.status = "failed"
        run.log_text = f"剖析失败：{exc}"
        run.metrics = {"error": str(exc)[:300]}
    run.finished_at = utcnow()
    db.flush()
    return run


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


def latest_published_version(db: Session) -> AnalysisVersion | None:
    return version_service.current_published(db)
