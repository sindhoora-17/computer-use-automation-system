import asyncio

import pytest

from cua.escalation.session import (
    HandoffSession,
)
from cua.surface.web import (
    PlaywrightSurface,
)


@pytest.mark.asyncio
async def test_handoff_preserves_live_session(
    tmp_path,
):
    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        await surface.navigate(
            "http://127.0.0.1:5000/"
            "content/member/10001"
        )

        original_url = (
            await surface.current_url()
        )

        handoff = HandoffSession(
            surface=surface,
            evidence_dir=tmp_path,
        )

        task = asyncio.create_task(
            handoff.escalate(
                capability_id=(
                    "lookup_savings_balance"
                ),
                capability_version=(
                    "1.0.0"
                ),
                step_id=(
                    "open_member"
                ),
                reason=(
                    "Checkpoint needs "
                    "human assistance."
                ),
                checkpoint_description=(
                    "Member Detail must "
                    "be visible."
                ),
                timeout_s=5,
            )
        )

        for _ in range(100):
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

        # The exact same Playwright page remains alive.
        assert (
            await surface.current_url()
            == original_url
        )

        assert (
            not task.done()
        )

        handoff.resume()

        request = await task

        assert (
            request.status
            == "resumed"
        )

        assert (
            await surface.current_url()
            == original_url
        )

        request_json = (
            tmp_path
            / request.request_id
            / "request.json"
        )

        screenshot = (
            tmp_path
            / request.request_id
            / "handoff.png"
        )

        assert (
            request_json.exists()
        )

        assert screenshot.exists()

    finally:
        await surface.close()