"""导出控制器：DDL SQL + CSV 响应 + 审计。"""
from __future__ import annotations

from fastapi import Request, Response
from sqlalchemy.orm import Session

from src.services import audit_service, export_service
from src.utils.csv_export import csv_response_headers


def ddl_sql(db: Session, principal: dict, request: Request) -> Response:
    payload = export_service.ddl_sql(db)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="export.ddl",
        entity="model_suggestion",
        entity_id=None,
        detail={"run_no": payload["run_no"], "segments": payload["segments"], "bytes": len(payload["sql"])},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return Response(
        content=payload["sql"].encode("utf-8"),
        media_type="application/sql; charset=utf-8",
        headers=csv_response_headers(payload["filename"]),
    )


def relations_csv(db: Session, principal: dict, request: Request) -> Response:
    content = export_service.relations_csv(db)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="export.relations",
        entity="relation",
        entity_id=None,
        detail={"bytes": len(content)},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers=csv_response_headers("starmodel-relations.csv"),
    )


def suggestions_csv(db: Session, principal: dict, request: Request) -> Response:
    content = export_service.suggestions_csv(db)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="export.ddl",
        entity="model_suggestion",
        entity_id=None,
        detail={"format": "csv", "bytes": len(content)},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers=csv_response_headers("starmodel-suggestions.csv"),
    )
