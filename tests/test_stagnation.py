from types import SimpleNamespace

from gm_os.protocols import ProtocolId
from llm.schemas import TurnEnvelope
from models import Character, Clock, Session as SessionModel, Thread
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
    def __init__(self, session, character):
        self.session = session
        self.character = character
        self.threads = []
        self.clocks = []
        self.created_threads = []

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
        if model is Thread:
            return DummyQuery(self.threads)
        if model is Clock:
            return DummyQuery(self.clocks)
        return DummyQuery([])

    def add(self, obj):
        if isinstance(obj, Thread):
            if getattr(obj, "id", None) is None:
                obj.id = len(self.created_threads) + 1
            self.created_threads.append(obj)

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


class StagnationClient:
    def generate_turn_envelope(self, player_text, context):
        return TurnEnvelope.model_validate(
            {
                "mode": "gm",
                "protocol_id": ProtocolId.PROTO_STAGNATION.value,
                "confidence": "high",
                "classification": {"primary_category": "stagnation"},
                "ooc_questions": [],
            }
        )

    def extract_intent(self, player_text, context):
        return None

    def generate_narration(self, narration_request):
        return "Stagnation narration."


def test_stagnation_creates_tension_hook(monkeypatch):
    session = SimpleNamespace(
        id=1,
        rng_seed=7,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "scene_text": "Test scene.",
            "settings": {"dev_mode_enabled": False},
        },
    )
    character = SimpleNamespace(session_id=1, attributes_json={})
    db = DummySession(session, character)
    db.threads.append(
        SimpleNamespace(id=1, session_id=1, status="open", text="Old hook")
    )
    db.clocks.append(
        SimpleNamespace(id=1, session_id=1, name="Threat", steps_done=0, steps_total=2)
    )
    _patch_session(monkeypatch, db)
    monkeypatch.setattr("rules.turn.OllamaClient", lambda: StagnationClient())
    monkeypatch.setattr("rules.turn.promote_memories_for_session", lambda *_: False)

    result = execute_turn(1, "I wait.")

    assert result.outcome["stagnation"] is True
    assert session.metadata_json.get("pacing_tag") == "tension"
    assert db.created_threads
    assert "Tension rises" in db.created_threads[0].text
