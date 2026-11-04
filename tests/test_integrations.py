"""Unit tests for Enterprise Integrations (GitLab, GitHub, Jira, Gmail, Slack)."""

import subprocess
from unittest.mock import MagicMock, patch
import pytest

from agentic_framework.integrations import (
    GitLabIntegration,
    GitHubIntegration,
    JiraIntegration,
    GmailIntegration,
    SlackIntegration,
)
from agentic_framework.mcp.tools import tool_registry
from agentic_framework.mcp.server import MCPServer


# =========================================================================
# 1. GitLab Integration Tests
# =========================================================================

def test_gitlab_detect_project_path():
    gitlab = GitLabIntegration(base_url="https://gitlab.example.com", token="glpat-test12345")

    with patch.object(gitlab, "_run_git") as mock_git:
        # Test SSH remote URL
        mock_git.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="git@gitlab.example.com:my-team/backend-service.git\n"
        )
        assert gitlab.detect_project_path() == "my-team/backend-service"

        # Test HTTPS remote URL
        mock_git.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="https://gitlab.example.com/corp/core-api.git\n"
        )
        assert gitlab.detect_project_path() == "corp/core-api"


def test_gitlab_workflow_success():
    gitlab = GitLabIntegration(
        base_url="https://gitlab.example.com",
        token="glpat-validtoken",
        default_project_id="corp/my-service",
    )

    def fake_git(args, cwd=None):
        cmd = args[0] if args else ""
        if "rev-parse" in args:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="true\n")
        if "status" in args:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="M file.py\n")
        if "remote" in args:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="git@gitlab.example.com:corp/my-service.git\n")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="")

    with patch.object(gitlab, "_run_git", side_effect=fake_git), patch("httpx.Client") as mock_httpx:
        # Mock GitLab MR creation API response (HTTP 201)
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "web_url": "https://gitlab.example.com/corp/my-service/-/merge_requests/42",
            "iid": 42,
        }
        mock_client.post.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_httpx.return_value = mock_client

        result = gitlab.gitlab_workflow(
            current_branch="feature/login-fix",
            target_branch="main",
            commit_message="Fix login authentication timeout",
            create_mr=True,
            project_id="corp/my-service",
        )

        assert "successfully pushed to remote" in result
        assert "GitLab Merge Request" in result
        assert "created successfully" in result
        assert "merge_requests/42" in result


# =========================================================================
# 2. GitHub Integration Tests
# =========================================================================

def test_github_workflow_success():
    github = GitHubIntegration(
        token="ghp_testtoken",
        default_repository="my-org/web-service",
    )

    def fake_git(args, cwd=None):
        if "rev-parse" in args:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="true\n")
        if "status" in args:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="M app.py\n")
        if "remote" in args:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="git@github.com:my-org/web-service.git\n")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="")

    with patch.object(github, "_run_git", side_effect=fake_git), patch("httpx.Client") as mock_httpx:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "html_url": "https://github.com/my-org/web-service/pull/15",
            "number": 15,
        }
        mock_client.post.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_httpx.return_value = mock_client

        result = github.github_workflow(
            current_branch="feature/payment-webhook",
            target_branch="main",
            commit_message="Add payment webhook verification",
            create_pr=True,
            repository="my-org/web-service",
        )

        assert "successfully pushed to GitHub" in result
        assert "GitHub Pull Request" in result
        assert "created successfully" in result
        assert "pull/15" in result


# =========================================================================
# 3. Jira Integration Tests
# =========================================================================

def test_jira_get_issue_and_update_status():
    jira = JiraIntegration(
        base_url="https://company.atlassian.net",
        email="developer@company.com",
        api_token="jira_secret_token",
    )

    with patch("httpx.Client") as mock_httpx:
        mock_client = MagicMock()

        # 1. Test get_issue
        resp_issue = MagicMock()
        resp_issue.status_code = 200
        resp_issue.json.return_value = {
            "key": "PAY-101",
            "fields": {
                "summary": "Fix payment gateway timeout",
                "status": {"name": "Open"},
                "issuetype": {"name": "Bug"},
                "priority": {"name": "High"},
                "assignee": {"displayName": "Alice Engineer"},
            },
        }
        mock_client.get.return_value = resp_issue
        mock_client.__enter__.return_value = mock_client
        mock_httpx.return_value = mock_client

        issue_info = jira.get_issue("PAY-101")
        assert "PAY-101" in issue_info
        assert "Fix payment gateway timeout" in issue_info
        assert "Open" in issue_info

        # 2. Test update_status transition matching
        resp_transitions = MagicMock()
        resp_transitions.status_code = 200
        resp_transitions.json.return_value = {
            "transitions": [
                {"id": "11", "name": "Start Progress", "to": {"name": "In Progress"}},
                {"id": "21", "name": "Resolve Issue", "to": {"name": "In Review"}},
                {"id": "31", "name": "Close", "to": {"name": "Done"}},
            ]
        }
        resp_post = MagicMock()
        resp_post.status_code = 204

        mock_client.get.return_value = resp_transitions
        mock_client.post.return_value = resp_post

        status_result = jira.update_status("PAY-101", "In Review", comment="Automated PR opened.")
        assert "Successfully updated Jira issue" in status_result
        assert "In Review" in status_result


