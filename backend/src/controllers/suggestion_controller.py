"""建议控制器：采纳（admin）/ 驳回（analyst + admin）。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, suggestion_service


def list_suggestions(db: Session, **filters) -> dict:
    return suggestion_service.list_suggestions(db, **filters)


def detail(db: Session, suggestion_id: int) -> dict:
    return suggestion_service.detail(db, suggestion_id)


def adopt(db: Session, suggestion_id: int, principal: dict, request: Request) -> dict:
    suggestion = suggestion_service.get_suggestion(db, suggestion_id)
    suggestion_service.adopt(db, suggestion, principal["email"])
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="suggestion.adopt",
        entity="model_suggestion",
        entity_id=suggestion.id,
        detail={"target": suggestion.target_name, "role": suggestion.role, "confidence": suggestion.confidence},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return suggestion_service.detail(db, suggestion_id)


def dismiss(db: Session, suggestion_id: int, principal: dict, request: Request) -> dict:
    suggestion = suggestion_service.get_suggestion(db, suggestion_id)
    suggestion_service.dismiss(db, suggestion, principal["email"])
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="suggestion.dismiss",
        entity="model_suggestion",
        entity_id=suggestion.id,
        detail={"target": suggestion.target_name},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return suggestion_service.detail(db, suggestion_id)
