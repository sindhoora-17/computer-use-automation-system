import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from cua.artifact.store import (
    load_artifact,
)
from cua.replay.recovery import (
    RecoveryEngine,
)
from cua.surface.web import (
    PlaywrightSurface,
)


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
        assert response.status == 200


@pytest.mark.asyncio
async def test_session_expiry_reauthentication():
    os.environ[
        "TARGET_APP_USERNAME"
    ] = "operator"

    os.environ[
        "TARGET_APP_PASSWORD"
    ] = "demo123"

    artifact = load_artifact(
        "capabilities/"
        "lookup_savings_balance.json"
    )

    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        await surface.navigate(
            "http://127.0.0.1:5000/"
            "content/search"
        )

        search_input = (
            artifact.steps[1].target
        )

        assert search_input is not None

        await surface.fill(
            search_input,
            "10001",
        )

        search_button = (
            artifact.steps[2].target
        )

        assert search_button is not None

        await surface.click(
            search_button
        )

        enable_scenario(
            "session_expired"
        )

        member_link = (
            artifact.steps[3].target
        )

        assert member_link is not None

        await surface.click(
            member_link
        )

        current_url = (
            await surface.current_url()
        )

        assert "/login" in current_url

        recovery = RecoveryEngine(
            surface
        )

        rule = await recovery.detect(
            artifact.recoveries
        )

        assert rule is not None
        assert rule.code == (
            "SESSION_EXPIRED"
        )

        result = await recovery.recover(
            rule
        )

        assert result.recovered is True

        current_url = (
            await surface.current_url()
        )

        assert (
            "/content/member/10001"
            in current_url
        )

        assert await surface.text_visible(
            "Member Detail"
        )

    finally:
        await surface.close()