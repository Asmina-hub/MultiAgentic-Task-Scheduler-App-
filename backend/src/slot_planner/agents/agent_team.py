from langchain_core.tools import BaseTool, StructuredTool
from langchain.agents import create_agent
from typing import Literal

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from slot_planner.agents.llm import llm_init
from slot_planner.agents.planner import today
from slot_planner.agents.prompt import COACH_AGENT, PLANNER_AGENT, SCHEDULE_AGENT,ORCHESTRATOR,ROUTER
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph


def _agent_as_tool(agent, name: str, description: str) -> BaseTool:
    async def run(request: str) -> str:
        result = await agent.ainvoke({"messages": [{"role": "user", "content": request}]})
        return result["messages"][-1].text
    
    return StructuredTool.from_function(coroutine=run, name=name, description=description)

Route = Literal["planner", "schedule", "coach", "direct"]


class TeamState(MessagesState):
    route: Route | None
    request: str | None


class RouteDecision(BaseModel):
    route: Route
    request: str = Field(description="Self-contained request for the specialist, or your reply for 'direct'.")


def _date_line() -> str:
    return f"\nToday is {today():%A, %Y-%m-%d}."

def build_team(tools, model=None, checkpointer=None):
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
    router_llm = model.with_structured_output(RouteDecision)

    async def router(state: TeamState) -> dict:
        prompt = [("system", ROUTER + _date_line()), *state["messages"]]
        decision = await router_llm.ainvoke(prompt)
        return {"route": decision.route, "request": decision.request}


    def specialist_node(agent):
        async def node(state: TeamState) -> dict:
            result = await agent.ainvoke({"messages": [{"role": "user", "content": state["request"]}]})
            return {"messages": [AIMessage(result["messages"][-1].text.strip())]}
        return node

    async def direct(state: TeamState) -> dict:
        return {"messages": [AIMessage(state["request"])]}

    graph = StateGraph(TeamState)
    graph.add_node("router", router)
    graph.add_node("planner", specialist_node(planner))
    graph.add_node("schedule", specialist_node(schedule))
    graph.add_node("coach", specialist_node(coach))
    graph.add_node("direct", direct)

    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", lambda state: state["route"], ["planner", "schedule", "coach", "direct"])
    for name in ["planner", "schedule", "coach", "direct"]:
        graph.add_edge(name, END)

    return graph.compile(checkpointer=checkpointer or InMemorySaver())

""" specialists = [
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
    return names """

