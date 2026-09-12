import pytest

from cua.artifact.schema import (
    LocatorStrategy,
    Step,
    TargetLocator,
)
from cua.policy.engine import (
    PolicyEngine,
    PolicyViolation,
)
from cua.surface.web import (
    PlaywrightSurface,
)
from cua.types import Effect


@pytest.mark.asyncio
async def test_search_button_is_read_only():
    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        await surface.navigate(
            "http://127.0.0.1:5000/content/search"
        )

        step = Step(
            id="submit_search",
            intent="Submit member search",
            action="click",
            effect=Effect.READ_ONLY,
            target=TargetLocator(
                strategies=[
                    LocatorStrategy(
                        kind="role_name",
                        rank=1,
                        role="button",
                        name="Search",
                    )
                ]
            ),
        )

        policy = PolicyEngine(surface)

        decision = await policy.authorize(
            step
        )

        assert decision.allowed is True

        assert (
            decision.classified_effect
            == Effect.READ_ONLY
        )

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_external_navigation_is_blocked():
    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        step = Step(
            id="leave_app",
            intent="Navigate outside app",
            action="navigate",
            effect=Effect.READ_ONLY,
        )

        policy = PolicyEngine(surface)

        with pytest.raises(
            PolicyViolation
        ):
            await policy.authorize(
                step,
                resolved_value=(
                    "https://example.com/"
                ),
            )

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_policy_classifies_from_live_target():
    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        await surface.navigate(
            "http://127.0.0.1:5000/content/search"
        )

        step = Step(
            id="bad_declaration",
            intent="Pretend unknown submit is safe",
            action="click",
            effect=Effect.READ_ONLY,
            target=TargetLocator(
                strategies=[
                    LocatorStrategy(
                        kind="xpath",
                        rank=1,
                        value=(
                            "//input[@type='submit']"
                        ),
                    )
                ]
            ),
        )

        policy = PolicyEngine(surface)

        decision = await policy.authorize(
            step
        )

        assert (
            decision.classified_effect
            == Effect.READ_ONLY
        )

    finally:
        await surface.close()