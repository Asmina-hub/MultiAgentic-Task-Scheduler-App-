import json
from datetime import date, time

import pytest

from slot_planner.db.database import connect, get_slots, mark_slot, save_plan
from slot_planner.engine.model import Activity, Rules, Slot

MON, TUE = date(2026, 10, 19), date(2026, 10, 20)
RULES = Rules(user_id=1, free_days=["Sat"], blocked_times=[{"start": "17:00", "end": "20:00"}])


@pytest.fixture
def db(tmp_path):
    """A fresh database file for every test, never your real one."""
    return tmp_path / "test.db"


def make_plan(name="Thesis"):
    acts = [Activity(id=1, user_id=1, name=name, target_type="daily", target_min=60, priority=1,
                     preferred_window=["morning", "night"], max_days_per_week=3)]
    slots = [
        Slot(user_id=1, activity_id=1, date=MON, start=time(9, 0), end=time(10, 0)),
        Slot(user_id=1, activity_id=1, date=TUE, start=time(9, 0), end=time(10, 0)),
    ]
    return acts, slots


def save(db, name="Thesis", text="my text"):
    acts, slots = make_plan(name)
    return save_plan(text, acts, RULES, slots, MON, TUE, db_path=db)


def test_save_and_read_back(db):
    save(db)
    today = get_slots(MON, MON, db_path=db)
    assert len(today) == 1
    assert today[0].activity == "Thesis"
    assert today[0].start == time(9, 0)
    assert today[0].status == "planned"


def test_lists_and_rules_are_stored(db):
    plan_id = save(db)
    with connect(db) as conn:
        plan = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        act = conn.execute("SELECT * FROM activities WHERE plan_id = ?", (plan_id,)).fetchone()
    assert json.loads(plan["free_days"]) == ["Sat"]
    assert json.loads(plan["blocked_times"])[0]["start"] == "17:00:00"
    assert json.loads(act["preferred_window"]) == ["morning", "night"]
    assert act["max_days_per_week"] == 3


def test_mark_slot(db):
    save(db)
    slot = get_slots(MON, MON, db_path=db)[0]
    assert mark_slot(slot.id, "done", db_path=db) is True
    assert get_slots(MON, MON, db_path=db)[0].status == "done"


def test_mark_unknown_slot(db):
    save(db)
    assert mark_slot(999, "done", db_path=db) is False


def test_new_plan_replaces_old_one(db):
    save(db, "Old thing")
    save(db, "New thing")
    names = {s.activity for s in get_slots(MON, TUE, db_path=db)}
    assert names == {"New thing"}


def test_empty_database(db):
    assert get_slots(MON, TUE, db_path=db) == []
