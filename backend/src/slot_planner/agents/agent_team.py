from langchain_core.tools import BaseTool, StructuredTool
from langchain.agents import create_agent

from slot_planner.agents.llm import llm_init
from slot_planner.agents.planner import today
from slot_planner.agents.prompt import COACH_AGENT, PLANNER_AGENT, SCHEDULE_AGENT,ORCHESTRATOR
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import AIMessage


def _agent_as_tool(agent, name: str, description: str) -> BaseTool:
    async def run(request: str) -> str:
        result = await agent.ainvoke({"messages": [{"role": "user", "content": request}]})
        return result["messages"][-1].text
    
    return StructuredTool.from_function(coroutine=run, name=name, description=description)


def _date_line() -> str:
    return f"\nToday is {today():%A, %Y-%m-%d}."

def build_team(tools, model=None):
    model =model or llm_init()
    t = {tool.name: tool for tool in tools}

    planner = create_agent(
        model,
        tools=[t["create_plan"]],
        system_prompt=PLANNER_AGENT + _date_line(),
    )
    schedule = create_agent(
        model,
        tools=[t["get_today"], t["get_week"], t["mark_slot"]],
        system_prompt=SCHEDULE_AGENT + _date_line(),
    )
    coach = create_agent(
        model,
        tools=[t["get_today"], t["get_week"]],
        system_prompt=COACH_AGENT + _date_line(),
    )

    specialists = [
    _agent_as_tool(planner, "planner",
                    "Creates a new calendar from the user's description of their tasks."),
    _agent_as_tool(schedule, "schedule",
                    "Answers questions about the existing calendar and marks blocks done or skipped."),
    _agent_as_tool(coach, "coach",
                    "Writes morning briefs, motivation and daily or weekly reviews."),
    ]

    return create_agent(
        model,
        tools=specialists,
        system_prompt=ORCHESTRATOR + _date_line(),
        checkpointer=InMemorySaver(),
    )


SPECIALISTS = ("planner", "schedule", "coach")


def routed_to(messages: list) -> list[str]:
    names = []
    for m in messages:
        if isinstance(m, AIMessage):
            for call in m.tool_calls:
                if call["name"] in SPECIALISTS:
                    names.append(call["name"])
    return names
