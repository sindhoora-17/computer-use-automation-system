from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from dotenv import load_dotenv

from cua.artifact.recorder import (
    ArtifactRecorder,
)
from cua.artifact.store import (
    load_artifact,
)
from cua.discovery.agent import (
    DiscoveryAgent,
)
from cua.discovery.runner import (
    DiscoveryRunner,
)
from cua.replay.engine import (
    ReplayEngine,
)
from cua.surface.web import (
    PlaywrightSurface,
)


app = typer.Typer(
    help=(
        "Computer-use automation system "
        "for discovery and deterministic replay."
    )
)


@app.callback()
def cli() -> None:
    """
    LLM discovery and deterministic replay.
    """


@app.command()
def discover(
    goal: str = typer.Argument(
        ...,
        help="Goal for the discovery agent.",
    ),
    start_url: str = typer.Option(
        (
            "http://127.0.0.1:5000/"
            "content/search"
        ),
        help="Starting URL for discovery.",
    ),
    headless: bool = typer.Option(
        False,
        help=(
            "Run the browser without "
            "a visible window."
        ),
    ),
) -> None:
    """
    Run a genuine LLM-driven discovery session.
    """

    load_dotenv()

    asyncio.run(
        _run_discovery(
            goal=goal,
            start_url=start_url,
            headless=headless,
        )
    )


@app.command(
    "compile-discovery"
)
def compile_discovery(
    actions_path: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help=(
            "Path to discovery actions.json."
        ),
    ),
    template_path: Path = typer.Option(
        Path(
            "capabilities/"
            "lookup_savings_balance.json"
        ),
        "--template",
        help=(
            "Approved capability contract "
            "used as the compilation template."
        ),
    ),
    output_path: Path = typer.Option(
        Path(
            "capabilities/generated/"
            "lookup_savings_balance.json"
        ),
        "--output",
        help=(
            "Destination for generated artifact."
        ),
    ),
) -> None:
    """
    Compile harvested discovery targets into a
    versioned deterministic capability artifact.
    """

    recorder = ArtifactRecorder()

    artifact = (
        recorder.compile_from_file(
            template_path=(
                template_path
            ),
            actions_path=(
                actions_path
            ),
            output_path=(
                output_path
            ),
        )
    )

    typer.echo(
        "Artifact compiled successfully."
    )

    typer.echo(
        f"Output: {output_path}"
    )

    typer.echo(
        "Capability: "
        f"{artifact.capability.id}"
    )

    typer.echo(
        "Version: "
        f"{artifact.capability.version}"
    )

    typer.echo(
        "Approval state: "
        f"{artifact.capability.approval_state.value}"
    )

    typer.echo(
        "Discovery run: "
        f"{artifact.provenance.discovery_run_id}"
    )


@app.command()
def replay(
    artifact_path: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help=(
            "Capability artifact to replay."
        ),
    ),
    member_id: str = typer.Option(
        ...,
        "--member-id",
        help="Member ID input.",
    ),
    headless: bool = typer.Option(
        False,
        help=(
            "Run the browser without "
            "a visible window."
        ),
    ),
) -> None:
    """
    Replay a capability deterministically without an LLM.
    """

    load_dotenv()

    asyncio.run(
        _run_replay(
            artifact_path=(
                artifact_path
            ),
            member_id=member_id,
            headless=headless,
        )
    )


async def _run_discovery(
    goal: str,
    start_url: str,
    headless: bool,
) -> None:
    surface = PlaywrightSurface(
        headless=headless
    )

    await surface.start()

    try:
        await surface.navigate(
            start_url
        )

        agent = DiscoveryAgent(
            surface
        )

        runner = DiscoveryRunner(
            surface=surface,
            agent=agent,
            max_steps=10,
        )

        recorder = await runner.run(
            goal
        )

        typer.echo(
            "\nDiscovery completed."
        )

        typer.echo(
            "Recorded actions: "
            f"{len(recorder.actions)}"
        )

        typer.echo(
            "\nAction trace:"
        )

        for (
            index,
            action,
        ) in enumerate(
            recorder.actions,
            start=1,
        ):
            typer.echo(
                (
                    f"{index}. "
                    f"{action.action} "
                    f"ref={action.ref} "
                    f"url="
                    f"{action.observed_url}"
                )
            )

    finally:
        await surface.close()


async def _run_replay(
    artifact_path: Path,
    member_id: str,
    headless: bool,
) -> None:
    artifact = load_artifact(
        artifact_path
    )

    surface = PlaywrightSurface(
        headless=headless
    )

    await surface.start()

    try:
        engine = ReplayEngine(
            surface
        )

        result = await engine.run(
            artifact,
            {
                "member_id": (
                    member_id
                ),
            },
        )

        typer.echo(
            result.model_dump_json(
                indent=2
            )
        )

    finally:
        await surface.close()


def main() -> None:
    app()


if __name__ == "__main__":
    main()