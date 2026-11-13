from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import TABLE_WRITE_ROLES
from src.controllers import source_table_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.source_table import TableIn
from src.utils.pagination import page_params

router = APIRouter(prefix="/source-tables", tags=["source-tables"])


@router.get("")
def list_tables(
    q: str | None = None,
    domain: str | None = None,
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return source_table_controller.list_tables(db, q=q, domain=domain, limit=page.limit, offset=page.offset)


@router.get("/{table_id}")
def get_table(
    table_id: int,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return source_table_controller.detail(db, table_id)


@router.post("", status_code=201)
def create_table(
    payload: TableIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*TABLE_WRITE_ROLES)),
) -> dict:
    return source_table_controller.create_table(db, payload.model_dump(), principal, request)
