"""GitLab Enterprise Integration Tool.

Automates staging changes, committing, pushing branches to GitLab,
and creating or linking Merge Requests (MR) via GitLab REST API v4.
"""

import os
import re
import subprocess
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional, List
import httpx

from agentic_framework.config import settings
from agentic_framework.observability.logger import logger


class GitLabIntegration:
    """Manages Git local workflow and GitLab remote Merge Requests."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        default_project_id: Optional[str] = None,
    ):
        self.base_url = (base_url or settings.GITLAB_URL).rstrip("/")
        self.token = token or settings.GITLAB_TOKEN
        self.default_project_id = default_project_id or settings.GITLAB_PROJECT_ID

    def _run_git(self, args: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        """Execute a git command safely."""
        repo_dir = str(cwd or settings.get_target_path())
        return subprocess.run(
            ["git"] + args,
            cwd=repo_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def detect_project_path(self, cwd: Optional[Path] = None) -> Optional[str]:
        """Auto-detect project path (e.g. 'my-org/my-repo') from git remote origin."""
        res = self._run_git(["remote", "get-url", "origin"], cwd=cwd)
        if res.returncode != 0 or not res.stdout.strip():
            return self.default_project_id

        remote = res.stdout.strip()
        # Handle SSH format: git@gitlab.com:owner/repo.git
        ssh_match = re.search(r"[:/]([a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+?)(?:\.git)?$", remote)
        if ssh_match:
            return ssh_match.group(1)
        return self.default_project_id

    def gitlab_workflow(
        self,
        current_branch: str,
        target_branch: str = "main",
        commit_message: str = "Automated changes via Agentic AI",
        create_mr: bool = True,
        mr_title: Optional[str] = None,
        mr_description: Optional[str] = None,
        files: Optional[List[str]] = None,
        project_id: Optional[str] = None,
    ) -> str:
        """Stage, commit, push branch, and optionally create a GitLab Merge Request."""
        target_dir = settings.get_target_path()

        # 1. Verify this is a Git repository
        check_repo = self._run_git(["rev-parse", "--is-inside-work-tree"], cwd=target_dir)
        if check_repo.returncode != 0:
            return f"Error: '{target_dir}' is not a valid Git repository."

        # 2. Checkout or create branch
        checkout_res = self._run_git(["checkout", "-B", current_branch], cwd=target_dir)
        if checkout_res.returncode != 0:
            return f"Error checking out branch '{current_branch}': {checkout_res.stderr.strip()}"

        # 3. Stage changes
        if files:
            add_args = ["add"] + files
        else:
            add_args = ["add", "-A"]
        add_res = self._run_git(add_args, cwd=target_dir)
        if add_res.returncode != 0:
            return f"Error staging files: {add_res.stderr.strip()}"

        # 4. Check if there are changes to commit
        status_res = self._run_git(["status", "--porcelain"], cwd=target_dir)
        has_staged_changes = bool(status_res.stdout.strip())

        if has_staged_changes:
            commit_res = self._run_git(["commit", "-m", commit_message], cwd=target_dir)
            if commit_res.returncode != 0:
                return f"Error committing changes: {commit_res.stderr.strip()}"
            commit_info = f"Committed: '{commit_message}'"
        else:
            commit_info = "No new local changes to commit (working tree clean)."

        # 5. Push to remote
        push_res = self._run_git(["push", "-u", "origin", current_branch], cwd=target_dir)
        if push_res.returncode != 0:
            return f"Error pushing branch '{current_branch}' to origin: {push_res.stderr.strip()}"

        result_lines = [
            f"✅ Branch '{current_branch}' successfully pushed to remote.",
            f"• {commit_info}",
        ]

        # 6. Create Merge Request if requested
        if create_mr:
            mr_result = self.create_merge_request(
                source_branch=current_branch,
                target_branch=target_branch,
                title=mr_title or commit_message,
                description=mr_description or f"Automated Merge Request created by Agentic AI Framework.\n\nCommit: {commit_message}",
                project_id=project_id,
                cwd=target_dir,
            )
            result_lines.append(mr_result)

        return "\n".join(result_lines)

    def create_merge_request(
        self,
        source_branch: str,
        target_branch: str = "main",
        title: str = "Merge Request",
        description: str = "",
        project_id: Optional[str] = None,
        cwd: Optional[Path] = None,
    ) -> str:
        """Call GitLab REST API v4 to open a Merge Request."""
        token = self.token or settings.GITLAB_TOKEN
        if not token:
            return "⚠️ GitLab Token not found. Set 'GITLAB_TOKEN' in your .env to automatically create Merge Requests."

        proj = project_id or self.detect_project_path(cwd=cwd)
        if not proj:
            return "⚠️ GitLab project_id could not be detected. Set 'GITLAB_PROJECT_ID' in .env or provide 'project_id'."

        # URL-encode project path (e.g. 'org/repo' -> 'org%2Frepo')
        encoded_project = urllib.parse.quote(str(proj), safe="")
        endpoint = f"{self.base_url}/api/v4/projects/{encoded_project}/merge_requests"

        headers = {
            "PRIVATE-TOKEN": token,
            "Content-Type": "application/json",
        }
        payload = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": description,
            "remove_source_branch": False,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(endpoint, headers=headers, json=payload)

                if resp.status_code == 201:
                    data = resp.json()
                    mr_url = data.get("web_url", "")
                    iid = data.get("iid", "")
                    return f"🚀 GitLab Merge Request !{iid} created successfully:\n  {mr_url}"

                # If MR already exists (409 Conflict)
                if resp.status_code == 409:
                    # Query existing open MRs
                    list_resp = client.get(
                        f"{endpoint}?source_branch={source_branch}&state=opened",
                        headers=headers,
                    )
                    if list_resp.status_code == 200 and list_resp.json():
                        existing_mr = list_resp.json()[0]
                        return f"ℹ️ An open Merge Request already exists for '{source_branch}':\n  {existing_mr.get('web_url')}"
                    return f"⚠️ Conflict: Merge request already exists for branch '{source_branch}'."

                return f"❌ GitLab API Error ({resp.status_code}): {resp.text}"

        except Exception as e:
            return f"❌ Failed to connect to GitLab API at {self.base_url}: {e}"


gitlab_integration = GitLabIntegration()

