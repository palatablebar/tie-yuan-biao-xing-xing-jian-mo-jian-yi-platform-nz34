"""贴源表控制器：登记写操作记领域审计。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, source_table_service


def list_tables(db: Session, **filters) -> dict:
    return source_table_service.list_tables(db, **filters)


def detail(db: Session, table_id: int) -> dict:
    return source_table_service.detail(db, table_id)


def create_table(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    table = source_table_service.create_table(db, payload)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="table.create",
        entity="source_table",
        entity_id=table.id,
        detail={"name": table.name, "columns": table.field_count},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return source_table_service.serialize(table, table.field_count)
