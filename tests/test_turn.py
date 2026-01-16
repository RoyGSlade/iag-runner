from types import SimpleNamespace

from gm_os.protocols import ProtocolId
from llm.schemas import Intent, TurnEnvelope
from rules.turn import execute_turn_for_state


class StubLlmClient:
    def generate_turn_envelope(self, player_text, context):
        return TurnEnvelope.model_validate(
            {
                "mode": "gm",
                "protocol_id": ProtocolId.PROTO_ROUTINE.value,
                "confidence": "high",
                "classification": {"primary_category": "scene"},
                "ooc_questions": [],
            }
        )

    def extract_intent(self, player_text, context):
        return Intent(action_type="attack", targets=[])

    def generate_narration(self, narration_request):
        return "Stub narration."


class FailingLlmClient:
    def generate_turn_envelope(self, player_text, context):
        raise ValueError("Invalid JSON from LLM")

    def extract_intent(self, player_text, context):
        raise ValueError("Invalid JSON from LLM")

    def generate_narration(self, narration_request):
        return "Should not be called."


class TrackingNarrationClient(StubLlmClient):
    def __init__(self):
        self.narration_calls = []

    def generate_narration(self, narration_request):
        self.narration_calls.append(narration_request)
        return "LLM narration."


def test_stubbed_intent_deterministic_rolls_and_updates() -> None:
    session_a = SimpleNamespace(
        rng_seed=123,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "roll_index": 0,
            "scene_text": "Test scene.",
        },
    )
    session_b = SimpleNamespace(
        rng_seed=123,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "roll_index": 0,
            "scene_text": "Test scene.",
        },
    )
    character_a = SimpleNamespace(attributes_json={})
    character_b = SimpleNamespace(attributes_json={})

    intent = Intent(action_type="attack", targets=[])
    result_a = execute_turn_for_state(
        session_a,
        character_a,
        "attack",
        llm_client=StubLlmClient(),
        intent_override=intent,
    )
    result_b = execute_turn_for_state(
        session_b,
        character_b,
        "attack",
        llm_client=StubLlmClient(),
        intent_override=intent,
    )

    assert result_a.rolls == result_b.rolls
    assert result_a.outcome == result_b.outcome
    assert result_a.state_diff["character"]["resources"]["actions"] == 0
    assert result_b.state_diff["character"]["resources"]["actions"] == 0


def test_golden_turn_sequence_with_seed() -> None:
    session = SimpleNamespace(
        rng_seed=2,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "roll_index": 0,
            "scene_text": "Test scene.",
        },
    )
    character = SimpleNamespace(attributes_json={}, statuses_json={})
    intent = Intent(action_type="attack", targets=[])

    result = execute_turn_for_state(
        session,
        character,
        "attack",
        llm_client=StubLlmClient(),
        intent_override=intent,
    )

    assert result.outcome["attack_roll"] == 20
    assert result.outcome["attack_total"] == 20
    assert result.outcome["target_ar"] == 12
    assert result.outcome["hit"] is True
    assert result.outcome["damage"] == 6
    assert result.rolls[0]["formula"] == "1d20"
    assert result.rolls[0]["result"] == 20
    assert result.rolls[1]["formula"] == "1d6"
    assert result.rolls[1]["result"] == 6


def test_explore_intent_produces_narration_and_outcome() -> None:
    session = SimpleNamespace(
        rng_seed=15,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "roll_index": 0,
            "scene_text": "Test scene.",
        },
    )
    character = SimpleNamespace(attributes_json={})
    intent = Intent(action_type="explore", targets=[])

    result = execute_turn_for_state(
        session,
        character,
        "explore",
        llm_client=StubLlmClient(),
        intent_override=intent,
    )

    assert result.outcome["explore"] is True
    assert result.narration == "Stub narration."


def test_attack_without_target_defaults_to_nearest_threat() -> None:
    session = SimpleNamespace(
        rng_seed=21,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "roll_index": 0,
            "scene_text": "Test scene.",
        },
    )
    character = SimpleNamespace(attributes_json={})
    intent = Intent(action_type="attack", targets=[])

    result = execute_turn_for_state(
        session,
        character,
        "attack",
        llm_client=StubLlmClient(),
        intent_override=intent,
    )

    assert result.outcome["target"] == "nearest_threat"


def test_llm_invalid_json_returns_clarification_and_no_state_change() -> None:
    session = SimpleNamespace(
        rng_seed=7,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "roll_index": 0,
            "scene_text": "Test scene.",
            "current_scene": {
                "scene_id": "test_entrance",
                "location_id": "test",
                "summary": "Test scene.",
                "active_threats": [],
                "npcs_present": [],
                "open_hooks": [],
                "established": True,
            },
        },
    )
    character = SimpleNamespace(attributes_json={"resources": {"actions": 1}})
    original_attributes = dict(character.attributes_json)
    original_metadata = dict(session.metadata_json)

    result = execute_turn_for_state(
        session,
        character,
        "attack",
        llm_client=FailingLlmClient(),
    )

    assert result.outcome["clarify"] is True
    assert result.needs_clarification is True
    assert result.narration
    assert result.suggested_actions
    assert result.state_diff == {}
    assert character.attributes_json == original_attributes
    assert session.metadata_json == original_metadata


