"""总览：表数 / 关系数 / 建议数、分布、最近运行、worker 心跳。"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import (
    RELATION_KIND_LABELS,
    RELATION_KIND_ORDER,
    SUGGESTION_ROLE_LABELS,
    SUGGESTION_ROLE_ORDER,
    SUGGESTION_STATUS_LABELS,
    SUGGESTION_STATUS_ORDER,
    TABLE_DOMAIN_LABELS,
    TABLE_DOMAIN_ORDER,
)
from src.models.column_profile import ColumnProfile
from src.models.model_run import ModelRun
from src.models.model_suggestion import ModelSuggestion
from src.models.relation import Relation
from src.models.source_table import SourceTable
from src.services.model_run_service import serialize as serialize_run
from src.utils.timeutil import local_now, utcnow


def worker_alive() -> bool:
    try:
        import time

        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
        value = client.get(f"{settings.app_name}:worker:heartbeat")
        return bool(value) and (time.time() - float(value)) < 120
    except Exception:
        return False


def _ordered(rows, order, labels) -> list[dict]:
    mapping = {key: count for key, count in rows}
    return [{"key": key, "label": labels.get(key, key), "count": mapping.get(key, 0)} for key in order]


def overview(db: Session) -> dict:
    tables_total = db.scalar(select(func.count()).select_from(SourceTable)) or 0
    profiles_total = db.scalar(select(func.count()).select_from(ColumnProfile)) or 0
    relations_total = db.scalar(select(func.count()).select_from(Relation)) or 0
    latest_run = db.scalar(select(ModelRun).order_by(ModelRun.id.desc()).limit(1))
    # 建议计数聚焦最新一次剖析（历史运行的建议留档，不混入当前模型口径）
    scope = [ModelSuggestion.run_id == latest_run.id] if latest_run else []
    suggestions_total = db.scalar(select(func.count()).select_from(ModelSuggestion).where(*scope)) or 0
    pending_total = (
        db.scalar(
            select(func.count()).select_from(ModelSuggestion).where(*scope, ModelSuggestion.status == "pending")
        )
        or 0
    )
    adopted_total = (
        db.scalar(
            select(func.count()).select_from(ModelSuggestion).where(*scope, ModelSuggestion.status == "adopted")
        )
        or 0
    )

    domain_rows = db.execute(
        select(SourceTable.domain, func.count()).group_by(SourceTable.domain)
    ).all()
    kind_rows = db.execute(select(Relation.kind, func.count()).group_by(Relation.kind)).all()
    role_rows = db.execute(
        select(ModelSuggestion.role, func.count()).where(*scope).group_by(ModelSuggestion.role)
    ).all()
    status_rows = db.execute(
        select(ModelSuggestion.status, func.count()).where(*scope).group_by(ModelSuggestion.status)
    ).all()

    since = utcnow() - timedelta(days=7)
    recent_runs = db.scalars(select(ModelRun).where(ModelRun.started_at >= since)).all()
    today = local_now().date()
    trend = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        count = sum(
            1
            for run in recent_runs
            if run.started_at
            and (run.started_at + timedelta(minutes=settings.app_timezone_offset_minutes)).date() == day
        )
        trend.append({"date": day.isoformat(), "runs": count})

    metrics = (latest_run.metrics or {}) if latest_run else {}
    return {
        "tables_total": tables_total,
        "profiles_total": profiles_total,
        "relations_total": relations_total,
        "suggestions_total": suggestions_total,
        "pending_total": pending_total,
        "adopted_total": adopted_total,
        "fact_total": int(metrics.get("fact_tables") or 0),
        "dim_total": int(metrics.get("dim_tables") or 0),
        "secondary_dim_total": int(metrics.get("secondary_dims") or 0),
        "unrelated_total": int(metrics.get("unrelated_tables") or 0),
        "worker_alive": worker_alive(),
        "latest_run": serialize_run(latest_run) if latest_run else None,
        "domains": _ordered(domain_rows, TABLE_DOMAIN_ORDER, TABLE_DOMAIN_LABELS),
        "relation_kinds": _ordered(kind_rows, RELATION_KIND_ORDER, RELATION_KIND_LABELS),
        "roles": _ordered(role_rows, SUGGESTION_ROLE_ORDER, SUGGESTION_ROLE_LABELS),
        "suggestion_status": _ordered(status_rows, SUGGESTION_STATUS_ORDER, SUGGESTION_STATUS_LABELS),
        "trend": trend,
    }
