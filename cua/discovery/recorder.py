from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)
from typing import Any

from cua.artifact.schema import (
    TargetLocator,
)


@dataclass
class RecordedAction:
    action: str
    ref: str | None
    value: str | None
    reason: str
    observed_url: str

    result: str | None = None

    target: (
        TargetLocator | None
    ) = None


@dataclass
class DiscoveryRecorder:
    actions: list[
        RecordedAction
    ] = field(
        default_factory=list
    )

    def record(
        self,
        action: str,
        ref: str | None,
        value: str | None,
        reason: str,
        observed_url: str,
        result: str | None = None,
        target: (
            TargetLocator | None
        ) = None,
    ) -> None:
        self.actions.append(
            RecordedAction(
                action=action,
                ref=ref,
                value=value,
                reason=reason,
                observed_url=(
                    observed_url
                ),
                result=result,
                target=target,
            )
        )

    def as_dicts(
        self,
    ) -> list[
        dict[str, Any]
    ]:
        return [
            {
                "action": action.action,
                "ref": action.ref,
                "value": action.value,
                "reason": action.reason,
                "observed_url": (
                    action.observed_url
                ),
                "result": action.result,
                "target": (
                    action.target.model_dump(
                        mode="json"
                    )
                    if action.target
                    is not None
                    else None
                ),
            }
            for action
            in self.actions
        ]