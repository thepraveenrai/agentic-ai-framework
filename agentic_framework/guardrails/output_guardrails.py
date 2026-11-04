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

    # Secret and credential leakage patterns
    SECRET_PATTERNS = [
        (r"sk-[a-zA-Z0-9_-]{20,}", "OpenAI API Key"),
        (r"sk-or-v1-[a-zA-Z0-9]{32,}", "OpenRouter API Key"),
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
        (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", "Private Cryptographic Key"),
        (r"(?i)(password|secret|apikey|api_key|token)\s*[:=]\s*['\"][^\s'\"]{10,}['\"]", "Hardcoded Password or Token"),
    ]

    def validate_command(self, command: str) -> OutputGuardrailResult:
        """Verify that shell command is safe to execute and does not leak credentials."""
        if not settings.GUARDRAILS_ENABLED or settings.ALLOW_DANGEROUS_COMMANDS:
            return OutputGuardrailResult(passed=True, violations=[])

        # 1. Check for destructive commands
        for pattern in self.DANGEROUS_COMMAND_PATTERNS:
            if re.search(pattern, command):
                violation = f"Potentially destructive system command blocked: '{command}'"
                logger.guardrail_alert("Output/DangerousCommand", violation, passed=False)
                return OutputGuardrailResult(
                    passed=False,
                    violations=[violation],
                    error_message=f"Dangerous command disallowed by security guardrail: pattern {pattern}",
                )

        # 2. Check for credential exposure in commands
        for pattern, secret_type in self.SECRET_PATTERNS:
            if re.search(pattern, command):
                violation = f"Potentially exposed credential in shell command: {secret_type}"
                logger.guardrail_alert("Output/SecretLeakage", violation, passed=False)
                return OutputGuardrailResult(
                    passed=False,
                    violations=[violation],
                    error_message=f"Command blocked: contains sensitive credential ({secret_type})",
                )

        return OutputGuardrailResult(passed=True, violations=[])

    def validate_code_syntax(self, file_path: str, code_content: str) -> OutputGuardrailResult:
        """Ensure proposed code has valid syntax and contains no exposed secrets."""
        if not settings.GUARDRAILS_ENABLED:
            return OutputGuardrailResult(passed=True, violations=[])

        # 1. Check for exposed secrets/credentials in code before saving
        for pattern, secret_type in self.SECRET_PATTERNS:
            if re.search(pattern, code_content):
                violation = f"Exposed credential detected in {file_path}: {secret_type}"
                logger.guardrail_alert("Output/SecretLeakage", violation, passed=False)
                return OutputGuardrailResult(
                    passed=False,
                    violations=[violation],
                    error_message=f"File update blocked: proposed code contains hardcoded secret/credential ({secret_type})",
                )

        # 2. Python syntax validation using built-in AST parser
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
