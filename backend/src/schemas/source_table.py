from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TableIn(BaseModel):
    name: str = Field(min_length=3, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    cn_name: str = Field(min_length=2, max_length=120)
    subject: str = Field(default="", max_length=40)
    domain: Literal["sales", "inventory", "member", "product", "supply", "org", "log", "config"] = "sales"
    row_count: int = Field(default=0, ge=0, le=10_000_000_000)
    sample_rows: list[dict] = Field(default_factory=list, max_length=200)
    note: str | None = Field(default=None, max_length=2000)


class TablePatch(BaseModel):
    cn_name: str | None = Field(default=None, min_length=2, max_length=120)
    note: str | None = Field(default=None, max_length=2000)
