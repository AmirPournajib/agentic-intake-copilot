from intake_copilot import Orchestrator, evals

BOT = Orchestrator()
FORM = {"name": "Test", "dob": "1990-01-01", "phone": "6045550000", "reason": "Checkup", "consent": True}


def run(message, **form):
    return BOT.run({"id": "t", "form": {**FORM, **form}, "message": message})


def test_clean_routine_case_is_automatic():
    r = run("Annual checkup, feeling fine.")
    assert r["priority"] == "routine"
    assert not r["needs_human_review"]


def test_red_flag_always_goes_to_a_person():
    r = run("I passed out this morning")
    assert r["priority"] == "urgent"
    assert r["needs_human_review"]
    assert "RED FLAGS" in r["summary"]


def test_missing_consent_blocks_auto_booking():
    r = run("Routine visit", consent=False)
    assert "missing:consent" in r["issues"]
    assert r["needs_human_review"]


def test_form_value_wins_over_message():
    r = run("call me at 778-555-1234")
    assert r["fields"]["phone"] == "6045550000"


def test_message_fills_gaps():
    r = BOT.run({"id": "t", "form": {"name": "X", "reason": "Checkup", "consent": True},
                 "message": "DOB 1980-05-05, phone 604 555 0199"})
    assert r["fields"]["dob"] == "1980-05-05"
    assert r["issues"] == []


def test_unmapped_complaint_lowers_confidence():
    r = run("my foot is swollen and it hurts")
    assert r["confidence"] < 0.6
    assert r["needs_human_review"]


def test_every_step_is_traced():
    agents = [s["agent"] for s in run("cough for 2 days")["trace"]]
    assert agents[0] == "extractor" and agents[-1] == "gate"
    assert {"validator", "triage", "summarizer"} <= set(agents)


def test_eval_set_quality_bar():
    report = evals.run()
    assert report["urgent_recall"] == 1.0
    assert report["priority_accuracy"] >= 0.9
    assert report["routing_accuracy"] >= 0.9
