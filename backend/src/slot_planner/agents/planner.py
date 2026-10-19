"""The whole planning pipeline in one function: text in, saved calendar out.

This is what the Planner agent will call as a tool.
"""

import calendar
from datetime import date, datetime

from slot_planner.agents.build_plan import build_plan
from slot_planner.agents.timetable import make_timetable, print_week, to_engine
from slot_planner.db.database import get_slots, save_plan
from slot_planner.engine.timetable_guards import expand_to_dates


def today() -> date:
    """Today's date in your local timezone."""
    return datetime.now().astimezone().date()


def end_of_month(day: date) -> date:
    last = calendar.monthrange(day.year, day.month)[1]
    return day.replace(day=last)


def create_plan(text: str, start: date | None = None, end: date | None = None, user_id: int = 1) -> int:
    """Extract activities, build a template week, stamp it onto real dates and save it.

    By default the plan runs from today to the end of this month. Returns the plan id.
    """
    start = start or today()
    end = end or end_of_month(start)

    plan = build_plan(text)                                   # LLM call 1
    activities, rules = to_engine(plan, user_id)              # trust boundary
    week = make_timetable(activities, rules)                  # LLM call 2 + guardrails
    slots = expand_to_dates(activities, week, start, end, user_id)
   
    return save_plan(text, activities, rules, slots, start, end)


if __name__ == "__main__":
    october = """
    hiwi i have to work for 8 hrs a week, can compensate with sat and sunday , keep only for 2 days
    thesis main focus need to work a fixed time every day
    job applying either early morning or late evening like night every day 1hr
    upskill theory and upskilling project coding  alternate
    keep saturday free monday to friday and sunday
    night 1hr german A1
    5 to 8 evening should not be added to this plan everyday
    """
    plan_id = create_plan(october)
    day = today()
    print(f"\nSaved plan {plan_id}. Today ({day:%a %d %b}):")
    for s in get_slots(day, day):
        print(f"  [{s.id}] {s.start:%H:%M}-{s.end:%H:%M}  {s.activity}  ({s.status})")
