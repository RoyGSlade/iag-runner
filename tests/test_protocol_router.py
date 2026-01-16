import pytest

from gm_os.protocols import ProtocolId
from gm_os.router import route_envelope
from llm.schemas import TurnEnvelope


def test_ooc_mode_freezes_and_no_execute() -> None:
    envelope = TurnEnvelope.model_validate(
        {
            "mode": "ooc",
            "protocol_id": ProtocolId.PROTO_ROUTINE.value,
            "confidence": "high",
            "classification": {"primary_category": "meta"},
            "ooc_questions": ["Confirm intent?"],
        }
    )
    decision = route_envelope(envelope, {})
    assert decision.freeze_time is True
    assert decision.execute is False


def test_invalid_protocol_id_dev_mode() -> None:
    envelope = TurnEnvelope.model_validate(
        {
            "mode": "gm",
            "protocol_id": "PROTO_UNKNOWN",
            "confidence": "medium",
            "classification": {"primary_category": "meta"},
            "ooc_questions": [],
        }
    )
    decision = route_envelope(envelope, {"settings": {"dev_mode": True}})
    assert decision.execute is False
    assert decision.dev_report is not None


def test_invalid_protocol_id_non_dev_routes_to_clarification() -> None:
    envelope = TurnEnvelope.model_validate(
        {
            "mode": "gm",
            "protocol_id": "PROTO_UNKNOWN",
            "confidence": "medium",
            "classification": {"primary_category": "meta"},
            "ooc_questions": [],
        }
    )
    decision = route_envelope(envelope, {"settings": {"dev_mode": False}})
    assert decision.execute is False
    assert decision.protocol_id == ProtocolId.PROTO_CLARIFICATION


def test_low_confidence_non_safe_routes_to_clarification() -> None:
    envelope = TurnEnvelope.model_validate(
        {
            "mode": "gm",
            "protocol_id": ProtocolId.PROTO_INVENTION.value,
            "confidence": "low",
            "classification": {"primary_category": "scene"},
            "ooc_questions": [],
        }
    )
    decision = route_envelope(envelope, {})
    assert decision.execute is False
    assert decision.protocol_id == ProtocolId.PROTO_CLARIFICATION


def test_safe_protocol_executes() -> None:
    envelope = TurnEnvelope.model_validate(
        {
            "mode": "gm",
            "protocol_id": ProtocolId.PROTO_EXPLORATION.value,
            "confidence": "low",
            "classification": {"primary_category": "scene"},
            "ooc_questions": [],
        }
    )
    decision = route_envelope(envelope, {})
    assert decision.execute is True
    assert decision.freeze_time is False
