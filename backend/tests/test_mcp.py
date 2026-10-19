"""Talk to the MCP server exactly like an agent would, but in memory and with a temp database."""

import asyncio
from datetime import date, time, timedelta
from functools import partial

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

import slot_planner.mcp_server.server as server
from slot_planner.db import database
from slot_planner.engine.model import Activity, Rules, Slot


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Point the server's database functions at a throwaway file."""
    path = tmp_path / "test.db"
    monkeypatch.setattr(server, "get_slots", partial(database.get_slots, db_path=path))
    monkeypatch.setattr(server, "db_mark_slot", partial(database.mark_slot, db_path=path))
    return path


def seed(path, day):
    """Save a small plan with one Thesis block on `day`."""
    acts = [Activity(id=1, user_id=1, name="Thesis", target_type="daily", target_min=60, priority=1)]
    slots = [Slot(user_id=1, activity_id=1, date=day, start=time(9), end=time(10))]
    database.save_plan("t", acts, Rules(user_id=1), slots, day, day, db_path=path)


def call(tool, args=None):
    async def go():
        async with Client(server.mcp) as client:
            return await client.call_tool(tool, args or {})
    return asyncio.run(go())


def test_tools_are_listed():
    async def go():
        async with Client(server.mcp) as client:
            return {t.name for t in await client.list_tools()}
    assert asyncio.run(go()) == {"create_plan", "get_today", "get_week", "mark_slot"}


def test_get_today(db):
    seed(db, server.today())
    result = call("get_today")
    assert result.structured_content["result"][0]["activity"] == "Thesis"


def test_get_week_finds_a_day_in_that_week(db):
    monday = date(2026, 10, 19)
    seed(db, monday + timedelta(days=2))                      # Wednesday
    result = call("get_week", {"day": "2026-10-23"})          # Friday, same week
    assert len(result.structured_content["result"]) == 1


def test_mark_slot(db):
    seed(db, server.today())
    slot_id = call("get_today").structured_content["result"][0]["id"]
    result = call("mark_slot", {"slot_id": slot_id, "status": "done"})
    assert result.structured_content == {"slot_id": slot_id, "status": "done"}
    assert call("get_today").structured_content["result"][0]["status"] == "done"


def test_mark_unknown_slot_is_a_tool_error(db):
    seed(db, server.today())
    with pytest.raises(ToolError, match="No block with id 999"):
        call("mark_slot", {"slot_id": 999, "status": "done"})


def test_bad_status_is_rejected(db):
    with pytest.raises(ToolError):
        call("mark_slot", {"slot_id": 1, "status": "maybe"})