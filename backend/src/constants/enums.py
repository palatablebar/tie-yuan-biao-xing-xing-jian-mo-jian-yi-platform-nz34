"""共享枚举（后端唯一定义处）。前端副本见 frontend/site/js/config.js。

README「共享枚举出现位置」一节列出全部出现点，改动需两侧同步。
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class TableDomain(StrEnum):
    """贴源表所属主题域（禾丰零售数仓分层前的业务域）。"""

    SALES = "sales"
    INVENTORY = "inventory"
    MEMBER = "member"
    PRODUCT = "product"
    SUPPLY = "supply"
    ORG = "org"
    LOG = "log"
    CONFIG = "config"


TABLE_DOMAIN_LABELS: dict[str, str] = {
    TableDomain.SALES.value: "销售",
    TableDomain.INVENTORY.value: "库存",
    TableDomain.MEMBER.value: "会员",
    TableDomain.PRODUCT.value: "商品",
    TableDomain.SUPPLY.value: "供应",
    TableDomain.ORG.value: "组织",
    TableDomain.LOG.value: "日志",
    TableDomain.CONFIG.value: "配置",
}

TABLE_DOMAIN_ORDER: list[str] = [item.value for item in TableDomain]


class DataType(StrEnum):
    INT = "int"
    DECIMAL = "decimal"
    DATE = "date"
    STRING = "string"
    BOOL = "bool"


DTYPE_LABELS: dict[str, str] = {
    DataType.INT.value: "整数",
    DataType.DECIMAL.value: "数值",
    DataType.DATE.value: "日期",
    DataType.STRING.value: "文本",
    DataType.BOOL.value: "布尔",
}


class RelationKind(StrEnum):
    """包含依赖关系类型：pk-fk 为强主外键（包含度 100%），fk 为弱外键候选。"""

    PK_FK = "pk-fk"
    FK = "fk"


RELATION_KIND_LABELS: dict[str, str] = {
    RelationKind.PK_FK.value: "主外键",
    RelationKind.FK.value: "弱外键候选",
}

RELATION_KIND_ORDER: list[str] = [RelationKind.PK_FK.value, RelationKind.FK.value]


class SuggestionRole(StrEnum):
    FACT = "fact"
    DIM = "dim"


SUGGESTION_ROLE_LABELS: dict[str, str] = {
    SuggestionRole.FACT.value: "事实表",
    SuggestionRole.DIM.value: "维度表",
}

SUGGESTION_ROLE_ORDER: list[str] = [SuggestionRole.FACT.value, SuggestionRole.DIM.value]


class SuggestionStatus(StrEnum):
    PENDING = "pending"
    ADOPTED = "adopted"
    DISMISSED = "dismissed"


SUGGESTION_STATUS_LABELS: dict[str, str] = {
    SuggestionStatus.PENDING.value: "待采纳",
    SuggestionStatus.ADOPTED.value: "已采纳",
    SuggestionStatus.DISMISSED.value: "已驳回",
}

SUGGESTION_STATUS_ORDER: list[str] = [
    SuggestionStatus.PENDING.value,
    SuggestionStatus.ADOPTED.value,
    SuggestionStatus.DISMISSED.value,
]


class ModelRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


MODEL_RUN_STATUS_LABELS: dict[str, str] = {
    ModelRunStatus.QUEUED.value: "排队中",
    ModelRunStatus.RUNNING.value: "剖析中",
    ModelRunStatus.SUCCESS.value: "成功",
    ModelRunStatus.PARTIAL.value: "部分成功",
    ModelRunStatus.FAILED.value: "失败",
}


class TriggerKind(StrEnum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    SEED = "seed"


TRIGGER_LABELS: dict[str, str] = {
    TriggerKind.MANUAL.value: "手动",
    TriggerKind.SCHEDULE.value: "定时",
    TriggerKind.SEED.value: "初始化",
}
