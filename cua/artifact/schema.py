from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from cua.types import ApprovalState, Effect, OutcomeClass


class LocatorStrategy(BaseModel):
    kind: Literal[
        "role_name",
        "label_text",
        "anchor_relative",
        "table_cell",
        "xpath",
        "bbox",
    ]

    rank: int = Field(ge=1)

    role: str | None = None
    name: str | None = None

    value: str | None = None

    anchor_text: str | None = None
    relationship: str | None = None

    row_anchor: str | None = None
    column_header: str | None = None

    x: float | None = None
    y: float | None = None


class TargetLocator(BaseModel):
    strategies: list[LocatorStrategy]
    degradation_policy: Literal[
        "ignore",
        "warn_above_rank_3",
        "fail_above_rank_3",
    ] = "warn_above_rank_3"


class ValueSource(BaseModel):
    source: Literal["input", "literal"]
    key: str | None = None
    value: Any | None = None


class WaitSpec(BaseModel):
    kind: Literal["settled", "visible", "url_change"]
    timeout_ms: int = Field(default=5000, ge=0)


class Checkpoint(BaseModel):
    kind: Literal[
        "field_value_matches_input",
        "text_visible",
        "url_matches",
        "element_visible",
        "table_contains_row",
    ]

    key: str | None = None
    value: str | None = None
    pattern: str | None = None

    target: TargetLocator | None = None


class Step(BaseModel):
    id: str
    intent: str

    action: Literal[
        "navigate",
        "click",
        "fill",
        "read",
    ]

    effect: Effect

    frame: str | None = None

    target: TargetLocator | None = None
    value: ValueSource | None = None

    wait: WaitSpec | None = None
    checkpoint: Checkpoint | None = None

    on_failure: Literal[
        "retry",
        "recover",
        "escalate",
        "fail",
    ] = "fail"


class Detector(BaseModel):
    kind: Literal[
        "text_visible",
        "role_visible",
        "url_matches",
        "table_has_no_row_matching",
    ]

    value: str | None = None
    role: str | None = None
    column_header: str | None = None


class ExpectedOutcome(BaseModel):
    code: str
    classification: OutcomeClass = OutcomeClass.BUSINESS_OUTCOME

    after_step: str | None = None
    precedence: int = 100

    detector: Detector
    returns: dict[str, Any] = Field(default_factory=dict)


class RecoveryAction(BaseModel):
    kind: Literal[
        "dismiss",
        "reauthenticate",
        "retry",
    ]

    control: TargetLocator | None = None


class RecoveryRule(BaseModel):
    code: str
    detector: Detector
    action: RecoveryAction

    then: Literal[
        "retry_current_step",
        "reverify_current_checkpoint",
    ]

    max_attempts: int = Field(default=1, ge=1)


class InputSpec(BaseModel):
    type: Literal["string", "integer", "decimal", "boolean"]
    required: bool = True

    pattern: str | None = None
    redact_in_logs: bool = False


class ExtractSpec(BaseModel):
    strategies: list[LocatorStrategy]

    parse_kind: Literal[
        "string",
        "currency",
        "integer",
        "decimal",
    ] = "string"


class OutputSpec(BaseModel):
    type: Literal["string", "integer", "decimal", "boolean"]

    redact_in_logs: bool = False
    return_to_caller: bool = True

    extract: ExtractSpec | None = None


class CapabilityMetadata(BaseModel):
    id: str
    version: str
    name: str
    description: str
    approval_state: ApprovalState = ApprovalState.DRAFT


class FingerprintRule(BaseModel):
    kind: Literal["text_visible", "url_pattern"]
    value: str


class TargetSpec(BaseModel):
    app_id: str
    vendor: str
    supported_versions: str | None = None

    fingerprint: list[FingerprintRule] = Field(default_factory=list)


class PolicyDeclaration(BaseModel):
    max_steps: int = Field(default=20, ge=1)
    max_duration_s: int = Field(default=60, ge=1)

    declared_max_effect: Effect = Effect.READ_ONLY


class Provenance(BaseModel):
    discovered_by: str | None = None
    discovery_run_id: str | None = None
    recorded_at: str | None = None
    reviewed_by: str | None = None


class SuccessCondition(BaseModel):
    all_of: list[str] = Field(default_factory=list)


class CapabilityArtifact(BaseModel):
    schema_version: str

    capability: CapabilityMetadata
    target: TargetSpec

    inputs: dict[str, InputSpec]
    outputs: dict[str, OutputSpec]

    steps: list[Step]

    recoveries: list[RecoveryRule] = Field(default_factory=list)
    expected_outcomes: list[ExpectedOutcome] = Field(default_factory=list)

    success_condition: SuccessCondition

    policy: PolicyDeclaration
    provenance: Provenance