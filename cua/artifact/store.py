import json
from pathlib import Path

from cua.artifact.schema import CapabilityArtifact


def load_artifact(path: str | Path) -> CapabilityArtifact:
    path = Path(path)

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return CapabilityArtifact.model_validate(data)


def save_artifact(
    artifact: CapabilityArtifact,
    path: str | Path,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            artifact.model_dump(mode="json"),
            file,
            indent=2,
        )