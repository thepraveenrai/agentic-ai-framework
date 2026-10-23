"""BugFixAgent for Autonomous Diagnosis, Triage, and Patching.

Analyzes error logs, reproduces bugs, retrieves relevant code context using RAG,
synthesizes minimal surgical patches, and verifies fixes against test runners.
"""

from typing import Optional, List
from agentic_framework.agents.base import BaseAgent

BUG_FIX_SYSTEM_PROMPT = """You are the BugFixAgent, an elite autonomous software debugging engineer.
Your mission is to analyze bug reports, triage code issues, and promptly apply surgical patches.

Direct Execution Rules:
1. Target Inspection: Call 'read_file' to examine the target file and function mentioned in the task.
2. Direct Patching: As soon as you identify the defect, missing guard, or bug, IMMEDIATELY call 'apply_patch' or 'write_file' to apply the fix to the target file.
   - Do NOT spend excess iterations over-analyzing or re-reading files without acting.
3. Verification: Run 'run_project_tests' to verify tests pass.
4. Conclude with a concise explanation of the root cause and the fix applied.
"""


class BugFixAgent(BaseAgent):
    """Specialized agent for bug triage, root-cause analysis, and patching."""

    def __init__(self, max_iterations: int = 8):
        super().__init__(
            name="BugFixAgent",
            role="Automated Software Debugger & Patch Engineer",
            system_prompt=BUG_FIX_SYSTEM_PROMPT,
            allowed_tools=[
                "read_file",
                "apply_patch",
                "write_file",
                "search_code",
                "run_project_tests",
                "analyze_project",
            ],
            max_iterations=max_iterations,
        )


bug_fix_agent = BugFixAgent()
