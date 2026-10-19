from collections import defaultdict
from datetime import date, time, timedelta
from itertools import pairwise

from slot_planner.engine.model import (
    ALL_DAYS,
    Activity,
    Rules,
    Slot,
    WeekSlot,
    to_minutes,
)

TOLERANCE_MIN = 15

WINDOWS = {
    "morning": (time(0, 0), time(12, 0)),
    "afternoon": (time(12, 0), time(17, 0)),
    "night": (time(17, 0), time(23, 59)),
}


def fmt(t: time) -> str:
    return t.strftime("%H:%M")


def check_timetable(activities: list[Activity], week: list[WeekSlot], rules: Rules) -> list[str]:
    """Return a list of human-readable problems. Empty list means the week is valid."""
    errors: list[str] = []
    by_name = {a.name: a for a in activities}

    for s in week:
        label = f"{s.activity} on {s.day} ({fmt(s.start)}-{fmt(s.end)})"

        # 1. Activity must exist
        activity = by_name.get(s.activity)
        if activity is None:
            errors.append(f"{label}: unknown activity. Use one of: {', '.join(by_name)}")
            continue

        # 2. Valid times inside the day window, on the 15-min grid
        if s.end <= s.start:
            errors.append(f"{label}: end must be after start")
            continue
        if s.start < rules.day_start or s.end > rules.day_end:
            errors.append(
                f"{label}: outside the day window {fmt(rules.day_start)}-{fmt(rules.day_end)}"
            )
        if to_minutes(s.start) % rules.slot_step_min or to_minutes(s.end) % rules.slot_step_min:
            errors.append(f"{label}: times must be on {rules.slot_step_min}-minute steps")
        if s.duration_min < rules.min_chunk_min:
            errors.append(f"{label}: shorter than {rules.min_chunk_min} min")

        # 3. Allowed days and free days
        if s.day in rules.free_days:
            errors.append(f"{label}: {s.day} is a free day")
        elif s.day not in activity.allowed_days:
            errors.append(f"{label}: {s.activity} is not allowed on {s.day}")

        # 5. Fixed time
        if activity.fixed_time and s.start != activity.fixed_time:
            errors.append(f"{label}: must start at {fmt(activity.fixed_time)}")

        # Preferred windows: must start inside at least one of them
        windows = activity.preferred_window
        if "any" not in windows and not any(
            WINDOWS[w][0] <= s.start < WINDOWS[w][1] for w in windows
        ):
            errors.append(f"{label}: should start in the {' or '.join(windows)}")

        # Blocked times: no slot may overlap a time the user keeps free
        for b in rules.blocked_times:
            if b.applies_to(s.day) and s.start < b.end and b.start < s.end:
                errors.append(f"{label}: overlaps blocked time {fmt(b.start)}-{fmt(b.end)}")

    # 4. Overlaps: sort each day by start, compare neighbours only
    per_day: dict[str, list[WeekSlot]] = defaultdict(list)
    for s in week:
        per_day[s.day].append(s)
    for day, slots in per_day.items():
        slots.sort(key=lambda s: s.start)
        for cur, nxt in pairwise(slots):
            if nxt.start < cur.end:
                errors.append(
                    f"{cur.activity} ({fmt(cur.start)}-{fmt(cur.end)}) overlaps "
                    f"{nxt.activity} ({fmt(nxt.start)}-{fmt(nxt.end)}) on {day}"
                )

    # 6. Totals
    for a in activities:
        mine = [s for s in week if s.activity == a.name]

        # Max days per week
        if a.max_days_per_week:
            days_used = {s.day for s in mine}
            if len(days_used) > a.max_days_per_week:
                errors.append(
                    f"{a.name} is on {len(days_used)} days, max is {a.max_days_per_week}"
                )

        if a.target_type == "weekly":
            total = sum(s.duration_min for s in mine)
            if abs(total - a.target_min) > TOLERANCE_MIN:
                errors.append(f"{a.name} has {total} min this week, needs {a.target_min}")
        else:
            for day in a.allowed_days:
                if day in rules.free_days:
                    continue
                total = sum(s.duration_min for s in mine if s.day == day)
                if abs(total - a.target_min) > TOLERANCE_MIN:
                    errors.append(f"{a.name} on {day} has {total} min, needs {a.target_min}")

    return errors

def expand_to_dates(
    activities: list[Activity],
    week: list[WeekSlot],
    start: date,
    end: date,
    user_id: int,
) -> list[Slot]:
    """Stamp the template week onto every date ie add the day also like monday tuesday wed"""
    ids = {a.name: a.id for a in activities}
    slots: list[Slot] = []
    day = start
    while day <= end:
        weekday = ALL_DAYS[day.weekday()]  # Monday is 0
        for s in week:
            if s.day == weekday:
                slots.append(Slot(
                    user_id=user_id,
                    activity_id=ids[s.activity],
                    date=day,
                    start=s.start,
                    end=s.end,
                ))
        day += timedelta(days=1)
    return slots