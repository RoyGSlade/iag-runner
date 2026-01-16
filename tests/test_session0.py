from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from llm.client import LLMClientError
from llm.schemas import SessionSetup
from models import Session as SessionModel


class DummySession:
    def __init__(self, session_obj):
        self.session_obj = session_obj

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, model, record_id: int):
        if model is SessionModel and record_id == self.session_obj.id:
            return self.session_obj
        return None

    def commit(self):
        return None

    def refresh(self, obj):
        return None


def _patch_session(monkeypatch, session_obj):
    def factory():
        return DummySession(session_obj)

    monkeypatch.setattr("app.main.SessionLocal", factory)


def test_session0_complete_stores_setup(monkeypatch):
    session = SimpleNamespace(id=1, metadata_json={})
    setup_payload = {
        "era": "Space",
        "setting": {
            "type": "space station",
            "tone": ["noir"],
            "inspirations": ["Blade Runner"],
        },
        "player_prefs": {
            "violence_level": "medium",
            "horror": "low",
            "avoid": ["gore"],
        },
        "starting_situation": {
            "hook": "mystery",
            "first_scene": "Dockside arrival",
            "immediate_problem": "Missing courier",
            "npcs": ["Harbor Master"],
        },
    }

    class StubClient:
        def complete_session0(self, payload):
            return SessionSetup.model_validate(setup_payload)

    monkeypatch.setattr("app.main.OllamaClient", StubClient)
    _patch_session(monkeypatch, session)
    client = TestClient(app)

    response = client.post(
        "/session0/complete",
        json={
            "session_id": 1,
            "era": "Space",
            "setting": {
                "type": "space station",
                "tone_tags": ["noir"],
                "inspirations": ["Blade Runner"],
            },
            "player_prefs": {
                "violence_level": "medium",
                "horror_level": "low",
                "avoid": ["gore"],
            },
            "starting_hook_preference": "mystery",
        },
    )

    assert response.status_code == 200
    assert session.metadata_json["session_setup"]["era"] == "Space"
    assert session.metadata_json["setting"]["type"] == "space station"


def test_session0_invalid_json_returns_error_and_no_mutation(monkeypatch):
    session = SimpleNamespace(id=2, metadata_json={})

    class StubClient:
        def complete_session0(self, payload):
            raise LLMClientError("Invalid JSON")

    monkeypatch.setattr("app.main.OllamaClient", StubClient)
    _patch_session(monkeypatch, session)
    client = TestClient(app)

    response = client.post(
        "/session0/complete",
        json={
            "session_id": 2,
            "era": "Space",
            "setting": {"type": "space station", "tone_tags": [], "inspirations": []},
            "player_prefs": {"violence_level": "low", "horror_level": "low", "avoid": []},
            "starting_hook_preference": "exploration",
        },
    )

    assert response.status_code == 400
    assert session.metadata_json == {}
