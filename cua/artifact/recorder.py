from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cua.artifact.schema import (
    ApprovalState,
    CapabilityArtifact,
    TargetLocator,
)
from cua.artifact.store import (
    load_artifact,
    save_artifact,
)


class ArtifactCompilationError(Exception):
    pass


class ArtifactRecorder:
    """
    Compiles a successful discovery trace into a reusable
    capability artifact.

    Discovery supplies the learned UI targets.

    The existing capability contract supplies:
    - inputs
    - outputs
    - expected business outcomes
    - recovery rules
    - policy declarations
    - success conditions

    This prevents the LLM from authoring safety or business
    semantics simply because it discovered a working path.
    """

    ACTIONABLE = {
        "fill",
        "click",
        "read",
    }

    def compile_from_file(
        self,
        template_path: str | Path,
        actions_path: str | Path,
        output_path: str | Path,
    ) -> CapabilityArtifact:
        template = load_artifact(
            template_path
        )

        actions_file = Path(
            actions_path
        )

        with actions_file.open(
            "r",
            encoding="utf-8",
        ) as file:
            actions = json.load(
                file
            )

        if not isinstance(
            actions,
            list,
        ):
            raise ArtifactCompilationError(
                "Discovery actions file "
                "must contain a JSON list."
            )

        discovery_run_id = (
            actions_file.parent.name
        )

        artifact = self.compile(
            template=template,
            actions=actions,
            discovery_run_id=(
                discovery_run_id
            ),
        )

        save_artifact(
            artifact,
            output_path,
        )

        return artifact

    def compile(
        self,
        template: CapabilityArtifact,
        actions: list[
            dict[str, Any]
        ],
        discovery_run_id: str,
    ) -> CapabilityArtifact:
        artifact = deepcopy(
            template
        )

        discovered_actions = [
            action
            for action in actions
            if action.get("action")
            in self.ACTIONABLE
        ]

        artifact_steps = [
            step
            for step in artifact.steps
            if step.action
            in self.ACTIONABLE
        ]

        if (
            len(discovered_actions)
            != len(artifact_steps)
        ):
            raise ArtifactCompilationError(
                "Discovery action count does "
                "not match capability contract: "
                f"{len(discovered_actions)} "
                "discovered vs "
                f"{len(artifact_steps)} expected."
            )

        for (
            step,
            discovered,
        ) in zip(
            artifact_steps,
            discovered_actions,
            strict=True,
        ):
            discovered_action = (
                discovered.get(
                    "action"
                )
            )

            if (
                discovered_action
                != step.action
            ):
                raise ArtifactCompilationError(
                    "Discovery action sequence "
                    "does not match contract. "
                    f"Step '{step.id}' expects "
                    f"'{step.action}' but "
                    "discovery recorded "
                    f"'{discovered_action}'."
                )

            target_data = (
                discovered.get(
                    "target"
                )
            )

            if target_data is None:
                raise ArtifactCompilationError(
                    "Discovery action "
                    f"'{discovered_action}' "
                    "does not contain a "
                    "harvested target."
                )

            step.target = (
                TargetLocator.model_validate(
                    target_data
                )
            )

        artifact.capability.approval_state = (
            ApprovalState.DRAFT
        )

        artifact.provenance.discovered_by = (
            "llm_discovery"
        )

        artifact.provenance.discovery_run_id = (
            discovery_run_id
        )

        artifact.provenance.recorded_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        artifact.provenance.reviewed_by = None

        return artifact