"""Rich Structured Logging for Agentic AI Framework.

Provides beautiful terminal panels, agent action highlights, diff rendering,
and hierarchical output.
"""

import sys

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.theme import Theme
from typing import Optional, Any, List, Callable, Dict

custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "agent": "bold magenta",
    "tool": "bold blue",
    "hitl": "bold yellow",
    "rag": "bold cyan",
})

console = Console(theme=custom_theme, safe_box=True)


class AgentLogger:
    """Specialized clean logger for multi-agent interactions."""

    _subscribers: List[Callable[[Dict[str, Any]], None]] = []

    @classmethod
    def subscribe(cls, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a real-time event listener (e.g. for Web UI / SSE)."""
        if callback not in cls._subscribers:
            cls._subscribers.append(callback)

    @classmethod
    def unsubscribe(cls, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Unregister an event listener."""
        if callback in cls._subscribers:
            cls._subscribers.remove(callback)

    @classmethod
    def _emit(cls, event_type_or_payload: Any, data: Optional[Dict[str, Any]] = None) -> None:
        import time
        if isinstance(event_type_or_payload, dict):
            payload = {"timestamp": time.time(), **event_type_or_payload}
        else:
            payload = {"type": str(event_type_or_payload), "timestamp": time.time(), **(data or {})}
        for cb in list(cls._subscribers):
            try:
                cb(payload)
            except Exception:
                pass

    @staticmethod
    def agent_start(agent_name: str, task: str) -> None:
        console.print(f"\n[bold magenta]🤖 [{agent_name}][/bold magenta] [white]{task}[/white]")
        AgentLogger._emit("agent_start", {"agent": agent_name, "task": task})

    @staticmethod
    def thought(agent_name: str, thought_text: str) -> None:
        if thought_text and thought_text.strip():
            first_line = thought_text.strip().splitlines()[0].strip()
            if first_line.startswith("#"):
                first_line = first_line.lstrip("#").strip()
            if len(first_line) > 100:
                first_line = first_line[:97] + "..."
            if first_line:
                console.print(f"  [dim]💭 {first_line}[/dim]")
            AgentLogger._emit("thought", {"agent": agent_name, "thought": thought_text.strip()})

    @staticmethod
    def tool_call(tool_name: str, detail: Optional[str] = None) -> None:
        if detail:
            d_str = str(detail)
            if len(d_str) > 60:
                d_str = "..." + d_str[-57:]
            extra = f" [dim]({d_str})[/dim]"
        else:
            extra = ""
        console.print(f"  [cyan]•[/cyan] {tool_name}{extra}")
        AgentLogger._emit("tool_call", {"tool": tool_name, "detail": detail or ""})

    @staticmethod
    def tool_error(tool_name: str, error_msg: str) -> None:
        console.print(f"  [error]✗ Tool {tool_name} error:[/error] {error_msg}")
        AgentLogger._emit("tool_error", {"tool": tool_name, "error": error_msg})

    @staticmethod
    def guardrail_alert(guardrail_name: str, message: str, passed: bool) -> None:
        if not passed:
            console.print(Panel(f"[error]🛡️ Guardrail [{guardrail_name}] Blocked:[/error]\n{message}", border_style="red"))
        AgentLogger._emit("guardrail", {"name": guardrail_name, "message": message, "passed": passed})

    @staticmethod
    def hitl_prompt(action_name: str, details: str) -> None:
        console.print(
            Panel(
                f"[hitl]⚠️ Human Approval Required[/hitl]\n"
                f"[bold]Action:[/bold] {action_name}\n"
                f"[bold]Details:[/bold]\n{details}",
                border_style="yellow",
            )
        )
        AgentLogger._emit("hitl_prompt", {"action": action_name, "details": details})

    @staticmethod
    def diff(file_path: str, diff_text: str) -> None:
        console.print(f"\n[bold yellow]Proposed Patch for {file_path}:[/bold yellow]")
        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
        console.print(syntax)
        AgentLogger._emit("diff", {"file_path": file_path, "diff": diff_text})

    @staticmethod
    def info(msg: str) -> None:
        console.print(f"[info]ℹ️ {msg}[/info]")
        AgentLogger._emit("info", {"message": msg})

    @staticmethod
    def success(msg: str) -> None:
        console.print(f"[success]✅ {msg}[/success]")
        AgentLogger._emit("success", {"message": msg})

    @staticmethod
    def warning(msg: str) -> None:
        console.print(f"[warning]⚠️ {msg}[/warning]")
        AgentLogger._emit("warning", {"message": msg})

    @staticmethod
    def error(msg: str) -> None:
        console.print(f"[error]❌ {msg}[/error]")
        AgentLogger._emit("error", {"message": msg})


logger = AgentLogger()
