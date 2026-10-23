"""Model Context Protocol (MCP) JSON-RPC 2.0 Server.

Exposes project inspection tools, RAG search, and code editing capabilities
to any MCP-compliant client or agent over stdio or JSON-RPC.
"""

import sys
import json
from typing import Dict, Any, Optional
from agentic_framework.mcp.tools import tool_registry
from agentic_framework.config import settings
from agentic_framework.observability.logger import logger


class MCPServer:
    """Implements the standard MCP JSON-RPC protocol."""

    PROTOCOL_VERSION = "2024-11-05"

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch JSON-RPC 2.0 request."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if not method:
            return self._error(req_id, -32600, "Invalid Request: missing method")

        try:
            if method == "initialize":
                return self._handle_initialize(req_id, params)
            elif method == "tools/list":
                return self._handle_tools_list(req_id)
            elif method == "tools/call":
                return self._handle_tools_call(req_id, params)
            elif method == "ping":
                return {"jsonrpc": "2.0", "id": req_id, "result": {}}
            else:
                return self._error(req_id, -32601, f"Method not found: {method}")
        except Exception as e:
            return self._error(req_id, -32603, f"Internal error: {str(e)}")

    def _handle_initialize(self, req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": self.PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False},
                },
                "serverInfo": {
                    "name": "agentic-ai-framework-mcp",
                    "version": "1.0.0",
                },
            },
        }

    def _handle_tools_list(self, req_id: Any) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": tool_registry.list_tools()
            },
        }

    def _handle_tools_call(self, req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments", {})

        tool = tool_registry.get(name)
        if not tool:
            return self._error(req_id, -32602, f"Unknown tool: {name}")

        result_content = tool.func(**arguments)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": str(result_content),
                    }
                ],
                "isError": False,
            },
        }

    def _error(self, req_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }

    def run_stdio(self) -> None:
        """Run MCP Server loop reading lines from stdin and writing to stdout."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = self.handle_request(req)
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
            except Exception as e:
                err_resp = self._error(None, -32700, f"Parse error: {str(e)}")
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()


mcp_server = MCPServer()

if __name__ == "__main__":
    mcp_server.run_stdio()
