from __future__ import annotations

import re
import time
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from cua.artifact.schema import (
    CapabilityArtifact,
    Checkpoint,
    Step,
    ValueSource,
)
from cua.observability.capture import EvidenceCapture
from cua.observability.log import RunLogger
from cua.policy.engine import (
    PolicyEngine,
    PolicyViolation,
)
from cua.replay.detectors import OutcomeDetector
from cua.replay.recovery import (
    RecoveryEngine,
    RecoveryError,
)
from cua.surface.web import PlaywrightSurface
from cua.types import (
    RunError,
    RunResult,
    RunStatus,
)


class ReplayEngine:
    def __init__(
        self,
        surface: PlaywrightSurface,
    ) -> None:
        self.surface = surface

        self.outcome_detector = OutcomeDetector()
        self.recovery_engine = RecoveryEngine(
            surface
        )

        self.policy = PolicyEngine(
            surface
        )

        self.logger: RunLogger | None = None
        self.capture: EvidenceCapture | None = None

    async def run(
        self,
        artifact: CapabilityArtifact,
        inputs: dict[str, Any],
    ) -> RunResult:
        run_id = (
            f"replay_{uuid.uuid4().hex[:8]}"
        )

        self.logger = RunLogger(
            run_id
        )

        self.capture = EvidenceCapture(
            self.logger.run_dir
        )

        # Recovery attempt counts belong to one run.
        self.recovery_engine = RecoveryEngine(
            self.surface
        )

        redact_keys = {
            name
            for name, spec
            in artifact.inputs.items()
            if spec.redact_in_logs
        }

        self.logger.log(
            "run_started",
            run_id=run_id,
            capability_id=(
                artifact.capability.id
            ),
            capability_version=(
                artifact.capability.version
            ),
            inputs=(
                self.logger.redact_inputs(
                    inputs,
                    redact_keys,
                )
            ),
        )

        started_at = time.monotonic()

        validation_error = (
            self._validate_inputs(
                artifact,
                inputs,
            )
        )

        if validation_error is not None:
            return await self._failure(
                artifact,
                code="INVALID_INPUT",
                message=validation_error,
            )

        if (
            len(artifact.steps)
            > artifact.policy.max_steps
        ):
            return await self._failure(
                artifact,
                code="MAX_STEPS_EXCEEDED",
                message=(
                    "Artifact contains more steps "
                    "than its declared policy allows."
                ),
            )

        for step in artifact.steps:
            elapsed = (
                time.monotonic()
                - started_at
            )

            if (
                elapsed
                > artifact.policy.max_duration_s
            ):
                return await self._failure(
                    artifact,
                    code="TIMEOUT",
                    message=(
                        "Replay exceeded maximum "
                        "duration."
                    ),
                    step_id=step.id,
                )

            self.logger.log(
                "step_started",
                step_id=step.id,
                action=step.action,
                intent=step.intent,
            )

            # Resolve values before policy evaluation so
            # navigation destinations can be checked.
            try:
                resolved_value = None

                if step.action in {
                    "navigate",
                    "fill",
                }:
                    resolved_value = (
                        self._resolve_value(
                            step.value,
                            inputs,
                        )
                    )

                decision = (
                    await self.policy.authorize(
                        step,
                        resolved_value=(
                            str(resolved_value)
                            if resolved_value
                            is not None
                            else None
                        ),
                    )
                )

                self.logger.log(
                    "policy_authorized",
                    step_id=step.id,
                    classified_effect=(
                        decision
                        .classified_effect
                        .value
                    ),
                    reason=decision.reason,
                )

            except PolicyViolation as exc:
                self.logger.log(
                    "policy_blocked",
                    step_id=step.id,
                    reason=str(exc),
                )

                return await self._failure(
                    artifact,
                    code="POLICY_VIOLATION",
                    message=str(exc),
                    step_id=step.id,
                )

            # Execute the deterministic artifact step.
            try:
                output = (
                    await self._execute_step(
                        step,
                        inputs,
                        resolved_value,
                    )
                )

                self._log_locator_resolution(
                    step
                )

            except Exception as exc:
                return await self._failure(
                    artifact,
                    code="STEP_EXECUTION_FAILED",
                    message=str(exc),
                    step_id=step.id,
                )

            # Recoverable runtime conditions are checked
            # before business outcomes and checkpoints.
            recovery_rule = (
                await self.recovery_engine.detect(
                    artifact.recoveries,
                    frame=step.frame,
                )
            )

            if recovery_rule is not None:
                self.logger.log(
                    "recovery_detected",
                    step_id=step.id,
                    recovery_code=(
                        recovery_rule.code
                    ),
                    recovery_action=(
                        recovery_rule
                        .action
                        .kind
                    ),
                    resume_mode=(
                        recovery_rule.then
                    ),
                )

                try:
                    self.logger.log(
                        "recovery_started",
                        step_id=step.id,
                        recovery_code=(
                            recovery_rule.code
                        ),
                    )

                    recovery_result = (
                        await self.recovery_engine
                        .recover(
                            recovery_rule
                        )
                    )

                except RecoveryError as exc:
                    self.logger.log(
                        "recovery_failed",
                        step_id=step.id,
                        recovery_code=(
                            recovery_rule.code
                        ),
                        reason=str(exc),
                    )

                    return await self._failure(
                        artifact,
                        code="RECOVERY_FAILED",
                        message=str(exc),
                        step_id=step.id,
                    )

                self.logger.log(
                    "recovery_succeeded",
                    step_id=step.id,
                    recovery_code=(
                        recovery_result.code
                    ),
                    resume_mode=(
                        recovery_result.resume_mode
                    ),
                )

                if (
                    recovery_result.resume_mode
                    == "reverify_current_checkpoint"
                ):
                    checkpoint_ok = (
                        await self
                        ._verify_checkpoint(
                            step.checkpoint,
                            inputs,
                            frame=step.frame,
                        )
                    )

                    if not checkpoint_ok:
                        return await self._failure(
                            artifact,
                            code=(
                                "RECOVERY_CHECKPOINT_FAILED"
                            ),
                            message=(
                                "Recovery succeeded, but "
                                "the interrupted step's "
                                "checkpoint was not "
                                "satisfied."
                            ),
                            step_id=step.id,
                        )

                    self.logger.log(
                        "recovery_checkpoint_passed",
                        step_id=step.id,
                        recovery_code=(
                            recovery_rule.code
                        ),
                    )

                    self.logger.log(
                        "checkpoint_passed",
                        step_id=step.id,
                    )

                    # Recovery placed the session into the
                    # state this step was supposed to reach.
                    # Continue with the next artifact step.
                    continue

                if (
                    recovery_result.resume_mode
                    == "retry_current_step"
                ):
                    retry_result = (
                        await self._retry_step(
                            artifact=artifact,
                            step=step,
                            inputs=inputs,
                            resolved_value=(
                                resolved_value
                            ),
                        )
                    )

                    if retry_result is not None:
                        return retry_result

                    continue

                return await self._failure(
                    artifact,
                    code=(
                        "UNSUPPORTED_RECOVERY_RESUME"
                    ),
                    message=(
                        "Recovery returned unsupported "
                        "resume mode: "
                        f"{recovery_result.resume_mode}"
                    ),
                    step_id=step.id,
                )

            # Expected business outcomes are legitimate
            # caller-visible results, not crashes.
            outcome = (
                await self.outcome_detector
                .detect_expected_outcome(
                    self.surface,
                    artifact.expected_outcomes,
                    after_step=step.id,
                    frame=step.frame,
                )
            )

            if outcome is not None:
                self.logger.log(
                    "business_outcome",
                    step_id=step.id,
                    outcome_code=(
                        outcome.code
                    ),
                )

                return RunResult(
                    status=(
                        RunStatus
                        .BUSINESS_OUTCOME
                    ),
                    capability_id=(
                        artifact
                        .capability
                        .id
                    ),
                    capability_version=(
                        artifact
                        .capability
                        .version
                    ),
                    outcome_code=(
                        outcome.code
                    ),
                    outputs=(
                        self
                        ._resolve_return_values(
                            outcome.returns,
                            inputs,
                        )
                    ),
                )

            checkpoint_ok = (
                await self._verify_checkpoint(
                    step.checkpoint,
                    inputs,
                    frame=step.frame,
                )
            )

            if not checkpoint_ok:
                return await self._failure(
                    artifact,
                    code="CHECKPOINT_FAILED",
                    message=(
                        "Checkpoint failed after "
                        f"step '{step.id}'."
                    ),
                    step_id=step.id,
                )

            self.logger.log(
                "checkpoint_passed",
                step_id=step.id,
            )

            if (
                step.action == "read"
                and output is not None
            ):
                self.logger.log(
                    "run_succeeded",
                    step_id=step.id,
                )

                return RunResult(
                    status=RunStatus.SUCCESS,
                    capability_id=(
                        artifact
                        .capability
                        .id
                    ),
                    capability_version=(
                        artifact
                        .capability
                        .version
                    ),
                    outputs={
                        "savings_balance":
                            output
                    },
                )

        return await self._failure(
            artifact,
            code=(
                "SUCCESS_CONDITION_NOT_REACHED"
            ),
            message=(
                "Replay completed all steps "
                "without producing the declared "
                "result."
            ),
        )

    async def _retry_step(
        self,
        artifact: CapabilityArtifact,
        step: Step,
        inputs: dict[str, Any],
        resolved_value: Any | None,
    ) -> RunResult | None:
        if self.logger is not None:
            self.logger.log(
                "step_retry_started",
                step_id=step.id,
            )

        try:
            output = await self._execute_step(
                step,
                inputs,
                resolved_value,
            )

            self._log_locator_resolution(
                step
            )

        except Exception as exc:
            return await self._failure(
                artifact,
                code="STEP_RETRY_FAILED",
                message=str(exc),
                step_id=step.id,
            )

        outcome = (
            await self.outcome_detector
            .detect_expected_outcome(
                self.surface,
                artifact.expected_outcomes,
                after_step=step.id,
                frame=step.frame,
            )
        )

        if outcome is not None:
            if self.logger is not None:
                self.logger.log(
                    "business_outcome",
                    step_id=step.id,
                    outcome_code=(
                        outcome.code
                    ),
                )

            return RunResult(
                status=(
                    RunStatus.BUSINESS_OUTCOME
                ),
                capability_id=(
                    artifact.capability.id
                ),
                capability_version=(
                    artifact.capability.version
                ),
                outcome_code=outcome.code,
                outputs=(
                    self._resolve_return_values(
                        outcome.returns,
                        inputs,
                    )
                ),
            )

        checkpoint_ok = (
            await self._verify_checkpoint(
                step.checkpoint,
                inputs,
                frame=step.frame,
            )
        )

        if not checkpoint_ok:
            return await self._failure(
                artifact,
                code=(
                    "RETRY_CHECKPOINT_FAILED"
                ),
                message=(
                    "Retried step completed, "
                    "but its checkpoint failed."
                ),
                step_id=step.id,
            )

        if self.logger is not None:
            self.logger.log(
                "step_retry_succeeded",
                step_id=step.id,
            )

        if (
            step.action == "read"
            and output is not None
        ):
            if self.logger is not None:
                self.logger.log(
                    "run_succeeded",
                    step_id=step.id,
                )

            return RunResult(
                status=RunStatus.SUCCESS,
                capability_id=(
                    artifact.capability.id
                ),
                capability_version=(
                    artifact.capability.version
                ),
                outputs={
                    "savings_balance":
                        output
                },
            )

        return None

    def _log_locator_resolution(
        self,
        step: Step,
    ) -> None:
        if self.logger is None:
            return

        result = (
            self.surface.last_resolution
        )

        if result is None:
            return

        self.logger.log(
            "locator_resolved",
            step_id=step.id,
            strategy_kind=(
                result.strategy.kind
            ),
            strategy_rank=(
                result.strategy.rank
            ),
            degraded=result.degraded,
        )

        if result.degraded:
            self.logger.log(
                "locator_degraded",
                step_id=step.id,
                used_rank=(
                    result.strategy.rank
                ),
                used_strategy=(
                    result.strategy.kind
                ),
            )

    async def _execute_step(
        self,
        step: Step,
        inputs: dict[str, Any],
        resolved_value: Any | None = None,
    ) -> Any | None:
        if step.action == "navigate":
            if resolved_value is None:
                resolved_value = (
                    self._resolve_value(
                        step.value,
                        inputs,
                    )
                )

            if not isinstance(
                resolved_value,
                str,
            ):
                raise ValueError(
                    "Navigate step requires "
                    "a URL string."
                )

            await self.surface.navigate(
                resolved_value
            )

            return None

        if step.action == "fill":
            if step.target is None:
                raise ValueError(
                    "Fill step requires a target."
                )

            if resolved_value is None:
                resolved_value = (
                    self._resolve_value(
                        step.value,
                        inputs,
                    )
                )

            await self.surface.fill(
                step.target,
                str(resolved_value),
                frame=step.frame,
            )

            return None

        if step.action == "click":
            if step.target is None:
                raise ValueError(
                    "Click step requires a target."
                )

            await self.surface.click(
                step.target,
                frame=step.frame,
            )

            return None

        if step.action == "read":
            if step.target is None:
                raise ValueError(
                    "Read step requires a target."
                )

            text = (
                await self.surface.read_text(
                    step.target,
                    frame=step.frame,
                )
            )

            return self._parse_currency(
                text
            )

        raise ValueError(
            "Unsupported action: "
            f"{step.action}"
        )

    async def _verify_checkpoint(
        self,
        checkpoint: Checkpoint | None,
        inputs: dict[str, Any],
        frame: str | None,
    ) -> bool:
        if checkpoint is None:
            return True

        if (
            checkpoint.kind
            == "text_visible"
        ):
            if checkpoint.value is None:
                return False

            return await self.surface.text_visible(
                checkpoint.value,
                frame=frame,
            )

        if (
            checkpoint.kind
            == "url_matches"
        ):
            if checkpoint.pattern is None:
                return False

            current_url = (
                await self.surface
                .current_url()
            )

            return (
                re.search(
                    checkpoint.pattern,
                    current_url,
                )
                is not None
            )

        if (
            checkpoint.kind
            == "field_value_matches_input"
        ):
            if checkpoint.key is None:
                return False

            return (
                checkpoint.key
                in inputs
            )

        if (
            checkpoint.kind
            == "table_contains_row"
        ):
            if checkpoint.value is None:
                return False

            return await self.surface.text_visible(
                checkpoint.value,
                frame=frame,
            )

        if (
            checkpoint.kind
            == "element_visible"
        ):
            if (
                checkpoint.target
                is None
            ):
                return False

            page = (
                self.surface
                ._require_page()
            )

            try:
                await (
                    self.surface
                    .resolver
                    .resolve(
                        page,
                        checkpoint.target,
                        frame,
                    )
                )

                return True

            except Exception:
                return False

        return False

    def _resolve_value(
        self,
        value_source: (
            ValueSource | None
        ),
        inputs: dict[str, Any],
    ) -> Any:
        if value_source is None:
            raise ValueError(
                "Step requires a value source."
            )

        if (
            value_source.source
            == "literal"
        ):
            return value_source.value

        if (
            value_source.source
            == "input"
        ):
            if value_source.key is None:
                raise ValueError(
                    "Input value source "
                    "requires key."
                )

            if (
                value_source.key
                not in inputs
            ):
                raise ValueError(
                    "Missing input: "
                    f"{value_source.key}"
                )

            return inputs[
                value_source.key
            ]

        raise ValueError(
            "Unsupported value source: "
            f"{value_source.source}"
        )

    def _validate_inputs(
        self,
        artifact: CapabilityArtifact,
        inputs: dict[str, Any],
    ) -> str | None:
        for (
            name,
            spec,
        ) in artifact.inputs.items():
            if (
                spec.required
                and name not in inputs
            ):
                return (
                    "Missing required input: "
                    f"{name}"
                )

            if name not in inputs:
                continue

            value = inputs[name]

            if (
                spec.pattern
                is not None
            ):
                if (
                    re.fullmatch(
                        spec.pattern,
                        str(value),
                    )
                    is None
                ):
                    return (
                        f"Input '{name}' "
                        "does not match "
                        "required pattern."
                    )

        return None

    def _resolve_return_values(
        self,
        values: dict[str, Any],
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        resolved: dict[
            str,
            Any,
        ] = {}

        for key, value in values.items():
            if (
                isinstance(
                    value,
                    str,
                )
                and value.startswith(
                    "$input."
                )
            ):
                input_key = (
                    value.removeprefix(
                        "$input."
                    )
                )

                resolved[key] = (
                    inputs.get(
                        input_key
                    )
                )

            else:
                resolved[key] = value

        return resolved

    def _parse_currency(
        self,
        value: str,
    ) -> Decimal:
        cleaned = (
            value
            .replace("$", "")
            .replace(",", "")
            .strip()
        )

        try:
            return Decimal(
                cleaned
            )

        except InvalidOperation as exc:
            raise ValueError(
                "Unable to parse currency: "
                f"{value}"
            ) from exc

    async def _failure(
        self,
        artifact: CapabilityArtifact,
        code: str,
        message: str,
        step_id: str | None = None,
    ) -> RunResult:
        screenshot_path: (
            str | None
        ) = None

        if (
            step_id is not None
            and self.capture
            is not None
        ):
            try:
                screenshot_path = (
                    await self.capture
                    .failure_screenshot(
                        self.surface,
                        step_id,
                    )
                )

            except Exception:
                screenshot_path = None

        if self.logger is not None:
            self.logger.log(
                "run_failed",
                code=code,
                message=message,
                step_id=step_id,
                screenshot=(
                    screenshot_path
                ),
            )

        return RunResult(
            status=RunStatus.FAILURE,
            capability_id=(
                artifact.capability.id
            ),
            capability_version=(
                artifact.capability.version
            ),
            error=RunError(
                code=code,
                message=message,
                step_id=step_id,
                details={
                    "screenshot":
                        screenshot_path
                },
            ),
        )