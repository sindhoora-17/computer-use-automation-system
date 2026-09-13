from copy import deepcopy

import pytest

from cua.artifact.store import (
    load_artifact,
)
from cua.replay.engine import (
    ReplayEngine,
)
from cua.surface.web import (
    PlaywrightSurface,
)
from cua.types import RunStatus


@pytest.mark.asyncio
async def test_replay_uses_artifact_output_name(
    tmp_path,
):
    artifact = load_artifact(
        "capabilities/"
        "lookup_savings_balance.json"
    )

    artifact = deepcopy(
        artifact
    )

    spec = artifact.outputs.pop(
        "savings_balance"
    )

    artifact.outputs[
        "generic_balance"
    ] = spec

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
                "member_id":
                    "10001",
            },
        )

        assert (
            result.status
            == RunStatus.SUCCESS
        )

        assert (
            "generic_balance"
            in result.outputs
        )

        assert (
            "savings_balance"
            not in result.outputs
        )

        assert (
            str(
                result.outputs[
                    "generic_balance"
                ]
            )
            == "1842.17"
        )

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_output_can_be_hidden_from_caller(
    tmp_path,
):
    artifact = load_artifact(
        "capabilities/"
        "lookup_savings_balance.json"
    )

    artifact = deepcopy(
        artifact
    )

    artifact.outputs[
        "savings_balance"
    ].return_to_caller = False

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
                "member_id":
                    "10001",
            },
        )

        assert (
            result.status
            == RunStatus.SUCCESS
        )

        assert (
            "savings_balance"
            not in result.outputs
        )

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_unsatisfied_success_condition_fails(
    tmp_path,
):
    artifact = load_artifact(
        "capabilities/"
        "lookup_savings_balance.json"
    )

    artifact = deepcopy(
        artifact
    )

    artifact.success_condition.all_of = [
        "step:never_happens"
    ]

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
                "member_id":
                    "10001",
            },
        )

        assert (
            result.status
            == RunStatus.FAILURE
        )

        assert result.error is not None

        assert (
            result.error.code
            == (
                "SUCCESS_CONDITION_"
                "NOT_REACHED"
            )
        )

    finally:
        await surface.close()