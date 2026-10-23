"""RegressionTestAgent for Test Discovery, Synthesis, and Regression Verification.

Discovers existing test suites, generates targeted unit/integration tests for
modified or new code, executes tests, and verifies zero regression across the system.
"""

from typing import Optional, List
from agentic_framework.agents.base import BaseAgent

REGRESSION_TEST_SYSTEM_PROMPT = """You are the RegressionTestAgent, an autonomous Regression Verification Gatekeeper.
Your sole mission is to verify that code modifications produced by BugFixAgent or FeatureDevAgent have NOT caused any regression issues in the updated file.

CRITICAL OPERATIONAL RULES:
1. Targeted Scope: Review ONLY the specific file that was updated. Do NOT inspect, read, or audit unrelated files in the project.
2. Targeted Test Run: Call 'run_project_tests' targeting ONLY the test file matching the updated module (e.g., 'test_target="tests/test_calculator.py"').
   - Do NOT run all tests or explore unrelated directories.
3. Verification Report:
   - Conclude with a concise verdict:
     [REGRESSION STATUS: PASSED] if the target test passes and no regressions occurred.
     [REGRESSION STATUS: FAILED] if any regression was introduced.
"""


class RegressionTestAgent(BaseAgent):
    """Specialized agent acting exclusively as Regression Verification Gatekeeper for BugFixAgent and FeatureDevAgent."""

    def __init__(self, max_iterations: int = 6):
        super().__init__(
            name="RegressionTestAgent",
            role="Regression Verification Gatekeeper for BugFixAgent & FeatureDevAgent",
            system_prompt=REGRESSION_TEST_SYSTEM_PROMPT,
            allowed_tools=[
                "run_project_tests",
                "read_file",
                "search_code",
                "apply_patch",
                "write_file",
                "list_directory",
                "analyze_project",
            ],
            max_iterations=max_iterations,
        )


regression_test_agent = RegressionTestAgent()
