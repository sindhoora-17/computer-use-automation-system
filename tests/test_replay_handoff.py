import asyncio
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from cua.artifact.store import (
    load_artifact,
)
from cua.escalation.session import (
    HandoffSession,
)
from cua.replay.engine import (
    ReplayEngine,
)
from cua.surface.web import (
    PlaywrightSurface,
)
from cua.types import RunStatus


def enable_scenario(
    name: str,
) -> None:
    data = urlencode(
        {
            "name": name,
            "enabled": "true",
        }
    ).encode()

    request = Request(
        (
            "http://127.0.0.1:5000"
            "/_control/scenario"
        ),
        data=data,
        method="POST",
    )

    with urlopen(
        request,
        timeout=5,
    ) as response:
        assert (
            response.status
            == 200
        )


@pytest.mark.asyncio
async def test_replay_handoff_resumes_same_session(
    tmp_path,
):
    artifact = load_artifact(
        "capabilities/"
        "lookup_savings_balance.json"
    )

    enable_scenario(
        "interstitial"
    )

    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        handoff = HandoffSession(
            surface=surface,
            evidence_dir=tmp_path,
        )

        engine = ReplayEngine(
            surface=surface,
            handoff_session=handoff,
            evidence_dir=tmp_path,
        )

        replay_task = (
            asyncio.create_task(
                engine.run(
                    artifact,
                    {
                        "member_id":
                            "10001"
                    },
                )
            )
        )

        for _ in range(300):
            if (
                handoff.current_request
                is not None
            ):
                break

            await asyncio.sleep(
                0.01
            )

        assert (
            handoff.current_request
            is not None
        )

        assert (
            handoff.current_request
            .status
            == "pending"
        )

        page = (
            surface._require_page()
        )

        assert (
            await page.get_by_text(
                "Manual Review Required"
            ).count()
            > 0
        )

        # This represents the human taking over
        # the exact same live browser session.
        await page.get_by_role(
            "button",
            name="Continue to Member",
        ).click()

        assert (
            await surface.text_visible(
                "Member Detail"
            )
        )

        # The operator signals that manual work
        # is complete.
        handoff.resume()

        result = await replay_task

        assert (
            result.status
            == RunStatus.SUCCESS
        )

        assert (
            str(
                result.outputs[
                    "savings_balance"
                ]
            )
            == "1842.17"
        )

    finally:
        await surface.close()