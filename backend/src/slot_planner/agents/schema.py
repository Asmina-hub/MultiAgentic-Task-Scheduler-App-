"""Shapes used on the agent side: messages and what the LLM extracts.

Agents may import from the engine (allowed direction). The engine never
imports from here.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from slot_planner.engine.model import (
    ALL_DAYS,
    BlockedTime,
    NaiveTime,
    TargetType,
    Weekday,
    WeekSlot,
    Windows,
)

Intent = Literal["plan", "log", "replan", "question"]



class Message(BaseModel):
    id: int
    user_id: int
    text: str = Field(min_length=1)
    intent: Intent | None = None  
    created_at: datetime


class ExtractedActivity(BaseModel):
    """One activity as the LLM understood it. The LLM fills in anything the user didn't say."""

    name: str = Field(min_length=1)
    target_type: TargetType 
    target_min: int  = Field( gt=0)
    priority: int = Field( ge=1)
    fixed_time: NaiveTime | None = None
    preferred_window: Windows = Field(default_factory=lambda: ["any"])
    allowed_days: list[Weekday] = Field(default_factory=lambda: list(ALL_DAYS))
    max_days_per_week: int | None = Field(default=None, ge=1, le=7)
    notes: str | None = None

    @field_validator("allowed_days")
    @classmethod
    def no_duplicate_days(cls, days: list[Weekday]) -> list[Weekday]:
        if len(days) != len(set(days)):
            raise ValueError("allowed_days contains duplicates")
        # An empty list from the LLM means "no restriction"
        return days or list(ALL_DAYS)


class PlanExtraction(BaseModel):
    """What the plan builder LLM returns."""

    activities: list[ExtractedActivity]
    free_days: list[Weekday] = Field(default_factory=list)
    blocked_times: list[BlockedTime] = Field(default_factory=list)


class WeekTimetable(BaseModel):
    """What the timetable LLM returns: one template week."""

    slots: list[WeekSlot]
