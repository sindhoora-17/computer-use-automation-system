import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from cua.artifact.store import load_artifact
from cua.replay.engine import ReplayEngine
from cua.surface.web import PlaywrightSurface
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
        assert response.status == 200


@pytest.mark.asyncio
async def test_replay_success():
    artifact = load_artifact(
        "capabilities/"
        "lookup_savings_balance.json"
    )

    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        engine = ReplayEngine(
            surface
        )

        result = await engine.run(
            artifact,
            {
                "member_id": "10001",
            },
        )

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


@pytest.mark.asyncio
async def test_replay_member_not_found():
    artifact = load_artifact(
        "capabilities/"
        "lookup_savings_balance.json"
    )

    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        engine = ReplayEngine(
            surface
        )

        result = await engine.run(
            artifact,
            {
                "member_id": "99999",
            },
        )

        assert (
            result.status
            == RunStatus.BUSINESS_OUTCOME
        )

        assert (
            result.outcome_code
            == "MEMBER_NOT_FOUND"
        )

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_replay_no_savings_account():
    artifact = load_artifact(
        "capabilities/"
        "lookup_savings_balance.json"
    )

    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        engine = ReplayEngine(
            surface
        )

        result = await engine.run(
            artifact,
            {
                "member_id": "10003",
            },
        )

        assert (
            result.status
            == RunStatus.BUSINESS_OUTCOME
        )

        assert (
            result.outcome_code
            == "NO_SAVINGS_ACCOUNT"
        )

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_replay_recovers_from_session_expiry():
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

    enable_scenario(
        "session_expired"
    )

    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        engine = ReplayEngine(
            surface
        )

        result = await engine.run(
            artifact,
            {
                "member_id": "10001",
            },
        )

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