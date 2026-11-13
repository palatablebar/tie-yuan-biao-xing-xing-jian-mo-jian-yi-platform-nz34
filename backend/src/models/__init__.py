"""ORM 模型聚合导出（Base 用于 create_all）。"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from src.models.user import User  # noqa: E402
from src.models.audit import AuditLog  # noqa: E402
from src.models.source_table import SourceTable  # noqa: E402
from src.models.analysis_version import AnalysisVersion  # noqa: E402
from src.models.column_profile import ColumnProfile  # noqa: E402
from src.models.relation import Relation  # noqa: E402
from src.models.model_run import ModelRun  # noqa: E402
from src.models.suggestion_decision import SuggestionDecision  # noqa: E402
from src.models.model_suggestion import ModelSuggestion  # noqa: E402

__all__ = [
    "Base",
    "User",
    "AuditLog",
    "SourceTable",
    "AnalysisVersion",
    "ColumnProfile",
    "Relation",
    "ModelRun",
    "SuggestionDecision",
    "ModelSuggestion",
]
