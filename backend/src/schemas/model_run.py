from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RunIn(BaseModel):
    trigger: Literal["manual", "schedule", "seed"] = "manual"
    note: str | None = Field(default=None, max_length=500)
