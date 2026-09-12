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
    RecordedAction,
)
from cua.locator.harvester import (
    LocatorHarvester,
)
from cua.policy.redaction import (
    Redactor,
)
from cua.surface.observation import (
    ObservedElement,
)
from cua.surface.base import (
    Surface,
)


class DiscoveryRunner:
    def __init__(
        self,
        surface: Surface,
        agent: DiscoveryAgent,
        max_steps: int = 10,
        evidence_root: str | Path = (
            "evidence/discovery"
        ),
    ) -> None:
        self.surface = surface
        self.agent = agent
        self.max_steps = max_steps

        self.evidence_root = Path(
            evidence_root
        )

        self.harvester = (
            LocatorHarvester()
        )

        self.redactor = Redactor()


    async def run(
        self,
        goal: str,
    ) -> DiscoveryRecorder:
        run_id = (
            "discovery_"
            f"{uuid.uuid4().hex[:8]}"
        )

        run_dir = (
            self.evidence_root
            / run_id
        )

        run_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        recorder = (
            DiscoveryRecorder()
        )

        recent_actions: list[
            dict[str, str | None]
        ] = []

        try:
            for step_number in range(
                1,
                self.max_steps + 1,
            ):
                (
                    observed_elements,
                    visible_text,
                ) = (
                    await self.surface
                    .observe_discovery()
                )

                current_url = (
                    await self.surface
                    .current_url()
                )


                title = (
                    await self.surface
                    .page_title()
                )

                elements = [
                    self._element_to_prompt_dict(
                        element
                    )
                    for element
                    in observed_elements
                ]

                observation = (
                    DiscoveryObservation(
                        url=current_url,
                        title=title,
                        elements=elements,
                        visible_text=(
                            visible_text
                        ),
                        recent_actions=(
                            recent_actions
                        ),
                    )
                )

                self._save_observation(
                    run_dir=run_dir,
                    step_number=(
                        step_number
                    ),
                    observation=observation,
                )

                await self.surface.screenshot(
                    str(
                        run_dir
                        / (
                            f"step_"
                            f"{step_number}.png"
                        )
                    )
                )

                decision = (
                    await self.agent.decide(
                        goal=goal,
                        observation=(
                            observation
                        ),
                        system_prompt=(
                            DISCOVERY_SYSTEM_PROMPT
                        ),
                    )
                )

                current_url = (
                    await self.surface
                    .current_url()
                )

                if (
                    decision.action
                    == "complete"
                ):
                    recorder.record(
                        RecordedAction(
                            action="complete",
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
                                current_url
                            ),
                        )
                    )

                    return recorder

                if (
                    decision.action
                    == "stuck"
                ):
                    recorder.record(
                        RecordedAction(
                            action="stuck",
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
                                current_url
                            ),
                        )
                    )

                    raise RuntimeError(
                        "Discovery agent "
                        "reported that it "
                        "was stuck."
                    )

                if decision.ref is None:
                    raise RuntimeError(
                        "Discovery action "
                        f"'{decision.action}' "
                        "requires an element ref."
                    )

                locator = (
                    await self.surface
                    .get_discovery_locator(
                        decision.ref
                    )
                )

                target = (
                    await self.harvester
                    .harvest(
                        locator
                    )
                )

                result: str | None = (
                    None
                )

                if (
                    decision.action
                    == "fill"
                ):
                    if (
                        decision.value
                        is None
                    ):
                        raise RuntimeError(
                            "Fill action "
                            "requires a value."
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
                    RecordedAction(
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
                            current_url
                        ),
                        result=result,
                        target=target,
                    )
                )

                recent_actions.append(
                    {
                        "action": (
                            decision.action
                        ),
                        "ref": (
                            decision.ref
                        ),
                        "value": (
                            decision.value
                        ),
                        "result": result,
                    }
                )

            raise RuntimeError(
                "Discovery exceeded "
                f"maximum steps "
                f"({self.max_steps}) "
                "without completion."
            )

        finally:
            recorder.save(
                run_dir
                / "actions.json"
            )

    def _element_to_prompt_dict(
        self,
        element: ObservedElement,
    ) -> dict[str, str]:
        return {
            "ref": (
                element.ref
            ),
            "tag_name": (
                element.tag_name
            ),
            "role": (
                element.role
                or ""
            ),
            "accessible_name": (
                element.accessible_name
                or ""
            ),
            "text": (
                element.text
                or ""
            ),
            "current_value": (
                element.current_value
                or ""
            ),
            "input_type": (
                element.input_type
                or ""
            ),
            "nearby_text": (
                element.nearby_text
                or ""
            ),
            "readable": (
                "true"
                if element.readable
                else "false"
            ),
        }

    def _save_observation(
        self,
        run_dir: Path,
        step_number: int,
        observation: (
            DiscoveryObservation
        ),
    ) -> None:
        path = (
            run_dir
            / (
                "observation_"
                f"{step_number}.json"
            )
        )

        payload = {
            "url": (
                observation.url
            ),
            "title": (
                observation.title
            ),
            "elements": (
                observation.elements
            ),
            "visible_text": (
                observation.visible_text
            ),
            "recent_actions": (
                observation.recent_actions
            ),
        }

        redacted_payload = (
            self.redactor
            .redact_discovery_payload(
                payload
            )
        )

        with path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                redacted_payload,
                file,
                indent=2,
            )