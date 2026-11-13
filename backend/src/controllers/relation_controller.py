"""关系 / 关系图控制器。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.services import relation_service


def list_relations(db: Session, **filters) -> dict:
    return relation_service.list_relations(db, **filters)


def graph(db: Session, scope: str | None = None) -> dict:
    return relation_service.graph(db, scope=scope)
