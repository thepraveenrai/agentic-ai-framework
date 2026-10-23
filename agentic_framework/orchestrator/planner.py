"""Dynamic Planner and Task Decomposer for Multi-Agent Orchestration.

Breaks complex user engineering requests into an executable directed sequence
of subtasks mapped to specialized agents.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from agentic_framework.core.llm import llm_client
from agentic_framework.observability.logger import logger


@dataclass
class PlanStep:
    step_id: int
    agent_name: str  # BugFixAgent, TechReviewAgent, FeatureDevAgent, RegressionTestAgent
    task: str
    expected_output: str


class TaskPlanner:
    """Decomposes engineering goals into multi-agent workflows."""

    PLANNING_PROMPT = """You are the Lead Engineering Orchestrator.
Analyze the user's software engineering task and create a step-by-step plan assigning each step to the most appropriate specialized agent.

Available Agents:
1. BugFixAgent: Use when there is a defect, crash, failing test, or bug to diagnose and fix.
2. TechReviewAgent: Use when code needs security audit, code quality review, architecture review, or best practice check.
3. FeatureDevAgent: Use when new functionality, new endpoints, new classes, or code enhancements must be designed and implemented.
4. RegressionTestAgent: Dedicated Regression Verification Gatekeeper. CRITICAL RULE: RegressionTestAgent MUST auto-run whenever BugFixAgent or FeatureDevAgent runs, to verify that their code modifications did not cause any regression issues in the project. RegressionTestAgent should only be used for this regression verification purpose.

Instructions:
- Keep the plan focused and sequential (typically 1 to 4 steps).
- Whenever BugFixAgent runs, RegressionTestAgent MUST immediately follow it to verify no regressions were introduced.
- Whenever FeatureDevAgent runs, RegressionTestAgent MUST immediately follow it to verify no regressions were introduced.
- Format your response as a numbered list where each line contains:
  STEP <number> | AGENT: <AgentName> | TASK: <Concise subtask description>
"""

    def plan_task(self, user_task: str) -> List[PlanStep]:
        """Generate structured plan steps for the user task."""
        # Fast heuristic planning if task mentions specific keywords
        task_lower = user_task.lower()
        steps: List[PlanStep] = []

        # If user explicitly wants just a review
        if "review" in task_lower and not any(k in task_lower for k in ["fix", "implement", "create", "add"]):
            return [
                PlanStep(
                    step_id=1,
                    agent_name="TechReviewAgent",
                    task=f"Conduct technical review on target project: {user_task}",
                    expected_output="Technical review report with security, architecture, and code quality recommendations.",
                )
            ]

        # If user asks for bug fix -> BugFixAgent + RegressionTestAgent (auto-run)
        if any(k in task_lower for k in ["fix", "bug", "error", "crash", "broken", "issue"]):
            steps.append(
                PlanStep(
                    step_id=1,
                    agent_name="BugFixAgent",
                    task=f"Diagnose and patch bug: {user_task}",
                    expected_output="Root cause analysis and surgical code patch.",
                )
            )
            steps.append(
                PlanStep(
                    step_id=2,
                    agent_name="RegressionTestAgent",
                    task="Run regression verification on the bug fix made by BugFixAgent. Verify that all existing tests pass and no regression issues were introduced.",
                    expected_output="Regression verification report confirming zero regressions.",
                )
            )
            return steps

        # If user asks for feature development -> FeatureDevAgent + RegressionTestAgent (auto-run) + TechReviewAgent
        if any(k in task_lower for k in ["create", "add", "implement", "feature", "build", "new"]):
            steps.append(
                PlanStep(
                    step_id=1,
                    agent_name="FeatureDevAgent",
                    task=f"Design and implement requested feature: {user_task}",
                    expected_output="Feature code implementation and integration.",
                )
            )
            steps.append(
                PlanStep(
                    step_id=2,
                    agent_name="RegressionTestAgent",
                    task="Run regression verification on the feature implemented by FeatureDevAgent. Verify that all existing tests pass and no regression issues were introduced.",
                    expected_output="Regression verification report confirming zero regressions.",
                )
            )
            steps.append(
                PlanStep(
                    step_id=3,
                    agent_name="TechReviewAgent",
                    task="Review new feature implementation for security, clean architecture, and best practices.",
                    expected_output="Architecture and security review report.",
                )
            )
            return steps

        # Default fallback: FeatureDevAgent followed by RegressionTestAgent
        return [
            PlanStep(
                step_id=1,
                agent_name="FeatureDevAgent",
                task=f"Analyze and execute task: {user_task}",
                expected_output="Task implementation.",
            ),
            PlanStep(
                step_id=2,
                agent_name="RegressionTestAgent",
                task="Run regression verification on the modifications to ensure no regression issues were introduced.",
                expected_output="Regression verification report confirming zero regressions.",
            ),
        ]


task_planner = TaskPlanner()
