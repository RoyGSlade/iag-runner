import json

from llm.client import _intent_messages


def test_intent_prompt_includes_required_context_fields() -> None:
    context = {
        "era": "Space",
        "available_actions": ["attack", "move"],
        "available_powers": ["sherlock.scanning_gaze"],
        "notes": "No illegal actions.",
    }
    messages = _intent_messages("attack the target", context, 1, None)
    assert messages[0]["role"] == "system"
    assert "JSON object" in messages[0]["content"]
    assert "action_type" in messages[0]["content"]
    assert "invalid" in messages[0]["content"]

    payload = json.loads(messages[1]["content"])
    assert payload["context"]["era"] == "Space"
    assert payload["context"]["available_actions"] == ["attack", "move"]
    assert payload["context"]["available_powers"] == ["sherlock.scanning_gaze"]
