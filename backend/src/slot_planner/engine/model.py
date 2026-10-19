from datetime import date, time
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

MINUTES_PER_DAY = 24 * 60

# A plain clock time like 09:30. LLMs sometimes send "09:30Z" or "09:30+00:00",
# which gives a timezone-aware time that can't be compared with plain ones.
# This strips the timezone, so every time in the app is the same kind.
NaiveTime = Annotated[time, AfterValidator(lambda t: t.replace(tzinfo=None))]
 
def to_minutes(t: time) -> int:
    """Minutes since midnight, e.g. 14:30 -> 870."""
    return t.hour * 60 + t.minute
 

Weekday = Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TargetType = Literal["daily", "weekly"]
TimeWindow = Literal["morning", "afternoon", "night", "any"]
SlotStatus = Literal["planned", "done", "skipped"]
SlotSource = Literal["plan", "replan"]
ALL_DAYS: list[Weekday] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _as_list(value):
    """Accept a single window ("night") as well as a list (["morning", "night"])."""
    return [value] if isinstance(value, str) else value


# One or more time windows an activity may start in. ["any"] means no preference.
Windows = Annotated[list[TimeWindow], BeforeValidator(_as_list)]

class EngineModel(BaseModel):
    model_config = ConfigDict(extra="forbid")



class Activity(EngineModel):
    id : int
    user_id : int
    name    : str = Field(min_length=1)      
    target_type  : TargetType
    target_min   : int = Field(gt=0)     
    priority      : int = Field(ge=1)   
    fixed_time   : NaiveTime | None = None     
    preferred_window  : Windows = Field(default_factory=lambda: ["any"])
    allowed_days: list[Weekday] = Field(default_factory=lambda: list(ALL_DAYS))
    max_days_per_week: int | None = Field(default=None, ge=1, le=7)
    max_min_per_day: int | None = Field(default=None, gt=0, le=MINUTES_PER_DAY)

    @computed_field
    @property
    def locked(self)-> bool:
        return ( self.fixed_time is not None)

    @model_validator(mode="after")
    def check_daily_target_fits_in_a_day(self) -> Activity:
        if self.target_type == "daily" and self.target_min > MINUTES_PER_DAY:
            raise ValueError("a daily target cannot exceed 1440 minutes")
        return self



    @field_validator("allowed_days")
    @classmethod
    def check_allowed_days(cls, days: list[Weekday]) -> list[Weekday]:
        if not days:
            raise ValueError("allowed_days cannot be empty")
        if len(days) != len(set(days)):
            raise ValueError("allowed_days contains duplicates")
        return days

    

class Slot(EngineModel):
    id: int | None = None
    user_id: int
    activity_id: int
    date: date
    start: NaiveTime
    end: NaiveTime
    status: SlotStatus = "planned"
    source: SlotSource = "plan"   


    @model_validator(mode="after")
    def check_date_start_end(self)-> Slot:
        if   self.start >= self.end:
            raise ValueError("slot end must be after start")

        return self

    @property
    def duration_min(self) -> int:
        return to_minutes(self.end) - to_minutes(self.start)
 
        
class ActivityLog(EngineModel):
    id: int
    user_id: int
    activity_id: int
    date: date
    minutes: int = Field(gt=0, le=MINUTES_PER_DAY)
    slot_id: int | None = None
 
 
class BlockedTime(EngineModel):
    """A time range that must stay free, e.g. gym 17:00-20:00. No days means every day."""

    start: NaiveTime
    end: NaiveTime
    days: list[Weekday] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_order(self) -> BlockedTime:
        if self.end <= self.start:
            raise ValueError("blocked time must end after it starts")
        return self

    def applies_to(self, day: Weekday) -> bool:
        return not self.days or day in self.days


class Rules(EngineModel):
    user_id: int
    free_days: list[Weekday] = Field(default_factory=lambda: ["Sat"])
    week_starts_on: Weekday = "Mon"
    day_start: NaiveTime = time(8, 0)
    day_end: NaiveTime = time(22, 0)
    slot_step_min: int = Field(default=15, gt=0, le=60)
    min_chunk_min: int = Field(default=60, gt=0)
    blocked_times: list[BlockedTime] = Field(default_factory=list)
 
    @model_validator(mode="after")
    def check_rules(self) -> Rules:
        if self.day_end <= self.day_start:
            raise ValueError("day_end must be after day_start")
        if self.min_chunk_min % self.slot_step_min != 0:
            raise ValueError("min_chunk_min must be a multiple of slot_step_min")
        if len(set(self.free_days)) == len(ALL_DAYS):
            raise ValueError("at least one day must not be free")
        return self
    
class WeekSlot(EngineModel):
    """One block in the template week. No date yet, just a weekday."""

    activity: str = Field(min_length=1)
    day: Weekday
    start: NaiveTime
    end: NaiveTime

    @property
    def duration_min(self) -> int:
        return to_minutes(self.end) - to_minutes(self.start)