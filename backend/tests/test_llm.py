import pytest
from pydantic import BaseModel
from slot_planner.agents.llm import llm_init


pytestmark = pytest.mark.integration


class Greeting(BaseModel):
    name: str
    language: str


@pytest.mark.parametrize("provider", ["tud", "anthropic"])
def test_structured_output(provider):
    # 1. Get the LLM object for this provider
    llm = llm_init(provider, temperature=0, fallback=False)

    # 2. Wrap it so it returns a Greeting instead of plain text
    structured_llm = llm.with_structured_output(Greeting)

    # 3. Call it
    result = structured_llm.invoke("Hallo, ich bin Asmina")
    print(provider, type(result), result)

    # 4. Check the result
    assert isinstance(result, Greeting)
    assert result.name == "Asmina"
