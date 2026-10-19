"""SQLite storage for plans, activities and slots.

Plain sqlite3 from the standard library, no ORM. Engine models go in,
engine models (or small read views) come out.
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, time
from pathlib import Path

from pydantic import BaseModel

from slot_planner.config import BACKEND_DIR
from slot_planner.engine.model import Activity, Rules, Slot, SlotStatus

DB_PATH = BACKEND_DIR / "slot_planner.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS plans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    source_text   TEXT    NOT NULL,
    start_date    TEXT    NOT NULL,
    end_date      TEXT    NOT NULL,
    free_days     TEXT    NOT NULL,                  -- JSON list, e.g. ["Sat"]
    blocked_times TEXT    NOT NULL,                  -- JSON list of {start, end, days}
    status        TEXT    NOT NULL DEFAULT 'active', -- active | archived
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS activities (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id           INTEGER NOT NULL REFERENCES plans(id),
    user_id           INTEGER NOT NULL,
    name              TEXT    NOT NULL,
    target_type       TEXT    NOT NULL,
    target_min        INTEGER NOT NULL,
    priority          INTEGER NOT NULL,
    fixed_time        TEXT,
    preferred_window  TEXT    NOT NULL,              -- JSON list, e.g. ["morning","night"]
    allowed_days      TEXT    NOT NULL,              -- JSON list, e.g. ["Mon","Tue"]
    max_days_per_week INTEGER
);

CREATE TABLE IF NOT EXISTS slots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    activity_id INTEGER NOT NULL REFERENCES activities(id),
    date        TEXT    NOT NULL,                    -- 2026-10-19
    start       TEXT    NOT NULL,                    -- 08:00
    end         TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'planned'   -- planned | done | skipped
);

CREATE INDEX IF NOT EXISTS idx_slots_user_date ON slots(user_id, date);
"""


class SlotView(BaseModel):
    """A slot as the outside world sees it: with the activity name, ready to show."""

    id: int
    date: date
    start: time
    end: time
    activity: str
    status: SlotStatus


@contextmanager
def connect(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    """Open a connection, commit if everything worked, roll back if not."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row          # rows behave like dicts: row["name"]
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def save_plan(
    source_text: str,
    activities: list[Activity],
    rules: Rules,
    slots: list[Slot],
    start: date,
    end: date,
    db_path: Path = DB_PATH,
) -> int:
    """Save a new plan and make it the active one. Returns the new plan id.

    Everything happens in one transaction: if any insert fails, nothing is saved.
    """
    user_id = rules.user_id
    init_db(db_path)
    with connect(db_path) as conn:
        # Only one active plan at a time
        conn.execute(
            "UPDATE plans SET status = 'archived' WHERE user_id = ? AND status = 'active'",
            (user_id,),
        )
        plan_id = conn.execute(
            "INSERT INTO plans (user_id, source_text, start_date, end_date, free_days, "
            "blocked_times, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                user_id, source_text, start.isoformat(), end.isoformat(),
                json.dumps(rules.free_days),
                json.dumps([b.model_dump(mode="json") for b in rules.blocked_times]),
                datetime.now().astimezone().isoformat(),
            ),
        ).lastrowid

        # The engine numbered activities 1, 2, 3... The database gives them real ids.
        id_map: dict[int, int] = {}
        for a in activities:
            new_id = conn.execute(
                "INSERT INTO activities (plan_id, user_id, name, target_type, target_min, priority, "
                "fixed_time, preferred_window, allowed_days, max_days_per_week) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    plan_id, user_id, a.name, a.target_type, a.target_min, a.priority,
                    a.fixed_time.strftime("%H:%M") if a.fixed_time else None,
                    json.dumps(a.preferred_window), json.dumps(a.allowed_days),
                    a.max_days_per_week,
                ),
            ).lastrowid
            id_map[a.id] = new_id

        conn.executemany(
            "INSERT INTO slots (user_id, activity_id, date, start, end, status) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (user_id, id_map[s.activity_id], s.date.isoformat(),
                 s.start.strftime("%H:%M"), s.end.strftime("%H:%M"), s.status)
                for s in slots
            ],
        )
    return plan_id


def get_slots(start: date, end: date, user_id: int = 1, db_path: Path = DB_PATH) -> list[SlotView]:
    """All slots of the active plan between two dates (inclusive), in time order."""
    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.date, s.start, s.end, s.status, a.name AS activity
            FROM slots s
            JOIN activities a ON a.id = s.activity_id
            JOIN plans p      ON p.id = a.plan_id
            WHERE s.user_id = ? AND p.status = 'active' AND s.date BETWEEN ? AND ?
            ORDER BY s.date, s.start
            """,
            (user_id, start.isoformat(), end.isoformat()),
        ).fetchall()
    return [SlotView.model_validate(dict(r)) for r in rows]


def mark_slot(slot_id: int, status: SlotStatus, user_id: int = 1, db_path: Path = DB_PATH) -> bool:
    """Set a slot to planned, done or skipped. Returns False if the slot doesn't exist."""
    init_db(db_path)
    with connect(db_path) as conn:
        cur = conn.execute(
            "UPDATE slots SET status = ? WHERE id = ? AND user_id = ?",
            (status, slot_id, user_id),
        )
    return cur.rowcount == 1
