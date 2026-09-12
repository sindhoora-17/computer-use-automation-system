from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cua.artifact.schema import TargetLocator
from cua.policy.redaction import Redactor


@dataclass
class RecordedAction:
    action: str
    ref: str | None = None
    value: str | None = None
    reason: str | None = None
    observed_url: str | None = None
    result: str | None = None
    target: TargetLocator | None = None


@dataclass
class DiscoveryRecorder:
    actions: list[RecordedAction] = field(
        default_factory=list
    )

    def record(
        self,
        action: RecordedAction,
    ) -> None:
        self.actions.append(action)

    def as_dicts(
        self,
    ) -> list[dict[str, Any]]:
        payload: list[
            dict[str, Any]
        ] = []

        for action in self.actions:
            payload.append(
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
            )

        return payload

    def save(
        self,
        path: str | Path,
    ) -> None:
        path = Path(path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        redactor = Redactor()

        payload = (
            redactor.redact_discovery_payload(
                self.as_dicts()
            )
        )

        with path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                payload,
                file,
                indent=2,
            )