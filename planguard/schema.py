"""Pydantic data models for PlanGuard."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Obj(BaseModel):
    id: str
    type: str
    props: set[str] = Field(default_factory=set)
    state: dict[str, bool | str | None] = Field(default_factory=dict)


class Scene(BaseModel):
    scene_id: str = "scene"
    objects: dict[str, Obj]
    holding: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _objects_list_to_dict(cls, data):
        # Accept objects as a list of {id, ...} (web console format) too.
        if isinstance(data, dict) and isinstance(data.get("objects"), list):
            data = {**data, "objects": {o["id"]: o for o in data["objects"]}}
        return data


class Step(BaseModel):
    idx: int
    action: str
    args: list[str]


class Plan(BaseModel):
    instruction: str
    steps: list[Step]


class Severity(str, Enum):
    critical = "critical"
    major = "major"
    minor = "minor"


class Finding(BaseModel):
    step: int | None = None
    code: str
    severity: Severity
    message: str
    evidence: list[str] = Field(default_factory=list)
    layer: Literal["L0", "L1", "L2", "VL"] = "L0"
    confidence: float = 1.0


class Verdict(BaseModel):
    decision: Literal["approve", "repair", "ask_human", "reject"]
    findings: list[Finding]
    plan: Plan
    repaired: Plan | None = None
    escalated: bool = False
    cost_usd: float = 0.0
    latency_ms: dict[str, float] = Field(default_factory=dict)
