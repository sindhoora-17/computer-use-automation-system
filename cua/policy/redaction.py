from __future__ import annotations

import re
from typing import Any, Iterator


class Redactor:
    """
    Redacts sensitive values before they are persisted to
    logs or evidence.

    Runtime/discovery logic continues to use the original
    in-memory values. Redaction is applied only at the
    persistence boundary.
    """

    REDACTED = "[REDACTED]"

    _currency_pattern = re.compile(
        r"\$\s?\d[\d,]*\.\d{2}"
    )

    _member_id_pattern = re.compile(
        r"(?<!\d)\d{5}(?!\d)"
    )

    _account_number_pattern = re.compile(
        r"(?<!\d)\d{8,19}(?!\d)"
    )

    _name_field_pattern = re.compile(
        r"\bName\s*(?:\t|:)\s*"
        r"([^\t\n\r]+)",
        re.IGNORECASE,
    )

    _name_headers = {
        "name",
        "first name",
        "last name",
        "middle name",
        "full name",
        "given name",
        "surname",
    }

    def redact_text(
        self,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        redacted = value

        redacted = (
            self._currency_pattern.sub(
                self.REDACTED,
                redacted,
            )
        )

        redacted = (
            self._member_id_pattern.sub(
                self.REDACTED,
                redacted,
            )
        )

        redacted = (
            self._account_number_pattern.sub(
                self.REDACTED,
                redacted,
            )
        )

        return redacted

    def redact_value(
        self,
        value: Any,
    ) -> Any:
        if isinstance(value, str):
            return self.redact_text(
                value
            )

        if isinstance(value, dict):
            return {
                key: self.redact_value(
                    item
                )
                for key, item
                in value.items()
            }

        if isinstance(value, list):
            return [
                self.redact_value(
                    item
                )
                for item in value
            ]

        if isinstance(value, tuple):
            return tuple(
                self.redact_value(
                    item
                )
                for item in value
            )

        return value

    def redact_discovery_payload(
        self,
        payload: Any,
    ) -> Any:
        """
        Redact normal pattern-based sensitive values and
        discover structured name values before persistence.

        Names may appear either as a normal field:

            Name    Elena Ramirez

        or inside a table:

            Member Number    Last Name    First Name    Status
            10001            Ramirez      Elena         Active

        Discovered name values are then replaced everywhere
        in the persisted payload, including standalone cells
        and nearby-text strings.
        """

        discovered_names: set[str] = set()

        self._collect_name_values(
            payload,
            discovered_names,
        )

        self._collect_table_name_values(
            payload,
            discovered_names,
        )

        redacted = self.redact_value(
            payload
        )

        for name in sorted(
            discovered_names,
            key=len,
            reverse=True,
        ):
            redacted = (
                self._replace_exact_text(
                    redacted,
                    name,
                )
            )

        return redacted

    def _collect_name_values(
        self,
        value: Any,
        output: set[str],
    ) -> None:
        if isinstance(value, str):
            for match in (
                self._name_field_pattern
                .finditer(value)
            ):
                name = (
                    match.group(1)
                    .strip()
                )

                if name:
                    output.add(name)

            return

        if isinstance(value, dict):
            for item in value.values():
                self._collect_name_values(
                    item,
                    output,
                )

            return

        if isinstance(value, (list, tuple)):
            for item in value:
                self._collect_name_values(
                    item,
                    output,
                )

    def _collect_table_name_values(
        self,
        payload: Any,
        output: set[str],
    ) -> None:
        """
        Discover values stored under name-related columns in
        tab-separated table text.

        Discovery observations often expose legacy HTML table
        rows as nearby text, for example:

            Member Number\tLast Name\tFirst Name\tStatus
            10001\tRamirez\tElena\tActive

        The first pass discovers which column indexes contain
        names. The second pass collects values from those
        columns so the values can be redacted everywhere.
        """

        strings = list(
            self._iter_strings(
                payload
            )
        )

        layouts: set[
            tuple[int, tuple[int, ...]]
        ] = set()

        for text in strings:
            columns = self._split_table_row(
                text
            )

            if len(columns) < 2:
                continue

            name_indexes = tuple(
                index
                for index, column
                in enumerate(columns)
                if (
                    self._normalize_header(
                        column
                    )
                    in self._name_headers
                )
            )

            if not name_indexes:
                continue

            layouts.add(
                (
                    len(columns),
                    name_indexes,
                )
            )

        for column_count, name_indexes in layouts:
            for text in strings:
                columns = self._split_table_row(
                    text
                )

                if (
                    len(columns)
                    != column_count
                ):
                    continue

                if self._looks_like_header_row(
                    columns
                ):
                    continue

                for index in name_indexes:
                    candidate = (
                        columns[index]
                        .strip()
                    )

                    if (
                        candidate
                        and candidate
                        != self.REDACTED
                        and not self._looks_numeric(
                            candidate
                        )
                    ):
                        output.add(
                            candidate
                        )

    def _iter_strings(
        self,
        value: Any,
    ) -> Iterator[str]:
        if isinstance(value, str):
            yield value
            return

        if isinstance(value, dict):
            for item in value.values():
                yield from self._iter_strings(
                    item
                )

            return

        if isinstance(value, (list, tuple)):
            for item in value:
                yield from self._iter_strings(
                    item
                )

    def _split_table_row(
        self,
        value: str,
    ) -> list[str]:
        if "\t" not in value:
            return []

        return [
            column.strip()
            for column in value.split(
                "\t"
            )
        ]

    def _looks_like_header_row(
        self,
        columns: list[str],
    ) -> bool:
        normalized = {
            self._normalize_header(
                column
            )
            for column in columns
        }

        return bool(
            normalized
            & self._name_headers
        )

    def _normalize_header(
        self,
        value: str,
    ) -> str:
        return " ".join(
            value.lower()
            .replace("_", " ")
            .split()
        )

    def _looks_numeric(
        self,
        value: str,
    ) -> bool:
        normalized = (
            value.replace(",", "")
            .replace(".", "")
            .replace("-", "")
            .strip()
        )

        return normalized.isdigit()

    def _replace_exact_text(
        self,
        value: Any,
        sensitive_value: str,
    ) -> Any:
        if isinstance(value, str):
            return value.replace(
                sensitive_value,
                self.REDACTED,
            )

        if isinstance(value, dict):
            return {
                key: (
                    self._replace_exact_text(
                        item,
                        sensitive_value,
                    )
                )
                for key, item
                in value.items()
            }

        if isinstance(value, list):
            return [
                self._replace_exact_text(
                    item,
                    sensitive_value,
                )
                for item in value
            ]

        if isinstance(value, tuple):
            return tuple(
                self._replace_exact_text(
                    item,
                    sensitive_value,
                )
                for item in value
            )

        return value