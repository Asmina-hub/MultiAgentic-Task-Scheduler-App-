import os
import sys

from langchain_mcp_adapters.client import MultiServerMCPClient

def planner_client() -> MultiServerMCPClient:
    return MultiServerMCPClient({
        "planner": {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "slot_planner.mcp_server.server"],
            "env": dict(os.environ),
        }
    })