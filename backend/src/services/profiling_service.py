"""算法 A：字段剖析 + 候选键 + 包含依赖发现（全部纯函数，可单测）。

口径：
1. 每张表最多抽样 200 行；逐列统计 unique_ratio = 去重值数 / 抽样行数（NULL 计入分母），
   null_ratio = 空值行数 / 抽样行数，cardinality = 去重值数，保留去重样本值（≤64 个）。
2. 候选键：unique_ratio == 1 且 null_ratio == 0 的列。
3. 包含依赖：左侧列名以 `_id` 结尾且不是本表自己的候选键；右侧列名与左侧同名、是本表候选键；
   包含度 = 左侧去重样本值落在右侧样本集合中的比例。包含度 ≥ 0.98 记为外键候选；
   包含度 = 1.0 记为强主外键（pk-fk），0.98 ≤ 包含度 < 1.0 记为弱外键候选（fk）。
4. 置信度 = min(0.99, 0.60 + 0.33 * 包含度 + 0.06)；纯确定性，无网络、无随机。
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

SAMPLE_LIMIT = 200
SAMPLE_VALUES_LIMIT = 64
CONTAINMENT_THRESHOLD = 0.98
UNIQUE_EPSILON = 1e-9

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$")


def normalize(value: Any) -> Any:
    """把样本值转成可比较、可 JSON 序列化的键。"""
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    return str(value)


def value_sort_key(value: Any) -> str:
    return f"{type(value).__name__}:{value}"


def infer_dtype(values: Sequence[Any]) -> str:
    sample = [value for value in values if value is not None and value != ""]
    if not sample:
        return "string"
    if all(isinstance(value, bool) for value in sample):
        return "bool"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in sample):
        return "int"
    if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in sample):
        return "decimal"
    if all(isinstance(value, str) for value in sample):
        if all(_DATE_RE.match(value) or _DATETIME_RE.match(value) for value in sample):
            return "date"
        return "string"
    return "string"


def profile_column(rows: Sequence[dict], column: str, limit: int = SAMPLE_LIMIT) -> dict:
    sample = list(rows)[:limit]
    total = len(sample)
    raw = [row.get(column) for row in sample]
    present = [value for value in raw if value is not None and value != ""]
    distinct = {normalize(value) for value in present}
    return {
        "column": column,
        "dtype": infer_dtype(present),
        "unique_ratio": round(len(distinct) / total, 4) if total else 0.0,
        "null_ratio": round((total - len(present)) / total, 4) if total else 0.0,
        "cardinality": len(distinct),
        "sample_values": sorted(distinct, key=value_sort_key)[:SAMPLE_VALUES_LIMIT],
        "sample_size": total,
    }


def columns_of(rows: Sequence[dict]) -> list[str]:
    seen: list[str] = []
    for row in rows:
        for key in row:
            if key not in seen:
                seen.append(key)
    return seen


def profile_table(rows: Sequence[dict], limit: int = SAMPLE_LIMIT) -> list[dict]:
    sample = list(rows)[:limit]
    return [profile_column(sample, column, limit) for column in columns_of(sample)]


def candidate_keys(profiles: Iterable[dict]) -> list[dict]:
    return [
        profile
        for profile in profiles
        if profile["unique_ratio"] >= 1 - UNIQUE_EPSILON and profile["null_ratio"] == 0
    ]


def preferred_key(profiles: Sequence[dict]) -> dict | None:
    """候选键里优先取 *_id 代理键（贴源表的业务主键），否则取第一个候选键。"""
    keys = candidate_keys(profiles)
    if not keys:
        return None
    for key in keys:
        if key["column"].endswith("_id"):
            return key
    return keys[0]


def containment(left_values: Sequence[Any], right_values: Sequence[Any]) -> float:
    """左侧去重样本值中，落在右侧样本集合里的比例。"""
    left = {normalize(value) for value in left_values if value is not None and value != ""}
    if not left:
        return 0.0
    right = {normalize(value) for value in right_values if value is not None and value != ""}
    return round(len(left & right) / len(left), 4)


def relation_confidence(ratio: float) -> float:
    return round(min(0.99, 0.60 + 0.33 * ratio + 0.06), 3)


def discover_relations(profiles: Sequence[dict], threshold: float = CONTAINMENT_THRESHOLD) -> dict:
    """profiles 需含 table_id / column / unique_ratio / null_ratio / sample_values / sample_size。"""
    unique_columns = [
        profile
        for profile in profiles
        if profile["unique_ratio"] >= 1 - UNIQUE_EPSILON and profile["null_ratio"] == 0
    ]
    by_table: dict[int, list[dict]] = {}
    for profile in unique_columns:
        by_table.setdefault(profile["table_id"], []).append(profile)
    own_key: dict[int, str] = {}
    for table_id, table_unique in by_table.items():
        key = preferred_key(table_unique)
        if key is not None:
            own_key[table_id] = key["column"]

    relations: list[dict] = []
    rejected = 0
    for left in profiles:
        column = left["column"]
        if not column.endswith("_id"):
            continue
        if own_key.get(left["table_id"]) == column:
            continue
        for right in unique_columns:
            if right["table_id"] == left["table_id"] or right["column"] != column:
                continue
            ratio = containment(left["sample_values"], right["sample_values"])
            if ratio < threshold:
                rejected += 1
                continue
            relations.append(
                {
                    "left_table_id": left["table_id"],
                    "left_column": column,
                    "right_table_id": right["table_id"],
                    "right_column": right["column"],
                    "containment": ratio,
                    "confidence": relation_confidence(ratio),
                    "kind": "pk-fk" if ratio >= 1 - 1e-9 else "fk",
                    "sample_size": min(int(left.get("sample_size") or 0), SAMPLE_LIMIT),
                }
            )
    relations.sort(key=lambda item: (item["left_table_id"], item["left_column"], item["right_table_id"]))
    return {"relations": relations, "rejected": rejected, "unique_columns": len(unique_columns)}


def profile_tables(tables: Sequence[dict], limit: int = SAMPLE_LIMIT) -> dict:
    """一次性剖析多张表，返回 {table_id: [profile...]} 与汇总。"""
    result: dict[int, list[dict]] = {}
    total = 0
    for table in tables:
        profiles = profile_table(table.get("sample_rows") or [], limit)
        result[table["id"]] = profiles
        total += len(profiles)
    return {"profiles": result, "total": total}
