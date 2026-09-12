from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml


class AllowlistViolation(Exception):
    pass


class Allowlist:
    def __init__(
        self,
        config_path: str | Path,
    ) -> None:
        path = Path(config_path)

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            config = yaml.safe_load(file)

        self.allowed_origins: set[str] = set(
            config.get(
                "allowed_origins",
                [],
            )
        )

        self.allowed_path_prefixes: list[str] = list(
            config.get(
                "allowed_path_prefixes",
                [],
            )
        )

        self.allowed_actions: set[str] = set(
            config.get(
                "allowed_actions",
                [],
            )
        )

        self.safe_click_terms: list[str] = list(
            config.get(
                "safe_click_terms",
                [],
            )
        )

        self.reversible_terms: list[str] = list(
            config.get(
                "reversible_terms",
                [],
            )
        )

        self.irreversible_terms: list[str] = list(
            config.get(
                "irreversible_terms",
                [],
            )
        )

    def require_action_allowed(
        self,
        action: str,
    ) -> None:
        if action not in self.allowed_actions:
            raise AllowlistViolation(
                f"Action '{action}' is not allowed."
            )

    def require_url_allowed(
        self,
        url: str,
        base_url: str | None = None,
    ) -> None:
        if base_url:
            url = urljoin(
                base_url,
                url,
            )

        parsed = urlparse(url)

        origin = (
            f"{parsed.scheme}://"
            f"{parsed.netloc}"
        )

        if origin not in self.allowed_origins:
            raise AllowlistViolation(
                f"Origin '{origin}' is not allowed."
            )

        if not any(
            parsed.path.startswith(prefix)
            for prefix
            in self.allowed_path_prefixes
        ):
            raise AllowlistViolation(
                f"Path '{parsed.path}' is not allowed."
            )