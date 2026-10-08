from pydantic import BaseModel, Field

from slot_planner.agents.schema import Option, Question, PlanExtraction
from slot_planner.engine.model import TargetType 

AUTO ='auto'
OTHER ='other'

Skip = tuple[str, str]
 
EXTRA_OPTIONS = [
    Option(label="Decide for me", value=AUTO),
    Option(label="Other", value=OTHER),
]
 
TYPE_OPTIONS = [
    Option(label="Every day", value="daily"),
    Option(label="Total per week", value="weekly"),
] + EXTRA_OPTIONS
 
DAILY_DURATION_OPTIONS = [
    Option(label="30 min", value=30),
    Option(label="1 hr", value=60),
    Option(label="2 hrs", value=120),
    Option(label="3 hrs", value=180),
    Option(label="4 hrs", value=240),
] + EXTRA_OPTIONS
 
WEEKLY_DURATION_OPTIONS = [
    Option(label="2 hrs", value=120),
    Option(label="5 hrs", value=300),
    Option(label="10 hrs", value=600),
    Option(label="20 hrs", value=1200),
] + EXTRA_OPTIONS
 
PRIORITY_KEY: Skip = ("*", "priority")

OTHER_SYSTEM = """
The user answered one question about their plan in their own words.
Extract only the value for the field asked about.
Convert hours to minutes: "2.5 hrs" -> 150.
"every day", "daily" -> "daily". "per week", "a week" -> "weekly".
If the answer doesn't contain a usable value, return null. Never guess.
"""
class OtherAnswer(BaseModel):
    target_type: TargetType | None = None
    target_min: int | None = Field(default=None, gt=0)
 
 
def make_question(plan:PlanExtraction,skipped ):
    questions =[]
    for a in plan.activities:
        if a.target_type is None and (a.name, "target_type") not in skipped:
                # Ask the type first. Duration comes next round, with the right options.
                questions.append(Question(
                    activity=a.name,
                    field="target_type",
                    text=f"Is {a.name} every day, or a total per week?",
                    options=TYPE_OPTIONS,
                ))
        elif (
            a.target_type is not None
            and a.target_min is None
            and (a.name, "target_min") not in skipped
        ):
            daily = a.target_type == "daily"
            questions.append(Question(
                activity=a.name,
                field="target_min",
                text=f"How long {'per day' if daily else 'per week'} for {a.name}?",
                options=DAILY_DURATION_OPTIONS if daily else WEEKLY_DURATION_OPTIONS,
            ))
    unranked = [a.name for a in plan.activities if a.priority is None]
    if unranked and PRIORITY_KEY not in skipped:
        questions.append(Question(
            field="priority",
            text="What's most important? Pick one or two. The rest get equal priority.",
            options=[Option(label=name, value=name) for name in unranked]
            + [Option(label="All equal", value=AUTO)],
            multi_select=True,
        ))
 
    return questions

