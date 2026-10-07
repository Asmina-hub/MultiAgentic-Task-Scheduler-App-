from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from slot_planner.agents.llm import llm_init
from slot_planner.agents.prompt import PLAN_BUILDER_SYSTEM
from slot_planner.agents.schema import PlanExtraction

MAX_RETRIES = 2


class PlanExtractionError(Exception):
    """Raised when the LLM can't produce a valid plan."""


def build_plan(text: str, structured_llm=None) -> PlanExtraction:
   
    if structured_llm is None:
        structured_llm = llm_init().with_structured_output(PlanExtraction)

    messages = [
        ("system", PLAN_BUILDER_SYSTEM),
        ("user", text),
    ]
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            result = structured_llm.invoke(messages)
            if result is None:
                # Some models answer in plain text instead of the schema
                raise OutputParserException("model returned no structured output")
            return result
        except (ValidationError, OutputParserException) as e:
            last_error = e
            messages.append((
                "user",
                f"Your last answer was invalid:\n{e}\n"
                "Return the full corrected output. Follow the rules and the schema exactly.",
            ))

    raise PlanExtractionError(
        f"no valid plan after {MAX_RETRIES + 1} attempts"
    ) from last_error


if __name__ == "__main__":
    october = """
    hiwi i have to work for 8 hrs a week, can compensate with sat and sunday also
    thesis main focus need to work a fixed time every day
    job applying either morning or evening like night every day 1hr
    upskill theory
    upskilling project coding daily some
    keep saturday free monday to friday and sunday
    night 1hr german A1
    """
    plan = build_plan(october)
    print(plan.model_dump_json(indent=2))
    print("missing:", plan.missing_fields())
