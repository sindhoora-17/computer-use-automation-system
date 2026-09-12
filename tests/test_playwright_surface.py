import pytest

from cua.artifact.schema import LocatorStrategy, TargetLocator
from cua.surface.web import PlaywrightSurface


@pytest.mark.asyncio
async def test_surface_can_search_member():
    surface = PlaywrightSurface(headless=True)

    await surface.start()

    try:
        await surface.navigate(
            "http://127.0.0.1:5000/login"
        )

        username = TargetLocator(
            strategies=[
                LocatorStrategy(
                    kind="role_name",
                    rank=1,
                    role="textbox",
                    name="Operator ID",
                )
            ]
        )

        password = TargetLocator(
            strategies=[
                LocatorStrategy(
                    kind="xpath",
                    rank=1,
                    value="//input[@name='password']",
                )
            ]
        )

        login_button = TargetLocator(
            strategies=[
                LocatorStrategy(
                    kind="role_name",
                    rank=1,
                    role="button",
                    name="Log In",
                )
            ]
        )

        await surface.fill(
            username,
            "operator",
        )

        await surface.fill(
            password,
            "demo123",
        )

        await surface.click(login_button)

        assert await surface.text_visible(
            "Meridian Core Admin"
        )

    finally:
        await surface.close()