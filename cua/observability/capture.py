from __future__ import annotations

from pathlib import Path

from cua.surface.base import Surface


class EvidenceCapture:
    def __init__(
        self,
        run_dir: Path,
    ) -> None:
        self.run_dir = run_dir

        self.screenshot_dir = (
            run_dir / "screenshots"
        )

        self.screenshot_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    async def failure_screenshot(
        self,
        surface: Surface,
        step_id: str,
    ) -> str:
        path = (
            self.screenshot_dir
            / f"failure_{step_id}.png"
        )

        await surface.screenshot(
            str(path)
        )

        return str(path)