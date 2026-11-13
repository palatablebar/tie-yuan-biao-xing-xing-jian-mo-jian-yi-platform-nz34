"""草案核对（validation）：关系与粒度的硬校验，发布前必须全部通过。

核对口径全部来自版本快照里的量化结果，不重新抽样、不联网：
1. 关系完整性：每条边的右列必须是右表候选键（唯一率 = 1 且空值率 = 0）。
2. 弱外键兜底：fk（弱外键候选）边的包含度必须仍 ≥ 0.98 阈值。
3. 事实粒度可落地：每张事实建议的粒度外键必须非空，且抽样去重组合数 ≤ 抽样行数。
4. 粒度组合真实去重：去重组合数至少为 1，且不能等于「每行一个组合」之外的异常态
   （去重数不得超过抽样行数）。
5. DDL 与关联边一致：事实建议 DDL 里的 FOREIGN KEY 数量必须等于 joins 关联边数。
6. 目标表名唯一：同一版本内 target_name 不允许重复（导出 DDL 不能撞名）。

任一 check 不通过 → passed=False，草案置 validation_failed，禁止发布；
正式版保持上一版不动，前端展示失败 check 与依据。
"""
from __future__ import annotations

from typing import Any, Sequence

from src.services.profiling_service import CONTAINMENT_THRESHOLD


def _check(check_id: str, label: str, passed: bool, detail: dict[str, Any]) -> dict[str, Any]:
    return {"id": check_id, "label": label, "passed": bool(passed), "detail": detail}


def validate_version(
    profiles: Sequence[dict],
    relations: Sequence[dict],
    suggestions: Sequence[dict],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    # 1. 关系完整性：右列必须是右表候选键
    unique_keys = {
        (profile["table_id"], profile["column"])
        for profile in profiles
        if profile["unique_ratio"] >= 1 - 1e-9 and profile["null_ratio"] == 0
    }
    bad_targets = [
        f"{rel['left_table_id']}.{rel['left_column']}->{rel['right_table_id']}.{rel['right_column']}"
        for rel in relations
        if (rel["right_table_id"], rel["right_column"]) not in unique_keys
    ]
    checks.append(
        _check(
            "relation_target_key",
            "关系右列均为候选键（唯一率=1 且无空值）",
            not bad_targets,
            {"violations": bad_targets, "relation_total": len(relations)},
        )
    )

    # 2. 弱外键包含度兜底
    weak_below = [
        {
            "edge": f"{rel['left_table_id']}.{rel['left_column']}->{rel['right_table_id']}.{rel['right_column']}",
            "containment": rel["containment"],
        }
        for rel in relations
        if rel["kind"] == "fk" and rel["containment"] < CONTAINMENT_THRESHOLD
    ]
    checks.append(
        _check(
            "weak_fk_containment",
            f"弱外键候选包含度均 ≥ {CONTAINMENT_THRESHOLD:.2f}",
            not weak_below,
            {"violations": weak_below},
        )
    )

    # 3 & 4. 事实粒度可落地 + 去重组合数合理
    grain_issues: list[dict[str, Any]] = []
    for suggestion in suggestions:
        if suggestion["role"] != "fact":
            continue
        evidence = suggestion.get("evidence") or {}
        grain_columns = evidence.get("grain_columns") or []
        combos = int(evidence.get("grain_combos") or 0)
        sampled = int(evidence.get("sampled_rows") or 0)
        if not grain_columns:
            grain_issues.append({"target": suggestion["target_name"], "reason": "事实表缺少粒度外键"})
        elif combos < 1:
            grain_issues.append({"target": suggestion["target_name"], "reason": "粒度去重组合数为 0"})
        elif sampled and combos > sampled:
            grain_issues.append(
                {"target": suggestion["target_name"], "reason": f"去重组合 {combos} 多于抽样行 {sampled}"}
            )
    checks.append(
        _check(
            "fact_grain",
            "事实建议粒度外键非空且抽样去重组合数 ≤ 抽样行数",
            not grain_issues,
            {"violations": grain_issues, "fact_total": sum(1 for s in suggestions if s["role"] == "fact")},
        )
    )

    # 5. DDL 外键数与关联边一致
    ddl_issues: list[dict[str, Any]] = []
    for suggestion in suggestions:
        if suggestion["role"] != "fact":
            continue
        fk_in_ddl = (suggestion.get("ddl") or "").count("FOREIGN KEY")
        joins = len(suggestion.get("joins") or [])
        if fk_in_ddl != joins:
            ddl_issues.append(
                {"target": suggestion["target_name"], "ddl_foreign_keys": fk_in_ddl, "join_edges": joins}
            )
    checks.append(
        _check(
            "ddl_join_consistency",
            "事实 DDL 的 FOREIGN KEY 数量与关联边数一致",
            not ddl_issues,
            {"violations": ddl_issues},
        )
    )

    # 6. 目标表名唯一
    target_names = [suggestion["target_name"] for suggestion in suggestions]
    duplicates = sorted({name for name in target_names if target_names.count(name) > 1})
    checks.append(
        _check(
            "target_name_unique",
            "同一版本内目标表名不重复",
            not duplicates,
            {"duplicates": duplicates},
        )
    )

    failed_checks = [check["id"] for check in checks if not check["passed"]]
    return {
        "passed": not failed_checks,
        "checks": checks,
        "failed_checks": failed_checks,
    }
