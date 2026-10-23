"""FeatureDevAgent for New Feature Implementation and Code Evolution.

Translates requirements into software designs, identifies insertion points
across existing code, crafts robust implementations, and ensures clean integration.
"""

from typing import Optional, List
from agentic_framework.agents.base import BaseAgent

FEATURE_DEV_SYSTEM_PROMPT = """You are the FeatureDevAgent, a Senior Full-Stack Feature Engineer.
Your objective is to design and implement new features, APIs, modules, or enhancements
into the target project according to user requirements.

Follow this direct, action-oriented development flow:
1. Locate and read the relevant target file using 'read_file'.
2. Promptly implement the change:
   - For adding functions or modifying existing code, call 'apply_patch' or 'write_file'.
   - Do NOT spend excess iterations inspecting metadata or traces; apply the code patch promptly!
3. Run tests using 'run_project_tests' to verify syntax and integration.
4. Conclude with a clear explanation of the implemented feature and signatures.
"""


class FeatureDevAgent(BaseAgent):
    """Specialized agent for designing and implementing new software features."""

    def __init__(self, max_iterations: int = 15):
        super().__init__(
            name="FeatureDevAgent",
            role="Senior Software Feature Engineer",
            system_prompt=FEATURE_DEV_SYSTEM_PROMPT,
            allowed_tools=[
                "search_code",
                "read_file",
                "write_file",
                "apply_patch",
                "list_directory",
                "run_project_tests",
                "analyze_project",
            ],
            max_iterations=max_iterations,
        )


feature_dev_agent = FeatureDevAgent()
