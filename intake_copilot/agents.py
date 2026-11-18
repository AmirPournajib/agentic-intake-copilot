"""The four agents and the orchestrator that runs them.

Flow:  Extractor -> Validator -> Triage -> Summarizer -> human-review gate

Each agent reads and writes one shared `IntakeState` and records every tool
call in the trace, so a reviewer can see why the system decided what it did.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import tools
from .llm import get_model

REQUIRED = ["name", "dob", "phone", "reason", "consent"]
CONFIDENCE_FLOOR = 0.6


@dataclass
class IntakeState:
    case_id: str
    form: dict
    message: str
    fields: dict = field(default_factory=dict)
    confidence: float = 1.0
    issues: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    priority: str = "routine"
    department: str = "general"
    slots: list[str] = field(default_factory=list)
    summary: str = ""
    needs_human_review: bool = False
    review_reasons: list[str] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)

    def log(self, agent: str, step: str, output, started: float):
        self.trace.append({
            "agent": agent,
            "step": step,
            "output": output,
            "ms": round((time.perf_counter() - started) * 1000, 2),
        })

    def result(self) -> dict:
        return {
            "case_id": self.case_id,
            "priority": self.priority,
            "department": self.department,
            "red_flags": self.red_flags,
            "issues": self.issues,
            "slots": self.slots,
            "needs_human_review": self.needs_human_review,
            "review_reasons": self.review_reasons,
            "confidence": self.confidence,
            "fields": self.fields,
            "summary": self.summary,
            "trace": self.trace,
        }


class Extractor:
    """Fills gaps in the form from the free-text message. Form values win."""

    def __init__(self, model=None):
        self.model = model or get_model()

    def run(self, s: IntakeState):
        t = time.perf_counter()
        found, s.confidence = self.model.extract(s.message)
        s.fields = {**{k: v for k, v in found.items() if v not in (None, [], "")}}
        for k, v in s.form.items():
            if v not in (None, "", []):
                s.fields[k] = v
        s.fields.setdefault("symptoms", [])
        s.log("extractor", f"model.extract ({self.model.name})", {"found": found, "confidence": s.confidence}, t)


class Validator:
    """Plain-code checks. No model involved, so they can't be talked out of."""

    def run(self, s: IntakeState):
        t = time.perf_counter()
        f = s.fields
        for key in REQUIRED:
            if f.get(key) in (None, "", False):
                s.issues.append(f"missing:{key}")
        if f.get("phone") and len(str(f["phone"])) != 10:
            s.issues.append("invalid:phone")
        if f.get("dob"):
            age = tools.age_from_dob(f["dob"])
            if age is None or not 0 <= age <= 120:
                s.issues.append("invalid:dob")
            else:
                f["age"] = age
        if f.get("pain_score") is not None and not 0 <= int(f["pain_score"]) <= 10:
            s.issues.append("invalid:pain_score")
        s.log("validator", "rules", {"issues": list(s.issues)}, t)


class Triage:
    """Uses tools to set priority, department and next slots."""

    def run(self, s: IntakeState):
        f = s.fields
        t = time.perf_counter()
        s.red_flags = tools.red_flag_check(f["symptoms"])
        s.log("triage", "tool:red_flag_check", s.red_flags, t)

        pain = int(f.get("pain_score") or 0)
        if s.red_flags:
            s.priority = "urgent"
        elif pain >= 7 or (f.get("duration_days") is not None and f["duration_days"] <= 2 and pain >= 5):
            s.priority = "high"
        else:
            s.priority = "routine"

        t = time.perf_counter()
        s.department = tools.route_department(f.get("reason", ""), f["symptoms"])
        s.log("triage", "tool:route_department", s.department, t)

        t = time.perf_counter()
        s.slots = tools.next_slots(s.department, s.priority)
        s.log("triage", "tool:next_slots", s.slots, t)


class Summarizer:
    """Writes the short note a clinician or front desk reads first."""

    def run(self, s: IntakeState):
        t = time.perf_counter()
        f = s.fields
        parts = [f"{s.priority.upper()} | {s.department}"]
        who = f.get("name", "Unknown patient")
        if f.get("age") is not None:
            who += f", {f['age']}"
        parts.append(who)
        if f.get("reason"):
            parts.append(f"Reason: {f['reason']}")
        if f["symptoms"]:
            parts.append("Symptoms: " + ", ".join(f["symptoms"]))
        if f.get("pain_score") is not None:
            parts.append(f"Pain {f['pain_score']}/10")
        if f.get("duration_days") is not None:
            parts.append(f"Duration {f['duration_days']} days")
        if s.red_flags:
            parts.append("RED FLAGS: " + ", ".join(s.red_flags) + ". Call patient now.")
        if s.issues:
            parts.append("Fix before booking: " + ", ".join(s.issues))
        s.summary = " | ".join(parts)
        s.log("summarizer", "template", s.summary, t)


class Orchestrator:
    def __init__(self, model=None):
        self.agents = [Extractor(model), Validator(), Triage(), Summarizer()]

    def run(self, case: dict) -> dict:
        s = IntakeState(case_id=case.get("id", "case"), form=dict(case.get("form", {})),
                        message=case.get("message", ""))
        for agent in self.agents:
            agent.run(s)
        self._review_gate(s)
        return s.result()

    @staticmethod
    def _review_gate(s: IntakeState):
        t = time.perf_counter()
        if s.priority == "urgent":
            s.review_reasons.append("urgent case: a person must call")
        if s.issues:
            s.review_reasons.append("form has issues")
        if s.confidence < CONFIDENCE_FLOOR:
            s.review_reasons.append(f"low confidence ({s.confidence})")
        s.needs_human_review = bool(s.review_reasons)
        s.log("gate", "human_review", s.review_reasons, t)
