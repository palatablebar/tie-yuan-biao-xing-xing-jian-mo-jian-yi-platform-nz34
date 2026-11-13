"""贴源表服务：列表、详情、登记（自然键 name）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import TABLE_DOMAIN_LABELS, DTYPE_LABELS
from src.models.column_profile import ColumnProfile
from src.models.source_table import SourceTable
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc
from src.services.profiling_service import profile_table


def serialize(table: SourceTable, profile_count: int | None = None) -> dict:
    return {
        "id": table.id,
        "name": table.name,
        "cn_name": table.cn_name,
        "subject": table.subject,
        "domain": table.domain,
        "domain_label": TABLE_DOMAIN_LABELS.get(table.domain, table.domain),
        "row_count": table.row_count,
        "field_count": table.field_count,
        "sample_count": len(table.sample_rows or []),
        "note": table.note,
        "profile_count": profile_count,
        "scanned_at": iso_utc(table.scanned_at),
        "created_at": iso_utc(table.created_at),
    }


def serialize_profile(profile: ColumnProfile) -> dict:
    return {
        "id": profile.id,
        "table_id": profile.table_id,
        "column": profile.column,
        "dtype": profile.dtype,
        "dtype_label": DTYPE_LABELS.get(profile.dtype, profile.dtype),
        "unique_ratio": profile.unique_ratio,
        "null_ratio": profile.null_ratio,
        "cardinality": profile.cardinality,
        "sample_values": profile.sample_values or [],
        "sample_size": profile.sample_size,
    }


def list_tables(
    db: Session,
    *,
    q: str | None = None,
    domain: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(SourceTable)
    count_stmt = select(func.count()).select_from(SourceTable)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(SourceTable.name.ilike(like) | SourceTable.cn_name.ilike(like))
        count_stmt = count_stmt.where(SourceTable.name.ilike(like) | SourceTable.cn_name.ilike(like))
    if domain:
        stmt = stmt.where(SourceTable.domain == domain)
        count_stmt = count_stmt.where(SourceTable.domain == domain)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(SourceTable.name).limit(limit).offset(offset)).all()
    counts = {
        table_id: count
        for table_id, count in db.execute(
            select(ColumnProfile.table_id, func.count()).group_by(ColumnProfile.table_id)
        ).all()
    }
    return {
        "items": [serialize(row, counts.get(row.id, 0)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_table(db: Session, table_id: int) -> SourceTable:
    table = db.get(SourceTable, table_id)
    if table is None:
        raise not_found("source_table", table_id)
    return table


def detail(db: Session, table_id: int) -> dict:
    table = get_table(db, table_id)
    profiles = db.scalars(
        select(ColumnProfile).where(ColumnProfile.table_id == table_id).order_by(ColumnProfile.id)
    ).all()
    payload = serialize(table, len(profiles))
    payload["profiles"] = [serialize_profile(profile) for profile in profiles]
    payload["sample_preview"] = (table.sample_rows or [])[:3]
    return payload


def create_table(db: Session, payload: dict) -> SourceTable:
    existing = db.scalar(select(SourceTable).where(SourceTable.name == payload["name"]))
    if existing is not None:
        raise AppError("CONFLICT", 409, {"name": payload["name"]})
    sample_rows = payload.get("sample_rows") or []
    profiles = profile_table(sample_rows) if sample_rows else []
    table = SourceTable(
        name=payload["name"],
        cn_name=payload.get("cn_name") or payload["name"],
        subject=payload.get("subject") or payload["name"],
        domain=payload.get("domain") or "sales",
        row_count=int(payload.get("row_count") or len(sample_rows)),
        field_count=len(profiles),
        sample_rows=sample_rows,
        note=payload.get("note"),
    )
    db.add(table)
    db.flush()
    for profile in profiles:
        db.add(
            ColumnProfile(
                table_id=table.id,
                column=profile["column"],
                dtype=profile["dtype"],
                unique_ratio=profile["unique_ratio"],
                null_ratio=profile["null_ratio"],
                cardinality=profile["cardinality"],
                sample_values=profile["sample_values"],
                sample_size=profile["sample_size"],
            )
        )
    db.flush()
    return table
