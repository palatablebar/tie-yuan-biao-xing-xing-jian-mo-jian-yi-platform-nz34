from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import SUGGESTION_ADOPT_ROLES, SUGGESTION_REVIEW_ROLES
from src.controllers import suggestion_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.utils.pagination import page_params

router = APIRouter(prefix="/model-suggestions", tags=["model-suggestions"])


@router.get("")
def list_suggestions(
    run_id: int | None = None,
    role: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(40),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return suggestion_controller.list_suggestions(
        db, run_id=run_id, role=role, status=status, q=q, limit=page.limit, offset=page.offset
    )


@router.get("/{suggestion_id}")
def get_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return suggestion_controller.detail(db, suggestion_id)


@router.post("/{suggestion_id}/adopt")
def adopt(
    suggestion_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*SUGGESTION_ADOPT_ROLES)),
) -> dict:
    return suggestion_controller.adopt(db, suggestion_id, principal, request)


@router.post("/{suggestion_id}/dismiss")
def dismiss(
    suggestion_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*SUGGESTION_REVIEW_ROLES)),
) -> dict:
    return suggestion_controller.dismiss(db, suggestion_id, principal, request)
