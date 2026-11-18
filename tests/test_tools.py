from intake_copilot import tools


def test_find_contact():
    out = tools.find_contact("Email jo@example.com, call 604-555-0142, born 1958-04-12.")
    assert out == {"email": "jo@example.com", "phone": "6045550142", "dob": "1958-04-12"}


def test_find_symptoms_aliases_pain_and_duration():
    out = tools.find_symptoms("Ringing in my ears for 3 weeks, pain 4/10")
    assert out["symptoms"] == ["tinnitus"]
    assert out["pain_score"] == 4
    assert out["duration_days"] == 21


def test_red_flags():
    assert tools.red_flag_check(["cough", "chest pain"]) == ["chest pain"]
    assert tools.red_flag_check(["cough"]) == []


def test_routing():
    assert tools.route_department("Hearing aid fitting", []) == "audiology"
    assert tools.route_department("", ["irregular cycle"]) == "fertility"
    assert tools.route_department("something else", []) == "general"


def test_urgent_slots_are_same_day():
    today = tools.SCHEDULE["_today"]
    assert all(s.startswith(today) for s in tools.next_slots("general", "urgent"))


def test_age():
    assert tools.age_from_dob("2000-01-16") == 25
    assert tools.age_from_dob("not a date") is None
