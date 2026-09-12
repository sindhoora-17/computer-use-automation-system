from __future__ import annotations

from cua.artifact.schema import (
    Detector,
    ExpectedOutcome,
)
from cua.surface.base import (
    Surface,
)


class OutcomeDetector:
    async def matches(
        self,
        surface: Surface,
        detector: Detector,
        frame: str | None = None,
    ) -> bool:
        if (
            detector.kind
            == "text_visible"
        ):
            if detector.value is None:
                return False

            return await surface.text_visible(
                detector.value,
                frame=frame,
            )

        if (
            detector.kind
            == "url_matches"
        ):
            if detector.value is None:
                return False

            current_url = (
                await surface.current_url()
            )

            return (
                detector.value
                in current_url
            )

        if (
            detector.kind
            == "role_visible"
        ):
            if detector.role is None:
                return False

            return await surface.role_visible(
                role=detector.role,
                name=detector.value,
                frame=frame,
            )

        if (
            detector.kind
            == "table_has_no_row_matching"
        ):
            if detector.value is None:
                return False

            return await (
                surface
                .table_has_no_row_matching(
                    value=detector.value,
                    column_header=(
                        detector.column_header
                    ),
                    frame=frame,
                )
            )

        return False

    async def detect_expected_outcome(
        self,
        surface: Surface,
        outcomes: list[
            ExpectedOutcome
        ],
        after_step: str,
        frame: str | None = None,
    ) -> ExpectedOutcome | None:
        candidates = [
            outcome
            for outcome in outcomes
            if (
                outcome.after_step
                == after_step
            )
        ]

        candidates.sort(
            key=lambda outcome:
                outcome.precedence
        )

        for outcome in candidates:
            if await self.matches(
                surface,
                outcome.detector,
                frame=frame,
            ):
                return outcome

        return None