def test_illegal_action_intent_returns_clarification_and_no_state_change() -> None:
    session = SimpleNamespace(
        rng_seed=5,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "roll_index": 0,
            "scene_text": "Test scene.",
        },
    )
    character = SimpleNamespace(attributes_json={"resources": {"actions": 1}})
    original_attributes = dict(character.attributes_json)

    intent = Intent(action_type="invalid", targets=[], reason="Illegal action")
    result = execute_turn_for_state(
        session,
        character,
        "illegal",
        llm_client=StubLlmClient(),
        intent_override=intent,
    )

    assert result.outcome["clarify"] is True
    assert "Illegal action" in result.outcome["message"]
    assert result.needs_clarification is True
    assert result.narration
    assert result.suggested_actions
    assert result.state_diff == {}
    assert character.attributes_json == original_attributes


def test_ask_clarifying_question_returns_suggestions_and_no_state_change() -> None:
    session = SimpleNamespace(
        rng_seed=9,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "roll_index": 0,
            "scene_text": "Test scene.",
        },
    )
    character = SimpleNamespace(attributes_json={"resources": {"actions": 1}})
    original_attributes = dict(character.attributes_json)

    intent = Intent(
        action_type="ask_clarifying_question",
        targets=[],
        dialogue="Clarify your intent.",
    )
    result = execute_turn_for_state(
        session,
        character,
        "",
        llm_client=StubLlmClient(),
        intent_override=intent,
    )

    assert result.needs_clarification is True
    assert result.narration
    assert result.suggested_actions
    assert result.state_diff == {}
    assert character.attributes_json == original_attributes


def test_missing_required_fields_fallbacks_to_clarification() -> None:
    session = SimpleNamespace(
        rng_seed=11,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "roll_index": 0,
            "scene_text": "Test scene.",
        },
    )
    character = SimpleNamespace(attributes_json={"resources": {"actions": 1}})
    original_attributes = dict(character.attributes_json)

    result = execute_turn_for_state(
        session,
        character,
        "",
        llm_client=FailingLlmClient(),
    )

    assert result.outcome["clarify"] is True
    assert result.needs_clarification is True
    assert result.narration
    assert result.suggested_actions
    assert result.state_diff == {}
    assert character.attributes_json == original_attributes


def test_vague_input_routes_to_questions_without_state_change() -> None:
    session = SimpleNamespace(
        rng_seed=13,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "roll_index": 0,
            "scene_text": "Test scene.",
        },
    )
    character = SimpleNamespace(
        attributes_json={
            "derived": {"hp": 5, "ap": 2},
            "resources": {"actions": 1},
        }
    )
    character.gear_pack_json = {"credits": 120}
    original_attributes = dict(character.attributes_json)
    original_gear = dict(character.gear_pack_json)

    class OocEnvelopeClient(StubLlmClient):
        def generate_turn_envelope(self, player_text, context):
            return TurnEnvelope.model_validate(
                {
                    "mode": "ooc",
                    "protocol_id": ProtocolId.PROTO_CLARIFICATION.value,
                    "confidence": "low",
                    "classification": {"primary_category": "clarification"},
                    "ooc_questions": ["What should I focus on?"],
                }
            )

    result = execute_turn_for_state(
        session,
        character,
        "uh...",
        llm_client=OocEnvelopeClient(),
    )

    assert result.needs_clarification is True
    assert result.clarification_questions == ["What should I focus on?"]
    assert result.state_diff == {}
    assert character.attributes_json == original_attributes
    assert character.gear_pack_json == original_gear


