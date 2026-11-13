from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import EXPORT_CSV_ROLES, EXPORT_ROLES
from src.controllers import export_controller
from src.middlewares.rbac import require_roles

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/ddl.sql")
def ddl_sql(
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*EXPORT_ROLES)),
):
    return export_controller.ddl_sql(db, principal, request)


@router.get("/relations.csv")
def relations_csv(
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*EXPORT_CSV_ROLES)),
):
    return export_controller.relations_csv(db, principal, request)


@router.get("/suggestions.csv")
def suggestions_csv(
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*EXPORT_CSV_ROLES)),
):
    return export_controller.suggestions_csv(db, principal, request)
