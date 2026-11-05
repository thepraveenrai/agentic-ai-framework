"""Model Context Protocol (MCP) Tools.

Standardized tool definitions exposing filesystem operations, code search (RAG),
patch application, terminal execution, and test runners with Guardrails and HITL.
"""

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from agentic_framework.config import settings
from agentic_framework.core.hitl import hitl_manager, ActionRiskLevel
from agentic_framework.guardrails.output_guardrails import output_guardrails
from agentic_framework.rag.retriever import retriever
from agentic_framework.utils.diff_utils import diff_utils
from agentic_framework.utils.project_analyzer import project_analyzer
from agentic_framework.observability.logger import logger
from agentic_framework.mcp.integrations import (
    gitlab_integration,
    github_integration,
    jira_integration,
    gmail_integration,
    slack_integration,
)


@dataclass
class FileModification:
    file_path: str
    lines_added: int
    lines_deleted: int
    total_lines_changed: int
    diff: str


class ToolDefinition:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        func: Callable,
        risk_level: ActionRiskLevel = ActionRiskLevel.LOW,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func
        self.risk_level = risk_level


class MCPToolRegistry:
    """Registry of tools available to agents and external MCP clients."""

    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self.recorded_modifications: List[FileModification] = []
        self._register_default_tools()

    def reset_modification_tracking(self) -> None:
        """Clear recorded file changes before an agent step."""
        self.recorded_modifications.clear()

    def record_modification(self, file_path: str, orig_content: str, new_content: str) -> None:
        """Track surgical line modifications made by tools."""
        diff_str = diff_utils.generate_diff(orig_content, new_content, file_path)
        added = sum(1 for line in diff_str.splitlines() if line.startswith('+') and not line.startswith('+++'))
        deleted = sum(1 for line in diff_str.splitlines() if line.startswith('-') and not line.startswith('---'))
        self.recorded_modifications.append(
            FileModification(
                file_path=file_path,
                lines_added=added,
                lines_deleted=deleted,
                total_lines_changed=added + deleted,
                diff=diff_str,
            )
        )

    def get_recorded_modifications(self) -> List[FileModification]:
        """Return all file modifications recorded in the current session."""
        return list(self.recorded_modifications)

    def register(self, tool: ToolDefinition) -> None:
        self.tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self.tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return MCP standard tool declarations."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.parameters,
            }
            for t in self.tools.values()
        ]

    def _resolve_path(self, file_path: str) -> Path:
        """Resolve path relative to target project root."""
        target_root = settings.get_target_path()
        p = Path(file_path)
        if not p.is_absolute():
            p = (target_root / p).resolve()
        return p

    def _register_default_tools(self) -> None:
        # 1. read_file
        self.register(
            ToolDefinition(
                name="read_file",
                description="Read lines or full content from a file in the target project.",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Relative or absolute file path"},
                        "start_line": {"type": "integer", "description": "Optional 1-indexed starting line"},
                        "end_line": {"type": "integer", "description": "Optional 1-indexed ending line"},
                    },
                    "required": ["file_path"],
                },
                func=self._tool_read_file,
                risk_level=ActionRiskLevel.LOW,
            )
        )

        # 2. write_file
        self.register(
            ToolDefinition(
                name="write_file",
                description="Create or overwrite a file in the target project with new content.",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Target file path"},
                        "content": {"type": "string", "description": "Complete new content of the file"},
                    },
                    "required": ["file_path", "content"],
                },
                func=self._tool_write_file,
                risk_level=ActionRiskLevel.MEDIUM,
            )
        )

        # 3. apply_patch
        self.register(
            ToolDefinition(
                name="apply_patch",
                description="Surgically replace target code with replacement code in an existing file.",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File to modify"},
                        "target_content": {"type": "string", "description": "Exact lines of code to replace"},
                        "replacement_content": {"type": "string", "description": "New code to put in place"},
                    },
                    "required": ["file_path", "target_content", "replacement_content"],
                },
                func=self._tool_apply_patch,
                risk_level=ActionRiskLevel.MEDIUM,
            )
        )

        # 4. list_directory
        self.register(
            ToolDefinition(
                name="list_directory",
                description="List files and folders in a target project directory.",
                parameters={
                    "type": "object",
                    "properties": {
                        "directory_path": {"type": "string", "description": "Directory to inspect (default '.')"},
                    },
                },
                func=self._tool_list_directory,
                risk_level=ActionRiskLevel.LOW,
            )
        )

        # 5. search_code
        self.register(
            ToolDefinition(
                name="search_code",
                description="Perform semantic & lexical RAG search across the target codebase.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Keywords, function name, or natural language query"},
                        "top_k": {"type": "integer", "description": "Number of snippets to retrieve (default 4)"},
                    },
                    "required": ["query"],
                },
                func=self._tool_search_code,
                risk_level=ActionRiskLevel.LOW,
            )
        )

        # 6. run_shell
        self.register(
            ToolDefinition(
                name="run_shell",
                description="Execute a safe shell command inside the target project directory.",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command line string to run"},
                    },
                    "required": ["command"],
                },
                func=self._tool_run_shell,
                risk_level=ActionRiskLevel.HIGH,
            )
        )

        # 7. run_project_tests
        self.register(
            ToolDefinition(
                name="run_project_tests",
                description="Run the test suite (pytest, npm test, etc.) in the target project.",
                parameters={
                    "type": "object",
                    "properties": {
                        "test_target": {"type": "string", "description": "Optional specific test file or test pattern"},
                    },
                },
                func=self._tool_run_tests,
                risk_level=ActionRiskLevel.HIGH,
            )
        )

        # 8. analyze_project
        self.register(
            ToolDefinition(
                name="analyze_project",
                description="Inspect the target project tech stack, languages, and test frameworks.",
                parameters={"type": "object", "properties": {}},
                func=self._tool_analyze_project,
                risk_level=ActionRiskLevel.LOW,
            )
        )

        # 9. gitlab_workflow
        self.register(
            ToolDefinition(
                name="gitlab_workflow",
                description="Stage changes, commit, push branch to GitLab, and create a Merge Request.",
                parameters={
                    "type": "object",
                    "properties": {
                        "current_branch": {"type": "string", "description": "Branch to create/push (e.g. 'fix/issue-12')"},
                        "target_branch": {"type": "string", "description": "Target branch to merge into (default: 'main')", "default": "main"},
                        "commit_message": {"type": "string", "description": "Git commit message"},
                        "create_mr": {"type": "boolean", "description": "Create a GitLab Merge Request (default: true)", "default": True},
                        "mr_title": {"type": "string", "description": "Optional custom MR title"},
                        "mr_description": {"type": "string", "description": "Optional custom MR description"},
                        "files": {"type": "array", "items": {"type": "string"}, "description": "Optional list of files to stage"},
                        "project_id": {"type": "string", "description": "Optional GitLab project ID or URL-encoded path"},
                    },
                    "required": ["current_branch", "commit_message"],
                },
                func=self._tool_gitlab_workflow,
                risk_level=ActionRiskLevel.HIGH,
            )
        )

        # 10. github_workflow
        self.register(
            ToolDefinition(
                name="github_workflow",
                description="Stage changes, commit, push branch to GitHub, and create a Pull Request.",
                parameters={
                    "type": "object",
                    "properties": {
                        "current_branch": {"type": "string", "description": "Branch to create/push (e.g. 'fix/issue-12')"},
                        "target_branch": {"type": "string", "description": "Target branch to merge into (default: 'main')", "default": "main"},
                        "commit_message": {"type": "string", "description": "Git commit message"},
                        "create_pr": {"type": "boolean", "description": "Create a GitHub Pull Request (default: true)", "default": True},
                        "pr_title": {"type": "string", "description": "Optional custom PR title"},
                        "pr_description": {"type": "string", "description": "Optional custom PR description"},
                        "files": {"type": "array", "items": {"type": "string"}, "description": "Optional list of files to stage"},
                        "repository": {"type": "string", "description": "Optional GitHub repository ('owner/repo')"},
                    },
                    "required": ["current_branch", "commit_message"],
                },
                func=self._tool_github_workflow,
                risk_level=ActionRiskLevel.HIGH,
            )
        )

        # 11. jira_update_status
        self.register(
            ToolDefinition(
                name="jira_update_status",
                description="Transition Jira ticket status (e.g. 'In Progress', 'In Review', 'Done').",
                parameters={
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string", "description": "Jira ticket key (e.g. 'PROJ-123')"},
                        "status_name": {"type": "string", "description": "Target status name"},
                        "comment": {"type": "string", "description": "Optional comment during transition"},
                    },
                    "required": ["issue_key", "status_name"],
                },
                func=self._tool_jira_update_status,
                risk_level=ActionRiskLevel.MEDIUM,
            )
        )

        # 12. jira_add_comment
        self.register(
            ToolDefinition(
                name="jira_add_comment",
                description="Add a comment to a Jira ticket.",
                parameters={
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string", "description": "Jira ticket key (e.g. 'PROJ-123')"},
                        "comment": {"type": "string", "description": "Comment content"},
                    },
                    "required": ["issue_key", "comment"],
                },
                func=self._tool_jira_add_comment,
                risk_level=ActionRiskLevel.LOW,
            )
        )

        # 13. jira_get_issue
        self.register(
            ToolDefinition(
                name="jira_get_issue",
                description="Get details, status, and summary of a Jira ticket.",
                parameters={
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string", "description": "Jira ticket key (e.g. 'PROJ-123')"},
                    },
                    "required": ["issue_key"],
                },
                func=self._tool_jira_get_issue,
                risk_level=ActionRiskLevel.LOW,
            )
        )

        # 14. gmail_send
        self.register(
            ToolDefinition(
                name="gmail_send",
                description="Send an email via Gmail SMTP.",
                parameters={
                    "type": "object",
                    "properties": {
                        "to_email": {"type": "string", "description": "Recipient email address"},
                        "subject": {"type": "string", "description": "Email subject"},
                        "body": {"type": "string", "description": "Email body (plain text or markdown)"},
                        "cc": {"type": "array", "items": {"type": "string"}, "description": "Optional CC addresses"},
                    },
                    "required": ["to_email", "subject", "body"],
                },
                func=self._tool_gmail_send,
                risk_level=ActionRiskLevel.HIGH,
            )
        )

        # 15. gmail_reply
        self.register(
            ToolDefinition(
                name="gmail_reply",
                description="Reply to an email thread with proper In-Reply-To and References headers.",
                parameters={
                    "type": "object",
                    "properties": {
                        "to_email": {"type": "string", "description": "Recipient email address"},
                        "subject": {"type": "string", "description": "Original email subject (will prepend Re: if missing)"},
                        "body": {"type": "string", "description": "Reply content"},
                        "in_reply_to": {"type": "string", "description": "Message-ID of the parent email"},
                        "references": {"type": "string", "description": "Optional chain of Message-IDs"},
                    },
                    "required": ["to_email", "subject", "body", "in_reply_to"],
                },
                func=self._tool_gmail_reply,
                risk_level=ActionRiskLevel.HIGH,
            )
        )

        # 16. slack_send_message
        self.register(
            ToolDefinition(
                name="slack_send_message",
                description="Send a message to a Slack channel or thread.",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Message text"},
                        "channel": {"type": "string", "description": "Channel ID/name (defaults to SLACK_DEFAULT_CHANNEL)"},
                        "thread_ts": {"type": "string", "description": "Optional thread timestamp for threaded replies"},
                    },
                    "required": ["text"],
                },
                func=self._tool_slack_send_message,
                risk_level=ActionRiskLevel.LOW,
            )
        )

        # 17. slack_edit_message
        self.register(
            ToolDefinition(
                name="slack_edit_message",
                description="Edit an existing Slack message using its timestamp (ts).",
                parameters={
                    "type": "object",
                    "properties": {
                        "timestamp": {"type": "string", "description": "The timestamp 'ts' of the message to edit"},
                        "text": {"type": "string", "description": "New message content"},
                        "channel": {"type": "string", "description": "Channel ID/name (defaults to SLACK_DEFAULT_CHANNEL)"},
                    },
                    "required": ["timestamp", "text"],
                },
                func=self._tool_slack_edit_message,
                risk_level=ActionRiskLevel.LOW,
            )
        )

        # 18. slack_delete_message
        self.register(
            ToolDefinition(
                name="slack_delete_message",
                description="Delete a message from a Slack channel.",
                parameters={
                    "type": "object",
                    "properties": {
                        "timestamp": {"type": "string", "description": "The timestamp 'ts' of the message to delete"},
                        "channel": {"type": "string", "description": "Channel ID/name (defaults to SLACK_DEFAULT_CHANNEL)"},
                    },
                    "required": ["timestamp"],
                },
                func=self._tool_slack_delete_message,
                risk_level=ActionRiskLevel.MEDIUM,
            )
        )

    # Tool Implementations
    def _tool_read_file(self, file_path: str = "", start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        if not file_path:
            return "Error: 'file_path' argument is required. Please specify the target file path."
        p = self._resolve_path(file_path)
        if not p.exists():
            return f"Error: File not found at {file_path}"
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            if start_line is not None or end_line is not None:
                s = max(1, start_line or 1)
                e = min(len(lines), end_line or len(lines))
                sliced = lines[s - 1:e]
                numbered = [f"{s + i}: {line}" for i, line in enumerate(sliced)]
                return "\n".join(numbered)
            return content
        except Exception as e:
            return f"Error reading file: {e}"

    def _tool_write_file(self, file_path: str = "", content: str = "") -> str:
        if not file_path:
            return "Error: 'file_path' argument is required."
        p = self._resolve_path(file_path)
        orig_content = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        diff_str = diff_utils.generate_diff(orig_content, content, file_path)

        # HITL Approval
        decision = hitl_manager.request_approval(
            action_name=f"write_file({file_path})",
            risk_level=ActionRiskLevel.MEDIUM,
            details=f"File: {file_path}\nDiff:\n{diff_str}",
            payload={"file_path": file_path, "diff": diff_str},
        )
        if not decision.approved:
            return f"Action rejected by user: {decision.user_feedback}"

        success, err = diff_utils.validate_and_apply(p, content)
        if not success:
            return f"Failed to write file: {err}"
        self.record_modification(str(p), orig_content, content)
        return f"Successfully wrote {len(content)} bytes to {file_path}"

    def _tool_apply_patch(self, file_path: str = "", target_content: str = "", replacement_content: str = "") -> str:
        if not file_path:
            return "Error: 'file_path' argument is required."
        if not target_content:
            return "Error: 'target_content' argument is required. Specify the exact lines to replace."
        p = self._resolve_path(file_path)
        if not p.exists():
            return f"Error: Target file does not exist at {file_path}"

        orig_content = p.read_text(encoding="utf-8", errors="replace")
        ok, new_content, err = diff_utils.apply_replacement(orig_content, target_content, replacement_content)
        if not ok:
            return f"Patch failed: {err}"

        diff_str = diff_utils.generate_diff(orig_content, new_content, file_path)

        # HITL Approval
        decision = hitl_manager.request_approval(
            action_name=f"apply_patch({file_path})",
            risk_level=ActionRiskLevel.MEDIUM,
            details=f"File: {file_path}\nDiff:\n{diff_str}",
            payload={"file_path": file_path, "diff": diff_str},
        )
        if not decision.approved:
            return f"Patch rejected by user: {decision.user_feedback}"

        success, write_err = diff_utils.validate_and_apply(p, new_content)
        if not success:
            return f"Failed to apply patch due to syntax error: {write_err}"
        self.record_modification(str(p), orig_content, new_content)
        return f"Successfully applied surgical patch to {file_path}"

    def _tool_list_directory(self, directory_path: str = ".") -> str:
        p = self._resolve_path(directory_path)
        if not p.exists():
            return f"Error: Directory not found at {directory_path}"
        try:
            items = []
            for item in p.iterdir():
                if item.name in settings.EXCLUDED_DIRS:
                    continue
                tag = "[DIR]" if item.is_dir() else "[FILE]"
                items.append(f"{tag} {item.name}")
            return "\n".join(items) if items else "(empty directory)"
        except Exception as e:
            return f"Error listing directory: {e}"

    def _tool_search_code(self, query: str = "", top_k: int = 4) -> str:
        if not query:
            return "Error: 'query' argument is required. Specify what code or symbol to search for."
        return retriever.format_context_for_prompt(query, top_k=top_k)

    def _tool_run_shell(self, command: str = "") -> str:
        if not command:
            return "Error: 'command' argument is required."
        # Guardrail check
        guard_res = output_guardrails.validate_command(command)
        if not guard_res.passed:
            return f"Security Guardrail Blocked Command: {guard_res.error_message}"

        # HITL Approval
        decision = hitl_manager.request_approval(
            action_name=f"run_shell('{command}')",
            risk_level=ActionRiskLevel.HIGH,
            details=f"Executing shell command in {settings.get_target_path()}:\n$ {command}",
            payload={"command": command},
        )
        if not decision.approved:
            return f"Execution cancelled by user: {decision.user_feedback}"

        try:
            res = subprocess.run(
                command,
                cwd=str(settings.get_target_path()),
                shell=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            out = res.stdout + ("\nSTDERR:\n" + res.stderr if res.stderr else "")
            return f"Exit Code: {res.returncode}\nOutput:\n{out.strip()}"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 60 seconds."
        except Exception as e:
            return f"Command execution error: {e}"

    def _tool_run_tests(self, test_target: Optional[str] = None) -> str:
        detected_cmd = project_analyzer.detect_test_runner()
        cmd = f"{detected_cmd} {test_target}" if test_target else detected_cmd
        return self._tool_run_shell(cmd)

    def _tool_analyze_project(self) -> str:
        analysis = project_analyzer.analyze()
        lines = [f"{k}: {v}" for k, v in analysis.items()]
        return "\n".join(lines)

    def _tool_gitlab_workflow(
        self,
        current_branch: str,
        commit_message: str,
        target_branch: str = "main",
        create_mr: bool = True,
        mr_title: Optional[str] = None,
        mr_description: Optional[str] = None,
        files: Optional[List[str]] = None,
        project_id: Optional[str] = None,
    ) -> str:
        decision = hitl_manager.request_approval(
            action_name=f"gitlab_workflow('{current_branch}' -> '{target_branch}')",
            risk_level=ActionRiskLevel.HIGH,
            details=f"Push branch '{current_branch}' to GitLab with commit: '{commit_message}' and create_mr={create_mr}",
            payload={"branch": current_branch, "commit": commit_message, "create_mr": create_mr},
        )
        if not decision.approved:
            return f"GitLab workflow cancelled by user: {decision.user_feedback}"

        return gitlab_integration.gitlab_workflow(
            current_branch=current_branch,
            target_branch=target_branch,
            commit_message=commit_message,
            create_mr=create_mr,
            mr_title=mr_title,
            mr_description=mr_description,
            files=files,
            project_id=project_id,
        )

    def _tool_github_workflow(
        self,
        current_branch: str,
        commit_message: str,
        target_branch: str = "main",
        create_pr: bool = True,
        pr_title: Optional[str] = None,
        pr_description: Optional[str] = None,
        files: Optional[List[str]] = None,
        repository: Optional[str] = None,
    ) -> str:
        decision = hitl_manager.request_approval(
            action_name=f"github_workflow('{current_branch}' -> '{target_branch}')",
            risk_level=ActionRiskLevel.HIGH,
            details=f"Push branch '{current_branch}' to GitHub with commit: '{commit_message}' and create_pr={create_pr}",
            payload={"branch": current_branch, "commit": commit_message, "create_pr": create_pr},
        )
        if not decision.approved:
            return f"GitHub workflow cancelled by user: {decision.user_feedback}"

        return github_integration.github_workflow(
            current_branch=current_branch,
            target_branch=target_branch,
            commit_message=commit_message,
            create_pr=create_pr,
            pr_title=pr_title,
            pr_description=pr_description,
            files=files,
            repository=repository,
        )

    def _tool_jira_update_status(
        self,
        issue_key: str,
        status_name: str = "",
        comment: Optional[str] = None,
        target_status: Optional[str] = None,
    ) -> str:
        resolved_status = target_status or status_name
        decision = hitl_manager.request_approval(
            action_name=f"jira_update_status('{issue_key}', '{resolved_status}')",
            risk_level=ActionRiskLevel.MEDIUM,
            details=f"Transition Jira issue '{issue_key}' to '{resolved_status}'",
            payload={"issue_key": issue_key, "status_name": resolved_status},
        )
        if not decision.approved:
            return f"Jira status update cancelled by user: {decision.user_feedback}"

        return jira_integration.update_status(
            issue_key=issue_key,
            target_status=resolved_status,
            comment=comment,
        )

    def _tool_jira_add_comment(
        self,
        issue_key: str,
        comment: str,
    ) -> str:
        return jira_integration.add_comment(
            issue_key=issue_key,
            comment=comment,
        )

    def _tool_jira_get_issue(
        self,
        issue_key: str,
    ) -> str:
        return jira_integration.get_issue(
            issue_key=issue_key,
        )

    def _tool_gmail_send(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
    ) -> str:
        decision = hitl_manager.request_approval(
            action_name=f"gmail_send('{to_email}', '{subject}')",
            risk_level=ActionRiskLevel.HIGH,
            details=f"Send email to '{to_email}' with subject: '{subject}'",
            payload={"to": to_email, "subject": subject},
        )
        if not decision.approved:
            return f"Email sending cancelled by user: {decision.user_feedback}"

        return gmail_integration.send_email(
            to_email=to_email,
            subject=subject,
            body=body,
            cc=cc,
        )

    def _tool_gmail_reply(
        self,
        to_email: str,
        subject: str,
        body: str,
        in_reply_to: str,
        references: Optional[str] = None,
    ) -> str:
        decision = hitl_manager.request_approval(
            action_name=f"gmail_reply('{to_email}', '{subject}')",
            risk_level=ActionRiskLevel.HIGH,
            details=f"Reply to email '{to_email}' (In-Reply-To: {in_reply_to})",
            payload={"to": to_email, "subject": subject, "in_reply_to": in_reply_to},
        )
        if not decision.approved:
            return f"Email reply cancelled by user: {decision.user_feedback}"

        return gmail_integration.reply_email(
            to_email=to_email,
            subject=subject,
            body=body,
            in_reply_to=in_reply_to,
            references=references,
        )

    def _tool_slack_send_message(
        self,
        text: str,
        channel: Optional[str] = None,
        thread_ts: Optional[str] = None,
    ) -> str:
        return slack_integration.send_message(
            text=text,
            channel=channel,
            thread_ts=thread_ts,
        )

    def _tool_slack_edit_message(
        self,
        timestamp: str,
        text: str,
        channel: Optional[str] = None,
    ) -> str:
        return slack_integration.edit_message(
            timestamp=timestamp,
            text=text,
            channel=channel,
        )

    def _tool_slack_delete_message(
        self,
        timestamp: str,
        channel: Optional[str] = None,
    ) -> str:
        decision = hitl_manager.request_approval(
            action_name=f"slack_delete_message('{timestamp}')",
            risk_level=ActionRiskLevel.MEDIUM,
            details=f"Delete Slack message '{timestamp}' in channel '{channel or settings.SLACK_DEFAULT_CHANNEL}'",
            payload={"timestamp": timestamp, "channel": channel},
        )
        if not decision.approved:
            return f"Slack message deletion cancelled by user: {decision.user_feedback}"

        return slack_integration.delete_message(
            timestamp=timestamp,
            channel=channel,
        )


# Singleton tool registry
tool_registry = MCPToolRegistry()
