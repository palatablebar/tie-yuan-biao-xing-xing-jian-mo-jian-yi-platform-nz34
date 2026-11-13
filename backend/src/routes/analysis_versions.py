from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import RUN_CREATE_ROLES, VERSION_RELEASE_ROLES
from src.controllers import analysis_version_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.analysis_version import IncrementalRunIn
from src.utils.pagination import page_params

router = APIRouter(prefix="/analysis-versions", tags=["analysis-versions"])


# 静态路径必须排在 /{version_id} 之前，避免被路径参数吞掉
@router.post("/incremental-run", status_code=201)
def incremental_run(
    payload: IncrementalRunIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*RUN_CREATE_ROLES)),
) -> dict:
    return analysis_version_controller.create_incremental_run(
        db, payload.model_dump(), principal, request
    )


@router.get("")
def list_versions(
    status: str | None = None,
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return analysis_version_controller.list_versions(
        db, status=status, limit=page.limit, offset=page.offset
    )


@router.get("/{version_id}")
def get_version(
    version_id: int,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return analysis_version_controller.get_version(db, version_id)


@router.get("/{version_id}/diff")
def get_version_diff(
    version_id: int,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return analysis_version_controller.get_diff(db, version_id)


@router.post("/{version_id}/revalidate")
def revalidate(
    version_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*RUN_CREATE_ROLES)),
) -> dict:
    return analysis_version_controller.revalidate(db, version_id, principal, request)


@router.post("/{version_id}/publish")
def publish(
    version_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*VERSION_RELEASE_ROLES)),
) -> dict:
    return analysis_version_controller.publish(db, version_id, principal, request)
