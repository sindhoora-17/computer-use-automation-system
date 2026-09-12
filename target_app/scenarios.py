from dataclasses import dataclass, fields


@dataclass
class ScenarioState:
    slow_load: bool = False
    session_expired: bool = False
    interstitial: bool = False
    validation_error: bool = False
    app_error: bool = False


SCENARIO = ScenarioState()


def reset_scenario() -> None:
    for field in fields(SCENARIO):
        setattr(
            SCENARIO,
            field.name,
            False,
        )


def set_scenario(
    name: str,
    enabled: bool,
) -> None:
    if not hasattr(
        SCENARIO,
        name,
    ):
        raise ValueError(
            f"Unknown scenario: {name}"
        )

    setattr(
        SCENARIO,
        name,
        enabled,
    )