def test_jira_add_comment():
    jira = JiraIntegration(
        base_url="https://company.atlassian.net",
        email="developer@company.com",
        api_token="jira_secret_token",
    )

    with patch("httpx.Client") as mock_httpx:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_client.post.return_value = mock_resp
        mock_client.__enter__.return_value = mock_client
        mock_httpx.return_value = mock_client

        res = jira.add_comment("PROJ-99", "Automated bug investigation completed.")
        assert "Comment successfully added" in res


# =========================================================================
# 4. Gmail Integration Tests
# =========================================================================

def test_gmail_send_and_reply():
    gmail = GmailIntegration(
        user="alerts@company.com",
        app_password="abcdefghijklmnop",
        smtp_host="smtp.gmail.com",
        smtp_port=587,
    )

    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        # 1. Send email
        send_res = gmail.send_email(
            to_email="devops@company.com",
            subject="Build Failure on main branch",
            body="Pipeline #345 failed at lint stage.",
        )
        assert "Successfully sent email" in send_res
        assert "devops@company.com" in send_res
        assert mock_server.starttls.called
        assert mock_server.login.called
        assert mock_server.sendmail.called

        # 2. Reply email with In-Reply-To
        reply_res = gmail.reply_email(
            to_email="devops@company.com",
            subject="Build Failure on main branch",
            body="Fixed in commit abc1234.",
            in_reply_to="<parent-msg-12345@company.com>",
            references="<parent-msg-12345@company.com>",
        )
        assert "Successfully sent email" in reply_res
        assert "Re: Build Failure" in reply_res


# =========================================================================
# 5. Slack Integration Tests
# =========================================================================

def test_slack_send_edit_delete():
    slack = SlackIntegration(
        bot_token="xoxb-mock-token-12345",
        default_channel="C12345678",
    )

    with patch("httpx.Client") as mock_httpx:
        mock_client = MagicMock()

        # 1. Send message
        resp_post = MagicMock()
        resp_post.json.return_value = {
            "ok": True,
            "channel": "C12345678",
            "ts": "1710000001.000100",
        }
        mock_client.post.return_value = resp_post
        mock_client.__enter__.return_value = mock_client
        mock_httpx.return_value = mock_client

        send_res = slack.send_message("Deployment to staging complete.")
        assert "Message sent successfully" in send_res
        assert "1710000001.000100" in send_res

        # 2. Edit message
        resp_edit = MagicMock()
        resp_edit.json.return_value = {
            "ok": True,
            "channel": "C12345678",
            "ts": "1710000001.000100",
            "text": "Deployment to staging verified and healthy.",
        }
        mock_client.post.return_value = resp_edit

        edit_res = slack.edit_message("1710000001.000100", "Deployment to staging verified and healthy.")
        assert "Message updated successfully" in edit_res

        # 3. Delete message
        resp_del = MagicMock()
        resp_del.json.return_value = {
            "ok": True,
            "channel": "C12345678",
            "ts": "1710000001.000100",
        }
        mock_client.post.return_value = resp_del

        del_res = slack.delete_message("1710000001.000100")
        assert "Message deleted successfully" in del_res


def test_slack_error_handling():
    slack = SlackIntegration(
        bot_token="xoxb-mock-token-12345",
        default_channel="C_INVALID",
    )

    with patch("httpx.Client") as mock_httpx:
        mock_client = MagicMock()
        resp_err = MagicMock()
        resp_err.json.return_value = {"ok": False, "error": "channel_not_found"}
        mock_client.post.return_value = resp_err
        mock_client.__enter__.return_value = mock_client
        mock_httpx.return_value = mock_client

        res = slack.send_message("Testing error")
        assert "Failed to post Slack message: channel_not_found" in res


# =========================================================================
# 6. MCP Protocol Integration Verification
# =========================================================================

def test_mcp_server_lists_and_dispatches_enterprise_tools():
    server = MCPServer()

    # 1. Verify all new enterprise tools are declared in tools/list
    resp_list = server.handle_request({"id": 1, "method": "tools/list", "params": {}})
    tools = resp_list["result"]["tools"]
    tool_names = {t["name"] for t in tools}

    enterprise_tools = {
        "gitlab_workflow",
        "github_workflow",
        "jira_update_status",
        "jira_add_comment",
        "jira_get_issue",
        "gmail_send",
        "gmail_reply",
        "slack_send_message",
        "slack_edit_message",
        "slack_delete_message",
    }
    for tool_name in enterprise_tools:
        assert tool_name in tool_names, f"Expected {tool_name} to be exposed via MCP tools/list"

    # 2. Verify tools/call dispatches correctly
    with patch("agentic_framework.integrations.slack_tool.slack_integration.send_message") as mock_slack:
        mock_slack.return_value = "Mocked Slack Message Success"
        call_req = {
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "slack_send_message",
                "arguments": {"text": "Hello team!"},
            },
        }
        resp_call = server.handle_request(call_req)
        assert resp_call["result"]["content"][0]["text"] == "Mocked Slack Message Success"
