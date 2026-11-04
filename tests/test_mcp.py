"""Unit Tests for MCP Tools and JSON-RPC Server."""

import pytest
from agentic_framework.mcp.tools import tool_registry
from agentic_framework.mcp.server import mcp_server


def test_mcp_tools_registration():
    tools = tool_registry.list_tools()
    tool_names = [t["name"] for t in tools]
    assert "read_file" in tool_names
    assert "apply_patch" in tool_names
    assert "run_shell" in tool_names
    assert "search_code" in tool_names


def test_mcp_server_initialize():
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {},
    }
    resp = mcp_server.handle_request(req)
    assert resp["id"] == 1
    assert "protocolVersion" in resp["result"]
    assert resp["result"]["serverInfo"]["name"] == "agentic-ai-framework-mcp"


def test_mcp_server_tools_list():
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    resp = mcp_server.handle_request(req)
    assert resp["id"] == 2
    assert "tools" in resp["result"]
    assert len(resp["result"]["tools"]) > 0


def test_mcp_server_tools_call():
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "analyze_project",
            "arguments": {},
        },
    }
    resp = mcp_server.handle_request(req)
    assert resp["id"] == 3
    assert not resp["result"]["isError"]
    assert "languages" in resp["result"]["content"][0]["text"].lower()


def test_mcp_server_tools_call_missing_or_invalid_name():
    # Missing name
    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {},
    }
    resp = mcp_server.handle_request(req)
    assert resp["id"] == 4
    assert "error" in resp
    assert resp["error"]["code"] == -32602

    # None name
    req_none = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": None},
    }
    resp_none = mcp_server.handle_request(req_none)
    assert resp_none["id"] == 5
    assert "error" in resp_none
    assert resp_none["error"]["code"] == -32602
