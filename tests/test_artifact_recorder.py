from cua.artifact.recorder import (
    ArtifactRecorder,
)
from cua.artifact.store import (
    load_artifact,
)


def test_compiles_discovery_into_artifact(
    tmp_path,
):
    template = load_artifact(
        "capabilities/"
        "lookup_savings_balance.json"
    )

    actions = [
        {
            "action": "fill",
            "ref": "e3",
            "value": "10001",
            "reason": "Enter member ID.",
            "observed_url": (
                "http://127.0.0.1:5000/"
                "content/search"
            ),
            "result": None,
            "target": {
                "strategies": [
                    {
                        "kind":
                            "anchor_relative",
                        "rank": 1,
                        "anchor_text": (
                            "Member Number "
                            "/ Last Name"
                        ),
                        "relationship":
                            "following_input",
                    },
                    {
                        "kind": "xpath",
                        "rank": 2,
                        "value": (
                            "//input"
                            "[@name='member_query']"
                        ),
                    },
                ]
            },
        },
        {
            "action": "click",
            "ref": "e4",
            "value": None,
            "reason": "Search.",
            "observed_url": (
                "http://127.0.0.1:5000/"
                "content/search"
            ),
            "result": None,
            "target": {
                "strategies": [
                    {
                        "kind": "role_name",
                        "rank": 1,
                        "role": "button",
                        "name": "Search",
                    }
                ]
            },
        },
        {
            "action": "click",
            "ref": "e10",
            "value": None,
            "reason": "Open member.",
            "observed_url": (
                "http://127.0.0.1:5000/"
                "content/search"
            ),
            "result": None,
            "target": {
                "strategies": [
                    {
                        "kind": "xpath",
                        "rank": 1,
                        "value": (
                            "//a[contains("
                            "@href, "
                            "'/content/member/'"
                            ")]"
                        ),
                    }
                ]
            },
        },
        {
            "action": "read",
            "ref": "e13",
            "value": None,
            "reason": "Read balance.",
            "observed_url": (
                "http://127.0.0.1:5000/"
                "content/member/10001"
            ),
            "result": "$1842.17",
            "target": {
                "strategies": [
                    {
                        "kind": "table_cell",
                        "rank": 1,
                        "row_anchor":
                            "Savings",
                        "column_header":
                            "Current Balance",
                    }
                ]
            },
        },
        {
            "action": "complete",
            "ref": None,
            "value": None,
            "reason": "Done.",
            "observed_url": (
                "http://127.0.0.1:5000/"
                "content/member/10001"
            ),
            "result": None,
            "target": None,
        },
    ]

    recorder = ArtifactRecorder()

    artifact = recorder.compile(
        template=template,
        actions=actions,
        discovery_run_id=(
            "discovery_test123"
        ),
    )

    assert (
        artifact.capability
        .approval_state.value
        == "draft"
    )

    assert (
        artifact.provenance
        .discovery_run_id
        == "discovery_test123"
    )

    fill_step = next(
        step
        for step in artifact.steps
        if step.id
        == "enter_member_id"
    )

    assert (
        fill_step.target
        is not None
    )

    assert (
        fill_step
        .target
        .strategies[0]
        .kind
        == "anchor_relative"
    )

    read_step = next(
        step
        for step in artifact.steps
        if step.id
        == "read_balance"
    )

    assert (
        read_step.target
        is not None
    )

    assert (
        read_step
        .target
        .strategies[0]
        .kind
        == "table_cell"
    )

    assert (
        read_step
        .target
        .strategies[0]
        .row_anchor
        == "Savings"
    )


def test_compile_preserves_input_binding():
    template = load_artifact(
        "capabilities/"
        "lookup_savings_balance.json"
    )

    actions = [
        {
            "action": "fill",
            "target": {
                "strategies": [
                    {
                        "kind": "xpath",
                        "rank": 1,
                        "value": (
                            "//input"
                            "[@name='member_query']"
                        ),
                    }
                ]
            },
        },
        {
            "action": "click",
            "target": {
                "strategies": [
                    {
                        "kind": "role_name",
                        "rank": 1,
                        "role": "button",
                        "name": "Search",
                    }
                ]
            },
        },
        {
            "action": "click",
            "target": {
                "strategies": [
                    {
                        "kind": "xpath",
                        "rank": 1,
                        "value": (
                            "//a[contains("
                            "@href, "
                            "'/content/member/'"
                            ")]"
                        ),
                    }
                ]
            },
        },
        {
            "action": "read",
            "target": {
                "strategies": [
                    {
                        "kind": "table_cell",
                        "rank": 1,
                        "row_anchor":
                            "Savings",
                        "column_header":
                            "Current Balance",
                    }
                ]
            },
        },
    ]

    recorder = ArtifactRecorder()

    artifact = recorder.compile(
        template=template,
        actions=actions,
        discovery_run_id=(
            "discovery_test456"
        ),
    )

    fill_step = next(
        step
        for step in artifact.steps
        if step.id
        == "enter_member_id"
    )

    assert (
        fill_step.value
        is not None
    )

    assert (
        fill_step.value.source
        == "input"
    )

    assert (
        fill_step.value.key
        == "member_id"
    )