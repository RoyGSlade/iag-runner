from rules.character import create_session_record


class DummyDb:
    def __init__(self) -> None:
        self.added = None

    def add(self, obj) -> None:
        self.added = obj

    def flush(self) -> None:
        return None


def test_session_settings_defaults() -> None:
    db = DummyDb()
    session = create_session_record(
        db,
        era_name="Space",
        location="Test",
        seed=1,
    )
    settings = session.metadata_json.get("settings", {})
    assert settings.get("dev_mode_enabled") is False
    assert settings.get("ooc_allowed") is True


def test_session_settings_partial_override() -> None:
    db = DummyDb()
    session = create_session_record(
        db,
        era_name="Space",
        location="Test",
        seed=1,
        settings={"dev_mode_enabled": True},
    )
    settings = session.metadata_json.get("settings", {})
    assert settings.get("dev_mode_enabled") is True
    assert settings.get("ooc_allowed") is True