def test_build_request_creates_project_and_questions() -> None:
    session = SimpleNamespace(
        id=12,
        rng_seed=17,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "roll_index": 0,
            "scene_text": "Test scene.",
        },
    )
    character = SimpleNamespace(
        id=34,
        attributes_json={
            "derived": {"hp": 9, "ap": 3},
            "resources": {"actions": 1},
        },
        gear_pack_json={"credits": 80},
    )
    original_attributes = dict(character.attributes_json)
    original_gear = dict(character.gear_pack_json)

    class CraftEnvelopeClient(StubLlmClient):
        def generate_turn_envelope(self, player_text, context):
            return TurnEnvelope.model_validate(
                {
                    "mode": "gm",
                    "protocol_id": ProtocolId.PROTO_INVENTION.value,
                    "confidence": "medium",
                    "classification": {"primary_category": "craft"},
                    "ooc_questions": [],
                    "gm_plan": [
                        {
                            "type": "craft",
                            "actor_id": 34,
                            "targets": ["glider"],
                            "skill_used": None,
                            "power_used": None,
                            "time_cost": "hours",
                            "risk_level": "med",
                            "notes": "Build a glider.",
                            "complexity": 2,
                        }
                    ],
                }
            )

    def project_creator(payload):
        return {
            "id": 1,
            "name": payload["name"],
            "type": payload["type"],
            "work_units_total": payload["work_units_total"],
            "work_units_done": 0,
            "status": "active",
        }

    result = execute_turn_for_state(
        session,
        character,
        "build a glider",
        llm_client=CraftEnvelopeClient(),
        project_creator=project_creator,
    )

    assert result.project_created is not None
    assert result.project_created["name"] == "glider"
    assert result.needs_clarification is True
    assert result.clarification_questions
    assert result.state_diff == {}
    assert character.attributes_json == original_attributes
    assert character.gear_pack_json == original_gear


def test_integration_turn_updates_state_and_log(monkeypatch) -> None:
    session = SimpleNamespace(
        id=99,
        rng_seed=3,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "roll_index": 0,
            "scene_text": "Test scene.",
        },
    )
    character = SimpleNamespace(
        id=10,
        session_id=99,
        attributes_json={"resources": {"actions": 1}},
        statuses_json={},
    )

    class StubClient:
        def generate_turn_envelope(self, player_text, context):
            return TurnEnvelope.model_validate(
                {
                    "mode": "gm",
                    "protocol_id": ProtocolId.PROTO_ROUTINE.value,
                    "confidence": "high",
                    "classification": {"primary_category": "combat"},
                    "ooc_questions": [],
                }
            )

        def extract_intent(self, player_text, context):
            return Intent(action_type="attack", targets=[])

        def generate_narration(self, narration_request):
            return "Stub narrative."

    result = execute_turn_for_state(
        session,
        character,
        "attack",
        llm_client=StubClient(),
    )

    assert result.state_diff["character"]["resources"]["actions"] == 0
    assert isinstance(session.metadata_json.get("turn_log"), list)
    assert session.metadata_json.get("turn_index") == 1


def test_retcon_dispute_returns_ooc_summary_and_options() -> None:
    session = SimpleNamespace(
        rng_seed=23,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "roll_index": 0,
            "scene_text": "Test scene.",
            "turn_index": 3,
            "turn_log": [
                {"action": "explore", "power": None, "item": None, "outcome": {}},
                {"action": "attack", "power": None, "item": None, "outcome": {"hit": True}},
                {"action": "attack", "power": None, "item": None, "outcome": {"hit": False}},
            ],
            "rolling_summary": "action=explore action=attack hit=True",
        },
    )
    character = SimpleNamespace(attributes_json={})

    class RetconEnvelopeClient(StubLlmClient):
        def generate_turn_envelope(self, player_text, context):
            return TurnEnvelope.model_validate(
                {
                    "mode": "gm",
                    "protocol_id": ProtocolId.PROTO_RETCON_DISPUTE.value,
                    "confidence": "medium",
                    "classification": {"primary_category": "dispute"},
                    "ooc_questions": [],
                }
            )

    result = execute_turn_for_state(
        session,
        character,
        "That didn't happen.",
        llm_client=RetconEnvelopeClient(),
    )

    assert result.needs_clarification is True
    assert result.state_diff == {}
    assert result.suggested_actions
    assert "Turn 2" in result.narration
    assert "Rolling summary" in result.narration


def test_scene_intro_uses_llm_narration_for_opening() -> None:
    session = SimpleNamespace(
        rng_seed=31,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "roll_index": 0,
        },
    )
    character = SimpleNamespace(attributes_json={})
    llm_client = TrackingNarrationClient()

    result = execute_turn_for_state(
        session,
        character,
        "",
        llm_client=llm_client,
    )

    assert llm_client.narration_calls
    assert "LLM narration." in result.narration
    assert session.metadata_json.get("scene_text") == "LLM narration."


def test_memory_recall_records_gm_notes() -> None:
    session = SimpleNamespace(
        rng_seed=41,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "roll_index": 0,
            "session_setup": {
                "starting_situation": {
                    "hook": "Recover the lost data shard.",
                    "npcs": ["Dr. Vance"],
                }
            },
        },
    )
    character = SimpleNamespace(attributes_json={})
    llm_client = TrackingNarrationClient()

    result = execute_turn_for_state(
        session,
        character,
        "What do I know?",
        llm_client=llm_client,
    )

    notes = session.metadata_json.get("gm_memory_notes")
    assert result.outcome["memory_recall"] is True
    assert isinstance(notes, list)
    assert notes
    assert notes[0]["verification_questions"] is not None
