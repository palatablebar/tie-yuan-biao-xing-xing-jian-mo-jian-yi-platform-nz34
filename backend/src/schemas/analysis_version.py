from __future__ import annotations

from pydantic import BaseModel, Field


class IncrementalRunIn(BaseModel):
    # 补数受影响的贴源表 id；只重算这些业务对象，其余建议沿用上一正式版快照
    affected_table_ids: list[int] = Field(default_factory=list, max_length=200)
    note: str | None = Field(default=None, max_length=500)
