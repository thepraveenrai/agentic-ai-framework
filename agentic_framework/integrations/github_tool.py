"""GitHub Enterprise Integration Tool.

Automates staging changes, committing, pushing branches to GitHub,
and creating or linking Pull Requests (PR) via GitHub REST API v3.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
import httpx

from agentic_framework.config import settings
from agentic_framework.observability.logger import logger


class GitHubIntegration:
    """Manages Git local workflow and GitHub remote Pull Requests."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        token: Optional[str] = None,
        default_repository: Optional[str] = None,
    ):
        self.api_url = (api_url or settings.GITHUB_API_URL).rstrip("/")
        self.token = token or settings.GITHUB_TOKEN
        self.default_repository = default_repository or settings.GITHUB_REPOSITORY

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

    def detect_repository(self, cwd: Optional[Path] = None) -> Optional[str]:
        """Auto-detect owner/repo (e.g. 'octocat/hello-world') from git remote origin."""
        res = self._run_git(["remote", "get-url", "origin"], cwd=cwd)
        if res.returncode != 0 or not res.stdout.strip():
            return self.default_repository

        remote = res.stdout.strip()
        # Handle SSH (git@github.com:owner/repo.git) and HTTPS (https://github.com/owner/repo.git)
        match = re.search(r"[:/]([a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+?)(?:\.git)?$", remote)
        if match:
            return match.group(1)
        return self.default_repository

    def github_workflow(
        self,
        current_branch: str,
        target_branch: str = "main",
        commit_message: str = "Automated changes via Agentic AI",
        create_pr: bool = True,
        pr_title: Optional[str] = None,
        pr_description: Optional[str] = None,
        files: Optional[List[str]] = None,
        repository: Optional[str] = None,
    ) -> str:
        """Stage, commit, push branch, and optionally create a GitHub Pull Request."""
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
            f"✅ Branch '{current_branch}' successfully pushed to GitHub.",
            f"• {commit_info}",
        ]

        # 6. Create Pull Request if requested
        if create_pr:
            pr_result = self.create_pull_request(
                head_branch=current_branch,
                base_branch=target_branch,
                title=pr_title or commit_message,
                description=pr_description or f"Automated Pull Request created by Agentic AI Framework.\n\nCommit: {commit_message}",
                repository=repository,
                cwd=target_dir,
            )
            result_lines.append(pr_result)

        return "\n".join(result_lines)

    def create_pull_request(
        self,
        head_branch: str,
        base_branch: str = "main",
        title: str = "Pull Request",
        description: str = "",
        repository: Optional[str] = None,
        cwd: Optional[Path] = None,
    ) -> str:
        """Call GitHub REST API to open a Pull Request."""
        token = self.token or settings.GITHUB_TOKEN
        if not token:
            return "⚠️ GitHub Token not found. Set 'GITHUB_TOKEN' in your .env to automatically create Pull Requests."

        repo = repository or self.detect_repository(cwd=cwd)
        if not repo:
            return "⚠️ GitHub repository could not be detected. Set 'GITHUB_REPOSITORY' (owner/repo) in .env or provide 'repository'."

        endpoint = f"{self.api_url}/repos/{repo}/pulls"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        payload = {
            "head": head_branch,
            "base": base_branch,
            "title": title,
            "body": description,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(endpoint, headers=headers, json=payload)

                if resp.status_code == 201:
                    data = resp.json()
                    pr_url = data.get("html_url", "")
                    pr_number = data.get("number", "")
                    return f"🚀 GitHub Pull Request #{pr_number} created successfully:\n  {pr_url}"

                # 422 Unprocessable Entity - often means PR already exists
                if resp.status_code == 422:
                    list_resp = client.get(
                        f"{endpoint}?head={repo.split('/')[0]}:{head_branch}&state=open",
                        headers=headers,
                    )
                    if list_resp.status_code == 200 and list_resp.json():
                        existing_pr = list_resp.json()[0]
                        return f"ℹ️ An open Pull Request already exists for '{head_branch}':\n  {existing_pr.get('html_url')}"
                    err_msg = resp.json().get("message", resp.text)
                    return f"⚠️ GitHub PR creation blocked: {err_msg}"

                return f"❌ GitHub API Error ({resp.status_code}): {resp.text}"

        except Exception as e:
            return f"❌ Failed to connect to GitHub API: {e}"


github_integration = GitHubIntegration()

