from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cua.artifact.schema import Step
from cua.policy.allowlist import (
    Allowlist,
    AllowlistViolation,
)
from cua.policy.effects import EffectClassifier
from cua.surface.base import Surface
from cua.types import Effect


class PolicyViolation(Exception):
    pass


@dataclass
class PolicyDecision:
    allowed: bool
    classified_effect: Effect
    reason: str


class PolicyEngine:
    def __init__(
        self,
        surface: Surface,
        config_path: str | Path = (
            "config/policy.yaml"
        ),
    ) -> None:
        self.surface = surface

        self.allowlist = Allowlist(
            config_path
        )

        self.classifier = EffectClassifier(
            safe_click_terms=(
                self.allowlist.safe_click_terms
            ),
            reversible_terms=(
                self.allowlist.reversible_terms
            ),
            irreversible_terms=(
                self.allowlist.irreversible_terms
            ),
        )

    async def authorize(
        self,
        step: Step,
        resolved_value: str | None = None,
    ) -> PolicyDecision:
        try:
            self.allowlist.require_action_allowed(
                step.action
            )

            if step.action == "navigate":
                if resolved_value is None:
                    raise PolicyViolation(
                        "Navigate action has no URL."
                    )

                self.allowlist.require_url_allowed(
                    resolved_value
                )

                actual_effect = (
                    Effect.READ_ONLY
                )

            else:
                semantics = None

                if step.target is not None:
                    semantics = (
                        await self.surface
                        .inspect_target(
                            step.target,
                            frame=step.frame,
                        )
                    )

                actual_effect = (
                    self.classifier.classify(
                        step.action,
                        semantics,
                    )
                )

                if (
                    semantics is not None
                    and semantics.href
                ):
                    current_url = (
                        await self.surface
                        .current_url()
                    )

                    self.allowlist.require_url_allowed(
                        semantics.href,
                        base_url=current_url,
                    )

            if actual_effect != step.effect:
                raise PolicyViolation(
                    "Artifact effect declaration "
                    f"'{step.effect.value}' does not "
                    "match independently classified "
                    f"effect '{actual_effect.value}'."
                )

            return PolicyDecision(
                allowed=True,
                classified_effect=actual_effect,
                reason="Policy checks passed.",
            )

        except (
            AllowlistViolation,
            PolicyViolation,
        ) as exc:
            raise PolicyViolation(
                str(exc)
            ) from exc