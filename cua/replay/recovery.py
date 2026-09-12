from __future__ import annotations

import os
from dataclasses import dataclass

from cua.artifact.schema import (
    LocatorStrategy,
    RecoveryRule,
    TargetLocator,
)
from cua.replay.detectors import (
    OutcomeDetector,
)
from cua.surface.base import (
    Surface,
)


class RecoveryError(Exception):
    pass


@dataclass
class RecoveryResult:
    code: str
    recovered: bool
    resume_mode: str


class RecoveryEngine:
    def __init__(
        self,
        surface: Surface,
    ) -> None:
        self.surface = surface

        self.detector = (
            OutcomeDetector()
        )

        self.attempts: dict[
            str,
            int,
        ] = {}

    async def detect(
        self,
        rules: list[RecoveryRule],
        frame: str | None = None,
    ) -> RecoveryRule | None:
        for rule in rules:
            if await self.detector.matches(
                self.surface,
                rule.detector,
                frame=frame,
            ):
                return rule

        return None

    async def recover(
        self,
        rule: RecoveryRule,
    ) -> RecoveryResult:
        attempts = self.attempts.get(
            rule.code,
            0,
        )

        if attempts >= rule.max_attempts:
            raise RecoveryError(
                f"Recovery '{rule.code}' "
                "exceeded maximum attempts."
            )

        self.attempts[rule.code] = (
            attempts + 1
        )

        if (
            rule.action.kind
            == "reauthenticate"
        ):
            await self._reauthenticate()

        elif (
            rule.action.kind
            == "retry"
        ):
            pass

        else:
            raise RecoveryError(
                "Unsupported recovery action: "
                f"{rule.action.kind}"
            )

        return RecoveryResult(
            code=rule.code,
            recovered=True,
            resume_mode=rule.then,
        )

    async def _reauthenticate(
        self,
    ) -> None:
        username = os.environ.get(
            "TARGET_APP_USERNAME"
        )

        password = os.environ.get(
            "TARGET_APP_PASSWORD"
        )

        if not username:
            raise RecoveryError(
                "TARGET_APP_USERNAME "
                "is not configured."
            )

        if not password:
            raise RecoveryError(
                "TARGET_APP_PASSWORD "
                "is not configured."
            )

        username_target = (
            TargetLocator(
                strategies=[
                    LocatorStrategy(
                        kind="role_name",
                        rank=1,
                        role="textbox",
                        name="Operator ID",
                    )
                ]
            )
        )

        password_target = (
            TargetLocator(
                strategies=[
                    LocatorStrategy(
                        kind="xpath",
                        rank=1,
                        value=(
                            "//input"
                            "[@name='password']"
                        ),
                    )
                ]
            )
        )

        login_target = (
            TargetLocator(
                strategies=[
                    LocatorStrategy(
                        kind="role_name",
                        rank=1,
                        role="button",
                        name="Log In",
                    )
                ]
            )
        )

        await self.surface.fill(
            username_target,
            username,
        )

        await self.surface.fill(
            password_target,
            password,
        )

        await self.surface.click(
            login_target
        )

        current_url = (
            await self.surface
            .current_url()
        )

        if "/login" in current_url:
            raise RecoveryError(
                "Reauthentication did "
                "not leave the login page."
            )