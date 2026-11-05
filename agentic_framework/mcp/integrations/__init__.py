"""Enterprise Integrations for Developer & IT Workflows.

Provides production-ready integrations with:
- GitLab (Git operations + Merge Request creation)
- GitHub (Git operations + Pull Request creation)
- Jira (Status transitions, commenting, and issue inspection)
- Gmail (Sending, replying with proper thread headers)
- Slack (Sending messages, editing, deleting)
"""

from agentic_framework.mcp.integrations.gitlab_tool import GitLabIntegration, gitlab_integration
from agentic_framework.mcp.integrations.github_tool import GitHubIntegration, github_integration
from agentic_framework.mcp.integrations.jira_tool import JiraIntegration, jira_integration
from agentic_framework.mcp.integrations.gmail_tool import GmailIntegration, gmail_integration
from agentic_framework.mcp.integrations.slack_tool import SlackIntegration, slack_integration

__all__ = [
    "GitLabIntegration",
    "gitlab_integration",
    "GitHubIntegration",
    "github_integration",
    "JiraIntegration",
    "jira_integration",
    "GmailIntegration",
    "gmail_integration",
    "SlackIntegration",
    "slack_integration",
]

