import os
from copy import deepcopy
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from cua.artifact.store import load_artifact
from cua.policy.engine import PolicyEngine
from cua.replay.engine import ReplayEngine
from cua.surface.web import PlaywrightSurface
from cua.types import OutcomeClass, RunStatus


def set_scenario(
    name: str,
    enabled: bool,
) -> None:
    data = urlencode(
        {
            "name": name,
            "enabled": (
                "true"
                if enabled
                else "false"
            ),
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
async def test_replay_success(
    tmp_path,
):
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
            surface,
            evidence_dir=tmp_path,
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
async def test_replay_member_not_found(
    tmp_path,
):
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
            surface,
            evidence_dir=tmp_path,
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
async def test_replay_no_savings_account(
    tmp_path,
):
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
            surface,
            evidence_dir=tmp_path,
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
async def test_application_error_is_artifact_hard_failure(
    tmp_path,
):
    artifact = load_artifact(
        "capabilities/"
        "lookup_savings_balance.json"
    )

    set_scenario(
        "app_error",
        True,
    )

    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        engine = ReplayEngine(
            surface,
            evidence_dir=tmp_path,
        )

        result = await engine.run(
            artifact,
            {
                "member_id": "10001",
            },
        )

        assert (
            result.status
            == RunStatus.FAILURE
        )

        assert result.error is not None

        assert (
            result.error.code
            == "APPLICATION_ERROR"
        )

    finally:
        set_scenario(
            "app_error",
            False,
        )
        await surface.close()


@pytest.mark.asyncio
async def test_replay_recovers_from_session_expiry(
    tmp_path,
):
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

    set_scenario(
        "session_expired",
        True,
    )

    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        engine = ReplayEngine(
            surface,
            evidence_dir=tmp_path,
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
        set_scenario(
            "session_expired",
            False,
        )
        await surface.close()


@pytest.mark.asyncio
async def test_hard_failure_outcome_is_not_business_outcome(
    tmp_path,
):
    artifact = load_artifact(
        "capabilities/"
        "lookup_savings_balance.json"
    )

    artifact = deepcopy(
        artifact
    )

    member_not_found = next(
        outcome
        for outcome in artifact.expected_outcomes
        if outcome.code == "MEMBER_NOT_FOUND"
    )

    member_not_found.classification = (
        OutcomeClass.HARD_FAILURE
    )

    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        engine = ReplayEngine(
            surface,
            evidence_dir=tmp_path,
        )

        result = await engine.run(
            artifact,
            {
                "member_id": "99999",
            },
        )

        assert (
            result.status
            == RunStatus.FAILURE
        )

        assert result.error is not None

        assert (
            result.error.code
            == "MEMBER_NOT_FOUND"
        )

        assert (
            result.outcome_code
            is None
        )

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_fingerprint_checked_before_non_navigate_first_step(
    tmp_path,
):
    artifact = load_artifact(
        "capabilities/"
        "lookup_savings_balance.json"
    )

    artifact = deepcopy(
        artifact
    )

    artifact.steps = artifact.steps[1:]

    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        await surface.navigate(
            "http://127.0.0.1:5000/login"
        )

        engine = ReplayEngine(
            surface,
            evidence_dir=tmp_path,
        )

        result = await engine.run(
            artifact,
            {
                "member_id": "10001",
            },
        )

        assert (
            result.status
            == RunStatus.FAILURE
        )

        assert result.error is not None

        assert (
            result.error.code
            == "TARGET_FINGERPRINT_MISMATCH"
        )

    finally:
        await surface.close()


def test_replay_engine_uses_injected_policy():
    surface = PlaywrightSurface(
        headless=True
    )

    policy = PolicyEngine(
        surface
    )

    engine = ReplayEngine(
        surface,
        policy=policy,
    )

    assert engine.policy is policy
