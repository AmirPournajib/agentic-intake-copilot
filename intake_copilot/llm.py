"""Model backends.

The pipeline only needs one model skill: turn a free-text message into
structured fields. Two backends implement it:

* OfflineModel: deterministic, uses the regex and knowledge-base tools.
  This is the default and the one the tests and evals run on, so results
  are repeatable and CI (Continuous Integration) needs no API key.
* AnthropicModel: optional. Used when INTAKE_BACKEND=anthropic and the
  `anthropic` package plus ANTHROPIC_API_KEY are available.

Swapping the backend never changes the guardrails: validation, red-flag
checks and the human-review gate always run as plain code.
"""
from __future__ import annotations

import json
import os
import re

from . import tools

UNGROUNDED_RE = re.compile(r"\b(hurts?|pain|sick|unwell|swollen|weird|worse|not right|bleed\w*)\b", re.I)

FIELDS = ["email", "phone", "dob", "symptoms", "pain_score", "duration_days"]


class OfflineModel:
    name = "offline"

    def extract(self, message: str) -> tuple[dict, float]:
        found = {**tools.find_contact(message), **tools.find_symptoms(message)}
        # Confidence: high when the message is clear, low when the patient
        # describes a problem we could not map to a known symptom.
        if not message.strip():
            return found, 0.0
        signals = sum(1 for k in ("symptoms", "pain_score", "duration_days") if found.get(k))
        confidence = 0.6 + 0.1 * signals
        if signals == 0 and UNGROUNDED_RE.search(message):
            confidence = 0.45
        return found, round(min(confidence, 0.9), 2)


class AnthropicModel:
    name = "anthropic"

    def __init__(self, model: str | None = None):
        import anthropic  # optional dependency

        self.client = anthropic.Anthropic()
        self.model = model or os.environ.get("INTAKE_MODEL", "claude-sonnet-4-5")

    def extract(self, message: str) -> tuple[dict, float]:
        known = sorted(tools.KNOWLEDGE_BASE["symptoms"])
        prompt = (
            "Extract intake fields from the patient message. Reply with JSON only, keys: "
            f"{FIELDS} and 'confidence' (0 to 1). Use only these symptom names: {known}. "
            "Leave a key out if the message does not state it. Do not guess.\n\n"
            f"Message:\n{message}"
        )
        resp = self.client.messages.create(
            model=self.model, max_tokens=400, messages=[{"role": "user", "content": prompt}]
        )
        text = resp.content[0].text.strip().strip("`").removeprefix("json").strip()
        data = json.loads(text)
        confidence = float(data.pop("confidence", 0.5))
        data["symptoms"] = [s for s in data.get("symptoms", []) if s in known]
        return {k: v for k, v in data.items() if k in FIELDS}, confidence


def get_model():
    if os.environ.get("INTAKE_BACKEND", "offline").lower() == "anthropic":
        return AnthropicModel()
    return OfflineModel()
