"""草案核对（关系与粒度校验）单测。"""
from __future__ import annotations

from src.services import validation_service


def _profiles():
    return [
        {"table_id": 1, "column": "fact_id", "unique_ratio": 1.0, "null_ratio": 0.0,
         "sample_values": [1, 2], "sample_size": 2, "dtype": "int", "cardinality": 2},
        {"table_id": 1, "column": "dim_id", "unique_ratio": 0.5, "null_ratio": 0.0,
         "sample_values": [10, 11], "sample_size": 2, "dtype": "int", "cardinality": 2},
        {"table_id": 2, "column": "dim_id", "unique_ratio": 1.0, "null_ratio": 0.0,
         "sample_values": [10, 11], "sample_size": 2, "dtype": "int", "cardinality": 2},
    ]


def _fact_suggestion(ddl_fk=1, joins=1, combos=2, sampled=2):
    return {
        "role": "fact",
        "target_name": "dwd_demo_fact",
        "ddl": "ALTER TABLE dwd_demo_fact ADD CONSTRAINT fk FOREIGN KEY (dim_id) REFERENCES dim_demo(dim_id);" * ddl_fk,
        "joins": [{}] * joins,
        "evidence": {"grain_columns": ["dim_id"], "grain_combos": combos, "sampled_rows": sampled},
    }


def test_validation_passes_on_consistent_snapshot():
    relations = [
        {"left_table_id": 1, "left_column": "dim_id", "right_table_id": 2, "right_column": "dim_id",
         "containment": 1.0, "confidence": 0.99, "kind": "pk-fk", "sample_size": 2},
    ]
    result = validation_service.validate_version(_profiles(), relations, [_fact_suggestion()])
    assert result["passed"] is True
    assert result["failed_checks"] == []
    assert len(result["checks"]) == 5


def test_validation_fails_when_relation_target_not_candidate_key():
    bad_profiles = [dict(p, unique_ratio=0.5) if p["table_id"] == 2 else p for p in _profiles()]
    relations = [
        {"left_table_id": 1, "left_column": "dim_id", "right_table_id": 2, "right_column": "dim_id",
         "containment": 1.0, "confidence": 0.99, "kind": "pk-fk", "sample_size": 2},
    ]
    result = validation_service.validate_version(bad_profiles, relations, [_fact_suggestion()])
    assert result["passed"] is False
    assert "relation_target_key" in result["failed_checks"]


def test_validation_fails_on_weak_fk_below_threshold():
    relations = [
        {"left_table_id": 1, "left_column": "dim_id", "right_table_id": 2, "right_column": "dim_id",
         "containment": 0.5, "confidence": 0.8, "kind": "fk", "sample_size": 2},
    ]
    result = validation_service.validate_version(_profiles(), relations, [_fact_suggestion()])
    assert "weak_fk_containment" in result["failed_checks"]


def test_validation_fails_when_ddl_foreign_keys_mismatch_joins():
    relations = [
        {"left_table_id": 1, "left_column": "dim_id", "right_table_id": 2, "right_column": "dim_id",
         "containment": 1.0, "confidence": 0.99, "kind": "pk-fk", "sample_size": 2},
    ]
    result = validation_service.validate_version(
        _profiles(), relations, [_fact_suggestion(ddl_fk=2, joins=1)]
    )
    assert "ddl_join_consistency" in result["failed_checks"]


def test_validation_fails_on_duplicate_target_names():
    dup = [_fact_suggestion(), _fact_suggestion()]
    relations = [
        {"left_table_id": 1, "left_column": "dim_id", "right_table_id": 2, "right_column": "dim_id",
         "containment": 1.0, "confidence": 0.99, "kind": "pk-fk", "sample_size": 2},
    ]
    result = validation_service.validate_version(_profiles(), relations, dup)
    assert "target_name_unique" in result["failed_checks"]


def test_validation_fails_on_empty_fact_grain():
    relations = []
    suggestion = _fact_suggestion()
    suggestion["evidence"] = {"grain_columns": [], "grain_combos": 0, "sampled_rows": 2}
    result = validation_service.validate_version(_profiles(), relations, [suggestion])
    assert "fact_grain" in result["failed_checks"]
