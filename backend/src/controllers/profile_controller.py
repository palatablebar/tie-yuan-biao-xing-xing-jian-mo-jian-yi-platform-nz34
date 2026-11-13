"""字段剖析控制器。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.services import profile_service


def list_profiles(db: Session, **filters) -> dict:
    return profile_service.list_profiles(db, **filters)
