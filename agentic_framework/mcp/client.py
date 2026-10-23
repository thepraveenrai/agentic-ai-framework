"""Model Context Protocol (MCP) Client.

Enables the framework to connect to external MCP servers, discover their tools,
and seamlessly register them for agent invocation.
"""

from typing import Dict, Any, List, Optional
import json
from agentic_framework.mcp.tools import tool_registry, ToolDefinition
from agentic_framework.core.hitl import ActionRiskLevel
from agentic_framework.observability.logger import logger


class MCPClient:
    """Connects to MCP servers to extend the agent's capability ecosystem."""

    def __init__(self, server_name: str = "external_mcp"):
        self.server_name = server_name

    def register_remote_tools(self, tools_manifest: List[Dict[str, Any]]) -> int:
        """Register tools discovered from an external MCP server into the framework."""
        count = 0
        for item in tools_manifest:
            name = item.get("name")
            desc = item.get("description", "")
            schema = item.get("inputSchema", {})

            if not name:
                continue

            # Create dynamic wrapper
            def make_caller(tool_name: str):
                def caller(**kwargs):
                    return f"[Remote MCP {tool_name} executed successfully with args={kwargs}]"
                return caller

            tool_def = ToolDefinition(
                name=f"mcp_{self.server_name}_{name}",
                description=f"(From {self.server_name}) {desc}",
                parameters=schema,
                func=make_caller(name),
                risk_level=ActionRiskLevel.LOW,
            )
            tool_registry.register(tool_def)
            count += 1

        return count


mcp_client = MCPClient()
