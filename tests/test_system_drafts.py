from types import SimpleNamespace

from gm_os.protocols import ProtocolId
from llm.schemas import TurnEnvelope
from models import Character, Session as SessionModel, SystemDraft
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
        self.system_drafts = []

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
        if isinstance(obj, SystemDraft):
            if getattr(obj, "id", None) is None:
                obj.id = len(self.system_drafts) + 1
            self.system_drafts.append(obj)

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


class ContentGapClient:
    def generate_turn_envelope(self, player_text, context):
        return TurnEnvelope.model_validate(
            {
                "mode": "gm",
                "protocol_id": ProtocolId.PROTO_CONTENT_GAP.value,
                "confidence": "medium",
                "classification": {"primary_category": "alchemy"},
                "ooc_questions": [],
            }
        )

    def extract_intent(self, player_text, context):
        return None

    def generate_narration(self, narration_request):
        return "Narration placeholder."


def test_content_gap_creates_system_draft_with_projects(monkeypatch):
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
    monkeypatch.setattr("rules.turn.OllamaClient", lambda: ContentGapClient())
    monkeypatch.setattr("rules.turn.promote_memories_for_session", lambda *_: False)

    result = execute_turn(1, "Alchemy recipes are missing.")

    assert result.outcome["content_gap"] is True
    assert result.outcome["system_draft"]["name"] == "Alchemy"
    assert len(db.system_drafts) == 1
    outputs = db.system_drafts[0].outputs_json or []
    assert any("Recipe" in item.get("description", "") for item in outputs)
