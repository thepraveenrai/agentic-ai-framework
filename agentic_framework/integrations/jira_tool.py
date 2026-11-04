"""Jira Enterprise Integration Tool.

Automates updating Jira issue statuses, retrieving issue details,
and adding comments via Jira REST API v2/v3.
"""

import base64
from typing import Dict, Any, Optional, List
import httpx

from agentic_framework.config import settings
from agentic_framework.observability.logger import logger


class JiraIntegration:
    """Manages Jira issue transitions, comments, and inspection."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
    ):
        self.base_url = (base_url or settings.JIRA_URL or "").rstrip("/")
        self.email = email or settings.JIRA_EMAIL
        self.api_token = api_token or settings.JIRA_API_TOKEN

    def _get_headers(self) -> Dict[str, str]:
        """Generate Jira basic auth header (Email:Token)."""
        if not self.email or not self.api_token:
            raise ValueError(
                "Missing Jira credentials. Please set 'JIRA_EMAIL' and 'JIRA_API_TOKEN' in your .env file."
            )
        auth_str = f"{self.email}:{self.api_token}"
        encoded = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _ensure_configured(self) -> Optional[str]:
        if not self.base_url or not self.email or not self.api_token:
            return (
                "⚠️ Jira not fully configured. Please set 'JIRA_URL', 'JIRA_EMAIL', "
                "and 'JIRA_API_TOKEN' in your .env file."
            )
        return None

    def get_issue(self, issue_key: str) -> str:
        """Fetch current summary, status, and details of a Jira ticket."""
        err = self._ensure_configured()
        if err:
            return err

        endpoint = f"{self.base_url}/rest/api/3/issue/{issue_key.strip()}"
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(endpoint, headers=self._get_headers())
                if resp.status_code == 404:
                    return f"❌ Jira issue '{issue_key}' not found."
                if resp.status_code != 200:
                    return f"❌ Jira API error ({resp.status_code}): {resp.text}"

                data = resp.json()
                fields = data.get("fields", {})
                summary = fields.get("summary", "No summary")
                status = fields.get("status", {}).get("name", "Unknown")
                priority = fields.get("priority", {}).get("name", "None")
                assignee = (fields.get("assignee") or {}).get("displayName", "Unassigned")
                issue_type = fields.get("issuetype", {}).get("name", "Issue")

                return (
                    f"📋 **Jira Issue {data.get('key')}** [{issue_type}]\n"
                    f"• **Summary:** {summary}\n"
                    f"• **Status:** {status}\n"
                    f"• **Assignee:** {assignee}\n"
                    f"• **Priority:** {priority}\n"
                    f"• **Link:** {self.base_url}/browse/{data.get('key')}"
                )
        except Exception as e:
            return f"❌ Failed to connect to Jira at {self.base_url}: {e}"

    def update_status(
        self,
        issue_key: str,
        target_status: str,
        comment: Optional[str] = None,
    ) -> str:
        """Dynamically transition a Jira issue to a new status (e.g. 'In Review', 'Done')."""
        err = self._ensure_configured()
        if err:
            return err

        key = issue_key.strip()
        transitions_url = f"{self.base_url}/rest/api/3/issue/{key}/transitions"

        try:
            with httpx.Client(timeout=30.0) as client:
                headers = self._get_headers()

                # 1. Fetch available workflow transitions for this issue
                get_resp = client.get(transitions_url, headers=headers)
                if get_resp.status_code == 404:
                    return f"❌ Jira issue '{key}' not found."
                if get_resp.status_code != 200:
                    return f"❌ Failed to fetch available transitions ({get_resp.status_code}): {get_resp.text}"

                transitions = get_resp.json().get("transitions", [])
                if not transitions:
                    return f"⚠️ No transitions currently available for issue '{key}'."

                # 2. Match target status (case-insensitive substring or exact match)
                matched_id = None
                matched_name = None
                target_clean = target_status.strip().lower()

                for t in transitions:
                    t_name = t.get("name", "")
                    to_status = (t.get("to") or {}).get("name", "")
                    if target_clean in t_name.lower() or target_clean in to_status.lower():
                        matched_id = t.get("id")
                        matched_name = to_status or t_name
                        break

                if not matched_id:
                    available = [f"'{t.get('name')}'" for t in transitions]
                    return (
                        f"⚠️ Status '{target_status}' is not a valid transition for '{key}'.\n"
                        f"Available transitions right now: {', '.join(available)}"
                    )

                # 3. Post transition
                post_payload = {"transition": {"id": matched_id}}
                post_resp = client.post(transitions_url, headers=headers, json=post_payload)

                if post_resp.status_code in (204, 200):
                    comment_info = ""
                    if comment:
                        c_res = self.add_comment(key, comment)
                        comment_info = f"\n• {c_res}"
                    return f"✅ Successfully updated Jira issue '{key}' status to: **{matched_name}**{comment_info}"

                return f"❌ Failed to transition Jira issue ({post_resp.status_code}): {post_resp.text}"

        except Exception as e:
            return f"❌ Failed to update Jira status: {e}"

    def add_comment(self, issue_key: str, comment: str) -> str:
        """Add a comment to a Jira issue."""
        err = self._ensure_configured()
        if err:
            return err

        key = issue_key.strip()
        endpoint = f"{self.base_url}/rest/api/3/issue/{key}/comment"

        # Construct Jira Cloud Atlassian Document Format (ADF)
        adf_payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": comment,
                            }
                        ],
                    }
                ],
            }
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                headers = self._get_headers()
                resp = client.post(endpoint, headers=headers, json=adf_payload)

                # If ADF fails on older Jira Server/Data Center (400), try fallback plain string
                if resp.status_code == 400:
                    fallback_payload = {"body": comment}
                    resp = client.post(
                        f"{self.base_url}/rest/api/2/issue/{key}/comment",
                        headers=headers,
                        json=fallback_payload,
                    )

                if resp.status_code in (201, 200):
                    return f"✅ Comment successfully added to Jira issue '{key}'."

                return f"❌ Failed to post comment to Jira ({resp.status_code}): {resp.text}"

        except Exception as e:
            return f"❌ Failed to add comment to Jira: {e}"


jira_integration = JiraIntegration()
