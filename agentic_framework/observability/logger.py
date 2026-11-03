"""Rich Structured Logging for Agentic AI Framework.

Provides clean terminal output, agent action highlights, diff rendering,
and suppresses noisy third-party libraries so only necessary info appears on the console.
"""

import logging
import sys
from typing import Optional, Any, Dict

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

# Suppress noisy third-party loggers (HTTP requests, connection pooling, etc.)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
for _noisy_logger in ("httpx", "httpcore", "openai", "urllib3", "asyncio", "charset_normalizer"):
    logging.getLogger(_noisy_logger).setLevel(logging.WARNING)

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.theme import Theme
from agentic_framework.config import settings

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

# Standard log level priority mapping
LOG_LEVEL_ORDER = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}


class AgentLogger:
    """Specialized clean logger for multi-agent interactions."""

    @staticmethod
    def _is_enabled(level_name: str) -> bool:
        """Check if message level satisfies configured settings.LOG_LEVEL."""
        configured = settings.LOG_LEVEL.upper() if hasattr(settings, "LOG_LEVEL") else "INFO"
        req_lvl = LOG_LEVEL_ORDER.get(configured, 20)
        msg_lvl = LOG_LEVEL_ORDER.get(level_name.upper(), 20)
        return msg_lvl >= req_lvl

    @staticmethod
    def _emit(event_type_or_payload: Any = None, data: Optional[Dict[str, Any]] = None) -> None:
        """Safe no-op kept for backward compatibility."""
        pass

    @classmethod
    def agent_start(cls, agent_name: str, task: str) -> None:
        if cls._is_enabled("INFO"):
            console.print(f"\n[bold magenta]🤖 [{agent_name}][/bold magenta] [white]{task}[/white]")

    @classmethod
    def thought(cls, agent_name: str, thought_text: str) -> None:
        """Internal model reasoning/scratchpad.

        Suppressed on normal INFO runs to prevent terminal clutter;
        displayed only when LOG_LEVEL is explicitly set to DEBUG.
        """
        if cls._is_enabled("DEBUG") and thought_text and thought_text.strip():
            first_line = thought_text.strip().splitlines()[0].strip()
            if first_line.startswith("#"):
                first_line = first_line.lstrip("#").strip()
            if len(first_line) > 100:
                first_line = first_line[:97] + "..."
            if first_line:
                console.print(f"  [dim]💭 {first_line}[/dim]")

    @classmethod
    def tool_call(cls, tool_name: str, detail: Optional[str] = None) -> None:
        if not cls._is_enabled("INFO"):
            return
        if detail:
            clean_detail = str(detail).strip().replace("\r", "").replace("\n", " ")
            if len(clean_detail) > 60:
                clean_detail = clean_detail[:57] + "..."
            extra = f" [dim]({clean_detail})[/dim]"
        else:
            extra = ""
        console.print(f"  [cyan]•[/cyan] {tool_name}{extra}")

    @classmethod
    def tool_error(cls, tool_name: str, error_msg: str) -> None:
        if cls._is_enabled("ERROR"):
            clean_err = str(error_msg).strip().replace("\r", "").replace("\n", " ")
            if len(clean_err) > 120:
                clean_err = clean_err[:117] + "..."
            console.print(f"  [error]✗ Tool {tool_name} error:[/error] {clean_err}")

    @classmethod
    def guardrail_alert(cls, guardrail_name: str, message: str, passed: bool) -> None:
        if not passed and cls._is_enabled("WARNING"):
            console.print(Panel(f"[error]🛡️ Guardrail [{guardrail_name}] Blocked:[/error]\n{message}", border_style="red"))

    @classmethod
    def hitl_prompt(cls, action_name: str, details: str) -> None:
        console.print(
            Panel(
                f"[hitl]⚠️ Human Approval Required[/hitl]\n"
                f"[bold]Action:[/bold] {action_name}\n"
                f"[bold]Details:[/bold]\n{details}",
                border_style="yellow",
            )
        )

    @classmethod
    def diff(cls, file_path: str, diff_text: str) -> None:
        if cls._is_enabled("INFO"):
            console.print(f"\n[bold yellow]Proposed Patch for {file_path}:[/bold yellow]")
            syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
            console.print(syntax)

    @classmethod
    def info(cls, msg: str) -> None:
        if cls._is_enabled("INFO"):
            console.print(f"[info]ℹ️ {msg}[/info]")

    @classmethod
    def success(cls, msg: str) -> None:
        if cls._is_enabled("INFO"):
            console.print(f"[success]✅ {msg}[/success]")

    @classmethod
    def warning(cls, msg: str) -> None:
        if cls._is_enabled("WARNING"):
            console.print(f"[warning]⚠️ {msg}[/warning]")

    @classmethod
    def error(cls, msg: str) -> None:
        if cls._is_enabled("ERROR"):
            console.print(f"[error]❌ {msg}[/error]")


logger = AgentLogger()
