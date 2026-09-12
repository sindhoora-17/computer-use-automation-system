from __future__ import annotations

from cua.artifact.schema import (
    Detector,
    ExpectedOutcome,
)
from cua.surface.web import PlaywrightSurface


class OutcomeDetector:
    async def matches(
        self,
        surface: PlaywrightSurface,
        detector: Detector,
        frame: str | None = None,
    ) -> bool:
        if detector.kind == "text_visible":
            if detector.value is None:
                return False

            return await surface.text_visible(
                detector.value,
                frame=frame,
            )

        if detector.kind == "url_matches":
            if detector.value is None:
                return False

            current_url = await surface.current_url()

            return detector.value in current_url

        if detector.kind == "role_visible":
            # We will make this richer later.
            # For now, dialog detection is enough
            # for the planned maintenance interstitial.
            if detector.role == "dialog":
                page = surface._require_page()

                if frame is not None:
                    selected_frame = page.frame(
                        name=frame
                    )

                    if selected_frame is None:
                        return False

                    locator = selected_frame.get_by_role(
                        "dialog"
                    )

                else:
                    locator = page.get_by_role(
                        "dialog"
                    )

                return await locator.count() > 0

            return False

        if detector.kind == "table_has_no_row_matching":
            if detector.value is None:
                return False

            page = surface._require_page()

            rows = page.locator("tr")

            matching_rows = rows.filter(
                has_text=detector.value
            )

            return await matching_rows.count() == 0

        return False

    async def detect_expected_outcome(
        self,
        surface: PlaywrightSurface,
        outcomes: list[ExpectedOutcome],
        after_step: str,
        frame: str | None = None,
    ) -> ExpectedOutcome | None:
        candidates = [
            outcome
            for outcome in outcomes
            if outcome.after_step == after_step
        ]

        candidates.sort(
            key=lambda outcome: outcome.precedence
        )

        for outcome in candidates:
            if await self.matches(
                surface,
                outcome.detector,
                frame=frame,
            ):
                return outcome

        return None