from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class SystemDraftItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    mechanic: Literal["project", "roll", "status"]
    description: str
    payload: dict[str, JsonValue] | None = None


class SystemDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str
    inputs: list[SystemDraftItem] = Field(default_factory=list)
    process: list[SystemDraftItem] = Field(default_factory=list)
    outputs: list[SystemDraftItem] = Field(default_factory=list)
    costs: list[SystemDraftItem] = Field(default_factory=list)
    risks: list[SystemDraftItem] = Field(default_factory=list)
    checks: list[SystemDraftItem] = Field(default_factory=list)
