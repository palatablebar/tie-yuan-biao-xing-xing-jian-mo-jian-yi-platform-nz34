"""算法 B 单测：事实/维判定、粒度、DDL、建议集合。"""
from __future__ import annotations

from src.services import profiling_service as ps
from src.services import star_service as ss
from scripts.demo_config import TABLES


def _table(table_id, name, cn_name, subject, row_count, rows):
    return {
        "id": table_id,
        "name": name,
        "cn_name": cn_name,
        "subject": subject,
        "row_count": row_count,
        "sample_rows": rows,
    }


def _pipeline():
    tables = [
        _table(index + 1, spec["name"], spec["cn_name"], spec["subject"], spec["row_count"], spec["sample_rows"])
        for index, spec in enumerate(TABLES)
    ]
    profiles = []
    for table in tables:
        profiles.extend(
            {"table_id": table["id"], **profile} for profile in ps.profile_table(table["sample_rows"])
        )
    discovery = ps.discover_relations(profiles)
    built = ss.build_suggestions(
        tables, profiles, discovery["relations"], {table["id"]: table["sample_rows"] for table in tables}
    )
    return tables, profiles, discovery, built


def test_classification_counts():
    _tables, _profiles, discovery, built = _pipeline()
    assert len(discovery["relations"]) == 18
    roles = [item["role"] for item in built["classified"]]
    assert roles.count(ss.ROLE_FACT) == 4
    assert roles.count(ss.ROLE_DIM) == 12
    assert roles.count(ss.ROLE_NONE) == 8
    assert len(built["suggestions"]) == 9


def test_sales_fact_grain_and_foreign_keys():
    _tables, _profiles, _discovery, built = _pipeline()
    sales = next(item for item in built["suggestions"] if item["target_name"] == "dwd_sales_fact")
    assert sales["role"] == ss.ROLE_FACT
    assert sales["grain"].startswith("门店×商品×日期")
    assert len(sales["joins"]) == 3
    assert sales["ddl"].count("FOREIGN KEY") == 3
    assert "PRIMARY KEY (order_item_id)" in sales["ddl"]
    assert "amount" in sales["ddl"]


def test_dim_suggestion_has_primary_key():
    _tables, _profiles, _discovery, built = _pipeline()
    store = next(item for item in built["suggestions"] if item["target_name"] == "dim_store")
    assert store["role"] == ss.ROLE_DIM
    assert "PRIMARY KEY (store_id)" in store["ddl"]
    assert "store_name" in store["ddl"]


def test_grain_combinations_dedup():
    rows = [
        {"a": 1, "b": 2},
        {"a": 1, "b": 2},
        {"a": 1, "b": 3},
        {"a": 2, "b": 2},
    ]
    combos, sampled = ss.grain_combinations(rows, ["a", "b"])
    assert (combos, sampled) == (3, 4)


def test_measure_and_date_helpers():
    assert ss.is_measure("amount")
    assert ss.is_measure("on_hand_qty")
    assert not ss.is_measure("store_name")
    assert ss.is_identifier("store_id")
    assert not ss.is_identifier("store_name")
    assert ss.is_dateish("created_at")
    assert ss.is_dateish("open_date")
    assert not ss.is_dateish("birthday")


def test_classify_skips_small_price_table():
    # 商品表有 price（度量）且出边 2 条，但体量小、度量列少 → 不能判成事实表
    tables = [
        _table(1, "t_fact", "事实", "f", 1_000_000, [{"id": 1, "a_id": 1, "b_id": 1, "amount": 2.0}]),
        _table(2, "t_dim_a", "维A", "a", 10, [{"a_id": 1, "name": "x"}]),
        _table(3, "t_dim_b", "维B", "b", 10, [{"b_id": 1, "name": "y"}]),
        _table(4, "t_sku", "商品", "sku", 20, [{"sku_id": "s1", "a_id": 1, "b_id": 1, "price": 9.9}]),
    ]
    profiles = []
    for table in tables:
        profiles.extend(
            {"table_id": table["id"], **profile} for profile in ps.profile_table(table["sample_rows"])
        )
    discovery = ps.discover_relations(profiles)
    classified = ss.classify_tables(tables, profiles, discovery["relations"])
    roles = {item["table_id"]: item["role"] for item in classified}
    assert roles[1] == ss.ROLE_FACT
    assert roles[4] == ss.ROLE_DIM


def test_export_sql_has_nine_segments():
    _tables, _profiles, _discovery, built = _pipeline()
    for index, suggestion in enumerate(built["suggestions"]):
        suggestion["status"] = "已采纳" if index == 0 else "待采纳"
    sql = ss.build_export_sql(built["suggestions"], "MR20261113-0001")
    assert sql.count("-- =====") == 9
    assert "[01] dwd_inventory_fact" in sql
    assert "已采纳" in sql


def test_build_suggestions_deterministic():
    first = _pipeline()[3]["suggestions"]
    second = _pipeline()[3]["suggestions"]
    assert first == second
