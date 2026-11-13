from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import relation_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.utils.pagination import page_params

router = APIRouter(prefix="/relations", tags=["relations"])


@router.get("")
def list_relations(
    kind: str | None = None,
    limit: int = Query(60),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return relation_controller.list_relations(db, kind=kind, limit=page.limit, offset=page.offset)


@router.get("/graph")
def graph(db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))) -> dict:
    return relation_controller.graph(db)
