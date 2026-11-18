"""Run the labelled eval set and report the numbers a product team tracks."""
from __future__ import annotations

import json
from pathlib import Path

from .agents import Orchestrator

EVAL_FILE = Path(__file__).resolve().parent.parent / "evals" / "cases.jsonl"


def load_cases(path: Path = EVAL_FILE) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run(cases: list[dict] | None = None, model=None) -> dict:
    cases = cases or load_cases()
    bot = Orchestrator(model)
    rows = []
    for c in cases:
        r = bot.run(c)
        exp = c["expected"]
        rows.append({
            "id": c["id"],
            "priority_ok": r["priority"] == exp["priority"],
            "department_ok": r["department"] == exp["department"],
            "review_ok": r["needs_human_review"] == exp["needs_human_review"],
            "urgent_expected": exp["priority"] == "urgent",
            "urgent_caught": r["priority"] == "urgent",
            "got": {k: r[k] for k in ("priority", "department", "needs_human_review")},
            "expected": exp,
        })
    n = len(rows)
    urgent = [x for x in rows if x["urgent_expected"]]
    return {
        "cases": n,
        "priority_accuracy": round(sum(x["priority_ok"] for x in rows) / n, 3),
        "routing_accuracy": round(sum(x["department_ok"] for x in rows) / n, 3),
        "review_gate_accuracy": round(sum(x["review_ok"] for x in rows) / n, 3),
        "urgent_recall": round(sum(x["urgent_caught"] for x in urgent) / len(urgent), 3) if urgent else None,
        "human_review_rate": round(sum(x["got"]["needs_human_review"] for x in rows) / n, 3),
        "failures": [x for x in rows if not (x["priority_ok"] and x["department_ok"] and x["review_ok"])],
    }


def to_markdown(report: dict) -> str:
    lines = [
        "| Metric | Value |", "|---|---|",
        f"| Cases | {report['cases']} |",
        f"| Urgent recall (must be 1.0) | {report['urgent_recall']} |",
        f"| Priority accuracy | {report['priority_accuracy']} |",
        f"| Routing accuracy | {report['routing_accuracy']} |",
        f"| Review gate accuracy | {report['review_gate_accuracy']} |",
        f"| Human review rate | {report['human_review_rate']} |",
    ]
    if report["failures"]:
        lines += ["", "Failures:"] + [f"- `{f['id']}` got {f['got']} expected {f['expected']}" for f in report["failures"]]
    return "\n".join(lines)
