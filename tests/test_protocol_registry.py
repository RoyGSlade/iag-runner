from gm_os.protocols import PROTOCOL_REGISTRY, ProtocolEntry, ProtocolId, VALID_TIME_POLICIES


def test_protocol_ids_unique() -> None:
    ids = [proto_id.value for proto_id in PROTOCOL_REGISTRY.keys()]
    assert len(ids) == len(set(ids))
    assert set(PROTOCOL_REGISTRY.keys()) == set(ProtocolId)


def test_protocol_entries_have_required_fields() -> None:
    for entry in PROTOCOL_REGISTRY.values():
        assert isinstance(entry, ProtocolEntry)
        assert entry.time_policy
        assert entry.risk_policy is not None
        assert entry.allowed_tools is not None
        assert entry.required_context is not None


def test_time_policy_values_valid() -> None:
    for entry in PROTOCOL_REGISTRY.values():
        assert entry.time_policy in VALID_TIME_POLICIES
