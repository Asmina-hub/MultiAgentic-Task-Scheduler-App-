import asyncio

from langchain_mcp_adapters.tools import load_mcp_tools

from slot_planner.agents.mcp_tools import planner_client
from slot_planner.agents.agent_team import build_team #routed_to
from dotenv import load_dotenv

from slot_planner.config import BACKEND_DIR

load_dotenv(BACKEND_DIR / ".env")

"""async def main():
    async with planner_client().session("planner") as session:
        tools = await load_mcp_tools(session)
        team = build_team(tools)
        config = {"configurable": {"thread_id": "terminal"}}
        seen = 0
        while text := input("\nyou > ").strip():
            result = await team.ainvoke({"messages": [{"role": "user", "content": text}]}, config)
            new_messages = result["messages"][seen:]
            seen = len(result["messages"])
            print("   [routed to:", routed_to(new_messages) or "answered directly", "]")
            print("bot >", result["messages"][-1].text)"""

async def main():
    async with planner_client().session("planner") as session:
        tools = await load_mcp_tools(session)
        team = build_team(tools)
        config = {
            "configurable": {"thread_id": "terminal"},
            "run_name": "slot-planner-team",
            "tags": ["chat"],
            "metadata": {"thread_id": "terminal"},
        }
        while text := input("\nyou > ").strip():
            result = await team.ainvoke({"messages": [{"role": "user", "content": text}]}, config)
            print(f"   [route: {result['route']} | request: {result['request']}]")
            print("bot >", result["messages"][-1].text)

if __name__ == "__main__":
    asyncio.run(main())