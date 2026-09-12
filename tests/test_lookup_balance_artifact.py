from pathlib import Path

from cua.artifact.store import load_artifact


def test_lookup_savings_balance_artifact_validates():
    artifact_path = Path("capabilities/lookup_savings_balance.json")

    artifact = load_artifact(artifact_path)

    assert artifact.capability.id == "lookup_savings_balance"
    assert artifact.capability.version == "1.0.0"
    assert artifact.inputs["member_id"].pattern == "^[0-9]{5}$"
    assert len(artifact.steps) == 5
    assert len(artifact.expected_outcomes) == 3