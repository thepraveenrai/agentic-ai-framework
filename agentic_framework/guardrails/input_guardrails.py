"""Input Guardrails for Agentic AI Framework.

Protects against prompt injections, jailbreak attempts, secret token leakage,
and out-of-scope requests before prompting the agents.
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Tuple
from agentic_framework.config import settings
from agentic_framework.observability.logger import logger


@dataclass
class InputGuardrailResult:
    passed: bool
    sanitized_text: str
    violations: List[str]
    blocked_reason: Optional[str] = None


class InputGuardrailEngine:
    """Multi-stage input validation and sanitation engine."""

    # Patterns indicating prompt injection or system override attempts
    INJECTION_PATTERNS = [
        r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"(?i)disregard\s+(the\s+)?(previous|prior)\s+rules",
        r"(?i)you\s+are\s+now\s+in\s+developer\s+mode",
        r"(?i)system\s+override",
        r"(?i)reveal\s+(your\s+)?(system\s+prompt|instructions|secret\s+key)",
        r"(?i)bypass\s+all\s+(filters|guardrails|safety)",
        r"(?i)act\s+as\s+DAN\b",
        r"(?i)jailbreak",
    ]

    # Secret / credential regex patterns
    SECRET_PATTERNS = [
        (r"sk-[a-zA-Z0-9_-]{20,}", "[REDACTED_OPENAI_KEY]"),
        (r"sk-or-v1-[a-zA-Z0-9]{32,}", "[REDACTED_OPENROUTER_KEY]"),
        (r"AKIA[0-9A-Z]{16}", "[REDACTED_AWS_KEY]"),
        (r"ghp_[a-zA-Z0-9]{36}", "[REDACTED_GITHUB_TOKEN]"),
        (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", "[REDACTED_PRIVATE_KEY]"),
        (r"(?i)(password|secret|apikey|token)\s*=\s*['\"][^\s'\"]{8,}['\"]", r"\1='[REDACTED]'"),
    ]

    def validate(self, text: str) -> InputGuardrailResult:
        """Run all input guardrail checks on user prompt or task specification."""
        if not settings.GUARDRAILS_ENABLED:
            return InputGuardrailResult(passed=True, sanitized_text=text, violations=[])

        violations = []
        sanitized = text

        # 1. Prompt Injection & Jailbreak Check
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, text):
                violations.append(f"Potential prompt injection detected matching pattern: {pattern}")
                logger.guardrail_alert("Input/PromptInjection", f"Blocked: {pattern}", passed=False)
                return InputGuardrailResult(
                    passed=False,
                    sanitized_text=sanitized,
                    violations=violations,
                    blocked_reason="Request contains patterns attempting to override agent instructions or guardrails.",
                )

        # 2. Secret Redaction
        redacted_count = 0
        for pattern, replacement in self.SECRET_PATTERNS:
            sanitized, count = re.subn(pattern, replacement, sanitized)
            if count > 0:
                redacted_count += count
                violations.append(f"Sanitized {count} sensitive credential/token instance(s)")

        if redacted_count > 0:
            logger.guardrail_alert("Input/SecretDetector", f"Redacted {redacted_count} sensitive token(s)", passed=True)

        return InputGuardrailResult(
            passed=True,
            sanitized_text=sanitized,
            violations=violations,
            blocked_reason=None,
        )


input_guardrails = InputGuardrailEngine()
