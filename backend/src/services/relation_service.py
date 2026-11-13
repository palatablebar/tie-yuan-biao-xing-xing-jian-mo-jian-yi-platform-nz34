"""关系查询 + 关系图节点（角色由算法 B 的判定函数现算，不落库）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import RELATION_KIND_LABELS
from src.models.column_profile import ColumnProfile
from src.models.relation import Relation
from src.models.source_table import SourceTable
from src.services.source_table_service import serialize_profile
from src.services.star_service import ROLE_DIM, ROLE_FACT, classify_tables


def _table_dict(table: SourceTable) -> dict:
    return {
        "id": table.id,
        "name": table.name,
        "cn_name": table.cn_name,
        "subject": table.subject,
        "domain": table.domain,
        "row_count": table.row_count,
    }


def _profile_dict(profile: ColumnProfile) -> dict:
    return {
        "table_id": profile.table_id,
        "column": profile.column,
        "dtype": profile.dtype,
        "unique_ratio": profile.unique_ratio,
        "null_ratio": profile.null_ratio,
        "cardinality": profile.cardinality,
        "sample_values": profile.sample_values or [],
        "sample_size": profile.sample_size,
    }


def list_relations(db: Session, *, kind: str | None = None, limit: int = 60, offset: int = 0) -> dict:
    stmt = select(Relation)
    count_stmt = select(func.count()).select_from(Relation)
    if kind:
        stmt = stmt.where(Relation.kind == kind)
        count_stmt = count_stmt.where(Relation.kind == kind)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Relation.left_table_id, Relation.left_column).limit(limit).offset(offset)).all()
    tables = {table.id: table for table in db.scalars(select(SourceTable)).all()}
    items = []
    for row in rows:
        left = tables.get(row.left_table_id)
        right = tables.get(row.right_table_id)
        items.append(
            {
                "id": row.id,
                "left_table": left.name if left else None,
                "left_cn_name": left.cn_name if left else None,
                "left_column": row.left_column,
                "right_table": right.name if right else None,
                "right_cn_name": right.cn_name if right else None,
                "right_column": row.right_column,
                "containment": row.containment,
                "confidence": row.confidence,
                "kind": row.kind,
                "kind_label": RELATION_KIND_LABELS.get(row.kind, row.kind),
                "sample_size": row.sample_size,
            }
        )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def graph(db: Session) -> dict:
    tables = db.scalars(select(SourceTable).order_by(SourceTable.id)).all()
    relations = db.scalars(select(Relation).order_by(Relation.id)).all()
    profiles = db.scalars(select(ColumnProfile)).all()
    table_dicts = [_table_dict(table) for table in tables]
    profile_dicts = [_profile_dict(profile) for profile in profiles]
    relation_dicts = [
        {
            "left_table_id": row.left_table_id,
            "left_column": row.left_column,
            "right_table_id": row.right_table_id,
            "right_column": row.right_column,
            "containment": row.containment,
            "confidence": row.confidence,
            "kind": row.kind,
        }
        for row in relations
    ]
    classified = classify_tables(table_dicts, profile_dicts, relation_dicts)
    role_by_id = {item["table_id"]: item["role"] for item in classified}
    nodes = []
    for table in table_dicts:
        degree = sum(
            1
            for relation in relation_dicts
            if relation["left_table_id"] == table["id"] or relation["right_table_id"] == table["id"]
        )
        nodes.append(
            {
                **table,
                "role": role_by_id.get(table["id"], "none"),
                "degree": degree,
            }
        )
    edges = []
    for row, edge in zip(relations, relation_dicts):
        left = next((node for node in nodes if node["id"] == row.left_table_id), None)
        right = next((node for node in nodes if node["id"] == row.right_table_id), None)
        edges.append(
            {
                "id": row.id,
                **edge,
                "left_name": left["name"] if left else None,
                "left_cn_name": left["cn_name"] if left else None,
                "right_name": right["name"] if right else None,
                "right_cn_name": right["cn_name"] if right else None,
                "kind_label": RELATION_KIND_LABELS.get(row.kind, row.kind),
            }
        )
    return {
        "nodes": nodes,
        "edges": edges,
        "edge_total": len(edges),
        "node_total": len(nodes),
        "fact_total": sum(1 for node in nodes if node["role"] == ROLE_FACT),
        "dim_total": sum(1 for node in nodes if node["role"] == ROLE_DIM),
        "unrelated_total": sum(1 for node in nodes if node["role"] not in (ROLE_FACT, ROLE_DIM)),
    }


def table_profiles(db: Session, table_id: int) -> dict:
    rows = db.scalars(
        select(ColumnProfile).where(ColumnProfile.table_id == table_id).order_by(ColumnProfile.id)
    ).all()
    return {"items": [serialize_profile(row) for row in rows], "total": len(rows)}
