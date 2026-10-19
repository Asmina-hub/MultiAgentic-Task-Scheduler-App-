from datetime import date, time

from slot_planner.engine.model import Activity, Rules, WeekSlot
from slot_planner.engine.timetable_guards import check_timetable, expand_to_dates

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sun"]
RULES = Rules(user_id=1, free_days=["Sat"])


def act(id, name, target_type, target_min, **kw) -> Activity:
    return Activity(id=id, user_id=1, name=name, target_type=target_type,
                    target_min=target_min, priority=kw.pop("priority", 2),
                    allowed_days=kw.pop("allowed_days", WEEKDAYS), **kw)


def slot(activity, day, start, end) -> WeekSlot:
    h1, m1 = start
    h2, m2 = end
    return WeekSlot(activity=activity, day=day, start=time(h1, m1), end=time(h2, m2))


GERMAN = act(1, "German", "daily", 60, preferred_window="night")
HIWI = act(2, "HiWi", "weekly", 120)


def valid_week() -> list[WeekSlot]:
    week = [slot("German", d, (20, 0), (21, 0)) for d in WEEKDAYS]
    week += [slot("HiWi", "Mon", (14, 0), (15, 0)), slot("HiWi", "Wed", (14, 0), (15, 0))]
    return week


def check(week, activities=(GERMAN, HIWI)):
    return check_timetable(list(activities), week, RULES)


def test_valid_week_has_no_errors():
    assert check(valid_week()) == []


def test_unknown_activity():
    assert any("unknown activity" in e for e in check(valid_week() + [slot("Gym", "Mon", (9, 0), (10, 0))]))


def test_outside_day_window():
    week = valid_week()
    week[0] = slot("German", "Mon", (21, 30), (22, 30))
    assert any("outside the day window" in e for e in check(week))


def test_free_day():
    errors = check(valid_week() + [slot("HiWi", "Sat", (10, 0), (11, 0))])
    assert any("Sat is a free day" in e for e in errors)


def test_overlap():
    errors = check(valid_week() + [slot("HiWi", "Mon", (20, 30), (21, 30))])
    assert any("overlaps" in e for e in errors)


def test_fixed_time():
    german = act(1, "German", "daily", 60, fixed_time=time(20, 0))
    week = valid_week()
    week[0] = slot("German", "Mon", (20, 15), (21, 15))
    assert any("must start at 20:00" in e for e in check(week, (german, HIWI)))


def test_preferred_window():
    week = valid_week()
    week[0] = slot("German", "Mon", (9, 0), (10, 0))
    assert any("should start in the night" in e for e in check(week))


def test_daily_total_missing_on_one_day():
    week = [s for s in valid_week() if not (s.activity == "German" and s.day == "Tue")]
    assert "German on Tue has 0 min, needs 60" in check(week)


def test_weekly_total_wrong():
    week = [s for s in valid_week() if not (s.activity == "HiWi" and s.day == "Wed")]
    assert "HiWi has 60 min this week, needs 120" in check(week)


def test_expand_to_dates_skips_free_days():
    # Oct 19 2026 is a Monday, so this is one full week
    slots = expand_to_dates([GERMAN, HIWI], valid_week(), date(2026, 10, 19), date(2026, 10, 25), user_id=1)
    assert len(slots) == 8                      # 6 German + 2 HiWi
    assert all(s.date.weekday() != 5 for s in slots)   # nothing on Saturday
    assert {s.activity_id for s in slots} == {1, 2}


def test_too_short():
    errors = check(valid_week() + [slot("HiWi", "Tue", (10, 0), (10, 30))])
    assert any("shorter than 60 min" in e for e in errors)


def test_timezone_is_stripped():
    # LLMs sometimes return "08:00Z". It must compare fine with the plain day window.
    s = WeekSlot.model_validate({"activity": "German", "day": "Mon", "start": "20:00Z", "end": "21:00+00:00"})
    assert s.start.tzinfo is None and s.end.tzinfo is None
    assert check([*valid_week()[1:], s]) == []


# ---------- blocked times, max days, multiple windows ----------

def test_blocked_time_every_day():
    rules = Rules(user_id=1, free_days=["Sat"], blocked_times=[{"start": "17:00", "end": "20:00"}])
    week = valid_week() + [slot("HiWi", "Tue", (18, 0), (19, 0))]
    errors = check_timetable([GERMAN, HIWI], week, rules)
    assert any("overlaps blocked time 17:00-20:00" in e for e in errors)


def test_blocked_time_only_on_some_days():
    rules = Rules(user_id=1, free_days=["Sat"],
                  blocked_times=[{"start": "14:00", "end": "16:00", "days": ["Tue"]}])
    # HiWi is on Mon and Wed 14:00-15:00, so a Tuesday-only block doesn't affect it
    assert check_timetable([GERMAN, HIWI], valid_week(), rules) == []


def test_max_days_per_week():
    hiwi = act(2, "HiWi", "weekly", 120, max_days_per_week=1)
    errors = check(valid_week(), (GERMAN, hiwi))
    assert "HiWi is on 2 days, max is 1" in errors


def test_two_preferred_windows():
    german = act(1, "German", "daily", 60, preferred_window=["morning", "night"])
    week = valid_week()
    week[0] = slot("German", "Mon", (8, 0), (9, 0))      # morning: fine
    week[1] = slot("German", "Tue", (14, 0), (15, 0))    # afternoon: not allowed
    errors = check(week, (german, HIWI))
    assert not any("on Mon" in e and "should start" in e for e in errors)
    assert any("on Tue" in e and "should start in the morning or night" in e for e in errors)


def test_single_window_string_still_works():
    assert act(1, "X", "daily", 60, preferred_window="night").preferred_window == ["night"]


def test_daily_with_max_days_becomes_weekly():
    from slot_planner.agents.schema import PlanExtraction
    from slot_planner.agents.timetable import to_engine

    plan = PlanExtraction.model_validate({
        "activities": [{"name": "Theory", "target_type": "daily", "target_min": 120,
                        "priority": 3, "max_days_per_week": 3}],
        "free_days": ["Sat"],
        "blocked_times": [{"start": "17:00", "end": "20:00", "days": []}],
    })
    activities, rules = to_engine(plan)
    assert activities[0].target_type == "weekly"
    assert activities[0].target_min == 360
    assert len(rules.blocked_times) == 1
