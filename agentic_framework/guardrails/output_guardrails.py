"""Output Guardrails for Agentic AI Framework.

Validates agent-proposed shell commands, code patches, and generated files
to prevent destructive system operations, syntax errors, and invalid packages.
"""

import ast
import json
import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from agentic_framework.config import settings
from agentic_framework.observability.logger import logger


@dataclass
class OutputGuardrailResult:
    passed: bool
    violations: List[str]
    error_message: Optional[str] = None


class OutputGuardrailEngine:
    """Enforces execution safety, code syntax validity, and patch boundaries."""

    # Explicitly blacklisted destructive commands
    DANGEROUS_COMMAND_PATTERNS = [
        r"(?i)\brm\s+(-rf|-fr|-r)\s+[/~]",
        r"(?i)\bdel\s+(/f\s+|/q\s+|/s\s+)*[c-z]:[\\/]",
        r"(?i)\brmdir\s+/s\s+/q\s+[c-z]:[\\/]",
        r"(?i)\bformat\s+[a-z]:",
        r"(?i)\bmkfs\b",
        r"(?i)\bdd\s+if=",
        r"(?i):\(\)\{\s*:\|:&\s*\};:",  # Fork bomb
        r"(?i)\bshutdown\b",
        r"(?i)\breboot\b",
        r"(?i)chmod\s+-R\s+777\s+/",
        r"(?i)curl.*\|\s*(bash|sh|powershell)",
        r"(?i)wget.*\|\s*(bash|sh|powershell)",
    ]

    def validate_command(self, command: str) -> OutputGuardrailResult:
        """Verify that shell command is safe to execute."""
        if not settings.GUARDRAILS_ENABLED or settings.ALLOW_DANGEROUS_COMMANDS:
            return OutputGuardrailResult(passed=True, violations=[])

        for pattern in self.DANGEROUS_COMMAND_PATTERNS:
            if re.search(pattern, command):
                violation = f"Potentially destructive system command blocked: '{command}'"
                logger.guardrail_alert("Output/DangerousCommand", violation, passed=False)
                return OutputGuardrailResult(
                    passed=False,
                    violations=[violation],
                    error_message=f"Dangerous command disallowed by security guardrail: pattern {pattern}",
                )

        return OutputGuardrailResult(passed=True, violations=[])

    def validate_code_syntax(self, file_path: str, code_content: str) -> OutputGuardrailResult:
        """Ensure proposed code or file edit has valid syntax."""
        if not settings.GUARDRAILS_ENABLED:
            return OutputGuardrailResult(passed=True, violations=[])

        # Python syntax validation using built-in AST parser
        if file_path.endswith(".py"):
            try:
                ast.parse(code_content, filename=file_path)
            except SyntaxError as e:
                violation = f"Syntax error in Python code for {file_path}: {e.msg} (line {e.lineno})"
                logger.guardrail_alert("Output/SyntaxValidator", violation, passed=False)
                return OutputGuardrailResult(
                    passed=False,
                    violations=[violation],
                    error_message=f"Generated code failed Python syntax validation: {e.msg} at line {e.lineno}",
                )

        # JSON syntax validation
        elif file_path.endswith(".json"):
            try:
                json.loads(code_content)
            except json.JSONDecodeError as e:
                violation = f"Invalid JSON syntax in {file_path}: {e.msg}"
                logger.guardrail_alert("Output/SyntaxValidator", violation, passed=False)
                return OutputGuardrailResult(
                    passed=False,
                    violations=[violation],
                    error_message=f"Generated JSON is malformed: {e.msg}",
                )

        return OutputGuardrailResult(passed=True, violations=[])


output_guardrails = OutputGuardrailEngine()
