import pytest
from pydantic import ValidationError

from llm.schemas import ContentRequest


def test_content_request_parses_strict() -> None:
    payload = {
        "kind": "npc",
        "purpose": "plot",
        "era": "Space",
        "tags": ["dock", "mysterious"],
        "difficulty": "medium",
        "constraints": {"faction": "Port Authority"},
        "reason": "Need a contact to move the story forward.",
    }
    request = ContentRequest.model_validate(payload)
    assert request.kind == "npc"
    assert request.constraints["faction"] == "Port Authority"


def test_content_request_rejects_extra_fields() -> None:
    payload = {
        "kind": "item",
        "purpose": "reward",
        "constraints": {},
        "reason": "Player requested loot.",
        "extra": True,
    }
    with pytest.raises(ValidationError):
        ContentRequest.model_validate(payload)


def test_content_request_rejects_bad_types() -> None:
    payload = {
        "kind": "monster",
        "purpose": "challenge",
        "constraints": "not-a-dict",
        "reason": "Need a threat.",
    }
    with pytest.raises(ValidationError):
        ContentRequest.model_validate(payload)
