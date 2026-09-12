from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from playwright.async_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    async_playwright,
)

from cua.artifact.schema import TargetLocator
from cua.locator.resolver import (
    LocatorResolver,
    ResolutionResult,
)
from cua.surface.observation import (
    ObservedElement,
    TargetSemantics,
)


class PlaywrightSurface:
    def __init__(
        self,
        headless: bool = False,
    ) -> None:
        self.headless = headless

        self._playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

        self.resolver = LocatorResolver()

        self.last_resolution: (
            ResolutionResult | None
        ) = None

        self._discovery_refs: dict[
            str,
            Locator,
        ] = {}

    async def start(self) -> None:
        self._playwright = (
            await async_playwright().start()
        )

        self.browser = (
            await self._playwright.chromium.launch(
                headless=self.headless,
            )
        )

        self.context = (
            await self.browser.new_context()
        )

        self.page = (
            await self.context.new_page()
        )

    async def close(self) -> None:
        if self.context is not None:
            await self.context.close()

        if self.browser is not None:
            await self.browser.close()

        if self._playwright is not None:
            await self._playwright.stop()

    def _require_page(self) -> Page:
        if self.page is None:
            raise RuntimeError(
                "Surface has not been started"
            )

        return self.page

    async def navigate(
        self,
        url: str,
    ) -> None:
        self.last_resolution = None

        page = self._require_page()

        await page.goto(
            url,
            wait_until="domcontentloaded",
        )

    async def click(
        self,
        target: TargetLocator,
        frame: str | None = None,
    ) -> None:
        page = self._require_page()

        result = await self.resolver.resolve(
            page,
            target,
            frame,
        )

        self.last_resolution = result

        await result.locator.click()

    async def fill(
        self,
        target: TargetLocator,
        value: str,
        frame: str | None = None,
    ) -> None:
        page = self._require_page()

        result = await self.resolver.resolve(
            page,
            target,
            frame,
        )

        self.last_resolution = result

        await result.locator.fill(
            value
        )

    async def read_text(
        self,
        target: TargetLocator,
        frame: str | None = None,
    ) -> str:
        page = self._require_page()

        result = await self.resolver.resolve(
            page,
            target,
            frame,
        )

        self.last_resolution = result

        text = (
            await result.locator.inner_text()
        )

        return text.strip()

    async def inspect_target(
        self,
        target: TargetLocator,
        frame: str | None = None,
    ) -> TargetSemantics:
        page = self._require_page()

        result = await self.resolver.resolve(
            page,
            target,
            frame,
        )

        self.last_resolution = result

        return await self._inspect_locator(
            result.locator
        )

    async def observe_discovery(
        self,
    ) -> tuple[
        list[ObservedElement],
        str,
    ]:
        page = self._require_page()

        self._discovery_refs.clear()

        elements: list[
            ObservedElement
        ] = []

        candidates = page.locator(
            (
                "a, button, input, select, "
                "textarea, td, th"
            )
        )

        count = await candidates.count()

        ref_counter = 1

        for index in range(count):
            locator = candidates.nth(
                index
            )

            if not await locator.is_visible():
                continue

            semantics = (
                await self._inspect_locator(
                    locator
                )
            )

            tag_name = (
                semantics.tag_name.casefold()
            )

            is_interactive = (
                tag_name
                in {
                    "a",
                    "button",
                    "input",
                    "select",
                    "textarea",
                }
            )

            is_readable = (
                tag_name
                in {
                    "td",
                    "th",
                }
                and bool(
                    semantics.text.strip()
                )
            )

            if (
                not is_interactive
                and not is_readable
            ):
                continue

            ref = f"e{ref_counter}"

            ref_counter += 1

            self._discovery_refs[
                ref
            ] = locator

            elements.append(
                ObservedElement(
                    ref=ref,
                    tag_name=(
                        semantics.tag_name
                    ),
                    role=semantics.role,
                    accessible_name=(
                        semantics.accessible_name
                        or ""
                    ),
                    text=semantics.text,
                    current_value=(
                        semantics.value
                        or ""
                    ),
                    input_type=(
                        semantics.input_type
                    ),
                    nearby_text=(
                        semantics.nearby_text
                        or ""
                    ),
                    readable=is_readable,
                )
            )

        body_text = (
            await page.locator(
                "body"
            ).inner_text()
        )

        return (
            elements,
            body_text[:6000],
        )

    async def get_discovery_locator(
        self,
        ref: str,
    ) -> Locator:
        if (
            ref
            not in self._discovery_refs
        ):
            raise ValueError(
                "Unknown discovery ref: "
                f"{ref}"
            )

        return self._discovery_refs[
            ref
        ]

    async def discovery_click(
        self,
        ref: str,
    ) -> None:
        locator = (
            await self
            .get_discovery_locator(
                ref
            )
        )

        await locator.click()

    async def discovery_fill(
        self,
        ref: str,
        value: str,
    ) -> None:
        locator = (
            await self
            .get_discovery_locator(
                ref
            )
        )

        await locator.fill(
            value
        )

    async def discovery_read(
        self,
        ref: str,
    ) -> str:
        locator = (
            await self
            .get_discovery_locator(
                ref
            )
        )

        tag_name = (
            await locator.evaluate(
                (
                    "(el) => "
                    "el.tagName.toLowerCase()"
                )
            )
        )

        if tag_name in {
            "input",
            "textarea",
            "select",
        }:
            return (
                await locator.input_value()
            )

        return (
            await locator.inner_text()
        ).strip()

    async def _inspect_locator(
        self,
        locator: Locator,
    ) -> TargetSemantics:
        data = await locator.evaluate(
            """
            (el) => {
                const form = el.closest('form');

                const tagName =
                    el.tagName
                        ? el.tagName.toLowerCase()
                        : '';

                let value = null;

                if (
                    tagName === 'input' ||
                    tagName === 'textarea' ||
                    tagName === 'select'
                ) {
                    value = el.value ?? null;
                } else {
                    value = el.getAttribute('value');
                }

                let accessibleName =
                    el.getAttribute('aria-label');

                if (!accessibleName && el.id) {
                    const label = document.querySelector(
                        `label[for="${CSS.escape(el.id)}"]`
                    );

                    if (label) {
                        accessibleName =
                            (
                                label.innerText ||
                                label.textContent ||
                                ''
                            ).trim();
                    }
                }

                if (!accessibleName) {
                    accessibleName =
                        el.getAttribute('placeholder');
                }

                if (
                    !accessibleName &&
                    (
                        tagName === 'button' ||
                        tagName === 'a'
                    )
                ) {
                    accessibleName =
                        (
                            el.innerText ||
                            el.textContent ||
                            ''
                        ).trim();
                }

                if (
                    !accessibleName &&
                    tagName === 'input' &&
                    (
                        el.type === 'submit' ||
                        el.type === 'button'
                    )
                ) {
                    accessibleName =
                        el.value || '';
                }

                const nearby =
                    el.closest('tr') ||
                    el.closest('td') ||
                    el.parentElement;

                return {
                    tagName,

                    text:
                        (
                            el.innerText ||
                            el.textContent ||
                            ''
                        ).trim(),

                    role:
                        el.getAttribute('role'),

                    inputType:
                        el.getAttribute('type'),

                    value,

                    accessibleName:
                        accessibleName || null,

                    nearbyText:
                        nearby
                            ? (
                                nearby.innerText ||
                                nearby.textContent ||
                                ''
                              ).trim()
                            : null,

                    href:
                        el.getAttribute('href'),

                    formMethod:
                        form
                            ? (
                                form.getAttribute(
                                    'method'
                                ) || 'get'
                              ).toLowerCase()
                            : null,

                    formAction:
                        form
                            ? form.getAttribute(
                                'action'
                              )
                            : null
                };
            }
            """
        )

        return TargetSemantics(
            tag_name=data.get(
                "tagName",
                "",
            ),
            text=data.get(
                "text",
                "",
            ),
            role=data.get(
                "role"
            ),
            input_type=data.get(
                "inputType"
            ),
            value=data.get(
                "value"
            ),
            accessible_name=data.get(
                "accessibleName"
            ),
            nearby_text=data.get(
                "nearbyText"
            ),
            href=data.get(
                "href"
            ),
            form_method=data.get(
                "formMethod"
            ),
            form_action=data.get(
                "formAction"
            ),
        )

    async def text_visible(
        self,
        value: str,
        frame: str | None = None,
    ) -> bool:
        page = self._require_page()

        if frame is not None:
            selected_frame = page.frame(
                name=frame
            )

            if selected_frame is None:
                return False

            locator = (
                selected_frame.get_by_text(
                    value,
                    exact=False,
                )
            )

            return (
                await locator.count()
                > 0
            )

        top_level_locator = (
            page.get_by_text(
                value,
                exact=False,
            )
        )

        if (
            await top_level_locator.count()
            > 0
        ):
            return True

        for child_frame in page.frames:
            if (
                child_frame
                == page.main_frame
            ):
                continue

            locator = (
                child_frame.get_by_text(
                    value,
                    exact=False,
                )
            )

            if (
                await locator.count()
                > 0
            ):
                return True

        return False

    async def current_url(
        self,
    ) -> str:
        return (
            self._require_page().url
        )

    async def screenshot(
        self,
        path: str,
    ) -> None:
        page = self._require_page()

        output = Path(
            path
        )

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        await page.screenshot(
            path=str(output),
            full_page=True,
        )

    async def page_title(
        self,
    ) -> str:
        page = self._require_page()

        return await page.title()

    async def target_visible(
        self,
        target: TargetLocator,
        frame: str | None = None,
    ) -> bool:
        page = self._require_page()

        try:
            result = (
                await self.resolver.resolve(
                    page,
                    target,
                    frame,
                )
            )

            return await (
                result.locator
                .is_visible()
            )

        except Exception:
            return False

    async def role_visible(
        self,
        role: str,
        name: str | None = None,
        frame: str | None = None,
    ) -> bool:
        page = self._require_page()

        scope = page

        if frame is not None:
            selected_frame = page.frame(
                name=frame
            )

            if selected_frame is None:
                return False

            scope = selected_frame

        aria_role = cast(
            Any,
            role,
        )

        if name is not None:
            locator = scope.get_by_role(
                aria_role,
                name=name,
            )
        else:
            locator = scope.get_by_role(
                aria_role
            )

        return (
            await locator.count()
            > 0
        )

    async def table_has_no_row_matching(
        self,
        value: str,
        column_header: str | None = None,
        frame: str | None = None,
    ) -> bool:
        """
        Return True only when a relevant table exists and
        none of its data rows contain the requested value.

        If no relevant table exists, return False so an
        unrelated error or interstitial page is not mistaken
        for a legitimate business outcome.
        """
        page = self._require_page()

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
            relevant_table = False

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

                if column_header is None:
                    relevant_table = True
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
                        == column_header
                        .casefold()
                    ):
                        header_index = index
                        relevant_table = True
                        data_start_index = (
                            row_index + 1
                        )
                        break

                if relevant_table:
                    break

            if not relevant_table:
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

                if column_header is not None:
                    if (
                        header_index is None
                        or header_index
                        >= cell_count
                    ):
                        continue

                    cell_value = (
                        await cells
                        .nth(
                            header_index
                        )
                        .inner_text()
                    ).strip()

                    if (
                        cell_value
                        .casefold()
                        == value
                        .casefold()
                    ):
                        return False

                else:
                    row_text = (
                        await row.inner_text()
                    )

                    if (
                        value.casefold()
                        in row_text.casefold()
                    ):
                        return False

            # We found the relevant table, but no matching
            # row value was present.
            return True

        # No relevant table was found.
        return False