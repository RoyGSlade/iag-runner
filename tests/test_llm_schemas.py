import pytest
from pydantic import ValidationError

from llm.schemas import Intent, LLMError, NarrationRequest


def test_intent_parses_strict() -> None:
    intent = Intent(
        action_type="attack",
        targets=[{"id": 1, "name": "Goblin", "type": "enemy"}],
        skill_used="Melee",
        movement={"mode": "run", "distance": 10},
    )
    assert intent.action_type == "attack"
    assert intent.targets[0].id == 1


def test_intent_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Intent(action_type="attack", extra_field=True)


def test_narration_request_requires_jsonable_state() -> None:
    request = NarrationRequest(
        state_summary={"era": "Space", "turn": 1, "flags": ["alert"]},
        outcome={"hit": True, "damage": 3},
        tone="gritty",
    )
    assert request.outcome["damage"] == 3


def test_llm_error_rejects_wrong_types() -> None:
    with pytest.raises(ValidationError):
        LLMError(code=404, message="Missing")
