from __future__ import annotations

from dataclasses import dataclass

from gm_os.protocols import PROTOCOL_REGISTRY, ProtocolId
from llm.schemas import TurnEnvelope


@dataclass(frozen=True)
class RoutedDecision:
    protocol_id: ProtocolId
    freeze_time: bool
    execute: bool
    reason: str | None = None
    dev_report: dict | None = None
    ooc_questions: list[str] | None = None


SAFE_PROTOCOLS: set[ProtocolId] = {
    ProtocolId.PROTO_CLARIFICATION,
    ProtocolId.PROTO_ROUTINE,
    ProtocolId.PROTO_EXPLORATION,
    ProtocolId.PROTO_DOWNTIME,
    ProtocolId.PROTO_CONTENT_GAP,
    ProtocolId.PROTO_RULE_EDGE_CASE,
    ProtocolId.PROTO_MEMORY_PROMOTION,
    ProtocolId.PROTO_MEMORY_RECALL,
}


def route_envelope(envelope: TurnEnvelope, session_state: dict | None) -> RoutedDecision:
    session_state = session_state or {}
    if envelope.mode == "ooc" or envelope.ooc_questions:
        return RoutedDecision(
            protocol_id=ProtocolId.PROTO_CLARIFICATION,
            freeze_time=True,
            execute=False,
            reason="ooc",
            ooc_questions=list(envelope.ooc_questions),
        )

    protocol_id = _resolve_protocol_id(envelope.protocol_id)
    if protocol_id is None:
        if _dev_mode_enabled(session_state):
            return RoutedDecision(
                protocol_id=ProtocolId.PROTO_RULE_EDGE_CASE,
                freeze_time=True,
                execute=False,
                reason="unknown_protocol",
                dev_report={
                    "error": "Unknown protocol_id",
                    "protocol_id": envelope.protocol_id,
                },
            )
        return RoutedDecision(
            protocol_id=ProtocolId.PROTO_CLARIFICATION,
            freeze_time=True,
            execute=False,
            reason="unknown_protocol",
            ooc_questions=[
                "Protocol not recognized. Can you restate your request?",
            ],
        )

    if envelope.confidence == "low" and protocol_id not in SAFE_PROTOCOLS:
        return RoutedDecision(
            protocol_id=ProtocolId.PROTO_CLARIFICATION,
            freeze_time=True,
            execute=False,
            reason="low_confidence",
            ooc_questions=[
                "I need a bit more detail to proceed safely. What should I focus on?",
            ],
        )

    entry = PROTOCOL_REGISTRY[protocol_id]
    return RoutedDecision(
        protocol_id=protocol_id,
        freeze_time=entry.time_policy == "freeze",
        execute=True,
        reason="ok",
    )


def _resolve_protocol_id(value: str) -> ProtocolId | None:
    try:
        return ProtocolId(value)
    except ValueError:
        return None


def _dev_mode_enabled(session_state: dict) -> bool:
    settings = session_state.get("settings")
    if isinstance(settings, dict):
        dev_flag = settings.get("dev_mode_enabled")
        if dev_flag is None:
            dev_flag = settings.get("dev_mode")
        if isinstance(dev_flag, bool):
            return dev_flag
        if isinstance(dev_flag, str):
            return dev_flag.lower() == "true"
    return False
