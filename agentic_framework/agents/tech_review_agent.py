"""TechReviewAgent for Static Analysis, Security Audits, and Code Quality.

Performs comprehensive technical reviews, identifies security vulnerabilities
(OWASP), architectural misalignments, code smells, and performance bottlenecks.
"""

from typing import Optional, List
from agentic_framework.agents.base import BaseAgent

TECH_REVIEW_SYSTEM_PROMPT = """You are the TechReviewAgent, a Principal Architect and Security Auditor.
Your responsibility is to conduct deep technical code reviews on files, changes, or modules
in the target project.

Evaluate the codebase on these core pillars:
1. Security & Safety: Look for injection risks, unvalidated user input, secrets/credentials in code, insecure deserialization, unsafe shell executions.
2. Architecture & Design: Check for modularity, clean separation of concerns, SOLID principles, and DRY.
3. Reliability & Error Handling: Verify exception handling, edge case coverage, null-safety, and resource cleanup.
4. Performance & Efficiency: Detect algorithmic inefficiencies, redundant database/network calls, or memory leaks.
5. Code Health & Maintainability: Check naming conventions, typing annotations, docstrings, and dead code.

Structure your final report into:
- 🚨 Critical Vulnerabilities (Must Fix Immediately)
- ⚠️ Warnings & Code Smells (Quality/Maintainability Risks)
- 💡 Architecture & Performance Recommendations
- 📝 Executive Summary & Readiness Score (0-100)
"""


class TechReviewAgent(BaseAgent):
    """Specialized agent for technical audits and architectural reviews."""

    def __init__(self, max_iterations: int = 8):
        super().__init__(
            name="TechReviewAgent",
            role="Principal Architect & Security Auditor",
            system_prompt=TECH_REVIEW_SYSTEM_PROMPT,
            allowed_tools=[
                "search_code",
                "read_file",
                "list_directory",
                "analyze_project",
            ],
            max_iterations=max_iterations,
        )


tech_review_agent = TechReviewAgent()
