"""MCP server: exposes planning and the calendar as tools any agent can call.

Run it on its own (stdio):   uv run python -m slot_planner.mcp_server.server
Or over HTTP for testing:    uv run python -m slot_planner.mcp_server.server --http
"""

import logging
import sys
from datetime import date, timedelta
from typing import Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel

from slot_planner.agents.build_plan import PlanExtractionError
from slot_planner.agents.planner import create_plan as run_planner
from slot_planner.agents.planner import end_of_month, today
from slot_planner.agents.timetable import TimetableError
from slot_planner.db.database import SlotView, get_slots
from slot_planner.db.database import mark_slot as db_mark_slot


logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

mcp = FastMCP(
    "slot-planner",
    instructions=(
        "Tools for a personal daily planner. Use create_plan when the user describes "
        "their tasks for a period. Use get_today / get_week to answer questions about "
        "the schedule. Use mark_slot when the user says they finished or skipped something. "
        "Dates are YYYY-MM-DD."
    ),
)
class PlanCreated(BaseModel):
    plan_id: int
    start: date
    end: date
    first_week: list[SlotView]


class SlotUpdated(BaseModel):
    slot_id: int
    status: str


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True})
def create_plan(description: str, start: date | None = None, end: date | None = None) -> PlanCreated:
    """Build a new calendar from the user's own description of their tasks.

    Use this when the user describes what they want to do over a period, for example
    "thesis every morning, HiWi 8 hrs a week on 2 days, keep Saturday free".
    Pass the user's description as they wrote it. This REPLACES the current plan.
    start and end default to today and the end of this month. Takes 30 to 60 seconds.
    Returns the plan id and the slots of the first 7 days.
    """
    start = start or today()
    end = end or end_of_month(start)
    try:
        plan_id = run_planner(description, start, end)
    except (PlanExtractionError, TimetableError) as e:
        raise ToolError(f"Could not build a valid plan: {e}") from e
    first_week = get_slots(start, min(end, start + timedelta(days=6)))
    return PlanCreated(plan_id=plan_id, start=start, end=end, first_week=first_week)


@mcp.tool(annotations={"readOnlyHint": True})
def get_today() -> list[SlotView]:
    """Today's planned blocks in time order, with each block's id, activity and status.

    Use this for questions like "what's on today?" or "what's next?".
    """
    day = today()
    return get_slots(day, day)


@mcp.tool(annotations={"readOnlyHint": True})
def get_week(day: date | None = None) -> list[SlotView]:
    """All blocks of the week (Monday to Sunday) that contains the given day.

    day defaults to today. Use this for "what does my week look like?" or questions
    about a specific day, e.g. pass the date of next Tuesday.
    """
    day = day or today()
    monday = day - timedelta(days=day.weekday())
    return get_slots(monday, monday + timedelta(days=6))


@mcp.tool(annotations={"readOnlyHint": False, "idempotentHint": True})
def mark_slot(slot_id: int, status: Literal["done", "skipped", "planned"]) -> SlotUpdated:
    """Mark one block as done or skipped (or back to planned).

    Use the slot id from get_today or get_week. Call this when the user says they
    finished, did, or skipped something.
    """
    if not db_mark_slot(slot_id, status):
        raise ToolError(f"No block with id {slot_id}. Call get_today or get_week to find the right id.")
    return SlotUpdated(slot_id=slot_id, status=status)


if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="http", host="127.0.0.1", port=8001)
    else:
        mcp.run()