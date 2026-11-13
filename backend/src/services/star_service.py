"""算法 B：星型建模建议（事实/维度判定 + 粒度 + DDL）+ DDL 导出（纯函数）。

判定口径：
1. 事实表：出边（本表 *_id 列指向候选键）≥ 2、存在度量列，且表体量 ≥ 10 万行或度量列 ≥ 3（避免把带单价的商品维判成事实）。
2. 维度表：存在候选键、≥2 个描述列（非 *_id、非度量、非日期）、表体量 ≤ 10 万行。
3. 其余为无关表（日志 / 配置 / 流水 staging）。
4. 粒度：事实表的维度外键按源表列顺序组合，对抽样行做去重计数。
5. 建议范围：4 张事实表 + 被事实表直接引用的维度表（seed 下 5 张，合计 9 条）；
   仅被其他维表引用的为二级维（雪花），在 metrics 里单列，不生成建议。
6. DDL：事实表保留代理键 + 维度外键 + 度量列，并生成 FOREIGN KEY；维度表保留代理键 + 属性列。
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

from src.services.profiling_service import normalize, preferred_key

ROLE_FACT = "fact"
ROLE_DIM = "dim"
ROLE_NONE = "none"

MEASURE_TOKENS = (
    "amount",
    "amt",
    "qty",
    "quantity",
    "points",
    "cost",
    "price",
    "discount",
    "tax",
    "total",
    "balance",
    "on_hand",
    "budget",
)
DATEISH_SUFFIXES = ("_at", "_date", "_ts", "_time")
DATEISH_NAMES = {"date", "ts", "day", "month", "year", "quarter", "weekday"}
DTYPE_SQL = {
    "int": "BIGINT",
    "decimal": "DECIMAL(18,3)",
    "date": "DATE",
    "string": "VARCHAR(128)",
    "bool": "TINYINT(1)",
}
DIM_DDL_TYPES = {
    "int": "BIGINT",
    "decimal": "DECIMAL(18,3)",
    "date": "DATE",
    "string": "VARCHAR(128)",
    "bool": "TINYINT(1)",
}


def is_measure(column: str) -> bool:
    lowered = column.lower()
    return any(token in lowered for token in MEASURE_TOKENS)


def is_identifier(column: str) -> bool:
    return column.lower().endswith("_id")


def is_dateish(column: str) -> bool:
    lowered = column.lower()
    if lowered.endswith(DATEISH_SUFFIXES):
        return True
    if "date" in lowered:
        return True
    return lowered in DATEISH_NAMES


def classify_tables(
    tables: Sequence[dict],
    profiles: Sequence[dict],
    relations: Sequence[dict],
) -> list[dict]:
    classified: list[dict] = []
    for table in tables:
        columns = [profile for profile in profiles if profile["table_id"] == table["id"]]
        keys = [
            profile
            for profile in columns
            if profile["unique_ratio"] >= 1 - 1e-9 and profile["null_ratio"] == 0
        ]
        key_profile = preferred_key(keys)
        measures = [profile["column"] for profile in columns if is_measure(profile["column"])]
        identifiers = [profile["column"] for profile in columns if is_identifier(profile["column"])]
        descriptive = [
            profile["column"]
            for profile in columns
            if not is_identifier(profile["column"])
            and not is_measure(profile["column"])
            and not is_dateish(profile["column"])
        ]
        outgoing = [relation for relation in relations if relation["left_table_id"] == table["id"]]
        fact_score = 0
        if len(outgoing) >= 2:
            fact_score += 2
        if measures:
            fact_score += 1
        if int(table.get("row_count") or 0) >= 100_000:
            fact_score += 1
        dim_score = 0
        if keys:
            dim_score += 2
        if len(descriptive) >= 2:
            dim_score += 1
        if identifiers:
            dim_score += 1
        if int(table.get("row_count") or 0) <= 100_000:
            dim_score += 1
        heavy_measures = len(measures) >= 3
        if (
            fact_score >= 3
            and len(outgoing) >= 2
            and (int(table.get("row_count") or 0) >= 100_000 or heavy_measures)
        ):
            role = ROLE_FACT
        elif dim_score >= 3 and keys:
            role = ROLE_DIM
        else:
            role = ROLE_NONE
        classified.append(
            {
                "table_id": table["id"],
                "role": role,
                "pk": key_profile["column"] if key_profile else None,
                "measures": measures,
                "identifiers": identifiers,
                "descriptive": descriptive,
                "outgoing": len(outgoing),
                "fact_score": fact_score,
                "dim_score": dim_score,
            }
        )
    return classified


def grain_combinations(rows: Sequence[dict], columns: Sequence[str], limit: int = 200) -> tuple[int, int]:
    sample = list(rows or [])[:limit]
    combos = {tuple(normalize(row.get(column)) for column in columns) for row in sample}
    return len(combos), len(sample)


def _column_sql(profile: dict, not_null: bool = False) -> str:
    dtype = DTYPE_SQL.get(profile["dtype"], "VARCHAR(128)")
    return f"  {profile['column']} {dtype}{' NOT NULL' if not_null else ''}"


def build_fact_ddl(
    target: str,
    table: dict,
    profiles: Sequence[dict],
    fk_pairs: Sequence[tuple[str, dict]],
    dim_targets: dict[int, str],
) -> str:
    key_profile = preferred_key(profiles)
    pk = key_profile["column"] if key_profile else None
    fk_columns = {column for column, _relation in fk_pairs}
    lines: list[str] = [
        f"-- 事实表建议：{table['name']}（{table['cn_name']}）→ {target}",
        f"CREATE TABLE {target} (",
    ]
    body: list[str] = []
    for profile in profiles:
        column = profile["column"]
        if column == pk:
            body.append(_column_sql(profile, not_null=True))
        elif column in fk_columns:
            body.append(_column_sql(profile, not_null=True))
        elif is_measure(column):
            body.append(_column_sql(profile))
    if pk:
        body.append(f"  PRIMARY KEY ({pk})")
    lines.append(",\n".join(body))
    lines.append(");")
    for column, relation in fk_pairs:
        dim_target = dim_targets.get(relation["right_table_id"], relation["right_table_id"])
        constraint = f"fk_{target}_{dim_target}".replace("-", "_")
        lines.append(
            f"ALTER TABLE {target} ADD CONSTRAINT {constraint} "
            f"FOREIGN KEY ({column}) REFERENCES {dim_target}({relation['right_column']});"
        )
    return "\n".join(lines)


def build_dim_ddl(target: str, table: dict, profiles: Sequence[dict], fk_pairs: Sequence[tuple[str, dict]], dim_targets: dict[int, str]) -> str:
    key_profile = preferred_key(profiles)
    pk = key_profile["column"] if key_profile else None
    fk_columns = {column for column, _relation in fk_pairs}
    body: list[str] = []
    for profile in profiles:
        column = profile["column"]
        if column == pk:
            body.append(_column_sql(profile, not_null=True))
        elif column in fk_columns:
            body.append(_column_sql(profile))
        elif not is_identifier(column) and not is_dateish(column):
            body.append(_column_sql(profile))
    if pk:
        body.append(f"  PRIMARY KEY ({pk})")
    lines = [
        f"-- 维度表建议：{table['name']}（{table['cn_name']}）→ {target}",
        f"CREATE TABLE {target} (",
        ",\n".join(body),
        ");",
    ]
    for column, relation in fk_pairs:
        parent = dim_targets.get(relation["right_table_id"], relation["right_table_id"])
        constraint = f"fk_{target}_{parent}".replace("-", "_")
        lines.append(
            f"ALTER TABLE {target} ADD CONSTRAINT {constraint} "
            f"FOREIGN KEY ({column}) REFERENCES {parent}({relation['right_column']});"
        )
    return "\n".join(lines)


def build_suggestions(
    tables: Sequence[dict],
    profiles: Sequence[dict],
    relations: Sequence[dict],
    rows_by_table: dict[int, list[dict]],
) -> dict:
    classified = classify_tables(tables, profiles, relations)
    role_by_id = {item["table_id"]: item["role"] for item in classified}
    table_by_id = {table["id"]: table for table in tables}
    dim_targets = {
        table["id"]: f"dim_{table['subject']}" for table in tables if role_by_id.get(table["id"]) == ROLE_DIM
    }

    facts = [table for table in tables if role_by_id.get(table["id"]) == ROLE_FACT]
    fact_ids = {table["id"] for table in facts}
    referenced = {
        relation["right_table_id"]
        for relation in relations
        if relation["left_table_id"] in fact_ids and role_by_id.get(relation["right_table_id"]) == ROLE_DIM
    }
    primary_dims = [table for table in tables if table["id"] in referenced]
    secondary_dims = [
        table
        for table in tables
        if role_by_id.get(table["id"]) == ROLE_DIM and table["id"] not in referenced
    ]

    suggestions: list[dict] = []
    for table in sorted(facts, key=lambda item: item["name"]):
        columns = [profile for profile in profiles if profile["table_id"] == table["id"]]
        outgoing = [relation for relation in relations if relation["left_table_id"] == table["id"]]
        relation_by_column = {relation["left_column"]: relation for relation in outgoing}
        fk_columns = sorted(
            (profile["column"] for profile in columns if profile["column"] in relation_by_column),
            key=lambda column: relation_by_column[column]["right_table_id"],
        )
        dims = [table_by_id[relation_by_column[column]["right_table_id"]] for column in fk_columns]
        combos, sampled = grain_combinations(rows_by_table.get(table["id"], []), fk_columns)
        grain_label = "×".join(dim["cn_name"] for dim in dims) or "全表汇总"
        avg_containment = (
            sum(relation_by_column[column]["containment"] for column in fk_columns) / len(fk_columns)
            if fk_columns
            else 0.0
        )
        target = f"dwd_{table['subject']}_fact"
        confidence = round(min(0.98, 0.70 + 0.05 * len(fk_columns) + 0.12 * avg_containment), 3)
        joins = [
            {
                "dim_table": table_by_id[relation_by_column[column]["right_table_id"]]["name"],
                "dim_target": dim_targets.get(relation_by_column[column]["right_table_id"], ""),
                "fact_column": column,
                "dim_column": relation_by_column[column]["right_column"],
                "containment": relation_by_column[column]["containment"],
            }
            for column in fk_columns
        ]
        suggestions.append(
            {
                "table_id": table["id"],
                "target_name": target,
                "role": ROLE_FACT,
                "grain": f"{grain_label}（抽样 {sampled} 行去重 {combos} 个组合）",
                "grain_columns": fk_columns,
                "grain_combos": combos,
                "joins": joins,
                "measures": [profile["column"] for profile in columns if is_measure(profile["column"])],
                "attributes": [],
                "confidence": confidence,
                "ddl": build_fact_ddl(
                    target,
                    table,
                    columns,
                    [(column, relation_by_column[column]) for column in fk_columns],
                    dim_targets,
                ),
                "reason": f"识别到 {len(fk_columns)} 个维度外键，{len([c for c in columns if is_measure(c['column'])])} 个度量列，按外键组合去重得到粒度。",
            }
        )

    for table in sorted(primary_dims, key=lambda item: item["name"]):
        columns = [profile for profile in profiles if profile["table_id"] == table["id"]]
        outgoing = [relation for relation in relations if relation["left_table_id"] == table["id"]]
        relation_by_column = {relation["left_column"]: relation for relation in outgoing}
        fk_columns = [profile["column"] for profile in columns if profile["column"] in relation_by_column]
        incoming_from_facts = [
            relation
            for relation in relations
            if relation["right_table_id"] == table["id"] and relation["left_table_id"] in fact_ids
        ]
        classified_item = next(item for item in classified if item["table_id"] == table["id"])
        pk = classified_item["pk"] or table["name"] + "_id"
        target = dim_targets.get(table["id"]) or f"dim_{table['subject']}"
        confidence = round(min(0.97, 0.82 + 0.03 * len(incoming_from_facts)), 3)
        suggestions.append(
            {
                "table_id": table["id"],
                "target_name": target,
                "role": ROLE_DIM,
                "grain": f"1 行 = 1 个{table['cn_name']}（{pk} 唯一）",
                "grain_columns": [pk],
                "grain_combos": int(table.get("row_count") or 0),
                "joins": [
                    {
                        "fact_table": table_by_id[relation["left_table_id"]]["name"],
                        "fact_column": relation["left_column"],
                        "dim_column": relation["right_column"],
                    }
                    for relation in incoming_from_facts
                ],
                "measures": [],
                "attributes": [profile["column"] for profile in columns if not is_identifier(profile["column"])],
                "confidence": confidence,
                "ddl": build_dim_ddl(
                    target,
                    table,
                    columns,
                    [(column, relation_by_column[column]) for column in fk_columns],
                    dim_targets,
                ),
                "reason": f"存在候选键 {pk} 与 {len(classified_item['descriptive'])} 个描述列，被 {len(incoming_from_facts)} 张事实表直接引用，判定为维度表。",
            }
        )

    return {
        "suggestions": suggestions,
        "classified": classified,
        "fact_tables": [table["name"] for table in facts],
        "primary_dim_tables": [table["name"] for table in primary_dims],
        "secondary_dim_tables": [table["name"] for table in secondary_dims],
        "unrelated_tables": [
            table["name"] for table in tables if role_by_id.get(table["id"]) == ROLE_NONE
        ],
    }


def build_export_sql(suggestions: Sequence[dict], run_no: str) -> str:
    """导出 9 段 DDL：每条建议一段，段头含序号 / 目标表 / 角色 / 置信度 / 状态。"""
    lines = [
        "-- 贴源表星型建模建议台 · DDL 导出",
        f"-- 运行 {run_no} · 建议 {len(suggestions)} 条 · 由后端算法生成，人工采纳状态见段头",
        "",
    ]
    ordered = sorted(
        suggestions,
        key=lambda item: (0 if item["role"] == ROLE_FACT else 1, item["target_name"]),
    )
    for index, suggestion in enumerate(ordered, start=1):
        label = "事实表" if suggestion["role"] == ROLE_FACT else "维度表"
        lines.append(
            f"-- ===== [{index:02d}] {suggestion['target_name']} · {label} · "
            f"置信度 {float(suggestion['confidence']):.3f} · 状态 {suggestion['status']}"
        )
        lines.append(suggestion["ddl"].strip())
        lines.append("")
    return "\n".join(lines) + "\n"
