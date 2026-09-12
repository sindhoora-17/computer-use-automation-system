from cua.artifact.schema import CapabilityArtifact


def test_minimal_artifact_validates():
    artifact = CapabilityArtifact.model_validate(
        {
            "schema_version": "1.0",
            "capability": {
                "id": "test_capability",
                "version": "1.0.0",
                "name": "Test Capability",
                "description": "Schema validation test.",
                "approval_state": "draft",
            },
            "target": {
                "app_id": "meridian-core-admin",
                "vendor": "meridian",
                "supported_versions": ">=3.0,<4.0",
                "fingerprint": [],
            },
            "inputs": {},
            "outputs": {},
            "steps": [],
            "recoveries": [],
            "expected_outcomes": [],
            "success_condition": {
                "all_of": [],
            },
            "policy": {
                "max_steps": 10,
                "max_duration_s": 30,
                "declared_max_effect": "read_only",
            },
            "provenance": {
                "discovered_by": None,
                "discovery_run_id": None,
                "recorded_at": None,
                "reviewed_by": None,
            },
        }
    )

    assert artifact.capability.id == "test_capability"
    assert artifact.schema_version == "1.0"