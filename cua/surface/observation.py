from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TargetSemantics:
    tag_name: str
    text: str

    role: str | None = None
    input_type: str | None = None

    value: str | None = None
    accessible_name: str | None = None
    nearby_text: str | None = None

    href: str | None = None

    form_method: str | None = None
    form_action: str | None = None


@dataclass
class ObservedElement:
    ref: str
    tag_name: str
    role: str | None

    accessible_name: str
    text: str
    current_value: str

    input_type: str | None
    nearby_text: str

    readable: bool = False