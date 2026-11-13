"""角色 -> 权限点映射。README 与前端 site/js/config.js 同步。

角色键固定为 admin / analyst / viewer，各项目的展示名与职责不同。
"""
from __future__ import annotations

from src.constants.enums import Role

ROLE_LABELS: dict[str, str] = {
    Role.ADMIN.value: "平台管理员",
    Role.ANALYST.value: "建模专员",
    Role.VIEWER.value: "只读访客",
}

ROLE_DUTIES: dict[str, str] = {
    Role.ADMIN.value: "登记贴源表、采纳建模建议、导出 DDL、查看审计",
    Role.ANALYST.value: "执行剖析与建模建议、复核建议（驳回），不能采纳或导出",
    Role.VIEWER.value: "只读表清单、关系图与建议列表",
}

PERMISSIONS: dict[str, set[str]] = {
    Role.ADMIN.value: {
        "table:read", "table:write",
        "profile:read", "relation:read",
        "run:read", "run:create",
        "suggestion:read", "suggestion:adopt", "suggestion:review",
        "version:read", "version:release",
        "export:read", "audit:read", "overview:read",
    },
    Role.ANALYST.value: {
        "table:read", "profile:read", "relation:read",
        "run:read", "run:create",
        "suggestion:read", "suggestion:review",
        "version:read",
        "export:read", "overview:read",
    },
    Role.VIEWER.value: {
        "table:read", "profile:read", "relation:read", "run:read",
        "suggestion:read", "version:read", "overview:read",
    },
}

TABLE_WRITE_ROLES = (Role.ADMIN.value,)
RUN_CREATE_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
SUGGESTION_REVIEW_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
SUGGESTION_ADOPT_ROLES = (Role.ADMIN.value,)
VERSION_RELEASE_ROLES = (Role.ADMIN.value,)
EXPORT_ROLES = (Role.ADMIN.value,)
EXPORT_CSV_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
AUDIT_ROLES = (Role.ADMIN.value,)
READ_ROLES = (Role.ADMIN.value, Role.ANALYST.value, Role.VIEWER.value)


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())
