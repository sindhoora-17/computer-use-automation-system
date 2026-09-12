from __future__ import annotations

import re
from typing import Any


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
        additionally discover structured Name-field values
        from the payload.

        Once a value is observed after a field such as:

            Name    Elena Ramirez

        that exact value is replaced everywhere in the
        persisted payload, including standalone element
        text.
        """

        discovered_names: set[str] = set()

        self._collect_name_values(
            payload,
            discovered_names,
        )

        redacted = self.redact_value(
            payload
        )

        for name in discovered_names:
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