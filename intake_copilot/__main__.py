"""Command line:

    python -m intake_copilot demo            # run the sample cases, show the trace
    python -m intake_copilot run case.json   # run one case from a file
    python -m intake_copilot eval            # score the eval set
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import evals
from .agents import Orchestrator

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "sample_cases.json"


def show(result: dict, trace: bool = True):
    flag = "REVIEW" if result["needs_human_review"] else "AUTO"
    print(f"\n[{result['case_id']}] {flag}  {result['summary']}")
    if result["slots"]:
        print("  next slots:", ", ".join(result["slots"]))
    if result["review_reasons"]:
        print("  review because:", "; ".join(result["review_reasons"]))
    if trace:
        for step in result["trace"]:
            print(f"    - {step['agent']:<10} {step['step']:<28} {json.dumps(step['output'])[:80]}")


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "demo"
    bot = Orchestrator()
    if cmd == "demo":
        for case in json.loads(SAMPLES.read_text()):
            show(bot.run(case))
    elif cmd == "run" and len(argv) > 1:
        show(bot.run(json.loads(Path(argv[1]).read_text())))
    elif cmd == "eval":
        report = evals.run()
        print(evals.to_markdown(report))
        return 0 if report["urgent_recall"] == 1.0 else 1
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
