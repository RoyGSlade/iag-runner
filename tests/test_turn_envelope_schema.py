import pytest
from pydantic import ValidationError

from llm.schemas import TurnEnvelope


def test_turn_envelope_parses_strict() -> None:
    payload = {
        "mode": "gm",
        "protocol_id": "session0-v1",
        "confidence": "high",
        "classification": {"primary_category": "combat"},
        "ooc_questions": ["Any limits on combat detail?"],
        "gm_plan": [
            {
                "type": "investigate",
                "actor_id": 1,
                "targets": ["dockside terminal"],
                "skill_used": "Investigation",
                "power_used": None,
                "time_cost": "action",
                "risk_level": "low",
                "notes": "Sweep for anomalies.",
            }
        ],
        "content_requests": [{"type": "npc_name", "count": 2}],
        "memory_suggestions": {"remember": ["player hates gore"]},
        "dev_report": {"notes": "ok"},
    }
    envelope = TurnEnvelope.model_validate(payload)
    assert envelope.mode == "gm"
    assert envelope.classification.primary_category == "combat"


def test_turn_envelope_rejects_extra_fields() -> None:
    payload = {
        "mode": "ooc",
        "protocol_id": "session0-v1",
        "confidence": "low",
        "classification": {"primary_category": "clarification"},
        "ooc_questions": [],
        "extra_field": True,
    }
    with pytest.raises(ValidationError):
        TurnEnvelope.model_validate(payload)


def test_turn_envelope_rejects_bad_types() -> None:
    payload = {
        "mode": "dev",
        "protocol_id": "session0-v1",
        "confidence": "medium",
        "classification": {"primary_category": "debug"},
        "ooc_questions": "not-a-list",
    }
    with pytest.raises(ValidationError):
        TurnEnvelope.model_validate(payload)


def test_turn_envelope_ooc_questions_length() -> None:
    payload = {
        "mode": "gm",
        "protocol_id": "session0-v1",
        "confidence": "medium",
        "classification": {"primary_category": "scene"},
        "ooc_questions": ["q1", "q2", "q3", "q4"],
    }
    with pytest.raises(ValidationError):
        TurnEnvelope.model_validate(payload)
