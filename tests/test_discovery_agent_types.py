from cua.discovery.agent import (
    AgentDecision,
)


def test_agent_decision_validates():
    decision = (
        AgentDecision.model_validate(
            {
                "action": "fill",
                "ref": "e2",
                "value": "10001",
                "reason": (
                    "Enter the requested "
                    "member ID."
                ),
            }
        )
    )

    assert (
        decision.action
        == "fill"
    )

    assert decision.ref == "e2"