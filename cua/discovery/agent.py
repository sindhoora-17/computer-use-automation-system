from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel

from cua.surface.web import PlaywrightSurface


class AgentDecision(BaseModel):
    action: Literal[
        "click",
        "fill",
        "read",
        "complete",
        "stuck",
    ]

    ref: str | None = None
    value: str | None = None
    reason: str


@dataclass
class DiscoveryObservation:
    url: str
    title: str

    elements: list[
        dict[str, str]
    ]

    visible_text: str

    recent_actions: list[
        dict[str, str | None]
    ]

    def to_prompt(self) -> str:
        return json.dumps(
            {
                "url": self.url,
                "title": self.title,
                "elements": self.elements,
                "visible_text": (
                    self.visible_text
                ),
                "recent_actions": (
                    self.recent_actions
                ),
            },
            indent=2,
        )


class DiscoveryAgent:
    def __init__(
        self,
        surface: PlaywrightSurface,
        model: str | None = None,
    ) -> None:
        self.surface = surface

        self.model = (
            model
            or os.environ.get(
                "OPENAI_MODEL",
                "gpt-5.6-luna",
            )
        )

        self.client = AsyncOpenAI()

    async def decide(
        self,
        goal: str,
        observation: DiscoveryObservation,
        system_prompt: str,
    ) -> AgentDecision:
        response = (
            await self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    system_prompt
                                ),
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    f"GOAL:\n"
                                    f"{goal}\n\n"
                                    "CURRENT OBSERVATION:\n"
                                    f"{observation.to_prompt()}"
                                    "\n\n"
                                    "Choose the next action. "
                                    "Pay attention to "
                                    "current_value and "
                                    "recent_actions. Do not "
                                    "repeat a successful fill "
                                    "when the field already "
                                    "contains the requested "
                                    "value.\n\n"
                                    "Return JSON with exactly "
                                    "these fields:\n"
                                    "action: click | fill | "
                                    "read | complete | stuck\n"
                                    "ref: element ref or null\n"
                                    "value: text to type or "
                                    "null\n"
                                    "reason: short explanation"
                                ),
                            }
                        ],
                    },
                ],
            )
        )

        text = (
            response.output_text.strip()
        )

        data = json.loads(
            text
        )

        return (
            AgentDecision.model_validate(
                data
            )
        )