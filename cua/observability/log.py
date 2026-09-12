from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RunLogger:
    def __init__(
        self,
        run_id: str,
        base_dir: str = "evidence/replay",
    ) -> None:
        self.run_id = run_id

        self.run_dir = Path(base_dir) / run_id
        self.run_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.log_path = self.run_dir / "run.jsonl"

    def log(
        self,
        event: str,
        **data: Any,
    ) -> None:
        record = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "event": event,
            **data,
        }

        with self.log_path.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(
                    record,
                    default=str,
                )
                + "\n"
            )

    def redact_inputs(
        self,
        inputs: dict[str, Any],
        redact_keys: set[str],
    ) -> dict[str, Any]:
        return {
            key: (
                "[REDACTED]"
                if key in redact_keys
                else value
            )
            for key, value in inputs.items()
        }