"""Tools the agents can call.

Every tool is a plain function with typed input and output, so it can be
unit tested on its own and logged in the trace. In a real deployment these
would wrap a clinic knowledge base, a scheduling API and so on.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(name: str):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


KNOWLEDGE_BASE = _load("knowledge_base.json")
SCHEDULE = _load("schedule.json")

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
DOB_RE = re.compile(r"\b(19\d{2}|20\d{2})-(\d{2})-(\d{2})\b")
PAIN_RE = re.compile(r"pain(?:\s+(?:is|at|level|score))?\s*(?:about\s*)?(\d{1,2})\s*(?:/|out of)\s*10", re.I)
DURATION_RE = re.compile(r"(?:for|since|past|last)\s+(?:the\s+)?(\d+|a|an|one|two|three|four|five|six|seven)\s+(hour|day|week|month|year)s?", re.I)
WORD_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
DAYS_PER = {"hour": 1 / 24, "day": 1, "week": 7, "month": 30, "year": 365}


def find_contact(text: str) -> dict:
    """Pull email, phone and date of birth out of free text."""
    out = {}
    if m := EMAIL_RE.search(text):
        out["email"] = m.group(0).rstrip(".")
    if m := PHONE_RE.search(text):
        out["phone"] = re.sub(r"\D", "", m.group(0))[-10:]
    if m := DOB_RE.search(text):
        out["dob"] = m.group(0)
    return out


def find_symptoms(text: str) -> dict:
    """Match symptoms from the knowledge base, plus pain score and duration."""
    low = text.lower()
    symptoms = []
    for name, info in KNOWLEDGE_BASE["symptoms"].items():
        if any(alias in low for alias in [name] + info.get("aliases", [])):
            symptoms.append(name)
    out: dict = {"symptoms": sorted(set(symptoms))}
    if m := PAIN_RE.search(text):
        out["pain_score"] = min(int(m.group(1)), 10)
    if m := DURATION_RE.search(text):
        n = m.group(1).lower()
        n = WORD_NUM.get(n, None) or int(n)
        out["duration_days"] = round(n * DAYS_PER[m.group(2).lower()], 2)
    return out


def red_flag_check(symptoms: list[str]) -> list[str]:
    """Return the symptoms that the knowledge base marks as red flags."""
    return [s for s in symptoms if KNOWLEDGE_BASE["symptoms"].get(s, {}).get("red_flag")]


def route_department(reason: str, symptoms: list[str]) -> str:
    """Pick a department from the visit reason and symptoms."""
    text = (reason or "").lower() + " " + " ".join(symptoms)
    best, best_hits = "general", 0
    for dept, keywords in KNOWLEDGE_BASE["routing"].items():
        hits = sum(1 for k in keywords if k in text)
        if hits > best_hits:
            best, best_hits = dept, hits
    return best


def next_slots(department: str, priority: str, limit: int = 3) -> list[str]:
    """Return open appointment slots. Urgent cases only get same-day slots."""
    slots = SCHEDULE.get(department, SCHEDULE["general"])
    if priority == "urgent":
        slots = [s for s in slots if s.startswith(SCHEDULE["_today"])]
    return slots[:limit]


def age_from_dob(dob: str, today: date | None = None) -> int | None:
    try:
        y, m, d = (int(x) for x in dob.split("-"))
        born = date(y, m, d)
    except (ValueError, AttributeError):
        return None
    today = today or date.fromisoformat(SCHEDULE["_today"])
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


TOOLS = {
    "find_contact": find_contact,
    "find_symptoms": find_symptoms,
    "red_flag_check": red_flag_check,
    "route_department": route_department,
    "next_slots": next_slots,
}
