from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import profile_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.utils.pagination import page_params

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("")
def list_profiles(
    table_id: int | None = None,
    q: str | None = None,
    dtype: str | None = None,
    limit: int = Query(40),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return profile_controller.list_profiles(
        db, table_id=table_id, q=q, dtype=dtype, limit=page.limit, offset=page.offset
    )
