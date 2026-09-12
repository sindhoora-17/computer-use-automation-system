from __future__ import annotations

import asyncio
import json
import uuid
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

from cua.escalation.requests import (
    EscalationRequest,
)
from cua.surface.web import (
    PlaywrightSurface,
)


class HandoffError(Exception):
    pass


class HandoffTimeout(HandoffError):
    pass


class HandoffSession:
    """
    Coordinates human takeover without destroying or
    recreating the live browser session.

    The Playwright browser, context, page, cookies, and
    application state remain untouched while execution
    waits for the operator.
    """

    def __init__(
        self,
        surface: PlaywrightSurface,
        evidence_dir: str | Path = (
            "evidence/escalation"
        ),
    ) -> None:
        self.surface = surface

        self.evidence_dir = Path(
            evidence_dir
        )

        self.evidence_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._current_request: (
            EscalationRequest | None
        ) = None

        self._resume_event: (
            asyncio.Event | None
        ) = None

    @property
    def current_request(
        self,
    ) -> EscalationRequest | None:
        return self._current_request

    async def escalate(
        self,
        capability_id: str,
        capability_version: str,
        step_id: str,
        reason: str,
        checkpoint_description: (
            str | None
        ) = None,
        timeout_s: float = 300,
    ) -> EscalationRequest:
        if (
            self._current_request
            is not None
            and self._current_request.status
            == "pending"
        ):
            raise HandoffError(
                "A handoff request is "
                "already pending."
            )

        request_id = (
            "handoff_"
            f"{uuid.uuid4().hex[:8]}"
        )

        request_dir = (
            self.evidence_dir
            / request_id
        )

        request_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        screenshot_path = (
            request_dir
            / "handoff.png"
        )

        try:
            await self.surface.screenshot(
                str(
                    screenshot_path
                )
            )

            stored_screenshot: (
                str | None
            ) = str(
                screenshot_path
            )

        except Exception:
            stored_screenshot = None

        current_url = (
            await self.surface.current_url()
        )

        request = EscalationRequest(
            request_id=request_id,
            capability_id=(
                capability_id
            ),
            capability_version=(
                capability_version
            ),
            step_id=step_id,
            reason=reason,
            current_url=current_url,
            checkpoint_description=(
                checkpoint_description
            ),
            screenshot_path=(
                stored_screenshot
            ),
            created_at=(
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
        )

        self._current_request = (
            request
        )

        self._resume_event = (
            asyncio.Event()
        )

        self._write_request(
            request
        )

        try:
            await asyncio.wait_for(
                self._resume_event.wait(),
                timeout=timeout_s,
            )

        except asyncio.TimeoutError as exc:
            request.status = (
                "timed_out"
            )

            self._write_request(
                request
            )

            raise HandoffTimeout(
                "Human handoff timed out "
                f"after {timeout_s} seconds."
            ) from exc

        request.status = "resumed"

        request.resumed_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        self._write_request(
            request
        )

        return request

    def resume(
        self,
    ) -> None:
        if (
            self._current_request
            is None
            or self._resume_event
            is None
        ):
            raise HandoffError(
                "There is no active "
                "handoff request."
            )

        if (
            self._current_request.status
            != "pending"
        ):
            raise HandoffError(
                "The current handoff "
                "request is not pending."
            )

        self._resume_event.set()

    def _write_request(
        self,
        request: EscalationRequest,
    ) -> None:
        request_dir = (
            self.evidence_dir
            / request.request_id
        )

        request_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        path = (
            request_dir
            / "request.json"
        )

        with path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                request.model_dump(
                    mode="json"
                ),
                file,
                indent=2,
            )