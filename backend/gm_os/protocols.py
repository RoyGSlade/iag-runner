from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

TimePolicy = Literal["freeze", "advance"]


class ProtocolId(str, Enum):
    PROTO_CLARIFICATION = "PROTO_CLARIFICATION"
    PROTO_INVENTION = "PROTO_INVENTION"
    PROTO_CATASTROPHIC = "PROTO_CATASTROPHIC"
    PROTO_CONTENT_GAP = "PROTO_CONTENT_GAP"
    PROTO_EXPLORATION = "PROTO_EXPLORATION"
    PROTO_STAGNATION = "PROTO_STAGNATION"
    PROTO_WORLD_BOOTSTRAP = "PROTO_WORLD_BOOTSTRAP"
    PROTO_ARC_SEEDING = "PROTO_ARC_SEEDING"
    PROTO_ROUTINE = "PROTO_ROUTINE"
    PROTO_RETCON_DISPUTE = "PROTO_RETCON_DISPUTE"
    PROTO_RULE_EDGE_CASE = "PROTO_RULE_EDGE_CASE"
    PROTO_DOWNTIME = "PROTO_DOWNTIME"
    PROTO_MEMORY_PROMOTION = "PROTO_MEMORY_PROMOTION"
    PROTO_MEMORY_RECALL = "PROTO_MEMORY_RECALL"


@dataclass(frozen=True)
class ProtocolEntry:
    time_policy: TimePolicy
    risk_policy: str
    allowed_tools: list[str]
    required_context: list[str]


PROTOCOL_REGISTRY: dict[ProtocolId, ProtocolEntry] = {
    ProtocolId.PROTO_CLARIFICATION: ProtocolEntry(
        time_policy="freeze",
        risk_policy="none",
        allowed_tools=[],
        required_context=["last_intent", "scene_snapshot"],
    ),
    ProtocolId.PROTO_INVENTION: ProtocolEntry(
        time_policy="advance",
        risk_policy="none",
        allowed_tools=["npc_generator", "location_generator"],
        required_context=["era", "setting"],
    ),
    ProtocolId.PROTO_CATASTROPHIC: ProtocolEntry(
        time_policy="freeze",
        risk_policy="confirm_catastrophic",
        allowed_tools=["threat_assessor"],
        required_context=["stakes", "party_state"],
    ),
    ProtocolId.PROTO_CONTENT_GAP: ProtocolEntry(
        time_policy="freeze",
        risk_policy="none",
        allowed_tools=["lore_lookup"],
        required_context=["requested_topic", "campaign_memory"],
    ),
    ProtocolId.PROTO_EXPLORATION: ProtocolEntry(
        time_policy="advance",
        risk_policy="none",
        allowed_tools=["map_hint", "sensory_prompt"],
        required_context=["location", "scene_snapshot"],
    ),
    ProtocolId.PROTO_STAGNATION: ProtocolEntry(
        time_policy="advance",
        risk_policy="none",
        allowed_tools=["pace_boost"],
        required_context=["last_actions", "scene_snapshot"],
    ),
    ProtocolId.PROTO_WORLD_BOOTSTRAP: ProtocolEntry(
        time_policy="freeze",
        risk_policy="none",
        allowed_tools=["world_seed"],
        required_context=["era", "setting", "player_prefs"],
    ),
    ProtocolId.PROTO_ARC_SEEDING: ProtocolEntry(
        time_policy="advance",
        risk_policy="none",
        allowed_tools=["plot_seed"],
        required_context=["session_setup", "npcs"],
    ),
    ProtocolId.PROTO_ROUTINE: ProtocolEntry(
        time_policy="advance",
        risk_policy="none",
        allowed_tools=[],
        required_context=["scene_snapshot"],
    ),
    ProtocolId.PROTO_RETCON_DISPUTE: ProtocolEntry(
        time_policy="freeze",
        risk_policy="confirm_catastrophic",
        allowed_tools=["log_review"],
        required_context=["turn_log", "player_statement"],
    ),
    ProtocolId.PROTO_RULE_EDGE_CASE: ProtocolEntry(
        time_policy="freeze",
        risk_policy="none",
        allowed_tools=["rules_lookup"],
        required_context=["rule_context", "character_state"],
    ),
    ProtocolId.PROTO_DOWNTIME: ProtocolEntry(
        time_policy="advance",
        risk_policy="none",
        allowed_tools=["downtime_generator"],
        required_context=["party_state", "resources"],
    ),
    ProtocolId.PROTO_MEMORY_PROMOTION: ProtocolEntry(
        time_policy="freeze",
        risk_policy="none",
        allowed_tools=["memory_writer"],
        required_context=["session_summary"],
    ),
    ProtocolId.PROTO_MEMORY_RECALL: ProtocolEntry(
        time_policy="freeze",
        risk_policy="none",
        allowed_tools=[],
        required_context=["turn_log", "session_summary"],
    ),
}


VALID_TIME_POLICIES: set[str] = {"freeze", "advance"}


def validate_protocol_registry() -> list[str]:
    errors: list[str] = []
    for proto_id, entry in PROTOCOL_REGISTRY.items():
        if entry.time_policy not in VALID_TIME_POLICIES:
            errors.append(f"{proto_id} has invalid time_policy {entry.time_policy}")
        if not isinstance(entry.allowed_tools, list):
            errors.append(f"{proto_id} allowed_tools must be list")
        if not isinstance(entry.required_context, list):
            errors.append(f"{proto_id} required_context must be list")
    return errors
