from __future__ import annotations

from cua.surface.observation import TargetSemantics
from cua.types import Effect


class EffectClassifier:
    def __init__(
        self,
        safe_click_terms: list[str],
        reversible_terms: list[str],
        irreversible_terms: list[str],
    ) -> None:
        self.safe_click_terms = [
            term.casefold()
            for term in safe_click_terms
        ]

        self.reversible_terms = [
            term.casefold()
            for term in reversible_terms
        ]

        self.irreversible_terms = [
            term.casefold()
            for term in irreversible_terms
        ]

    def classify(
        self,
        action: str,
        semantics: TargetSemantics | None,
    ) -> Effect:
        if action in {
            "navigate",
            "fill",
            "read",
        }:
            return Effect.READ_ONLY

        if action != "click":
            return Effect.IRREVERSIBLE_MUTATION

        if semantics is None:
            return Effect.REVERSIBLE_MUTATION

        combined_text = " ".join(
            value
            for value in [
                semantics.text,
                semantics.value,
                semantics.role,
            ]
            if value
        ).casefold()

        if self._contains_any(
            combined_text,
            self.irreversible_terms,
        ):
            return Effect.IRREVERSIBLE_MUTATION

        if self._contains_any(
            combined_text,
            self.reversible_terms,
        ):
            return Effect.REVERSIBLE_MUTATION

        if self._contains_any(
            combined_text,
            self.safe_click_terms,
        ):
            return Effect.READ_ONLY

        # Ordinary links are navigational unless the
        # destination itself is later rejected by the
        # allowlist.
        if semantics.href:
            return Effect.READ_ONLY

        # POSTing an unknown form is treated conservatively.
        if (
            semantics.form_method
            and semantics.form_method.casefold()
            == "post"
        ):
            return Effect.REVERSIBLE_MUTATION

        # Unknown buttons are not assumed harmless.
        if semantics.tag_name.casefold() in {
            "button",
            "input",
        }:
            return Effect.REVERSIBLE_MUTATION

        return Effect.READ_ONLY

    def _contains_any(
        self,
        text: str,
        terms: list[str],
    ) -> bool:
        return any(
            term in text
            for term in terms
        )