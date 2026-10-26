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

    @classmethod
    def approve(cls, feedback: Optional[str] = None) -> "HITLDecision":
        return cls(approved=True, user_feedback=feedback)

    @classmethod
    def reject(cls, feedback: Optional[str] = None) -> "HITLDecision":
        return cls(approved=False, user_feedback=feedback or "Operation rejected by user.")


# Constants for convenience and backward compatibility
HITLDecision.APPROVE = HITLDecision(approved=True)  # type: ignore
HITLDecision.REJECT = HITLDecision(approved=False, user_feedback="Operation rejected by user.")  # type: ignore


class HITLManager:
    """Manages interactive human approvals and feedback checkpoints."""

    def __init__(self):
        self.mode = settings.HITL_MODE  # "always", "on_modify", "never"
        self.enabled: bool = settings.HITL_ENABLED
        self._custom_callback: Optional[Callable[..., HITLDecision]] = None

    def set_callback(self, callback: Optional[Callable[..., HITLDecision]]) -> None:
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
        if not self.enabled or not settings.HITL_ENABLED or self.mode == "never":
            return HITLDecision.APPROVE

        if self.mode == "on_modify" and risk_level == ActionRiskLevel.LOW:
            return HITLDecision.APPROVE

        # If custom callback registered (e.g. from Web UI / Dashboard / API)
        if self._custom_callback is not None:
            try:
                # Preferred: 4-argument signature (action_name, details, risk, metadata)
                return self._custom_callback(action_name, details, risk_level, payload or {})
            except TypeError:
                try:
                    # Fallback: 2-argument signature (action_name, payload)
                    return self._custom_callback(action_name, payload or {})
                except Exception as e:
                    logger.error(f"Error in custom HITL callback: {e}")
                    return HITLDecision(approved=False, user_feedback=f"Callback execution error: {e}")

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
