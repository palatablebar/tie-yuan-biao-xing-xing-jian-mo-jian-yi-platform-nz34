"""算法 A 单测：字段剖析 / 候选键 / 包含度 / 关系发现。"""
from __future__ import annotations

from src.services import profiling_service as ps


def _rows():
    return [
        {"id": 1, "store_id": 1001, "amount": 12.5},
        {"id": 2, "store_id": 1002, "amount": 8.0},
        {"id": 3, "store_id": 1001, "amount": 6.5},
        {"id": 4, "store_id": 1003, "amount": 15.0},
    ]


def test_profile_column_ratios():
    profile = ps.profile_column(_rows(), "store_id")
    assert profile["unique_ratio"] == 0.75  # 3 个不同值 / 4 行
    assert profile["null_ratio"] == 0.0
    assert profile["cardinality"] == 3
    assert profile["dtype"] == "int"
    assert profile["sample_values"] == [1001, 1002, 1003]


def test_profile_column_counts_nulls():
    rows = _rows() + [{"id": 5, "store_id": None, "amount": None}]
    profile = ps.profile_column(rows, "store_id")
    assert profile["null_ratio"] == 0.2
    assert profile["unique_ratio"] == 0.6


def test_candidate_keys_require_unique_and_non_null():
    rows = _rows()
    profiles = ps.profile_table(rows)
    keys = [item["column"] for item in ps.candidate_keys(profiles)]
    assert keys == ["id", "amount"]
    rows_with_null = rows + [{"id": None, "store_id": 1004, "amount": 9.0}]
    null_profiles = ps.profile_table(rows_with_null)
    null_keys = [item["column"] for item in ps.candidate_keys(null_profiles)]
    assert "id" not in null_keys


def test_containment_exact_and_partial():
    assert ps.containment([1, 2, 3], [1, 2, 3, 4]) == 1.0
    assert ps.containment([1, 2, 3, 9], [1, 2, 3]) == 0.75
    assert ps.containment([], [1]) == 0.0


def _profiles():
    return [
        {"table_id": 1, "column": "order_id", "unique_ratio": 1.0, "null_ratio": 0.0,
         "sample_values": ["A", "B"], "sample_size": 2},
        {"table_id": 1, "column": "store_id", "unique_ratio": 0.5, "null_ratio": 0.0,
         "sample_values": [1001, 1002, 1001], "sample_size": 4},
        {"table_id": 1, "column": "region_id", "unique_ratio": 0.25, "null_ratio": 0.0,
         "sample_values": [1], "sample_size": 4},
        {"table_id": 2, "column": "store_id", "unique_ratio": 1.0, "null_ratio": 0.0,
         "sample_values": [1001, 1002], "sample_size": 2},
        {"table_id": 2, "column": "region_id", "unique_ratio": 1.0, "null_ratio": 0.0,
         "sample_values": [1], "sample_size": 1},
        {"table_id": 3, "column": "store_id", "unique_ratio": 0.5, "null_ratio": 0.0,
         "sample_values": [1001, 1001], "sample_size": 2},
    ]


def test_discover_relations_matches_same_name_key():
    result = ps.discover_relations(_profiles())
    edges = {(item["left_table_id"], item["left_column"], item["right_table_id"]) for item in result["relations"]}
    assert (1, "store_id", 2) in edges
    assert (1, "region_id", 2) in edges
    # 右表 store_id 不唯一 → 不能作为外键目标
    assert (1, "store_id", 3) not in edges
    # 本表自己的候选键不作为外键
    assert all(item["left_column"] != "order_id" for item in result["relations"])


def test_discover_relations_rejects_below_threshold():
    profiles = [
        {"table_id": 1, "column": "store_id", "unique_ratio": 0.5, "null_ratio": 0.0,
         "sample_values": [1001, 9999], "sample_size": 4},
        {"table_id": 2, "column": "store_id", "unique_ratio": 1.0, "null_ratio": 0.0,
         "sample_values": [1001, 1002], "sample_size": 2},
    ]
    result = ps.discover_relations(profiles)
    assert result["relations"] == []
    assert result["rejected"] == 1
    weak = ps.discover_relations(profiles, threshold=0.5)
    assert weak["relations"][0]["containment"] == 0.5
    assert weak["relations"][0]["kind"] == "fk"


def test_relation_confidence_bounds():
    assert ps.relation_confidence(1.0) == 0.99
    assert ps.relation_confidence(0.98) < 0.99
    assert ps.relation_confidence(0.0) == 0.66


def test_profile_is_deterministic():
    assert ps.profile_table(_rows()) == ps.profile_table(_rows())
