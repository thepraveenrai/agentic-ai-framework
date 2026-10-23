"""Diff and Patch Utility for Agentic Code Updates.

Generates unified diffs, performs surgical code replacements, and validates
syntactic consistency before applying file mutations.
"""

import difflib
from pathlib import Path
from typing import Tuple, Optional
from agentic_framework.guardrails.output_guardrails import output_guardrails


class DiffUtils:
    """Handles unified diff generation and atomic patching."""

    @staticmethod
    def generate_diff(original_text: str, modified_text: str, file_path: str = "file") -> str:
        """Create standard unified diff string."""
        orig_lines = original_text.splitlines(keepends=True)
        mod_lines = modified_text.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            mod_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
        return "".join(diff)

    @staticmethod
    def apply_replacement(
        original_text: str, target_content: str, replacement_content: str
    ) -> Tuple[bool, str, Optional[str]]:
        """Safely replace target_content in original_text if unique."""
        count = original_text.count(target_content)
        if count == 0:
            return False, original_text, "Target content not found in file."
        if count > 1:
            return False, original_text, f"Target content is ambiguous (found {count} occurrences)."

        new_text = original_text.replace(target_content, replacement_content, 1)
        return True, new_text, None

    @staticmethod
    def validate_and_apply(
        file_path: Path, new_content: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate code syntax and write atomically to disk."""
        # 1. Output guardrail syntax validation
        check = output_guardrails.validate_code_syntax(str(file_path), new_content)
        if not check.passed:
            return False, check.error_message

        # 2. Write file safely
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(new_content, encoding="utf-8")
            return True, None
        except Exception as e:
            return False, str(e)


diff_utils = DiffUtils()
