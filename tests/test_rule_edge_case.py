from types import SimpleNamespace

from gm_os.protocols import ProtocolId
from llm.schemas import TurnEnvelope
from models import Character, Ruling, Session as SessionModel
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
        self.rulings = []

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
        if isinstance(obj, Ruling):
            if getattr(obj, "id", None) is None:
                obj.id = len(self.rulings) + 1
            self.rulings.append(obj)

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


class EdgeCaseClient:
    def generate_turn_envelope(self, player_text, context):
        return TurnEnvelope.model_validate(
            {
                "mode": "gm",
                "protocol_id": ProtocolId.PROTO_RULE_EDGE_CASE.value,
                "confidence": "medium",
                "classification": {"primary_category": "combat"},
                "ooc_questions": [],
            }
        )

    def extract_intent(self, player_text, context):
        return None

    def generate_narration(self, narration_request):
        return "Narration placeholder."


def test_rule_edge_case_logs_ruling_in_prod(monkeypatch):
    session = SimpleNamespace(
        id=1,
        rng_seed=1,
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
    monkeypatch.setattr("rules.turn.OllamaClient", lambda: EdgeCaseClient())
    monkeypatch.setattr("rules.turn.promote_memories_for_session", lambda *_: False)

    result = execute_turn(1, "Edge case question.")

    assert result.needs_clarification is False
    assert "ruling_note" in result.outcome
    assert len(db.rulings) == 1
    assert db.rulings[0].question
    assert db.rulings[0].ruling
    assert db.rulings[0].affected_systems_json == ["combat"]


def test_rule_edge_case_prompts_in_dev(monkeypatch):
    session = SimpleNamespace(
        id=1,
        rng_seed=1,
        metadata_json={
            "era": "Space",
            "location": "Test",
            "scene_text": "Test scene.",
            "settings": {"dev_mode_enabled": True},
        },
    )
    character = SimpleNamespace(session_id=1, attributes_json={})
    db = DummySession(session, character)
    _patch_session(monkeypatch, db)
    monkeypatch.setattr("rules.turn.OllamaClient", lambda: EdgeCaseClient())
    monkeypatch.setattr("rules.turn.promote_memories_for_session", lambda *_: False)

    result = execute_turn(1, "Edge case question.")

    assert result.needs_clarification is True
    assert "proposal" in result.outcome
    assert len(db.rulings) == 0
