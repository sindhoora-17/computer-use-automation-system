from __future__ import annotations

from dataclasses import dataclass

from playwright.async_api import Frame, Locator, Page

from cua.artifact.schema import LocatorStrategy, TargetLocator


@dataclass
class ResolutionResult:
    locator: Locator
    strategy: LocatorStrategy
    degraded: bool


class LocatorResolutionError(Exception):
    pass


class LocatorResolver:
    async def resolve(
        self,
        page: Page,
        target: TargetLocator,
        frame_name: str | None = None,
    ) -> ResolutionResult:
        scope: Page | Frame = page

        if frame_name:
            frame = page.frame(name=frame_name)

            if frame is None:
                raise LocatorResolutionError(
                    f"Frame not found: {frame_name}"
                )

            scope = frame

        strategies = sorted(
            target.strategies,
            key=lambda strategy: strategy.rank,
        )

        errors: list[str] = []

        for strategy in strategies:
            try:
                locator = await self._build_locator(
                    scope,
                    strategy,
                )

                count = await locator.count()

                if count == 0:
                    errors.append(
                        f"rank {strategy.rank} "
                        f"({strategy.kind}): no matches"
                    )
                    continue

                first = locator.first

                if not await first.is_visible():
                    errors.append(
                        f"rank {strategy.rank} "
                        f"({strategy.kind}): not visible"
                    )
                    continue

                return ResolutionResult(
                    locator=first,
                    strategy=strategy,
                    degraded=strategy.rank > 1,
                )

            except Exception as exc:
                errors.append(
                    f"rank {strategy.rank} "
                    f"({strategy.kind}): {exc}"
                )

        raise LocatorResolutionError(
            "Unable to resolve target. "
            + " | ".join(errors)
        )

    async def _build_locator(
        self,
        scope: Page | Frame,
        strategy: LocatorStrategy,
    ) -> Locator:
        if strategy.kind == "role_name":
            if strategy.role is None:
                raise ValueError(
                    "role_name requires role"
                )

            if strategy.name is None:
                raise ValueError(
                    "role_name requires name"
                )

            return scope.get_by_role(
                strategy.role,
                name=strategy.name,
            )

        if strategy.kind == "label_text":
            if strategy.value is None:
                raise ValueError(
                    "label_text requires value"
                )

            return scope.get_by_label(
                strategy.value
            )

        if strategy.kind == "anchor_relative":
            if strategy.anchor_text is None:
                raise ValueError(
                    "anchor_relative requires anchor_text"
                )

            if (
                strategy.relationship
                == "following_input"
            ):
                return scope.locator(
                    "xpath="
                    "//*[normalize-space(text())="
                    f"{self._xpath_literal(strategy.anchor_text)}]"
                    "/following::input[1]"
                )

            raise ValueError(
                "Unsupported anchor relationship: "
                f"{strategy.relationship}"
            )

        if strategy.kind == "table_cell":
            if strategy.row_anchor is None:
                raise ValueError(
                    "table_cell requires row_anchor"
                )

            if strategy.column_header is None:
                raise ValueError(
                    "table_cell requires column_header"
                )

            return await self._resolve_table_cell(
                scope,
                row_anchor=strategy.row_anchor,
                column_header=strategy.column_header,
            )

        if strategy.kind == "xpath":
            if strategy.value is None:
                raise ValueError(
                    "xpath requires value"
                )

            return scope.locator(
                f"xpath={strategy.value}"
            )

        if strategy.kind == "bbox":
            raise ValueError(
                "bbox resolution is not implemented yet"
            )

        raise ValueError(
            "Unsupported locator strategy: "
            f"{strategy.kind}"
        )

    async def _resolve_table_cell(
        self,
        scope: Page | Frame,
        row_anchor: str,
        column_header: str,
    ) -> Locator:
        """
        Resolve a table cell by semantic row and column anchors.

        We deliberately do not rely on fixed column positions.
        The resolver finds the table containing the requested
        header, determines that header's index, finds the row
        containing row_anchor, then returns the cell at the
        discovered column index.
        """

        tables = scope.locator("table")
        table_count = await tables.count()

        for table_index in range(table_count):
            table = tables.nth(table_index)

            headers = table.locator("th")
            header_count = await headers.count()

            matching_header_index: int | None = None

            for index in range(header_count):
                header_text = (
                    await headers.nth(index).inner_text()
                ).strip()

                if (
                    header_text.casefold()
                    == column_header.casefold()
                ):
                    matching_header_index = index
                    break

            if matching_header_index is None:
                continue

            rows = table.locator(
                "tr",
                has_text=row_anchor,
            )

            row_count = await rows.count()

            if row_count == 0:
                continue

            row = rows.first
            cells = row.locator("td")

            cell_count = await cells.count()

            if matching_header_index >= cell_count:
                raise ValueError(
                    "Resolved header index "
                    f"{matching_header_index}, but matching "
                    f"row only contains {cell_count} cells."
                )

            return cells.nth(
                matching_header_index
            )

        raise ValueError(
            "Unable to find table cell for "
            f"row '{row_anchor}' and "
            f"column '{column_header}'."
        )

    def _xpath_literal(
        self,
        value: str,
    ) -> str:
        """
        Safely represent arbitrary text as an XPath literal.
        """

        if "'" not in value:
            return f"'{value}'"

        if '"' not in value:
            return f'"{value}"'

        pieces = value.split("'")

        encoded = ", \"'\", ".join(
            f"'{piece}'"
            for piece in pieces
        )

        return f"concat({encoded})"