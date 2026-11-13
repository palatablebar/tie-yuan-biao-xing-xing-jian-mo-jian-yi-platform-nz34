"""运行控制器：剖析产出分析版本（草案），写领域审计。

手动 / 定时运行只生成草案；草案通过关系与粒度核对后，由管理员在版本模块发布为正式版。
"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, model_run_service


def list_runs(db: Session, **filters) -> dict:
    return model_run_service.list_runs(db, **filters)


def get_run(db: Session, run_id: int) -> dict:
    return model_run_service.serialize(model_run_service.get_run(db, run_id))


def create_run(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    run = model_run_service.create_and_execute(
        db,
        trigger=payload.get("trigger") or "manual",
        operator_email=principal["email"],
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="run.create",
        entity="model_run",
        entity_id=run.id,
        detail={
            "run_no": run.run_no,
            "version_id": run.version_id,
            "relations": run.relation_count,
            "suggestions": run.suggestion_count,
        },
        ip=request.client.host if request.client else None,
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="run.complete",
        entity="model_run",
        entity_id=run.id,
        detail={
            "status": run.status,
            "tables": run.table_count,
            "profiles": run.profile_count,
            "version_id": run.version_id,
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return model_run_service.serialize(run)
