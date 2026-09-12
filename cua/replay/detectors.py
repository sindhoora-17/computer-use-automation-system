from __future__ import annotations

from cua.artifact.schema import (
    Detector,
    ExpectedOutcome,
)
from cua.surface.web import (
    PlaywrightSurface,
)


class OutcomeDetector:
    async def matches(
        self,
        surface: PlaywrightSurface,
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

            page = (
                surface._require_page()
            )

            if frame is not None:
                selected_frame = page.frame(
                    name=frame
                )

                if selected_frame is None:
                    return False

                locator = (
                    selected_frame
                    .get_by_role(
                        detector.role
                    )
                )

            else:
                locator = (
                    page.get_by_role(
                        detector.role
                    )
                )

            return (
                await locator.count()
                > 0
            )

        if (
            detector.kind
            == "table_has_no_row_matching"
        ):
            return await (
                self._table_has_no_row_matching(
                    surface=surface,
                    detector=detector,
                    frame=frame,
                )
            )

        return False

    async def _table_has_no_row_matching(
        self,
        surface: PlaywrightSurface,
        detector: Detector,
        frame: str | None,
    ) -> bool:
        """
        Return True only when a relevant table exists and
        none of its data rows contain detector.value in the
        requested column.

        This distinction matters:

        - Member detail page with an Accounts table but no
          Savings row -> legitimate NO_SAVINGS_ACCOUNT.

        - Login/interstitial/error page with no Accounts
          table at all -> NOT a business outcome. The
          replay engine should continue into recovery,
          checkpoint failure, or human handoff.
        """

        if detector.value is None:
            return False

        page = (
            surface._require_page()
        )

        if frame is not None:
            scope = page.frame(
                name=frame
            )

            if scope is None:
                return False

        else:
            scope = page

        tables = scope.locator(
            "table"
        )

        table_count = (
            await tables.count()
        )

        found_relevant_table = False

        for table_index in range(
            table_count
        ):
            table = tables.nth(
                table_index
            )

            rows = table.locator(
                "tr"
            )

            row_count = (
                await rows.count()
            )

            if row_count == 0:
                continue

            header_index: (
                int | None
            ) = None

            data_start_index = 0

            for row_index in range(
                row_count
            ):
                row = rows.nth(
                    row_index
                )

                headers = row.locator(
                    "th"
                )

                header_count = (
                    await headers.count()
                )

                if header_count == 0:
                    continue

                header_values = [
                    (
                        await headers
                        .nth(index)
                        .inner_text()
                    ).strip()
                    for index in range(
                        header_count
                    )
                ]

                if (
                    detector.column_header
                    is None
                ):
                    found_relevant_table = True
                    data_start_index = (
                        row_index + 1
                    )
                    break

                for (
                    index,
                    header_value,
                ) in enumerate(
                    header_values
                ):
                    if (
                        header_value
                        .casefold()
                        == detector
                        .column_header
                        .casefold()
                    ):
                        header_index = index
                        found_relevant_table = True
                        data_start_index = (
                            row_index + 1
                        )
                        break

                if (
                    found_relevant_table
                ):
                    break

            if not found_relevant_table:
                continue

            for row_index in range(
                data_start_index,
                row_count,
            ):
                row = rows.nth(
                    row_index
                )

                cells = row.locator(
                    "td"
                )

                cell_count = (
                    await cells.count()
                )

                if cell_count == 0:
                    continue

                if (
                    detector.column_header
                    is not None
                ):
                    if (
                        header_index
                        is None
                        or header_index
                        >= cell_count
                    ):
                        continue

                    value = (
                        await cells
                        .nth(
                            header_index
                        )
                        .inner_text()
                    ).strip()

                    if (
                        value.casefold()
                        == detector
                        .value
                        .casefold()
                    ):
                        return False

                else:
                    row_text = (
                        await row.inner_text()
                    )

                    if (
                        detector.value
                        .casefold()
                        in row_text
                        .casefold()
                    ):
                        return False

            # We found the table specified by the detector,
            # and no matching row was present.
            return True

        # No relevant table means this detector cannot
        # legitimately classify the page.
        return False

    async def detect_expected_outcome(
        self,
        surface: PlaywrightSurface,
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