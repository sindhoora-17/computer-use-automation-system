from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class EscalationRequest(BaseModel):
    request_id: str

    capability_id: str
    capability_version: str

    step_id: str
    reason: str

    current_url: str

    checkpoint_description: (
        str | None
    ) = None

    screenshot_path: str | None = None

    status: Literal[
        "pending",
        "resumed",
        "timed_out",
    ] = "pending"

    created_at: str

    resumed_at: str | None = None