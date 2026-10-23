"""Model Context Protocol (MCP) Tools.

Standardized tool definitions exposing filesystem operations, code search (RAG),
patch application, terminal execution, and test runners with Guardrails and HITL.
"""

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from agentic_framework.config import settings
from agentic_framework.core.hitl import hitl_manager, ActionRiskLevel
from agentic_framework.guardrails.output_guardrails import output_guardrails
from agentic_framework.rag.retriever import retriever
from agentic_framework.utils.diff_utils import diff_utils
from agentic_framework.utils.project_analyzer import project_analyzer
from agentic_framework.observability.logger import logger


@dataclass
class FileModification:
    file_path: str
    lines_added: int
    lines_deleted: int
    total_lines_changed: int
    diff: str


class ToolDefinition:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        func: Callable,
        risk_level: ActionRiskLevel = ActionRiskLevel.LOW,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func
        self.risk_level = risk_level


class MCPToolRegistry:
    """Registry of tools available to agents and external MCP clients."""

    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self.recorded_modifications: List[FileModification] = []
        self._register_default_tools()

    def reset_modification_tracking(self) -> None:
        """Clear recorded file changes before an agent step."""
        self.recorded_modifications.clear()

    def record_modification(self, file_path: str, orig_content: str, new_content: str) -> None:
        """Track surgical line modifications made by tools."""
        diff_str = diff_utils.generate_diff(orig_content, new_content, file_path)
        added = sum(1 for line in diff_str.splitlines() if line.startswith('+') and not line.startswith('+++'))
        deleted = sum(1 for line in diff_str.splitlines() if line.startswith('-') and not line.startswith('---'))
        self.recorded_modifications.append(
            FileModification(
                file_path=file_path,
                lines_added=added,
                lines_deleted=deleted,
                total_lines_changed=added + deleted,
                diff=diff_str,
            )
        )

    def get_recorded_modifications(self) -> List[FileModification]:
        """Return all file modifications recorded in the current session."""
        return list(self.recorded_modifications)

    def register(self, tool: ToolDefinition) -> None:
        self.tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self.tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return MCP standard tool declarations."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.parameters,
            }
            for t in self.tools.values()
        ]

    def _resolve_path(self, file_path: str) -> Path:
        """Resolve path relative to target project root."""
        target_root = settings.get_target_path()
        p = Path(file_path)
        if not p.is_absolute():
            p = (target_root / p).resolve()
        return p

    def _register_default_tools(self) -> None:
        # 1. read_file
        self.register(
            ToolDefinition(
                name="read_file",
                description="Read lines or full content from a file in the target project.",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Relative or absolute file path"},
                        "start_line": {"type": "integer", "description": "Optional 1-indexed starting line"},
                        "end_line": {"type": "integer", "description": "Optional 1-indexed ending line"},
                    },
                    "required": ["file_path"],
                },
                func=self._tool_read_file,
                risk_level=ActionRiskLevel.LOW,
            )
        )

        # 2. write_file
        self.register(
            ToolDefinition(
                name="write_file",
                description="Create or overwrite a file in the target project with new content.",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Target file path"},
                        "content": {"type": "string", "description": "Complete new content of the file"},
                    },
                    "required": ["file_path", "content"],
                },
                func=self._tool_write_file,
                risk_level=ActionRiskLevel.MEDIUM,
            )
        )

        # 3. apply_patch
        self.register(
            ToolDefinition(
                name="apply_patch",
                description="Surgically replace target code with replacement code in an existing file.",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File to modify"},
                        "target_content": {"type": "string", "description": "Exact lines of code to replace"},
                        "replacement_content": {"type": "string", "description": "New code to put in place"},
                    },
                    "required": ["file_path", "target_content", "replacement_content"],
                },
                func=self._tool_apply_patch,
                risk_level=ActionRiskLevel.MEDIUM,
            )
        )

        # 4. list_directory
        self.register(
            ToolDefinition(
                name="list_directory",
                description="List files and folders in a target project directory.",
                parameters={
                    "type": "object",
                    "properties": {
                        "directory_path": {"type": "string", "description": "Directory to inspect (default '.')"},
                    },
                },
                func=self._tool_list_directory,
                risk_level=ActionRiskLevel.LOW,
            )
        )

        # 5. search_code
        self.register(
            ToolDefinition(
                name="search_code",
                description="Perform semantic & lexical RAG search across the target codebase.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Keywords, function name, or natural language query"},
                        "top_k": {"type": "integer", "description": "Number of snippets to retrieve (default 4)"},
                    },
                    "required": ["query"],
                },
                func=self._tool_search_code,
                risk_level=ActionRiskLevel.LOW,
            )
        )

        # 6. run_shell
        self.register(
            ToolDefinition(
                name="run_shell",
                description="Execute a safe shell command inside the target project directory.",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command line string to run"},
                    },
                    "required": ["command"],
                },
                func=self._tool_run_shell,
                risk_level=ActionRiskLevel.HIGH,
            )
        )

        # 7. run_project_tests
        self.register(
            ToolDefinition(
                name="run_project_tests",
                description="Run the test suite (pytest, npm test, etc.) in the target project.",
                parameters={
                    "type": "object",
                    "properties": {
                        "test_target": {"type": "string", "description": "Optional specific test file or test pattern"},
                    },
                },
                func=self._tool_run_tests,
                risk_level=ActionRiskLevel.HIGH,
            )
        )

        # 8. analyze_project
        self.register(
            ToolDefinition(
                name="analyze_project",
                description="Inspect the target project tech stack, languages, and test frameworks.",
                parameters={"type": "object", "properties": {}},
                func=self._tool_analyze_project,
                risk_level=ActionRiskLevel.LOW,
            )
        )

    # Tool Implementations
    def _tool_read_file(self, file_path: str = "", start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        if not file_path:
            return "Error: 'file_path' argument is required. Please specify the target file path."
        p = self._resolve_path(file_path)
        if not p.exists():
            return f"Error: File not found at {file_path}"
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            if start_line is not None or end_line is not None:
                s = max(1, start_line or 1)
                e = min(len(lines), end_line or len(lines))
                sliced = lines[s - 1:e]
                numbered = [f"{s + i}: {line}" for i, line in enumerate(sliced)]
                return "\n".join(numbered)
            return content
        except Exception as e:
            return f"Error reading file: {e}"

    def _tool_write_file(self, file_path: str = "", content: str = "") -> str:
        if not file_path:
            return "Error: 'file_path' argument is required."
        p = self._resolve_path(file_path)
        orig_content = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        diff_str = diff_utils.generate_diff(orig_content, content, file_path)

        # HITL Approval
        decision = hitl_manager.request_approval(
            action_name=f"write_file({file_path})",
            risk_level=ActionRiskLevel.MEDIUM,
            details=f"File: {file_path}\nDiff:\n{diff_str}",
            payload={"file_path": file_path, "diff": diff_str},
        )
        if not decision.approved:
            return f"Action rejected by user: {decision.user_feedback}"

        success, err = diff_utils.validate_and_apply(p, content)
        if not success:
            return f"Failed to write file: {err}"
        self.record_modification(str(p), orig_content, content)
        return f"Successfully wrote {len(content)} bytes to {file_path}"

    def _tool_apply_patch(self, file_path: str = "", target_content: str = "", replacement_content: str = "") -> str:
        if not file_path:
            return "Error: 'file_path' argument is required."
        if not target_content:
            return "Error: 'target_content' argument is required. Specify the exact lines to replace."
        p = self._resolve_path(file_path)
        if not p.exists():
            return f"Error: Target file does not exist at {file_path}"

        orig_content = p.read_text(encoding="utf-8", errors="replace")
        ok, new_content, err = diff_utils.apply_replacement(orig_content, target_content, replacement_content)
        if not ok:
            return f"Patch failed: {err}"

        diff_str = diff_utils.generate_diff(orig_content, new_content, file_path)

        # HITL Approval
        decision = hitl_manager.request_approval(
            action_name=f"apply_patch({file_path})",
            risk_level=ActionRiskLevel.MEDIUM,
            details=f"File: {file_path}\nDiff:\n{diff_str}",
            payload={"file_path": file_path, "diff": diff_str},
        )
        if not decision.approved:
            return f"Patch rejected by user: {decision.user_feedback}"

        success, write_err = diff_utils.validate_and_apply(p, new_content)
        if not success:
            return f"Failed to apply patch due to syntax error: {write_err}"
        self.record_modification(str(p), orig_content, new_content)
        return f"Successfully applied surgical patch to {file_path}"

    def _tool_list_directory(self, directory_path: str = ".") -> str:
        p = self._resolve_path(directory_path)
        if not p.exists():
            return f"Error: Directory not found at {directory_path}"
        try:
            items = []
            for item in p.iterdir():
                if item.name in settings.EXCLUDED_DIRS:
                    continue
                tag = "[DIR]" if item.is_dir() else "[FILE]"
                items.append(f"{tag} {item.name}")
            return "\n".join(items) if items else "(empty directory)"
        except Exception as e:
            return f"Error listing directory: {e}"

    def _tool_search_code(self, query: str = "", top_k: int = 4) -> str:
        if not query:
            return "Error: 'query' argument is required. Specify what code or symbol to search for."
        return retriever.format_context_for_prompt(query, top_k=top_k)

    def _tool_run_shell(self, command: str = "") -> str:
        if not command:
            return "Error: 'command' argument is required."
        # Guardrail check
        guard_res = output_guardrails.validate_command(command)
        if not guard_res.passed:
            return f"Security Guardrail Blocked Command: {guard_res.error_message}"

        # HITL Approval
        decision = hitl_manager.request_approval(
            action_name=f"run_shell('{command}')",
            risk_level=ActionRiskLevel.HIGH,
            details=f"Executing shell command in {settings.get_target_path()}:\n$ {command}",
            payload={"command": command},
        )
        if not decision.approved:
            return f"Execution cancelled by user: {decision.user_feedback}"

        try:
            res = subprocess.run(
                command,
                cwd=str(settings.get_target_path()),
                shell=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            out = res.stdout + ("\nSTDERR:\n" + res.stderr if res.stderr else "")
            return f"Exit Code: {res.returncode}\nOutput:\n{out.strip()}"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 60 seconds."
        except Exception as e:
            return f"Command execution error: {e}"

    def _tool_run_tests(self, test_target: Optional[str] = None) -> str:
        detected_cmd = project_analyzer.detect_test_runner()
        cmd = f"{detected_cmd} {test_target}" if test_target else detected_cmd
        return self._tool_run_shell(cmd)

    def _tool_analyze_project(self) -> str:
        analysis = project_analyzer.analyze()
        lines = [f"{k}: {v}" for k, v in analysis.items()]
        return "\n".join(lines)


# Singleton tool registry
tool_registry = MCPToolRegistry()
