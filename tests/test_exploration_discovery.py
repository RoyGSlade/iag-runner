from types import SimpleNamespace

from gm_os.protocols import ProtocolId
from llm.schemas import TurnEnvelope
from models import Character, Discovery, Session as SessionModel, Thread
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

    def first(self):
        if self.session_id is None:
            return self.data[0] if self.data else None
        for item in self.data:
            if item.session_id == self.session_id:
                return item
        return None


class DummySession:
    def __init__(self, session, character):
        self.session = session
        self.character = character
        self.discoveries = []
        self.threads = []

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
        return DummyQuery([])

    def add(self, obj):
        if isinstance(obj, Discovery):
            if getattr(obj, "id", None) is None:
                obj.id = len(self.discoveries) + 1
            self.discoveries.append(obj)
        if isinstance(obj, Thread):
            if getattr(obj, "id", None) is None:
                obj.id = len(self.threads) + 1
            self.threads.append(obj)

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


class ExplorationClient:
    def generate_turn_envelope(self, player_text, context):
        return TurnEnvelope.model_validate(
            {
                "mode": "gm",
                "protocol_id": ProtocolId.PROTO_EXPLORATION.value,
                "confidence": "high",
                "classification": {"primary_category": "exploration"},
                "ooc_questions": [],
            }
        )

    def extract_intent(self, player_text, context):
        return None

    def generate_narration(self, narration_request):
        return "Exploration narration."


def test_exploration_creates_discovery_and_thread(monkeypatch):
    session = SimpleNamespace(
        id=1,
        rng_seed=5,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "scene_text": "Test scene.",
            "settings": {"dev_mode_enabled": False},
        },
    )
    character = SimpleNamespace(session_id=1, attributes_json={})
    db = DummySession(session, character)
    _patch_session(monkeypatch, db)
    monkeypatch.setattr("rules.turn.OllamaClient", lambda: ExplorationClient())
    monkeypatch.setattr("rules.turn.promote_memories_for_session", lambda *_: False)

    result = execute_turn(1, "Search the area.")

    assert result.outcome["exploration"] is True
    assert len(db.discoveries) == 1
    assert db.discoveries[0].gradient in {
        "myth",
        "partial",
        "lost",
        "false",
        "dangerous",
    }
    assert len(db.threads) == 1
    assert db.threads[0].text
