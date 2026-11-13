"""分析版本化端到端单测：草案 / 发布 / 回滚 / 补数增量 / 决定迁移 / 幂等 / 口径隔离。

用 SQLite 内存库 + 真实 ORM 与 service，不启动 FastAPI；算法仍走 profiling / star 纯函数。
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.models import Base
from src.models.analysis_version import AnalysisVersion
from src.models.model_suggestion import ModelSuggestion
from src.models.relation import Relation
from src.models.source_table import SourceTable
from src.models.suggestion_decision import SuggestionDecision
from src.services import (
    analysis_version_service as version_service,
    export_service,
    relation_service,
    suggestion_service,
)
from src.utils.errors import AppError
from scripts.demo_config import TABLES


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = Session()
    for spec in TABLES:
        session.add(
            SourceTable(
                name=spec["name"],
                cn_name=spec["cn_name"],
                subject=spec["subject"],
                domain=spec["domain"],
                row_count=spec["row_count"],
                field_count=len(spec["sample_rows"][0]) if spec["sample_rows"] else 0,
                sample_rows=spec["sample_rows"],
                note=spec.get("note"),
            )
        )
    session.flush()
    yield session
    session.close()


def _publish_first(db):
    v1 = version_service.build_version(db, trigger="manual", operator_email="seed@x.io", auto_publish=True)
    return v1


def test_build_publish_and_supersede(db):
    # 首个草案（不自动发布）
    v0 = version_service.build_version(db, trigger="manual", operator_email="seed@x.io")
    assert v0.status == "draft"
    assert version_service.current_published(db) is None
    version_service.publish_version(db, v0.id, "seed@x.io")
    v1 = version_service.current_published(db)
    assert v1.id == v0.id
    assert v1.suggestion_count == 9
    assert v1.relation_count == 18
    assert v1.validation["passed"] is True

    # 改输入后产生新草案；发布前正式版仍是 v1
    source = db.scalar(select(SourceTable).order_by(SourceTable.id).limit(1))
    source.sample_rows = [dict(row) for row in source.sample_rows] + [dict(source.sample_rows[0])]
    db.flush()
    v2 = version_service.build_version(db, trigger="manual", operator_email="a@x.io")
    assert v2.id != v1.id
    assert v2.status == "draft"
    assert version_service.current_published(db).id == v1.id

    version_service.publish_version(db, v2.id, "admin@x.io")
    assert version_service.current_published(db).id == v2.id
    db.refresh(v1)
    assert v1.status == "superseded"
    # 历史版本数据不删
    assert len(version_service._suggestions_of(db, v1.id)) == 9


def test_idempotent_rerun_creates_no_new_version_or_suggestion(db):
    v1 = _publish_first(db)
    # 输入未变：全量重跑直接复用最新版本
    again = version_service.build_version(db, trigger="manual", operator_email="a@x.io")
    assert again.id == v1.id
    assert db.scalar(select(func.count()).select_from(AnalysisVersion)) == 1
    assert db.scalar(select(func.count()).select_from(ModelSuggestion)) == 9


def test_decision_follows_business_object_and_is_never_deleted(db):
    # 第一个草案上人工采纳一条建议，再发布
    v0 = version_service.build_version(db, trigger="manual", operator_email="seed@x.io")
    target = version_service._suggestions_of(db, v0.id)[0]
    suggestion_service.adopt(db, target, "admin@x.io")
    table_id = target.table_id
    version_service.publish_version(db, v0.id, "seed@x.io")
    v1 = version_service.current_published(db)

    # 改样本制造输入变化，产生新草案
    source = db.get(SourceTable, table_id)
    source.sample_rows = [dict(row) for row in (source.sample_rows or [])] + [
        dict(source.sample_rows[0])
    ]
    db.flush()
    v2 = version_service.build_version(db, trigger="manual", operator_email="a@x.io")
    assert v2.status == "draft"

    # 新草案同表建议状态被迁移为 adopted
    new_target = db.scalar(
        select(ModelSuggestion).where(
            ModelSuggestion.version_id == v2.id, ModelSuggestion.table_id == table_id
        )
    )
    assert new_target.status == "adopted"
    assert new_target.adopted_by == "admin@x.io"
    # 决定表只追加：迁移记录 + 原始人工记录都在
    decisions = db.scalars(
        select(SuggestionDecision).where(SuggestionDecision.table_id == table_id)
    ).all()
    assert len(decisions) == 2
    assert {d.source for d in decisions} == {"manual", "migrated"}

    # 再补一次数（链式增量）决定仍然保留，不会被重置成 pending
    source.sample_rows = [dict(row) for row in source.sample_rows] + [dict(source.sample_rows[0])]
    db.flush()
    v3 = version_service.build_version(
        db, trigger="incremental", operator_email="a@x.io", affected_table_ids=[table_id]
    )
    v3_target = db.scalar(
        select(ModelSuggestion).where(
            ModelSuggestion.version_id == v3.id, ModelSuggestion.table_id == table_id
        )
    )
    assert v3_target.status == "adopted"
    assert v1.id != v3.id


def test_incremental_only_reprofiles_affected_tables(db):
    v1 = _publish_first(db)
    affected_id = db.scalar(select(SourceTable.id).order_by(SourceTable.id).limit(1))
    # 让受影响表输入变化，确保产生新草案而不是被指纹幂等复用
    source = db.get(SourceTable, affected_id)
    source.sample_rows = [dict(row) for row in source.sample_rows] + [dict(source.sample_rows[0])]
    db.flush()
    v2 = version_service.build_version(
        db,
        trigger="incremental",
        operator_email="a@x.io",
        affected_table_ids=[affected_id],
    )
    assert v2.id != v1.id
    assert v2.status == "draft"
    assert v2.affected_table_ids == [affected_id]
    assert v2.metrics["incremental"] is True
    # 未受影响表的 profile 沿用上一版：行数口径与 v1 一致
    assert v2.profile_count == v1.profile_count
    assert v2.relation_count == v1.relation_count
    assert v2.suggestion_count == v1.suggestion_count


def test_publish_failure_rolls_back_and_keeps_previous_version(db):
    v1 = _publish_first(db)
    source = db.scalar(select(SourceTable).order_by(SourceTable.id).limit(1))
    source.sample_rows = [dict(row) for row in source.sample_rows] + [dict(source.sample_rows[0])]
    db.flush()
    v2 = version_service.build_version(db, trigger="manual", operator_email="a@x.io")
    assert v2.status == "draft"

    # 核对未过的版本发布必须被拒绝（409），正式版保持 v1 不动
    v2.validation = {"passed": False, "checks": [], "failed_checks": ["forced"]}
    db.flush()
    with pytest.raises(AppError) as exc:
        version_service.publish_version(db, v2.id, "admin@x.io")
    assert exc.value.status_code == 409
    assert version_service.current_published(db).id == v1.id
    db.refresh(v2)
    assert v2.status == "draft"


def test_published_scope_isolates_graph_and_export_from_draft(db):
    v1 = _publish_first(db)
    # 制造输入变化产生草案
    source = db.scalar(select(SourceTable).order_by(SourceTable.id).limit(1))
    source.sample_rows = [dict(row) for row in source.sample_rows] + [dict(source.sample_rows[0])]
    db.flush()
    v2 = version_service.build_version(db, trigger="manual", operator_email="a@x.io")
    assert v2.id != v1.id

    # 默认关系图 / 导出锚定正式版 v1
    graph = relation_service.graph(db)
    assert graph["version_id"] == v1.id
    ddl = export_service.ddl_sql(db)
    assert ddl["version_id"] == v1.id
    assert ddl["segments"] == 9
    # 草案预览能看到 v2
    draft_graph = relation_service.graph(db, scope="draft")
    assert draft_graph["version_id"] == v2.id

    # 建议列表默认正式版；指定 version_id 可看草案
    listing = suggestion_service.list_suggestions(db)
    assert listing["version_id"] == v1.id
    draft_listing = suggestion_service.list_suggestions(db, version_id=v2.id)
    assert draft_listing["version_id"] == v2.id


def test_cannot_adopt_published_snapshot_suggestion(db):
    v1 = _publish_first(db)
    target = version_service._suggestions_of(db, v1.id)[0]
    with pytest.raises(AppError) as exc:
        suggestion_service.adopt(db, target, "admin@x.io")
    assert exc.value.status_code == 409


def test_diff_flags_added_changed_unchanged(db):
    v1 = _publish_first(db)
    source = db.scalar(select(SourceTable).order_by(SourceTable.id).limit(1))
    source.sample_rows = [dict(row) for row in source.sample_rows] + [dict(source.sample_rows[0])]
    db.flush()
    v2 = version_service.build_version(db, trigger="manual", operator_email="a@x.io")
    diff = version_service.version_diff(db, v2.id)
    kinds = {item["change_kind"] for item in diff["suggestions"]}
    # 至少能识别出无变化项；变更/新增项取决于受影响表是否落在建议集合
    assert "unchanged" in kinds
    assert diff["base_version"] is not None and diff["base_version"]["id"] == v1.id
    summary = v2.diff_summary["suggestions"]
    assert summary["added"] + summary["changed"] + summary["unchanged"] + summary["removed"] == v2.suggestion_count


def test_relations_have_version_and_no_cross_version_mix(db):
    v1 = _publish_first(db)
    affected_id = db.scalar(select(SourceTable.id).order_by(SourceTable.id).limit(1))
    source = db.get(SourceTable, affected_id)
    source.sample_rows = [dict(row) for row in source.sample_rows] + [dict(source.sample_rows[0])]
    db.flush()
    v2 = version_service.build_version(
        db, trigger="incremental", operator_email="a@x.io", affected_table_ids=[affected_id]
    )
    # 每个版本的关系只挂自己的 version_id，不存在无版本归属的边
    for version_id in (v1.id, v2.id):
        count = db.scalar(
            select(func.count()).select_from(Relation).where(Relation.version_id == version_id)
        )
        assert count == 18
    orphan = db.scalar(select(func.count()).select_from(Relation).where(Relation.version_id.is_(None)))
    assert orphan == 0
