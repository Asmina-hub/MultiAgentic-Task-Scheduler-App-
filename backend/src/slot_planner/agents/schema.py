"""Shapes used on the agent side: messages and what the LLM extracts.

Agents may import from the engine (allowed direction). The engine never
imports from here.
"""

from datetime import datetime, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from slot_planner.engine.model import ALL_DAYS, TargetType, TimeWindow, Weekday

Intent = Literal["plan", "log", "replan", "question"]

# Fields with no safe default. If the LLM leaves one empty, we ask the user.
REQUIRED_FIELDS = ["target_type", "target_min", "priority"]


class Message(BaseModel):
    id: int
    user_id: int
    text: str = Field(min_length=1)
    intent: Intent | None = None  
    created_at: datetime


class ExtractedActivity(BaseModel):
    """One activity as the LLM understood it. None means 'user didn't say'."""

    name: str = Field(min_length=1)
    target_type: TargetType | None = None
    target_min: int | None = Field(default=None, gt=0)
    priority: int | None = Field(default=None, ge=1)
    fixed_time: time | None = None
    preferred_window: TimeWindow = "any"
    allowed_days: list[Weekday] = Field(default_factory=lambda: list(ALL_DAYS))
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

    def missing_fields(self) -> list[tuple[str, str]]:
        """(activity_name, field_name) for every required field the user didn't give."""
        return [
            (activity.name, field)
            for activity in self.activities
            for field in REQUIRED_FIELDS
            if getattr(activity, field) is None
        ]