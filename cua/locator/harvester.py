from __future__ import annotations

import re

from playwright.async_api import Locator

from cua.artifact.schema import (
    LocatorStrategy,
    TargetLocator,
)

SEMANTIC_RANK = 1
RELATIONAL_RANK = 2
XPATH_RANK = 4
BBOX_RANK = 5

class LocatorHarvester:
    """
    Deterministically converts a live DOM element into
    a ranked reusable locator ladder.

    The LLM selects an observed element, but it never
    authors selectors.
    """

    async def harvest(
        self,
        locator: Locator,
    ) -> TargetLocator:
        metadata = await locator.evaluate(
            """
            (el) => {
                const tag =
                    el.tagName
                        ? el.tagName.toLowerCase()
                        : '';

                const text =
                    (
                        el.innerText ||
                        el.textContent ||
                        ''
                    ).trim();

                let labelText = null;

                if (el.id) {
                    const label =
                        document.querySelector(
                            `label[for="${CSS.escape(el.id)}"]`
                        );

                    if (label) {
                        labelText =
                            (
                                label.innerText ||
                                label.textContent ||
                                ''
                            ).trim();
                    }
                }

                const ariaLabel =
                    el.getAttribute(
                        'aria-label'
                    );

                const name =
                    el.getAttribute(
                        'name'
                    );

                const href =
                    el.getAttribute(
                        'href'
                    );

                const role =
                    el.getAttribute(
                        'role'
                    );

                const type =
                    el.getAttribute(
                        'type'
                    );

                const value =
                    (
                        'value' in el
                        ? el.value
                        : el.getAttribute(
                            'value'
                        )
                    );

                let anchorText = null;

                /*
                 * Legacy table forms often place a visual
                 * field label in the previous table cell
                 * instead of using a real <label>.
                 *
                 * Example:
                 *
                 * <tr>
                 *   <td>Member Number / Last Name</td>
                 *   <td><input ...></td>
                 * </tr>
                 */
                if (
                    tag === 'input' ||
                    tag === 'textarea' ||
                    tag === 'select'
                ) {
                    const containingCell =
                        el.closest('td, th');

                    if (containingCell) {
                        const previousCell =
                            containingCell
                                .previousElementSibling;

                        if (previousCell) {
                            const candidate =
                                (
                                    previousCell.innerText ||
                                    previousCell.textContent ||
                                    ''
                                ).trim();

                            if (candidate) {
                                anchorText = candidate;
                            }
                        }
                    }
                }

                let rowTexts = [];
                let columnHeader = null;
                let columnIndex = null;

                const cell =
                    el.closest('td, th');

                const row =
                    cell
                        ? cell.closest('tr')
                        : null;

                const table =
                    row
                        ? row.closest('table')
                        : null;

                if (row) {
                    rowTexts = Array.from(
                        row.querySelectorAll(
                            'th, td'
                        )
                    ).map(
                        (node) =>
                            (
                                node.innerText ||
                                node.textContent ||
                                ''
                            ).trim()
                    );
                }

                if (cell && row && table) {
                    const cells =
                        Array.from(
                            row.querySelectorAll(
                                'th, td'
                            )
                        );

                    columnIndex =
                        cells.indexOf(cell);

                    const headerRow =
                        Array.from(
                            table.querySelectorAll(
                                'tr'
                            )
                        ).find(
                            (candidate) =>
                                candidate.querySelector(
                                    'th'
                                )
                        );

                    if (
                        headerRow &&
                        columnIndex >= 0
                    ) {
                        const headers =
                            Array.from(
                                headerRow.querySelectorAll(
                                    'th, td'
                                )
                            );

                        if (
                            columnIndex <
                            headers.length
                        ) {
                            columnHeader =
                                (
                                    headers[
                                        columnIndex
                                    ].innerText ||
                                    headers[
                                        columnIndex
                                    ].textContent ||
                                    ''
                                ).trim();
                        }
                    }
                }

                return {
                    tag,
                    text,
                    labelText,
                    ariaLabel,
                    anchorText,
                    name,
                    href,
                    role,
                    type,
                    value,
                    rowTexts,
                    columnHeader,
                    columnIndex
                };
            }
            """
        )

        strategies: list[
            LocatorStrategy
        ] = []

        tag = (
            metadata.get(
                "tag",
                "",
            )
            or ""
        ).strip()

        text = (
            metadata.get(
                "text",
                "",
            )
            or ""
        ).strip()

        label_text = (
            metadata.get(
                "labelText",
                "",
            )
            or ""
        ).strip()

        aria_label = (
            metadata.get(
                "ariaLabel",
                "",
            )
            or ""
        ).strip()

        anchor_text = (
            metadata.get(
                "anchorText",
                "",
            )
            or ""
        ).strip()

        name = (
            metadata.get(
                "name",
                "",
            )
            or ""
        ).strip()

        href = (
            metadata.get(
                "href",
                "",
            )
            or ""
        ).strip()

        value = (
            metadata.get(
                "value",
                "",
            )
            or ""
        ).strip()

        input_type = (
            metadata.get(
                "type",
                "",
            )
            or ""
        ).strip()

        column_header = (
            metadata.get(
                "columnHeader",
                "",
            )
            or ""
        ).strip()

        column_index_raw = metadata.get(
            "columnIndex"
        )

        column_index = (
            int(column_index_raw)
            if column_index_raw is not None
            else None
        )

        row_texts = [
            str(item).strip()
            for item in metadata.get(
                "rowTexts",
                [],
            )
            if str(item).strip()
        ]

        # Strong semantic strategy for tabular data.
        if (
            tag in {
                "td",
                "th",
            }
            and column_header
            and row_texts
        ):
            row_anchor = (
                self._choose_row_anchor(
                    row_texts,
                    text,
                )
            )

            if row_anchor:
                strategies.append(
                    LocatorStrategy(
                        kind="table_cell",
                        rank=SEMANTIC_RANK,
                        row_anchor=row_anchor,
                        column_header=(
                            column_header
                        ),
                    )
                )

                if (
                    column_index
                    is not None
                ):
                    strategies.append(
                        LocatorStrategy(
                            kind="table_position",
                            rank=XPATH_RANK,
                            row_anchor=row_anchor,
                            column_index=(
                                column_index
                            ),
                        )
                    )

        # Proper HTML labels are preferred when available.
        if (
            tag
            in {
                "input",
                "textarea",
                "select",
            }
            and label_text
        ):
            strategies.append(
                LocatorStrategy(
                    kind="label_text",
                    rank=SEMANTIC_RANK,
                    value=label_text,
                )
            )

        # Legacy forms often use a nearby table cell as the
        # only human-readable label.
        if (
            tag
            in {
                "input",
                "textarea",
                "select",
            }
            and not label_text
            and anchor_text
        ):
            relationship = (
                "following_input"
                if tag == "input"
                else None
            )

            if relationship:
                strategies.append(
                    LocatorStrategy(
                        kind="anchor_relative",
                        rank=RELATIONAL_RANK,
                        anchor_text=(
                            anchor_text
                        ),
                        relationship=(
                            relationship
                        ),
                    )
                )


        role_name = (
            aria_label
            or self._semantic_name(
                tag=tag,
                text=text,
                value=value,
            )
        )

        role = self._infer_role(
            tag=tag,
            input_type=input_type,
        )

        if (
            role
            and role_name
            and not self._looks_dynamic(
                role_name
            )
        ):
            strategies.append(
                LocatorStrategy(
                    kind="role_name",
                    rank=SEMANTIC_RANK,
                    role=role,
                    name=role_name,
                )
            )

        if (
            tag == "a"
            and href
        ):
            href_prefix = (
                self._generalize_href(
                    href
                )
            )

            if (
                href_prefix
                and href_prefix != href
            ):
                strategies.append(
                    LocatorStrategy(
                        kind="href_prefix",
                        rank=RELATIONAL_RANK,
                        value=href_prefix,
                    )
                )

        xpath = self._build_xpath(
            tag=tag,
            name=name,
            href=href,
            text=text,
            input_type=input_type,
            value=value,
        )

        if xpath:
            strategies.append(
                LocatorStrategy(
                    kind="xpath",
                    rank=XPATH_RANK,
                    value=xpath,
                )
            )

        if not strategies:
            raise ValueError(
                "Unable to harvest a reusable "
                "locator for selected element."
            )

        return TargetLocator(
            strategies=strategies
        )

    def _choose_row_anchor(
        self,
        row_texts: list[str],
        selected_text: str,
    ) -> str | None:
        for value in row_texts:
            if (
                value
                and value
                != selected_text
                and not self._looks_like_currency(
                    value
                )
                and not self._looks_like_account_number(
                    value
                )
            ):
                return value

        return None

    def _semantic_name(
        self,
        tag: str,
        text: str,
        value: str,
    ) -> str | None:
        if tag in {
            "button",
            "a",
        }:
            return text or None

        if (
            tag == "input"
            and value
        ):
            return value

        return None

    def _infer_role(
        self,
        tag: str,
        input_type: str,
    ) -> str | None:
        if tag == "a":
            return "link"

        if tag == "button":
            return "button"

        if tag == "textarea":
            return "textbox"

        if tag == "select":
            return "combobox"

        if tag == "input":
            lowered = (
                input_type.casefold()
            )

            if lowered in {
                "submit",
                "button",
                "reset",
            }:
                return "button"

            if lowered in {
                "text",
                "password",
                "email",
                "search",
                "",
            }:
                return "textbox"

        return None

    def _build_xpath(
        self,
        tag: str,
        name: str,
        href: str,
        text: str,
        input_type: str,
        value: str,
    ) -> str | None:
        if not tag:
            return None

        if name:
            return (
                f"//{tag}"
                f"[@name="
                f"{self._xpath_literal(name)}]"
            )

        if (
            tag == "a"
            and href
        ):
            normalized = (
                self._generalize_href(
                    href
                )
            )

            if normalized:
                return (
                    "//a[contains(@href, "
                    f"{self._xpath_literal(normalized)}"
                    ")]"
                )

        if (
            tag == "input"
            and input_type
            in {
                "submit",
                "button",
            }
            and value
        ):
            return (
                "//input"
                f"[@type="
                f"{self._xpath_literal(input_type)}"
                " and "
                f"@value="
                f"{self._xpath_literal(value)}"
                "]"
            )

        if (
            text
            and not self._looks_dynamic(
                text
            )
        ):
            return (
                f"//{tag}"
                "[normalize-space(.)="
                f"{self._xpath_literal(text)}"
                "]"
            )

        return None

    def _generalize_href(
        self,
        href: str,
    ) -> str | None:
        # Example:
        # /content/member/10001
        # becomes:
        # /content/member/
        if re.search(
            r"/\d+$",
            href,
        ):
            return re.sub(
                r"\d+$",
                "",
                href,
            )

        return href

    def _looks_dynamic(
        self,
        value: str,
    ) -> bool:
        stripped = value.strip()

        if re.fullmatch(
            r"\d{4,}",
            stripped,
        ):
            return True

        if self._looks_like_currency(
            stripped
        ):
            return True

        return False

    def _looks_like_currency(
        self,
        value: str,
    ) -> bool:
        return (
            re.fullmatch(
                r"\$?[\d,]+\.\d{2}",
                value.strip(),
            )
            is not None
        )

    def _looks_like_account_number(
        self,
        value: str,
    ) -> bool:
        stripped = (
            value
            .replace("*", "")
            .replace("•", "")
            .strip()
        )

        return (
            stripped.isdigit()
            and len(stripped) >= 4
        )

    def _xpath_literal(
        self,
        value: str,
    ) -> str:
        if "'" not in value:
            return f"'{value}'"

        if '"' not in value:
            return f'"{value}"'

        parts = value.split("'")

        joined = (
            ", \"'\", ".join(
                f"'{part}'"
                for part in parts
            )
        )

        return (
            f"concat({joined})"
        )