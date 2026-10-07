from datetime import date, time
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

MINUTES_PER_DAY = 24 * 60
 
def to_minutes(t: time) -> int:
    """Minutes since midnight, e.g. 14:30 -> 870."""
    return t.hour * 60 + t.minute
 

Weekday = Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TargetType = Literal["daily", "weekly"]
TimeWindow = Literal["morning", "afternoon", "night", "any"]
SlotStatus = Literal["planned", "done", "skipped", "replaced"]
SlotSource = Literal["plan", "replan"]
ALL_DAYS: list[Weekday] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

class EngineModel(BaseModel):
    model_config = ConfigDict(extra="forbid")



class Activity(EngineModel):
    id : int
    user_id : int
    name    : str = Field(min_length=1)      
    target_type  : TargetType
    target_min   : int = Field(gt=0)     
    priority      : int = Field(ge=1)   
    fixed_time   : time | None = None     
    preferred_window  : TimeWindow = "any"
    allowed_days: list[Weekday] = Field(default_factory=lambda: list(ALL_DAYS))
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
    id: int
    user_id: int
    activity_id: int
    date: date
    start: time
    end: time
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
 
 
class Rules(EngineModel):
    user_id: int
    free_days: list[Weekday] = Field(default_factory=lambda: ["Sat"])
    week_starts_on: Weekday = "Mon"
    day_start: time = time(8, 0)
    day_end: time = time(22, 0)
    slot_step_min: int = Field(default=15, gt=0, le=60)
    min_chunk_min: int = Field(default=30, gt=0)
 
    @model_validator(mode="after")
    def check_rules(self) -> Rules:
        if self.day_end <= self.day_start:
            raise ValueError("day_end must be after day_start")
        if self.min_chunk_min % self.slot_step_min != 0:
            raise ValueError("min_chunk_min must be a multiple of slot_step_min")
        if len(set(self.free_days)) == len(ALL_DAYS):
            raise ValueError("at least one day must not be free")
        return self
