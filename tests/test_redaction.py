from cua.policy.redaction import (
    Redactor,
)


def test_redacts_member_id():
    redactor = Redactor()

    value = (
        "Member 10001 was opened."
    )

    assert (
        redactor.redact_text(
            value
        )
        == (
            "Member [REDACTED] "
            "was opened."
        )
    )


def test_redacts_currency():
    redactor = Redactor()

    value = (
        "Savings balance is "
        "$1,842.17."
    )

    assert (
        redactor.redact_text(
            value
        )
        == (
            "Savings balance is "
            "[REDACTED]."
        )
    )


def test_redacts_nested_payload():
    redactor = Redactor()

    payload = {
        "url": (
            "http://127.0.0.1:5000/"
            "content/member/10001"
        ),
        "result": "$1842.17",
        "nested": {
            "member_id": "10001",
        },
    }

    result = (
        redactor.redact_value(
            payload
        )
    )

    assert result[
        "url"
    ].endswith(
        "/[REDACTED]"
    )

    assert (
        result["result"]
        == "[REDACTED]"
    )

    assert (
        result["nested"][
            "member_id"
        ]
        == "[REDACTED]"
    )

def test_redacts_structured_name_everywhere():
    redactor = Redactor()

    payload = {
        "visible_text": (
            "Member Number\t10001\t"
            "Name\tElena Ramirez"
        ),
        "elements": [
            {
                "text": "Elena Ramirez",
                "nearby_text": (
                    "Name\tElena Ramirez"
                ),
            }
        ],
    }

    result = (
        redactor.redact_discovery_payload(
            payload
        )
    )

    assert (
        "Elena Ramirez"
        not in str(result)
    )

    assert (
        "[REDACTED]"
        in str(result)
    )

def test_redacts_names_from_table_columns():
    redactor = Redactor()

    payload = {
        "elements": [
            {
                "text": "Last Name",
                "nearby_text": (
                    "Member Number\t"
                    "Last Name\t"
                    "First Name\t"
                    "Status"
                ),
            },
            {
                "text": "Ramirez",
                "nearby_text": (
                    "10001\t"
                    "Ramirez\t"
                    "Elena\t"
                    "Active"
                ),
            },
            {
                "text": "Elena",
                "nearby_text": (
                    "10001\t"
                    "Ramirez\t"
                    "Elena\t"
                    "Active"
                ),
            },
            {
                "text": "Active",
            },
        ]
    }

    result = (
        redactor.redact_discovery_payload(
            payload
        )
    )

    serialized = str(result)

    assert "Ramirez" not in serialized
    assert "Elena" not in serialized

    assert (
        result["elements"][1]["text"]
        == "[REDACTED]"
    )

    assert (
        result["elements"][2]["text"]
        == "[REDACTED]"
    )

    assert (
        result["elements"][3]["text"]
        == "Active"
    )