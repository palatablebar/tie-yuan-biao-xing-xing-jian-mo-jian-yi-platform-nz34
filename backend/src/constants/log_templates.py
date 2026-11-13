"""审计动作 -> 中文标签。"""
from __future__ import annotations

ACTIONS: dict[str, str] = {
    "auth.login": "登录",
    "table.create": "登记贴源表",
    "run.create": "执行剖析建模",
    "run.complete": "运行完成",
    "suggestion.adopt": "采纳建议",
    "suggestion.dismiss": "驳回建议",
    "export.ddl": "导出 DDL",
    "export.relations": "导出关系清单",
    "http.mutation": "写请求",
}
