from __future__ import annotations

from typing import Any, Protocol

from cua.artifact.schema import (
    TargetLocator,
)
from cua.locator.resolver import (
    ResolutionResult,
)
from cua.surface.observation import (
    ObservedElement,
    TargetSemantics,
)


class Surface(Protocol):
    @property
    def last_resolution(
        self,
    ) -> ResolutionResult | None:
        ...

    async def navigate(
        self,
        url: str,
    ) -> None:
        ...

    async def click(
        self,
        target: TargetLocator,
        frame: str | None = None,
    ) -> None:
        ...

    async def fill(
        self,
        target: TargetLocator,
        value: str,
        frame: str | None = None,
    ) -> None:
        ...

    async def read_text(
        self,
        target: TargetLocator,
        frame: str | None = None,
    ) -> str:
        ...

    async def text_visible(
        self,
        value: str,
        frame: str | None = None,
    ) -> bool:
        ...

    async def target_visible(
        self,
        target: TargetLocator,
        frame: str | None = None,
    ) -> bool:
        ...

    async def role_visible(
        self,
        role: str,
        name: str | None = None,
        frame: str | None = None,
    ) -> bool:
        ...

    async def table_has_no_row_matching(
        self,
        value: str,
        column_header: str | None = None,
        frame: str | None = None,
    ) -> bool:
        ...

    async def inspect_target(
        self,
        target: TargetLocator,
        frame: str | None = None,
    ) -> TargetSemantics:
        ...

    async def current_url(
        self,
    ) -> str:
        ...

    async def page_title(
        self,
    ) -> str:
        ...

    async def screenshot(
        self,
        path: str,
    ) -> None:
        ...

    async def observe_discovery(
        self,
    ) -> tuple[
        list[ObservedElement],
        str,
    ]:
        ...

    async def get_discovery_locator(
        self,
        ref: str,
    ) -> Any:
        ...

    async def discovery_click(
        self,
        ref: str,
    ) -> None:
        ...

    async def discovery_fill(
        self,
        ref: str,
        value: str,
    ) -> None:
        ...

    async def discovery_read(
        self,
        ref: str,
    ) -> str:
        ...