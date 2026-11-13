"""分析版本服务：把一次剖析整理成可比较、可重跑的草案，并管理发布切换。

设计要点（对应需求）：
- 快照隔离：profiles / relations / suggestions 全部带 version_id，草案与正式版各自留档，
  页面、关系图、DDL 导出默认只读正式版，草案不污染线上口径。
- 补数增量：只重算 affected_table_ids 内表的剖析，其余从上一正式版快照沿用；关系在合并后的
  完整快照上重算，差异（change_kind）精确落到受影响建议。
- 决定跟随业务对象：人工采纳/驳回存 suggestion_decisions（只追加），构建新版本时按 table_id
  迁移最近一次决定，人工结论不被重置、不被误删。
- 幂等重跑：输入指纹不变且最新版本产物相同时直接复用（草案/正式版皆然），不新增建议、不产生新版本行。
- 一次性切换：发布在单事务内把旧正式版置 superseded、草案置 published；任何一步失败整体回滚，
  上一正式版保持可用。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import (
    ANALYSIS_VERSION_STATUS_LABELS,
    SUGGESTION_CHANGE_LABELS,
    SUGGESTION_STATUS_LABELS,
    AnalysisVersionStatus,
    SuggestionChangeKind,
)
from src.models.analysis_version import AnalysisVersion
from src.models.column_profile import ColumnProfile
from src.models.model_suggestion import ModelSuggestion
from src.models.relation import Relation
from src.models.source_table import SourceTable
from src.models.suggestion_decision import SuggestionDecision
from src.services import profiling_service, star_service, validation_service
from src.utils.errors import AppError
from src.utils.timeutil import iso_utc, local_now, utcnow

# ---- 状态快捷方式 -------------------------------------------------------

DRAFT = AnalysisVersionStatus.DRAFT.value
PUBLISHED = AnalysisVersionStatus.PUBLISHED.value
SUPERSEDED = AnalysisVersionStatus.SUPERSEDED.value
VALIDATION_FAILED = AnalysisVersionStatus.VALIDATION_FAILED.value


# ---- 查询 ----------------------------------------------------------------

def current_draft(db: Session) -> AnalysisVersion | None:
    return db.scalar(
        select(AnalysisVersion)
        .where(AnalysisVersion.status.in_([DRAFT, VALIDATION_FAILED]))
        .order_by(AnalysisVersion.id.desc())
        .limit(1)
    )


def current_published(db: Session) -> AnalysisVersion | None:
    return db.scalar(
        select(AnalysisVersion)
        .where(AnalysisVersion.status == PUBLISHED)
        .order_by(AnalysisVersion.id.desc())
        .limit(1)
    )


def get_version(db: Session, version_id: int) -> AnalysisVersion:
    version = db.get(AnalysisVersion, version_id)
    if version is None:
        raise AppError("NOT_FOUND", 404, {"entity": "analysis_version", "id": version_id})
    return version


def next_version_no(db: Session) -> str:
    prefix = f"AV{local_now():%Y%m%d}"
    count = db.scalar(
        select(func.count()).select_from(AnalysisVersion).where(AnalysisVersion.version_no.like(f"{prefix}%"))
    ) or 0
    return f"{prefix}-{count + 1:04d}"


# ---- 序列化 --------------------------------------------------------------

def serialize(version: AnalysisVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "version_no": version.version_no,
        "run_id": version.run_id,
        "status": version.status,
        "status_label": ANALYSIS_VERSION_STATUS_LABELS.get(version.status, version.status),
        "trigger": version.trigger,
        "operator_email": version.operator_email,
        "base_version_id": version.base_version_id,
        "parent_version_id": version.parent_version_id,
        "affected_table_ids": version.affected_table_ids or [],
        "input_fingerprint": version.input_fingerprint,
        "table_count": version.table_count,
        "profile_count": version.profile_count,
        "relation_count": version.relation_count,
        "suggestion_count": version.suggestion_count,
        "validation": version.validation or {},
        "diff_summary": version.diff_summary or {},
        "metrics": version.metrics or {},
        "log_text": version.log_text,
        "published_by": version.published_by,
        "published_at": iso_utc(version.published_at),
        "created_at": iso_utc(version.created_at),
        "updated_at": iso_utc(version.updated_at),
    }


def list_versions(db: Session, *, status: str | None = None, limit: int = 20, offset: int = 0) -> dict:
    stmt = select(AnalysisVersion)
    count_stmt = select(func.count()).select_from(AnalysisVersion)
    if status:
        stmt = stmt.where(AnalysisVersion.status == status)
        count_stmt = count_stmt.where(AnalysisVersion.status == status)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(AnalysisVersion.id.desc()).limit(limit).offset(offset)).all()
    return {"items": [serialize(row) for row in rows], "total": total, "limit": limit, "offset": offset}


# ---- 输入指纹与快照读取 --------------------------------------------------

def _input_fingerprint(tables: Sequence[SourceTable]) -> str:
    payload = [
        {"name": t.name, "row_count": t.row_count, "sample_rows": t.sample_rows or []}
        for t in sorted(tables, key=lambda item: item.name)
    ]
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _profiles_of(db: Session, version_id: int) -> list[ColumnProfile]:
    return list(
        db.scalars(select(ColumnProfile).where(ColumnProfile.version_id == version_id)).all()
    )


def _relations_of(db: Session, version_id: int) -> list[Relation]:
    return list(db.scalars(select(Relation).where(Relation.version_id == version_id)).all())


def _suggestions_of(db: Session, version_id: int) -> list[ModelSuggestion]:
    return list(
        db.scalars(select(ModelSuggestion).where(ModelSuggestion.version_id == version_id)).all()
    )


def _profile_dicts(rows: Sequence[ColumnProfile]) -> list[dict]:
    return [
        {
            "table_id": row.table_id,
            "column": row.column,
            "dtype": row.dtype,
            "unique_ratio": row.unique_ratio,
            "null_ratio": row.null_ratio,
            "cardinality": row.cardinality,
            "sample_values": row.sample_values or [],
            "sample_size": row.sample_size,
        }
        for row in rows
    ]


def _relation_dicts(rows: Sequence[Relation]) -> list[dict]:
    return [
        {
            "left_table_id": row.left_table_id,
            "left_column": row.left_column,
            "right_table_id": row.right_table_id,
            "right_column": row.right_column,
            "containment": row.containment,
            "confidence": row.confidence,
            "kind": row.kind,
            "sample_size": row.sample_size,
        }
        for row in rows
    ]


# ---- 决定迁移 ------------------------------------------------------------

def _latest_decisions_by_table(db: Session) -> dict[int, SuggestionDecision]:
    """每张业务表取全局最新一条人工决定（跨全部版本），用于迁移到新草案。"""
    rows = db.scalars(select(SuggestionDecision).order_by(SuggestionDecision.id.asc())).all()
    return {row.table_id: row for row in rows}


def _apply_decisions(
    db: Session,
    version_id: int,
    suggestions: Sequence[ModelSuggestion],
) -> int:
    decisions = _latest_decisions_by_table(db)
    migrated = 0
    for suggestion in suggestions:
        decision = decisions.get(suggestion.table_id)
        if decision is None:
            continue
        # 迁移决定也落成一行可追溯记录（source=migrated）；同版本同表只迁移一次，
        # 之后人工改判会再追加 manual 记录，最新一条始终生效
        exists = db.scalar(
            select(SuggestionDecision).where(
                SuggestionDecision.version_id == version_id,
                SuggestionDecision.table_id == suggestion.table_id,
            )
        )
        if exists is None:
            db.add(
                SuggestionDecision(
                    table_id=suggestion.table_id,
                    version_id=version_id,
                    target_name=suggestion.target_name,
                    decision=decision.decision,
                    source="migrated",
                    decided_by=decision.decided_by,
                    note=f"沿用上一版本决定（决定记录 #{decision.id}）",
                )
            )
        suggestion.status = decision.decision
        suggestion.adopted_by = decision.decided_by
        suggestion.adopted_at = decision.created_at
        migrated += 1
    return migrated


# ---- 差异计算 ------------------------------------------------------------

def _suggestion_signature(suggestion: dict) -> tuple:
    return (
        suggestion.get("target_name"),
        suggestion.get("role"),
        suggestion.get("grain"),
        round(float(suggestion.get("confidence") or 0.0), 4),
        json.dumps(suggestion.get("joins") or [], sort_keys=True, ensure_ascii=False),
        json.dumps(suggestion.get("measures") or [], sort_keys=True, ensure_ascii=False),
        (suggestion.get("ddl") or "").strip(),
    )


def _edge_key(rel: dict) -> tuple:
    return (rel["left_table_id"], rel["left_column"], rel["right_table_id"], rel["right_column"])


def compute_diff(
    base_suggestions: Sequence[ModelSuggestion] | None,
    new_suggestions: Sequence[ModelSuggestion],
    base_relations: Sequence[Relation] | None,
    new_relations: Sequence[Relation],
) -> dict[str, Any]:
    base_by_table = {row.table_id: row for row in (base_suggestions or [])}
    added, changed, removed, unchanged = [], [], [], []
    for row in new_suggestions:
        base = base_by_table.get(row.table_id)
        if base is None:
            added.append(row.table_id)
            continue
        same = _suggestion_signature(_suggestion_dict(row)) == _suggestion_signature(_suggestion_dict(base))
        (unchanged if same else changed).append(row.table_id)
    new_table_ids = {row.table_id for row in new_suggestions}
    for table_id, row in base_by_table.items():
        if table_id not in new_table_ids:
            removed.append(table_id)

    base_edge = {_edge_key(_relation_dict(row)): row for row in (base_relations or [])}
    new_edge = {_edge_key(_relation_dict(row)): row for row in new_relations}
    rel_added = [key for key in new_edge if key not in base_edge]
    rel_removed = [key for key in base_edge if key not in new_edge]
    rel_changed = [
        key
        for key in new_edge
        if key in base_edge and abs(new_edge[key].containment - base_edge[key].containment) > 1e-9
    ]
    return {
        "suggestions": {
            "added": sorted(added),
            "changed": sorted(changed),
            "removed": sorted(removed),
            "unchanged": sorted(unchanged),
            "counts": {
                "added": len(added),
                "changed": len(changed),
                "removed": len(removed),
                "unchanged": len(unchanged),
            },
        },
        "relations": {
            "added": [list(key) for key in sorted(rel_added)],
            "removed": [list(key) for key in sorted(rel_removed)],
            "changed": [list(key) for key in sorted(rel_changed)],
            "counts": {
                "added": len(rel_added),
                "removed": len(rel_removed),
                "changed": len(rel_changed),
                "unchanged": len(new_edge) - len(rel_added) - len(rel_changed),
            },
        },
    }


def _suggestion_dict(row: ModelSuggestion) -> dict:
    return {
        "target_name": row.target_name,
        "role": row.role,
        "grain": row.grain,
        "confidence": row.confidence,
        "joins": row.joins or [],
        "measures": row.measures or [],
        "ddl": row.ddl or "",
    }


def _relation_dict(row: Relation) -> dict:
    return {
        "left_table_id": row.left_table_id,
        "left_column": row.left_column,
        "right_table_id": row.right_table_id,
        "right_column": row.right_column,
        "containment": row.containment,
    }


# ---- 构建草案 ------------------------------------------------------------

def build_version(
    db: Session,
    *,
    trigger: str,
    operator_email: str,
    run_id: int | None = None,
    affected_table_ids: Sequence[int] | None = None,
    auto_publish: bool = False,
) -> AnalysisVersion:
    tables = list(db.scalars(select(SourceTable).order_by(SourceTable.id)).all())
    fingerprint = _input_fingerprint(tables)

    # 幂等：算法纯确定性，输入指纹相同则产物必然相同。
    # 最新版本指纹一致时直接复用（无论它是草案还是正式版），重复执行不新增版本、不新增建议。
    latest = db.scalar(select(AnalysisVersion).order_by(AnalysisVersion.id.desc()).limit(1))
    if latest is not None and latest.input_fingerprint == fingerprint:
        if run_id is not None:
            latest.run_id = run_id
        return latest

    published = current_published(db)
    # 增量链式：已有草案时在草案上继续累积受影响表，避免第二次补数把第一次的改动丢掉
    carry_base = current_draft(db) or published
    compare_base = published  # 差异始终相对「将要被替换的正式版」
    affected = set(affected_table_ids or [])
    if carry_base is not None and carry_base.status != PUBLISHED:
        affected |= set(carry_base.affected_table_ids or [])
        carry_base.status = SUPERSEDED
    incremental = bool(affected and carry_base is not None)

    table_dicts = [
        {
            "id": table.id,
            "name": table.name,
            "cn_name": table.cn_name,
            "subject": table.subject,
            "domain": table.domain,
            "row_count": table.row_count,
            "sample_rows": table.sample_rows or [],
        }
        for table in tables
    ]

    # 1. 剖析：增量模式只重算受影响表，其余沿用基线（草案链上一版或正式版）快照
    profile_rows: list[dict] = []
    if incremental:
        carried = [
            profile
            for profile in _profile_dicts(_profiles_of(db, carry_base.id))
            if profile["table_id"] not in affected
        ]
        profile_rows.extend(carried)
        re_profiled_ids = affected
    else:
        re_profiled_ids = {table.id for table in tables}

    for table in table_dicts:
        if table["id"] not in re_profiled_ids:
            continue
        table_profiles = profiling_service.profile_table(table["sample_rows"])
        profile_rows.extend({"table_id": table["id"], **profile} for profile in table_profiles)
        source = db.get(SourceTable, table["id"])
        if source is not None:
            source.field_count = len(table_profiles)
            source.scanned_at = utcnow()

    # 2. 关系发现在合并后的完整快照上重算（保证边与当前剖析一致）
    discovery = profiling_service.discover_relations(profile_rows)

    # 3. 星型建议
    rows_by_table = {table["id"]: table["sample_rows"] for table in table_dicts}
    built = star_service.build_suggestions(
        table_dicts, profile_rows, discovery["relations"], rows_by_table
    )

    # 4. 落版本行（先 draft，核对未过再改 validation_failed）
    version = AnalysisVersion(
        version_no=next_version_no(db),
        run_id=run_id,
        status=DRAFT,
        trigger=trigger,
        operator_email=operator_email,
        # 差异基线锚定将被替换的正式版；链式草案的直接父版本另存 parent_version_id
        base_version_id=compare_base.id if compare_base else None,
        parent_version_id=carry_base.id if carry_base and carry_base.id != (compare_base.id if compare_base else None) else None,
        affected_table_ids=sorted(affected),
        input_fingerprint=fingerprint,
    )
    db.add(version)
    db.flush()

    for profile in profile_rows:
        db.add(ColumnProfile(version_id=version.id, **profile))
    for relation in discovery["relations"]:
        db.add(Relation(version_id=version.id, **relation))

    suggestion_rows: list[ModelSuggestion] = []
    for suggestion in built["suggestions"]:
        row = ModelSuggestion(
            version_id=version.id,
            table_id=suggestion["table_id"],
            target_name=suggestion["target_name"],
            role=suggestion["role"],
            grain=suggestion["grain"],
            joins=suggestion["joins"],
            measures=suggestion["measures"],
            attributes=suggestion["attributes"],
            confidence=suggestion["confidence"],
            status="pending",
            ddl=suggestion["ddl"],
            reason=suggestion["reason"],
            evidence=suggestion.get("evidence") or {},
            change_kind=SuggestionChangeKind.UNCHANGED.value,
        )
        db.add(row)
        suggestion_rows.append(row)
    db.flush()

    # 5. 决定跟随业务对象迁移（只追加 suggestion_decisions，不覆盖历史）
    migrated = _apply_decisions(db, version.id, suggestion_rows)

    # 6. 与当前正式版比较，落定 change_kind 与差异摘要（草案链式累积时仍相对正式版）
    base_suggestions = _suggestions_of(db, compare_base.id) if compare_base else None
    base_relations = _relations_of(db, compare_base.id) if compare_base else None
    diff = compute_diff(base_suggestions, suggestion_rows, base_relations, _relations_of(db, version.id))
    kind_by_table = {}
    for kind in ("added", "changed", "removed", "unchanged"):
        for table_id in diff["suggestions"][kind]:
            kind_by_table[table_id] = kind
    for row in suggestion_rows:
        row.change_kind = kind_by_table.get(row.table_id, SuggestionChangeKind.UNCHANGED.value)
    version.diff_summary = {
        "suggestions": diff["suggestions"]["counts"],
        "relations": diff["relations"]["counts"],
        "base_version_id": compare_base.id if compare_base else None,
        "base_version_no": compare_base.version_no if compare_base else None,
        "incremental": incremental,
        "affected_table_ids": sorted(affected),
    }

    # 7. 关系与粒度核对
    result = validation_service.validate_version(
        profile_rows, discovery["relations"], built["suggestions"]
    )
    version.validation = result

    # 8. 计数 / 指标 / 日志
    fact_count = sum(1 for item in built["classified"] if item["role"] == star_service.ROLE_FACT)
    dim_count = sum(1 for item in built["classified"] if item["role"] == star_service.ROLE_DIM)
    none_count = sum(1 for item in built["classified"] if item["role"] == star_service.ROLE_NONE)
    confidences = [float(item["confidence"]) for item in discovery["relations"]]
    version.table_count = len(table_dicts)
    version.profile_count = len(profile_rows)
    version.relation_count = len(discovery["relations"])
    version.suggestion_count = len(built["suggestions"])
    version.metrics = {
        "tables": len(table_dicts),
        "profiles": len(profile_rows),
        "pk_candidates": len(profiling_service.candidate_keys(profile_rows)),
        "relations": len(discovery["relations"]),
        "rejected_pairs": discovery["rejected"],
        "unique_columns": discovery["unique_columns"],
        "fact_tables": fact_count,
        "dim_tables": dim_count,
        "unrelated_tables": none_count,
        "secondary_dims": len(built["secondary_dim_tables"]),
        "suggestions": len(built["suggestions"]),
        "avg_relation_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
        "migrated_decisions": migrated,
        "incremental": incremental,
    }
    scope_label = f"补数增量（受影响 {len(affected)} 表）" if incremental else "全量"
    version.log_text = (
        f"{scope_label}剖析 {len(table_dicts)} 张表 / {len(profile_rows)} 个字段；"
        f"发现 {len(discovery['relations'])} 条包含依赖；生成 {len(built['suggestions'])} 条建议，"
        f"迁移 {migrated} 条人工决定；核对 {'通过' if result['passed'] else '未通过'}。"
    )

    if not result["passed"]:
        version.status = VALIDATION_FAILED
    elif auto_publish:
        _publish_inline(db, version, operator_email)
    db.flush()
    return version


# ---- 发布（事务性切换）---------------------------------------------------

def _publish_inline(db: Session, version: AnalysisVersion, operator_email: str) -> None:
    """调用方需在外层事务内；任何异常抛出即整体回滚，上一正式版不动。"""
    if not (version.validation or {}).get("passed"):
        raise AppError(
            "CONFLICT",
            409,
            {"reason": "草案未通过关系与粒度核对，不能发布", "failed_checks": version.validation.get("failed_checks")},
        )
    previous = current_published(db)
    if previous is not None and previous.id != version.id:
        previous.status = SUPERSEDED
    version.status = PUBLISHED
    version.published_by = operator_email
    version.published_at = utcnow()


def publish_version(db: Session, version_id: int, operator_email: str) -> AnalysisVersion:
    version = get_version(db, version_id)
    if version.status == PUBLISHED:
        return version
    if version.status not in (DRAFT, VALIDATION_FAILED):
        raise AppError("CONFLICT", 409, {"reason": f"状态 {version.status} 的版本不能发布"})
    # 发布前再做一次实时核对，防止快照期间口径被标记失效
    if not (version.validation or {}).get("passed"):
        raise AppError(
            "CONFLICT",
            409,
            {"reason": "草案未通过关系与粒度核对，不能发布", "failed_checks": version.validation.get("failed_checks")},
        )
    _publish_inline(db, version, operator_email)
    db.flush()
    return version


def revalidate(db: Session, version_id: int) -> AnalysisVersion:
    """重新核对（不重算剖析）：通过则把 validation_failed 草案退回 draft。"""
    version = get_version(db, version_id)
    profiles = _profile_dicts(_profiles_of(db, version.id))
    relations = _relation_dicts(_relations_of(db, version.id))
    suggestions = [
        {
            "role": row.role,
            "target_name": row.target_name,
            "joins": row.joins or [],
            "ddl": row.ddl or "",
            "evidence": row.evidence or {},
        }
        for row in _suggestions_of(db, version.id)
    ]
    version.validation = validation_service.validate_version(profiles, relations, suggestions)
    if version.status == VALIDATION_FAILED and version.validation["passed"]:
        version.status = DRAFT
    db.flush()
    return version


# ---- 版本差异详情（页面用）----------------------------------------------

def version_diff(db: Session, version_id: int) -> dict[str, Any]:
    version = get_version(db, version_id)
    # 差异相对正式版基线（base_version_id 锚定）；首个版本无基线
    base = db.get(AnalysisVersion, version.base_version_id) if version.base_version_id else None
    if base is None:
        base = db.scalar(
            select(AnalysisVersion)
            .where(AnalysisVersion.status == PUBLISHED, AnalysisVersion.id < version.id)
            .order_by(AnalysisVersion.id.desc())
            .limit(1)
        )
    new_suggestions = _suggestions_of(db, version.id)
    base_suggestions = _suggestions_of(db, base.id) if base else []
    new_relations = _relations_of(db, version.id)
    base_relations = _relations_of(db, base.id) if base else []
    tables = {table.id: table for table in db.scalars(select(SourceTable)).all()}

    base_by_table = {row.table_id: row for row in base_suggestions}
    suggestion_items = []
    for row in new_suggestions:
        base_row = base_by_table.get(row.table_id)
        if base_row is None:
            kind = SuggestionChangeKind.ADDED.value
        elif _suggestion_signature(_suggestion_dict(row)) == _suggestion_signature(_suggestion_dict(base_row)):
            kind = SuggestionChangeKind.UNCHANGED.value
        else:
            kind = SuggestionChangeKind.CHANGED.value
        suggestion_items.append(
            {
                "table_id": row.table_id,
                "table_name": tables[row.table_id].name if row.table_id in tables else None,
                "target_name": row.target_name,
                "role": row.role,
                "change_kind": kind,
                "change_label": SUGGESTION_CHANGE_LABELS.get(kind, kind),
                "status": row.status,
                "status_label": SUGGESTION_STATUS_LABELS.get(row.status, row.status),
                "confidence": row.confidence,
                "grain": row.grain,
                "base_grain": base_row.grain if base_row else None,
                "base_confidence": base_row.confidence if base_row else None,
            }
        )
    new_table_ids = {row.table_id for row in new_suggestions}
    for table_id, row in base_by_table.items():
        if table_id not in new_table_ids:
            suggestion_items.append(
                {
                    "table_id": table_id,
                    "table_name": tables[table_id].name if table_id in tables else None,
                    "target_name": row.target_name,
                    "role": row.role,
                    "change_kind": SuggestionChangeKind.REMOVED.value,
                    "change_label": SUGGESTION_CHANGE_LABELS[SuggestionChangeKind.REMOVED.value],
                    "status": row.status,
                    "status_label": SUGGESTION_STATUS_LABELS.get(row.status, row.status),
                    "confidence": None,
                    "grain": None,
                    "base_grain": row.grain,
                    "base_confidence": row.confidence,
                }
            )

    base_edge = {_edge_key(_relation_dict(row)): row for row in base_relations}
    new_edge = {_edge_key(_relation_dict(row)): row for row in new_relations}
    relation_items = []
    for key, row in new_edge.items():
        kind = (
            SuggestionChangeKind.ADDED.value
            if key not in base_edge
            else (
                SuggestionChangeKind.CHANGED.value
                if abs(row.containment - base_edge[key].containment) > 1e-9
                else SuggestionChangeKind.UNCHANGED.value
            )
        )
        relation_items.append(
            {
                "edge": list(key),
                "kind": kind,
                "containment": row.containment,
                "base_containment": base_edge[key].containment if key in base_edge else None,
            }
        )
    for key, row in base_edge.items():
        if key not in new_edge:
            relation_items.append(
                {
                    "edge": list(key),
                    "kind": SuggestionChangeKind.REMOVED.value,
                    "containment": None,
                    "base_containment": row.containment,
                }
            )

    order = {"added": 0, "changed": 1, "removed": 2, "unchanged": 3}
    suggestion_items.sort(key=lambda item: (order[item["change_kind"]], item["target_name"] or ""))
    relation_items.sort(key=lambda item: (order[item["kind"]], str(item["edge"])))
    return {
        "version": serialize(version),
        "base_version": serialize(base) if base else None,
        "suggestions": suggestion_items,
        "relations": relation_items,
    }
