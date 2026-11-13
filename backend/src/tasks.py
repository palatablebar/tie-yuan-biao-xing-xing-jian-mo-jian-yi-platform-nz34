"""Celery 任务：心跳 + 每日剖析（重跑一次全库剖析与星型建议）。"""
from __future__ import annotations

import time

from src.config.celery_app import TASK_DAILY, TASK_HEARTBEAT, celery_app
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("tasks")


def _redis():
    import redis

    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


@celery_app.task(name=TASK_HEARTBEAT)
def heartbeat() -> str:
    try:
        _redis().set(f"{settings.app_name}:worker:heartbeat", time.time())
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat failed: %s", exc)
        return "error"


@celery_app.task(name=TASK_DAILY)
def daily_refresh() -> dict:
    """每天 07:40 重跑剖析，产出一个待核对的分析版本（草案）；不自动发布，正式版保持不变。"""
    from src.config.database import session_scope
    from src.services import audit_service, model_run_service

    operator = "scheduler@" + settings.app_name + ".io"
    with session_scope() as db:
        run = model_run_service.create_and_execute(db, trigger="schedule", operator_email=operator)
        audit_service.record(
            db,
            actor_email=operator,
            actor_role="admin",
            action="run.create",
            entity="model_run",
            entity_id=run.id,
            detail={
                "trigger": "schedule",
                "run_no": run.run_no,
                "version_id": run.version_id,
                "relations": run.relation_count,
                "suggestions": run.suggestion_count,
            },
            layer="worker",
        )
    logger.info(
        "daily profiling finished: run=%s version=%s relations=%s",
        run.run_no,
        run.version_id,
        run.relation_count,
    )
    return {"run_no": run.run_no, "version_id": run.version_id, "relations": run.relation_count}
