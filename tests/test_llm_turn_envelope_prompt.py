import json

from llm.client import _turn_envelope_messages
from gm_os.protocols import ProtocolId


def test_turn_envelope_prompt_includes_required_context_fields() -> None:
    context = {
        "era": "Space",
        "scene_summary": "Dockside arrivals under neon rain.",
        "dev_mode_enabled": True,
    }
    messages = _turn_envelope_messages("look around", context, 1, None)
    assert messages[0]["role"] == "system"
    assert "TurnEnvelope" in messages[0]["content"]
    assert "protocol_id" in messages[0]["content"]
    assert "dev_report" in messages[0]["content"]
    assert "council" in messages[0]["content"]
    assert "confidence is low" in messages[0]["content"]
    assert "dev_mode_enabled" in messages[0]["content"]

    payload = json.loads(messages[1]["content"])
    assert payload["context"]["era"] == "Space"
    assert payload["context"]["scene_summary"] == "Dockside arrivals under neon rain."
    assert payload["context"]["dev_mode_enabled"] is True
    assert payload["context"]["protocols"] == [proto.value for proto in ProtocolId]
