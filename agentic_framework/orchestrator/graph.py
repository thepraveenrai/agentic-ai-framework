"""Multi-Agent State Graph and Orchestration Engine.

Coordinates the 4 specialized agents (BugFixAgent, TechReviewAgent, FeatureDevAgent,
RegressionTestAgent), executes dynamic plans, manages shared state, and collects telemetry.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional
from rich.panel import Panel
from rich.table import Table
from agentic_framework.config import settings
from agentic_framework.agents.bug_fix_agent import bug_fix_agent
from agentic_framework.agents.tech_review_agent import tech_review_agent
from agentic_framework.agents.feature_dev_agent import feature_dev_agent
from agentic_framework.agents.regression_test_agent import regression_test_agent
from agentic_framework.orchestrator.planner import task_planner, PlanStep
from agentic_framework.rag.retriever import retriever
from agentic_framework.observability.tracer import tracer
from agentic_framework.observability.logger import logger, console


@dataclass
class OrchestratorState:
    task: str
    target_project: str
    steps: List[PlanStep] = field(default_factory=list)
    current_step_idx: int = 0
    agent_outputs: Dict[str, Any] = field(default_factory=dict)
    history: List[str] = field(default_factory=list)
    status: str = "initialized"  # initialized, in_progress, completed, failed


class MultiAgentOrchestrator:
    """Supervises and coordinates multi-agent autonomous execution graphs."""

    def __init__(self):
        self.agents = {
            "BugFixAgent": bug_fix_agent,
            "TechReviewAgent": tech_review_agent,
            "FeatureDevAgent": feature_dev_agent,
            "RegressionTestAgent": regression_test_agent,
        }

    def run(
        self,
        task: str,
        target_dir: Optional[str] = None,
        specific_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute full multi-agent orchestration on target project."""
        if target_dir:
            settings.TARGET_PROJECT_PATH = target_dir

        target_path = settings.get_target_path()
        trace_id = tracer.start_trace(task_description=task, target_project=str(target_path))
        retriever.initialize_index()

        console.print(
            Panel(
                f"[bold cyan]AGENTIC AI FRAMEWORK[/bold cyan]\n"
                f"[dim]Target:[/dim] [white]{target_path}[/white]  |  [dim]Trace:[/dim] [cyan]{trace_id}[/cyan]\n"
                f"[dim]Task:[/dim] [bold white]{task}[/bold white]",
                border_style="magenta",
                expand=False,
            )
        )

        # 3. Formulate Plan (Auto-chaining RegressionTestAgent after BugFixAgent or FeatureDevAgent)
        if specific_agent and specific_agent in self.agents:
            if specific_agent == "BugFixAgent":
                steps = [
                    PlanStep(
                        step_id=1,
                        agent_name="BugFixAgent",
                        task=task,
                        expected_output="Root cause analysis and surgical patch for the issue.",
                    ),
                    PlanStep(
                        step_id=2,
                        agent_name="RegressionTestAgent",
                        task="Run regression verification on the bug fix made by BugFixAgent. Verify that all existing tests pass and no regression issues were introduced.",
                        expected_output="Regression verification report confirming zero regressions.",
                    ),
                ]
            elif specific_agent == "FeatureDevAgent":
                steps = [
                    PlanStep(
                        step_id=1,
                        agent_name="FeatureDevAgent",
                        task=task,
                        expected_output="Feature design and implementation.",
                    ),
                    PlanStep(
                        step_id=2,
                        agent_name="RegressionTestAgent",
                        task="Run regression verification on the feature implemented by FeatureDevAgent. Verify that all existing tests pass and no regression issues were introduced.",
                        expected_output="Regression verification report confirming zero regressions.",
                    ),
                ]
            else:
                steps = [
                    PlanStep(
                        step_id=1,
                        agent_name=specific_agent,
                        task=task,
                        expected_output=f"Output from {specific_agent}",
                    )
                ]
        else:
            steps = task_planner.plan_task(task)

        # Print plan table
        plan_table = Table(title="Multi-Agent Execution Plan", show_header=True, header_style="bold magenta")
        plan_table.add_column("Step", style="dim", width=6)
        plan_table.add_column("Assigned Agent", style="cyan", width=22)
        plan_table.add_column("Subtask Description", style="white")

        for s in steps:
            plan_table.add_row(str(s.step_id), f"🤖 {s.agent_name}", s.task)
        console.print(plan_table)

        # 4. State Graph Execution
        state = OrchestratorState(
            task=task,
            target_project=str(target_path),
            steps=steps,
            status="in_progress",
        )

        accumulated_context = f"Main Goal: {task}\nTarget Directory: {target_path}\n"

        for s in steps:
            state.current_step_idx = s.step_id
            agent = self.agents.get(s.agent_name)
            if not agent:
                logger.error(f"Unknown agent: {s.agent_name}")
                continue

            # Intelligent gating for RegressionTestAgent:
            # Skip if preceding agent only made minor changes (<= 12 lines) with high confidence
            if s.agent_name == "RegressionTestAgent" and s.step_id > 1:
                prev_step_idx = s.step_id - 1
                prev_out = next((v for k, v in state.agent_outputs.items() if k.startswith(f"step_{prev_step_idx}_")), None)

                should_run, reason, target_test = self._evaluate_regression_gate(prev_out, target_path)
                if not should_run:
                    console.print(f"\n[bold green]⚡ [Regression Gate][/bold green] [dim]{reason}[/dim]")
                    state.agent_outputs[f"step_{s.step_id}_{s.agent_name}"] = {
                        "agent": s.agent_name,
                        "role": "Regression Verification Gatekeeper",
                        "output": f"Regression verification skipped: {reason}",
                        "status": "skipped",
                    }
                    continue
                else:
                    # Restrict scope to ONLY the updated file and its matching test
                    if target_test:
                        s.task = (
                            f"Run targeted regression verification ONLY on the updated file. "
                            f"Focus exclusively on test target: '{target_test}'. "
                            f"Do not review or run tests on unrelated files."
                        )

            # Execute agent
            res = agent.run(task_description=s.task, context=accumulated_context)
            state.agent_outputs[f"step_{s.step_id}_{s.agent_name}"] = res

            # Update accumulated context for subsequent agents
            accumulated_context += f"\n--- Step {s.step_id} Output by {s.agent_name} ---\n{res.get('output', '')}\n"

        # 5. Conclude Trace
        final_summary = self._synthesize_final_report(state)
        tracer.end_trace(status="success", final_output=final_summary)

        # Display Final Summary
        console.print(
            Panel(
                f"[bold green]Multi-Agent Workflow Completed Successfully![/bold green]\n\n"
                f"{final_summary}",
                border_style="green",
                title="✨ Framework Execution Summary",
            )
        )

        return {
            "trace_id": trace_id,
            "status": "success",
            "summary": final_summary,
            "agent_outputs": state.agent_outputs,
        }

    def _evaluate_regression_gate(
        self, prev_out: Optional[Dict[str, Any]], target_path: Path
    ) -> Tuple[bool, str, Optional[str]]:
        """Intelligently determine whether RegressionTestAgent should execute.
        
        Rules:
        1. If previous agent made no changes (0 lines): Skip regression test.
        2. If previous agent made minor changes (<= 12 lines in 1 file) with high confidence (>= 0.85): Skip regression test.
        3. If confidence is low (< 0.85) or substantial changes were made (> 12 lines, multiple files): Run targeted test ONLY for updated file.
        """
        if not prev_out:
            return True, "No prior agent output found; running regression verification.", None

        modified_files = prev_out.get("modified_files", [])
        lines_changed = prev_out.get("total_lines_changed", 0)
        confidence = prev_out.get("confidence_score", 0.90)
        risk = prev_out.get("risk_level", "LOW")

        target_test_file = self._find_matching_test(modified_files, target_path)

        # 1. No files modified
        if not modified_files or lines_changed == 0:
            return False, "No code changes were made by the preceding agent. Regression verification not needed.", None

        # 2. Minor change with high confidence
        if len(modified_files) == 1 and lines_changed <= 12 and confidence >= 0.85 and risk == "LOW":
            fname = Path(modified_files[0]).name
            return (
                False,
                f"Minor change ({lines_changed} lines updated in {fname}, confidence {confidence:.2f}). Regression test skipped.",
                None,
            )

        # 3. Substantial change or low confidence -> Run targeted test
        if confidence < 0.85:
            reason = f"Low confidence ({confidence:.2f} < 0.85). Triggering targeted regression test on updated file."
        elif len(modified_files) > 1:
            reason = f"Multiple files updated ({len(modified_files)} files). Triggering targeted regression test."
        else:
            reason = f"Substantial change ({lines_changed} lines updated). Triggering targeted regression test."

        return True, reason, target_test_file

    def _find_matching_test(self, modified_files: List[str], target_path: Path) -> Optional[str]:
        """Locate test file specifically matching the modified source file."""
        if not modified_files:
            return None
        first_mod = Path(modified_files[0])
        stem = first_mod.stem

        candidates = [
            f"test_{stem}.py",
            f"{stem}_test.py",
            f"{stem}.test.ts",
            f"{stem}.test.js",
        ]
        for cand in candidates:
            for p in target_path.rglob(cand):
                if p.is_file():
                    try:
                        return str(p.relative_to(target_path))
                    except Exception:
                        return str(p)
        return None

    def _synthesize_final_report(self, state: OrchestratorState) -> str:
        """Combine all agent findings into a polished summary."""
        lines = [f"**Target Project:** `{state.target_project}`", f"**Task:** {state.task}\n"]
        lines.append("### Agent Execution Outcomes:")

        for k, out in state.agent_outputs.items():
            agent_name = out.get("agent", "Agent")
            status = out.get("status", "unknown")
            output_snippet = out.get("output", "").strip()
            # Truncate if very long
            if len(output_snippet) > 600:
                output_snippet = output_snippet[:600] + "\n...(see full trace for details)"
            lines.append(f"- **{agent_name}** `[{status.upper()}]`:\n  {output_snippet}\n")

        return "\n".join(lines)


orchestrator = MultiAgentOrchestrator()
