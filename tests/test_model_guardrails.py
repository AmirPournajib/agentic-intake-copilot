"""The hosted-model backend is tested with a fake client, so no API key is needed."""
import sys
import types

from intake_copilot import Orchestrator


def fake_anthropic(reply: str):
    mod = types.ModuleType("anthropic")

    class Client:
        def __init__(self):
            content = [types.SimpleNamespace(text=reply)]
            self.messages = types.SimpleNamespace(create=lambda **kw: types.SimpleNamespace(content=content))

    mod.Anthropic = Client
    return mod


def test_model_cannot_invent_symptoms(monkeypatch):
    reply = '```json\n{"symptoms": ["chest pain", "made up thing"], "pain_score": 8, "confidence": 0.9}\n```'
    monkeypatch.setitem(sys.modules, "anthropic", fake_anthropic(reply))
    monkeypatch.setenv("INTAKE_BACKEND", "anthropic")
    form = {"name": "A", "dob": "1990-01-01", "phone": "6045550000", "reason": "x", "consent": True}
    r = Orchestrator().run({"id": "m", "form": form, "message": "chest"})
    assert r["fields"]["symptoms"] == ["chest pain"]
    # The red-flag rule is code, so the case still goes to a person.
    assert r["priority"] == "urgent" and r["needs_human_review"]
