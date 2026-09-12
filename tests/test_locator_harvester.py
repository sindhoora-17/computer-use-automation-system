import pytest

from cua.locator.harvester import (
    LocatorHarvester,
)
from cua.surface.web import (
    PlaywrightSurface,
)


@pytest.mark.asyncio
async def test_harvests_legacy_search_input_locator():
    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        await surface.navigate(
            "http://127.0.0.1:5000/"
            "content/search"
        )

        elements, _ = (
            await surface
            .observe_discovery()
        )

        search_element = next(
            element
            for element
            in elements
            if (
                element.tag_name
                == "input"
                and element.input_type
                == "text"
            )
        )

        locator = (
            await surface
            .get_discovery_locator(
                search_element.ref
            )
        )

        harvester = (
            LocatorHarvester()
        )

        target = (
            await harvester.harvest(
                locator
            )
        )

        kinds = [
            strategy.kind
            for strategy
            in target.strategies
        ]

        assert (
            "anchor_relative"
            in kinds
        )

        assert (
            "xpath"
            in kinds
        )

        anchor_strategy = next(
            strategy
            for strategy
            in target.strategies
            if (
                strategy.kind
                == "anchor_relative"
            )
        )

        assert (
            anchor_strategy.anchor_text
            == (
                "Member Number "
                "/ Last Name"
            )
        )

        assert (
            anchor_strategy.relationship
            == "following_input"
        )

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_harvests_balance_as_table_cell():
    surface = PlaywrightSurface(
        headless=True
    )

    await surface.start()

    try:
        await surface.navigate(
            "http://127.0.0.1:5000/"
            "content/member/10001"
        )

        elements, _ = (
            await surface
            .observe_discovery()
        )

        balance_element = next(
            element
            for element
            in elements
            if (
                element.text
                == "$1842.17"
            )
        )

        locator = (
            await surface
            .get_discovery_locator(
                balance_element.ref
            )
        )

        harvester = (
            LocatorHarvester()
        )

        target = (
            await harvester.harvest(
                locator
            )
        )

        first = (
            target.strategies[0]
        )

        assert (
            first.kind
            == "table_cell"
        )

        assert (
            first.row_anchor
            == "Savings"
        )

        assert (
            first.column_header
            == "Current Balance"
        )

    finally:
        await surface.close()