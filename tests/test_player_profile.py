from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from gm_os.protocols import ProtocolId
from llm.schemas import Intent, TurnEnvelope
from models import Character, Clock, PlayerProfile, Session as SessionModel, Thread
from rules.turn import execute_turn


class DummyQuery:
    def __init__(self, data):
        self.data = data
        self.session_id = None

    def filter(self, *args, **kwargs):
        if args:
            expr = args[0]
            right = getattr(expr, "right", None)
            value = getattr(right, "value", None)
            if value is not None:
                self.session_id = value
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        if self.session_id is None:
            return self.data
        return [item for item in self.data if item.session_id == self.session_id]

    def first(self):
        records = self.all()
        return records[0] if records else None


class DummySession:
    def __init__(self, session, character, profile):
        self.session = session
        self.character = character
        self.profile = profile
        self.threads = []
        self.clocks = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, model, record_id):
        if model is SessionModel and record_id == self.session.id:
            return self.session
        return None

    def query(self, model):
        if model is Character:
            return DummyQuery([self.character])
        if model is PlayerProfile:
            return DummyQuery([self.profile])
        if model is Thread:
            return DummyQuery(self.threads)
        if model is Clock:
            return DummyQuery(self.clocks)
        return DummyQuery([])

    def add(self, obj):
        if isinstance(obj, PlayerProfile):
            self.profile = obj

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, obj):
        return None


def _patch_session(monkeypatch, db):
    def factory():
        return db

    monkeypatch.setattr("rules.turn.SessionLocal", factory)
    monkeypatch.setattr("app.main.SessionLocal", factory)


class ProfileClient:
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
        return "Profile narration."


def test_profile_weights_update_after_turn(monkeypatch):
    session = SimpleNamespace(
        id=1,
        rng_seed=1,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "scene_text": "Test scene.",
        },
    )
    character = SimpleNamespace(session_id=1, attributes_json={})
    profile = PlayerProfile(
        session_id=1,
        interests_json={
            "combat": {"count": 0, "weight": 0.0},
            "crafting": {"count": 0, "weight": 0.0},
            "mystery": {"count": 0, "weight": 0.0},
            "politics": {"count": 0, "weight": 0.0},
            "horror": {"count": 0, "weight": 0.0},
            "exploration": {"count": 0, "weight": 0.0},
        },
    )
    db = DummySession(session, character, profile)
    _patch_session(monkeypatch, db)
    monkeypatch.setattr("rules.turn.OllamaClient", lambda: ProfileClient())
    monkeypatch.setattr("rules.turn.promote_memories_for_session", lambda *_: False)

    execute_turn(1, "Attack.")

    updated = profile.interests_json["combat"]
    assert updated["count"] == 1
    assert updated["weight"] == 1.0


def test_get_profile_endpoint_returns_payload(monkeypatch):
    session = SimpleNamespace(
        id=1,
        rng_seed=1,
        metadata_json={"era": "Space"},
    )
    character = SimpleNamespace(session_id=1, attributes_json={})
    profile = PlayerProfile(
        session_id=1,
        tone_prefs_json={"violence_level": None},
        themes_json={"avoid": []},
        pacing_json={"pace": "balanced"},
        challenge_json={"level": "standard"},
        boundaries_json={"lines": [], "veils": []},
        interests_json={"combat": {"count": 0, "weight": 0.0}},
    )
    db = DummySession(session, character, profile)
    _patch_session(monkeypatch, db)
    client = TestClient(app)

    response = client.get("/sessions/1/profile")
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == 1
    assert "interests" in payload
