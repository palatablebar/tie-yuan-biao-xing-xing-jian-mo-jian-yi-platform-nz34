"""幂等 seed：3 账号 / 24 张贴源表 / 1 次剖析运行 / 9 条建模建议。

自然键 upsert：
  users.email
  source_tables.name
  model_runs.seed_key
  suggestions(run_id, table_id) —— 只在首次运行生成，重复执行不覆盖采纳状态
  audit_logs.seed_key

SEED_SUMMARY 行逐字稳定；连跑两次完全一致。
"""
from __future__ import annotations

from sqlalchemy import func, select

from src.config.database import session_scope
from src.models.audit import AuditLog
from src.models.model_run import ModelRun
from src.models.model_suggestion import ModelSuggestion
from src.models.source_table import SourceTable
from src.models.user import User
from src.services import model_run_service
from src.utils.security import hash_password

from scripts.demo_config import DEMO_PASSWORD, DEMO_USERS, ORG, SEED_RUNS, TABLES


def ensure_users(db) -> int:
    for email, display_name, role in DEMO_USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            db.add(
                User(
                    email=email,
                    password_hash=hash_password(DEMO_PASSWORD),
                    display_name=display_name,
                    role=role,
                    org=ORG,
                )
            )
    db.flush()
    return db.scalar(select(func.count()).select_from(User)) or 0


def ensure_tables(db) -> int:
    for spec in TABLES:
        table = db.scalar(select(SourceTable).where(SourceTable.name == spec["name"]))
        if table is None:
            table = SourceTable(
                name=spec["name"],
                cn_name=spec["cn_name"],
                subject=spec["subject"],
                domain=spec["domain"],
                row_count=spec["row_count"],
                field_count=len(spec["sample_rows"][0]) if spec["sample_rows"] else 0,
                sample_rows=spec["sample_rows"],
                note=spec["note"],
            )
            db.add(table)
        else:
            table.cn_name = spec["cn_name"]
            table.subject = spec["subject"]
            table.domain = spec["domain"]
            table.row_count = spec["row_count"]
            table.note = spec["note"]
            table.field_count = len(spec["sample_rows"][0]) if spec["sample_rows"] else table.field_count
    db.flush()
    return db.scalar(select(func.count()).select_from(SourceTable)) or 0


def ensure_runs(db) -> int:
    for seed_key, trigger, operator in SEED_RUNS:
        model_run_service.create_and_execute(
            db,
            trigger=trigger,
            operator_email=operator,
            seed_key=seed_key,
        )
    return db.scalar(select(func.count()).select_from(ModelRun)) or 0


def ensure_audit(db) -> None:
    seeds = [
        ("seed-audit-1", "admin@starmodel.io", "admin", "table.create", "source_table", {"table": "ods_sales_order_item"}),
        ("seed-audit-2", "analyst@starmodel.io", "analyst", "run.create", "model_run", {"run": "seed-run-a"}),
    ]
    for seed_key, email, role, action, entity, detail in seeds:
        exists = db.scalar(select(AuditLog).where(AuditLog.seed_key == seed_key))
        if exists is None:
            db.add(
                AuditLog(
                    actor_email=email,
                    actor_role=role,
                    action=action,
                    entity=entity,
                    detail=detail,
                    layer="seed",
                    seed_key=seed_key,
                )
            )
    db.flush()


def seed_all() -> dict:
    with session_scope() as db:
        users = ensure_users(db)
        tables = ensure_tables(db)
        runs = ensure_runs(db)
        ensure_audit(db)
        suggestions = db.scalar(select(func.count()).select_from(ModelSuggestion)) or 0
        pending = (
            db.scalar(select(func.count()).select_from(ModelSuggestion).where(ModelSuggestion.status == "pending")) or 0
        )
        summary = (
            f"SEED_SUMMARY brand=starmodel users={users} sources={tables} "
            f"runs={runs} findings={suggestions} pending={pending}"
        )
        print(summary, flush=True)
        return {"users": users, "tables": tables, "runs": runs, "suggestions": suggestions, "pending": pending}


if __name__ == "__main__":
    seed_all()
