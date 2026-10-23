"""Human-in-the-Loop (HITL) Execution Controller.

Provides interactive approval checkpoints, user feedback loops, and diff inspection
before applying code modifications or executing terminal commands.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, Dict, Any
from rich.prompt import Prompt
from agentic_framework.config import settings
from agentic_framework.observability.logger import logger


class ActionRiskLevel(str, Enum):
    LOW = "low"  # Read-only operations, search, retrieval
    MEDIUM = "medium"  # Writing/modifying code files, applying patches
    HIGH = "high"  # Executing terminal commands, running tests, git operations


@dataclass
class HITLDecision:
    approved: bool
    user_feedback: Optional[str] = None
    modified_payload: Optional[Any] = None


class HITLManager:
    """Manages interactive human approvals and feedback checkpoints."""

    def __init__(self):
        self.mode = settings.HITL_MODE  # "always", "on_modify", "never"
        self._custom_callback: Optional[Callable[[str, Dict[str, Any]], HITLDecision]] = None

    def set_callback(self, callback: Callable[[str, Dict[str, Any]], HITLDecision]) -> None:
        """Register programmatic approval callback for web or API integrations."""
        self._custom_callback = callback

    def request_approval(
        self,
        action_name: str,
        risk_level: ActionRiskLevel,
        details: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> HITLDecision:
        """Request human approval before performing an action."""
        if not settings.HITL_ENABLED or self.mode == "never":
            return HITLDecision(approved=True)

        if self.mode == "on_modify" and risk_level == ActionRiskLevel.LOW:
            return HITLDecision(approved=True)

        # If custom callback registered (e.g. from Web UI / Dashboard / API)
        if self._custom_callback is not None:
            return self._custom_callback(action_name, payload or {})

        # Default: Terminal Interactive HITL Prompt
        logger.hitl_prompt(action_name, details)

        while True:
            choice = Prompt.ask(
                "[bold yellow]Do you approve this action?[/bold yellow] ([green]y[/green]es / [red]n[/red]o / [cyan]f[/cyan]eedback)",
                choices=["y", "n", "f"],
                default="y",
            ).lower()

            if choice == "y":
                logger.success(f"Action '{action_name}' approved by user.")
                return HITLDecision(approved=True)
            elif choice == "n":
                logger.warning(f"Action '{action_name}' rejected by user.")
                return HITLDecision(
                    approved=False,
                    user_feedback="Operation was cancelled by user.",
                )
            elif choice == "f":
                feedback = Prompt.ask("[cyan]Enter instructions or modifications for the agent[/cyan]")
                logger.info(f"User provided feedback: {feedback}")
                return HITLDecision(approved=False, user_feedback=feedback)


hitl_manager = HITLManager()
