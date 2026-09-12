from __future__ import annotations

from typing import Protocol

from cua.artifact.schema import TargetLocator


class Surface(Protocol):
    async def navigate(self, url: str) -> None:
        ...

    async def click(self, target: TargetLocator, frame: str | None = None) -> None:
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

    async def text_visible(self, value: str, frame: str | None = None) -> bool:
        ...

    async def current_url(self) -> str:
        ...

    async def screenshot(self, path: str) -> None:
        ...