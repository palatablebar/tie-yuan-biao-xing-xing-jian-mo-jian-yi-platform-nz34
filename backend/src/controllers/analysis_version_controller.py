"""分析版本控制器：草案列表 / 详情 / 差异 / 重核对 / 发布（事务性切换）+ 审计。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import analysis_version_service as version_service
from src.services import audit_service, model_run_service


def list_versions(db: Session, **filters) -> dict:
    return version_service.list_versions(db, **filters)


def get_version(db: Session, version_id: int) -> dict:
    return version_service.serialize(version_service.get_version(db, version_id))


def get_diff(db: Session, version_id: int) -> dict:
    return version_service.version_diff(db, version_id)


def revalidate(db: Session, version_id: int, principal: dict, request: Request) -> dict:
    version = version_service.revalidate(db, version_id)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="version.revalidate",
        entity="analysis_version",
        entity_id=version.id,
        detail={"version_no": version.version_no, "passed": (version.validation or {}).get("passed")},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return version_service.serialize(version)


def publish(db: Session, version_id: int, principal: dict, request: Request) -> dict:
    # 发布在单事务内切换：service 抛错则整体回滚，上一正式版保持可用
    version = version_service.publish_version(db, version_id, principal["email"])
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="version.publish",
        entity="analysis_version",
        entity_id=version.id,
        detail={
            "version_no": version.version_no,
            "relations": version.relation_count,
            "suggestions": version.suggestion_count,
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return version_service.serialize(version)


def create_incremental_run(
    db: Session,
    payload: dict,
    principal: dict,
    request: Request,
) -> dict:
    """补数入口：只重算 payload.affected_table_ids 内的业务对象，其余建议沿用上一正式版。"""
    affected = payload.get("affected_table_ids") or []
    run = model_run_service.create_and_execute(
        db,
        trigger="incremental",
        operator_email=principal["email"],
        affected_table_ids=affected,
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="run.incremental",
        entity="model_run",
        entity_id=run.id,
        detail={
            "run_no": run.run_no,
            "affected_table_ids": affected,
            "version_id": run.version_id,
            "relations": run.relation_count,
            "suggestions": run.suggestion_count,
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return model_run_service.serialize(run)
