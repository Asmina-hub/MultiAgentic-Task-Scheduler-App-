from datetime import date, time

import pytest
from pydantic import ValidationError

from slot_planner.engine.model import Activity, ActivityLog, Rules, Slot

# ---------- helpers: build a valid object, override one field per test ----------

def make_activity(**overrides) -> Activity:
    data = {
        "id": 1,
        "user_id": 1,
        "name": "HiWi",
        "target_type": "weekly",
        "target_min": 480,
        "priority": 2,
    }
    data.update(overrides)
    return Activity(**data)


def make_slot(**overrides) -> Slot:
    data = {
        "id": 1,
        "user_id": 1,
        "activity_id": 1,
        "date": date(2026, 10, 5),
        "start": time(14, 0),
        "end": time(16, 0),
    }
    data.update(overrides)
    return Slot(**data)


def make_log(**overrides) -> ActivityLog:
    data = {
        "id": 1,
        "user_id": 1,
        "activity_id": 1,
        "date": date(2026, 10, 5),
        "minutes": 300,
    }
    data.update(overrides)
    return ActivityLog(**data)


# ---------- Activity ----------

def test_valid_activity():
    hiwi = make_activity()
    assert hiwi.name == "HiWi"
    assert hiwi.allowed_days == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@pytest.mark.parametrize("bad_minutes", [0, -60])
def test_activity_target_must_be_positive(bad_minutes):
    with pytest.raises(ValidationError):
        make_activity(target_min=bad_minutes)


def test_activity_rejects_unknown_target_type():
    with pytest.raises(ValidationError):
        make_activity(target_type="monthly")


def test_daily_target_cannot_exceed_a_day():
    with pytest.raises(ValidationError):
        make_activity(target_type="daily", target_min=1500)


def test_weekly_target_can_exceed_a_day():
    hiwi = make_activity(target_type="weekly", target_min=1500)
    assert hiwi.target_min == 1500


def test_locked_when_fixed_time_is_set():
    german = make_activity(name="German A1", target_type="daily",
                           target_min=60, fixed_time=time(20, 30))
    assert german.locked is True


def test_not_locked_without_fixed_time():
    assert make_activity().locked is False


def test_locked_cannot_be_set_directly():
    with pytest.raises(ValidationError):
        make_activity(locked=True)


def test_allowed_days_cannot_be_empty():
    with pytest.raises(ValidationError):
        make_activity(allowed_days=[])


def test_allowed_days_rejects_duplicates():
    with pytest.raises(ValidationError):
        make_activity(allowed_days=["Mon", "Mon"])


def test_allowed_days_rejects_unknown_day():
    with pytest.raises(ValidationError):
        make_activity(allowed_days=["Monday"])


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        make_activity(target_mins=480)


# ---------- Slot ----------

def test_valid_slot_and_duration():
    slot = make_slot()
    assert slot.status == "planned"
    assert slot.duration_min == 120


@pytest.mark.parametrize("end", [time(13, 0), time(14, 0)])
def test_slot_end_must_be_after_start(end):
    with pytest.raises(ValidationError):
        make_slot(end=end)


def test_slot_rejects_unknown_status():
    with pytest.raises(ValidationError):
        make_slot(status="maybe")


# ---------- ActivityLog ----------

def test_valid_log():
    assert make_log().minutes == 300


@pytest.mark.parametrize("bad_minutes", [0, -30, 1500])
def test_log_minutes_must_be_realistic(bad_minutes):
    with pytest.raises(ValidationError):
        make_log(minutes=bad_minutes)


# ---------- Rules ----------

def test_default_rules():
    rules = Rules(user_id=1)
    assert rules.free_days == ["Sat"]
    assert rules.day_start == time(8, 0)


def test_day_window_must_be_valid():
    with pytest.raises(ValidationError):
        Rules(user_id=1, day_start=time(22, 0), day_end=time(8, 0))


def test_min_chunk_must_fit_slot_step():
    with pytest.raises(ValidationError):
        Rules(user_id=1, slot_step_min=15, min_chunk_min=20)


def test_not_every_day_can_be_free():
    with pytest.raises(ValidationError):
        Rules(user_id=1, free_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])