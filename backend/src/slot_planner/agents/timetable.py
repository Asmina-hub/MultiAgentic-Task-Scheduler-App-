"""Planner, part 2: turn validated activities into a template week.

The LLM proposes the week. The engine checks it. If the check finds problems,
they go back to the LLM as feedback, the same self-correction loop as build_plan.
"""


import json

from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from slot_planner.agents.llm import llm_init
from slot_planner.agents.prompt import TIMETABLE_SYSTEM
from slot_planner.agents.schema import PlanExtraction, WeekTimetable
from slot_planner.engine.model import Activity, Rules, WeekSlot
from slot_planner.engine.timetable_guards import check_timetable
import json
import logging

MAX_RETRIES = 3

log = logging.getLogger(__name__)

class TimetableError(Exception):
    """Raised when the LLM can't produce a week that passes the checks."""

def to_engine(plan: PlanExtraction, user_id: int = 1) -> tuple[list[Activity], Rules]:
    """LLM output becomes trusted engine data here.

    Code rules applied whatever the LLM said:
      - free days always win
      - a daily activity gets at least min_chunk_min (60) minutes
      - "1 hr daily, but only on 3 days" is really weekly: 3 x 60 = 180 min a week
    """
    rules = Rules(user_id=user_id, free_days=plan.free_days, blocked_times=plan.blocked_times)
    activities = []
    for i, a in enumerate(plan.activities, start=1):
        data = a.model_dump(exclude={"notes"})
        days = [d for d in a.allowed_days if d not in rules.free_days]
        data["allowed_days"] = days
        if a.target_type == "daily":
            per_day = max(a.target_min, rules.min_chunk_min)
            if a.max_days_per_week and a.max_days_per_week < len(days):
                data["target_type"] = "weekly"
                data["target_min"] = per_day * a.max_days_per_week
            else:
                data["target_min"] = per_day
        activities.append(Activity(id=i, user_id=user_id, **data))
    return activities, rules

def make_timetable(activities: list[Activity], rules: Rules, structured_llm=None) -> list[WeekSlot]:
    if structured_llm is None:
        structured_llm = llm_init().with_structured_output(WeekTimetable)

    payload = {
        "rules": {
            "day_window": f"{rules.day_start:%H:%M}-{rules.day_end:%H:%M}",
            "free_days": rules.free_days,
            "min_slot_minutes": rules.min_chunk_min,
            "blocked_times": [b.model_dump(mode="json") for b in rules.blocked_times],
        },
        "activities": [a.model_dump(mode="json", exclude={"id", "user_id", "locked"}) for a in activities],
    }
    messages = [
        ("system", TIMETABLE_SYSTEM),
        ("user", json.dumps(payload, indent=2)),
    ]
    last_problem = None
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            result = structured_llm.invoke(messages)
            if result is None:
                raise OutputParserException("model returned no structured output")
        except (ValidationError, OutputParserException) as e:
            last_problem = str(e)
            feedback = f"Your last answer was not valid JSON for the schema:\n{e}"
        else:
            errors = check_timetable(activities, result.slots, rules) #guardrail
            if not errors:
                return result.slots
            last_problem = "\n".join(errors)
            log.info("attempt %d: %d rule problems, asking the model to fix them", attempt, len(errors))
            # Show the model its own answer plus the problems, so it can fix just those
            messages.append(("assistant", result.model_dump_json()))
            feedback = (
                "Your timetable breaks these rules:\n"
                + "\n".join(f"- {e}" for e in errors)
                + "\nReturn the FULL corrected week, not only the changed slots."
            )
        messages.append(("user", feedback))

    raise TimetableError(f"no valid week after {MAX_RETRIES + 1} attempts:\n{last_problem}")




def print_week(week: list[WeekSlot]) -> None:
    for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        slots = sorted((s for s in week if s.day == day), key=lambda s: s.start)
        print(f"\n{day}")
        if not slots:
            print("  free")
        for s in slots:
            print(f"  {s.start:%H:%M}-{s.end:%H:%M}  {s.activity}")


if __name__ == "__main__":
    from slot_planner.agents.build_plan import build_plan

    october = """
    hiwi i have to work for 8 hrs a week, can compensate with sat and sunday , keep only for 2 days
    thesis main focus need to work a fixed time every day
    job applying either early morning or late evening like night every day 1hr
    upskill theory and upskilling project coding  alternate
    keep saturday free monday to friday and sunday
    night 1hr german A1
    5 to 8 evening should not be added to this plan everyday
    """
    plan = build_plan(october)
    print(plan)
    activities, rules = to_engine(plan)
    print(activities)
    print(rules)
    week = make_timetable(activities, rules)
    print_week(week)
