from __future__ import annotations

import json
import uuid
from pathlib import Path

from cua.discovery.agent import (
    DiscoveryAgent,
    DiscoveryObservation,
)
from cua.discovery.prompts import (
    DISCOVERY_SYSTEM_PROMPT,
)
from cua.discovery.recorder import (
    DiscoveryRecorder,
)
from cua.locator.harvester import (
    LocatorHarvester,
)
from cua.surface.web import (
    PlaywrightSurface,
)


class DiscoveryRunner:
    def __init__(
        self,
        surface: PlaywrightSurface,
        agent: DiscoveryAgent,
        max_steps: int = 12,
    ) -> None:
        self.surface = surface
        self.agent = agent
        self.max_steps = max_steps

        self.harvester = (
            LocatorHarvester()
        )

    async def run(
        self,
        goal: str,
    ) -> DiscoveryRecorder:
        recorder = (
            DiscoveryRecorder()
        )

        run_id = (
            f"discovery_"
            f"{uuid.uuid4().hex[:8]}"
        )

        run_dir = (
            Path(
                "evidence/discovery"
            )
            / run_id
        )

        run_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        completed = False

        try:
            for step_number in range(
                1,
                self.max_steps + 1,
            ):
                (
                    elements,
                    visible_text,
                ) = (
                    await self.surface
                    .observe_discovery()
                )

                page = (
                    self.surface
                    ._require_page()
                )

                recent_actions = [
                    {
                        "action": (
                            action.action
                        ),
                        "ref": (
                            action.ref
                        ),
                        "value": (
                            action.value
                        ),
                        "reason": (
                            action.reason
                        ),
                        "result": (
                            action.result
                        ),
                    }
                    for action
                    in recorder.actions[-5:]
                ]

                observation = (
                    DiscoveryObservation(
                        url=page.url,
                        title=(
                            await page.title()
                        ),
                        elements=[
                            {
                                "ref": (
                                    element.ref
                                ),
                                "tag": (
                                    element
                                    .tag_name
                                ),
                                "role": (
                                    element.role
                                    or ""
                                ),
                                "accessible_name": (
                                    element
                                    .accessible_name
                                ),
                                "text": (
                                    element.text
                                ),
                                "current_value": (
                                    element
                                    .current_value
                                ),
                                "input_type": (
                                    element
                                    .input_type
                                    or ""
                                ),
                                "nearby_text": (
                                    element
                                    .nearby_text
                                ),
                                "readable": (
                                    str(
                                        element
                                        .readable
                                    )
                                ),
                            }
                            for element
                            in elements
                        ],
                        visible_text=(
                            visible_text
                        ),
                        recent_actions=(
                            recent_actions
                        ),
                    )
                )

                with (
                    run_dir
                    / (
                        "observation_"
                        f"{step_number}.json"
                    )
                ).open(
                    "w",
                    encoding="utf-8",
                ) as file:
                    json.dump(
                        {
                            "url": (
                                observation.url
                            ),
                            "title": (
                                observation.title
                            ),
                            "elements": (
                                observation
                                .elements
                            ),
                            "visible_text": (
                                observation
                                .visible_text
                            ),
                            "recent_actions": (
                                observation
                                .recent_actions
                            ),
                        },
                        file,
                        indent=2,
                    )

                await (
                    self.surface
                    .screenshot(
                        str(
                            run_dir
                            / (
                                "step_"
                                f"{step_number}"
                                ".png"
                            )
                        )
                    )
                )

                decision = (
                    await self.agent
                    .decide(
                        goal,
                        observation,
                        DISCOVERY_SYSTEM_PROMPT,
                    )
                )

                if (
                    decision.action
                    == "complete"
                ):
                    recorder.record(
                        action=(
                            decision.action
                        ),
                        ref=(
                            decision.ref
                        ),
                        value=(
                            decision.value
                        ),
                        reason=(
                            decision.reason
                        ),
                        observed_url=(
                            observation.url
                        ),
                    )

                    completed = True
                    break

                if (
                    decision.action
                    == "stuck"
                ):
                    recorder.record(
                        action=(
                            decision.action
                        ),
                        ref=(
                            decision.ref
                        ),
                        value=(
                            decision.value
                        ),
                        reason=(
                            decision.reason
                        ),
                        observed_url=(
                            observation.url
                        ),
                    )

                    raise RuntimeError(
                        "Discovery agent "
                        "reported stuck: "
                        f"{decision.reason}"
                    )

                if not decision.ref:
                    raise RuntimeError(
                        "Agent selected an "
                        "action without an "
                        "element ref."
                    )

                selected_locator = (
                    await self.surface
                    .get_discovery_locator(
                        decision.ref
                    )
                )

                target = (
                    await self.harvester
                    .harvest(
                        selected_locator
                    )
                )

                result: str | None = None

                if (
                    decision.action
                    == "click"
                ):
                    await (
                        self.surface
                        .discovery_click(
                            decision.ref
                        )
                    )

                elif (
                    decision.action
                    == "fill"
                ):
                    if (
                        decision.value
                        is None
                    ):
                        raise RuntimeError(
                            "Fill action "
                            "missing value."
                        )

                    await (
                        self.surface
                        .discovery_fill(
                            decision.ref,
                            decision.value,
                        )
                    )

                elif (
                    decision.action
                    == "read"
                ):
                    result = (
                        await self.surface
                        .discovery_read(
                            decision.ref
                        )
                    )

                else:
                    raise RuntimeError(
                        "Unsupported discovery "
                        "action: "
                        f"{decision.action}"
                    )

                recorder.record(
                    action=(
                        decision.action
                    ),
                    ref=(
                        decision.ref
                    ),
                    value=(
                        decision.value
                    ),
                    reason=(
                        decision.reason
                    ),
                    observed_url=(
                        observation.url
                    ),
                    result=result,
                    target=target,
                )

        finally:
            with (
                run_dir
                / "actions.json"
            ).open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    recorder.as_dicts(),
                    file,
                    indent=2,
                )

        if not completed:
            raise RuntimeError(
                "Discovery reached the "
                f"{self.max_steps}-step "
                "limit without completing "
                "the goal."
            )

        return recorder