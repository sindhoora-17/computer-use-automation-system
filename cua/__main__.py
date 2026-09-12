from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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
from cua.escalation.operator_app import (
    OperatorServer,
)
from cua.escalation.session import (
    HandoffSession,
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
    allow_draft: bool = typer.Option(
        False,
        "--allow-draft",
        help=(
            "Allow replay of a draft capability "
            "for local development/testing."
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
            allow_draft=allow_draft,
        )
    )


@app.command(
    "handoff-demo"
)
def handoff_demo(
    artifact_path: Path = typer.Option(
        Path(
            "capabilities/generated/"
            "lookup_savings_balance.json"
        ),
        "--artifact",
        exists=True,
        readable=True,
        help=(
            "Capability artifact used "
            "for the handoff demo."
        ),
    ),
    member_id: str = typer.Option(
        "10001",
        "--member-id",
        help="Member ID used in demo.",
    ),
) -> None:
    """
    Demonstrate same-session human handoff and resume.
    """

    load_dotenv()

    asyncio.run(
        _run_handoff_demo(
            artifact_path=artifact_path,
            member_id=member_id,
        )
    )


@app.command(
    "failure-demo"
)
def failure_demo(
    artifact_path: Path = typer.Option(
        Path(
            "capabilities/generated/"
            "lookup_savings_balance.json"
        ),
        "--artifact",
        exists=True,
        readable=True,
        help=(
            "Capability artifact used "
            "for the hard-failure demo."
        ),
    ),
    member_id: str = typer.Option(
        "10001",
        "--member-id",
        help="Member ID used in demo.",
    ),
) -> None:
    """
    Demonstrate structured hard failure and evidence capture.
    """

    load_dotenv()

    asyncio.run(
        _run_failure_demo(
            artifact_path=artifact_path,
            member_id=member_id,
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
    allow_draft: bool,
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
            surface,
            allow_draft=allow_draft,
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


async def _run_handoff_demo(
    artifact_path: Path,
    member_id: str,
) -> None:
    artifact = load_artifact(
        artifact_path
    )

    _set_scenario(
        "interstitial",
        True,
    )

    surface = PlaywrightSurface(
        headless=False
    )

    await surface.start()

    handoff = HandoffSession(
        surface=surface
    )

    operator = OperatorServer(
        session=handoff,
        port=8765,
    )

    await operator.start()

    typer.echo(
        "\nHuman handoff demo started."
    )

    typer.echo(
        "Live browser will pause on "
        "the manual review screen."
    )

    typer.echo(
        "Operator console:"
    )

    typer.echo(
        operator.url
    )

    typer.echo(
        "\nWhen the browser shows "
        "'Manual Review Required':"
    )

    typer.echo(
        "1. Click 'Continue to Member' "
        "in the live browser."
    )

    typer.echo(
        "2. Open the operator console."
    )

    typer.echo(
        "3. Click 'Resume Automation'."
    )

    try:
        engine = ReplayEngine(
            surface=surface,
            handoff_session=handoff,
            allow_draft=True,
        )

        result = await engine.run(
            artifact,
            {
                "member_id": member_id,
            },
        )

        typer.echo(
            "\nReplay result:"
        )

        typer.echo(
            result.model_dump_json(
                indent=2
            )
        )

    finally:
        await operator.stop()
        await surface.close()

        _set_scenario(
            "interstitial",
            False,
        )


async def _run_failure_demo(
    artifact_path: Path,
    member_id: str,
) -> None:
    artifact = load_artifact(
        artifact_path
    )

    _set_scenario(
        "app_error",
        True,
    )

    surface = PlaywrightSurface(
        headless=False
    )

    await surface.start()

    typer.echo(
        "\nHard-failure demo started."
    )

    typer.echo(
        "The target app will return "
        "an unexpected application error."
    )

    try:
        engine = ReplayEngine(
            surface,
            allow_draft=True,
        )

        result = await engine.run(
            artifact,
            {
                "member_id": member_id,
            },
        )

        typer.echo(
            "\nReplay result:"
        )

        typer.echo(
            result.model_dump_json(
                indent=2
            )
        )

    finally:
        await surface.close()

        _set_scenario(
            "app_error",
            False,
        )


def _set_scenario(
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
        if response.status != 200:
            raise RuntimeError(
                "Unable to configure "
                "target-app scenario."
            )


def main() -> None:
    app()


if __name__ == "__main__":
    main()