from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    SUCCESS = "success"
    BUSINESS_OUTCOME = "business_outcome"
    FAILURE = "failure"
    ESCALATED = "escalated"


class OutcomeClass(str, Enum):
    BUSINESS_OUTCOME = "business_outcome"
    RECOVERABLE = "recoverable"
    HARD_FAILURE = "hard_failure"


class Effect(str, Enum):
    READ_ONLY = "read_only"
    REVERSIBLE_MUTATION = "reversible_mutation"
    IRREVERSIBLE_MUTATION = "irreversible_mutation"


class ApprovalState(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"


class RunError(BaseModel):
    code: str
    message: str

    step_id: str | None = None
    details: dict[str, Any] = Field(
        default_factory=dict
    )


class RunResult(BaseModel):
    status: RunStatus

    capability_id: str
    capability_version: str

    outputs: dict[str, Any] = Field(
        default_factory=dict
    )

    outcome_code: str | None = None
    error: RunError | None = None