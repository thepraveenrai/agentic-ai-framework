"""Framework Configuration Module.

Loads settings from environment variables or .env file with robust defaults.
Supports OpenRouter, OpenAI, Anthropic, and local mock testing mode.
"""

from pathlib import Path
from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FrameworkSettings(BaseSettings):
    """Central configuration for Agentic AI Framework."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Provider & Model Settings
    LLM_PROVIDER: str = Field(default="openrouter", description="openrouter, openai, anthropic, or mock")
    MODEL_NAME: str = Field(default="deepseek/deepseek-v4-flash-0731", description="Target LLM model ID")
    MODEL_TEMPERATURE: float = Field(default=0.0, description="Sampling temperature")
    MAX_TOKENS: int = Field(default=4096, description="Max response tokens")
    REQUEST_TIMEOUT_SECONDS: float = Field(default=90.0, description="HTTP timeout for LLM calls")

    # OpenRouter Specifics
    OPENROUTER_API_KEY: Optional[str] = Field(default=None, description="OpenRouter API Key")
    OPENROUTER_BASE_URL: str = Field(default="https://openrouter.ai/api/v1", description="OpenRouter API Endpoint")
    OPENROUTER_HTTP_REFERER: str = Field(default="https://localhost", description="HTTP Referer header for OpenRouter")
    OPENROUTER_APP_NAME: str = Field(default="Agentic AI Framework", description="App title header for OpenRouter")

    # Direct OpenAI / Other providers
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="Direct OpenAI Key if used")
    OPENAI_BASE_URL: Optional[str] = Field(default=None, description="Custom OpenAI-compatible base URL")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic API Key if used")

    # Target Project Settings
    TARGET_PROJECT_PATH: str = Field(default=".", description="Path to the repository/project to inspect & modify")
    MAX_FILE_SIZE_KB: int = Field(default=512, description="Max file size in KB to index/read")
    EXCLUDED_DIRS: List[str] = Field(
        default_factory=lambda: [
            ".git", ".venv", "venv", "node_modules", "__pycache__",
            ".pytest_cache", ".mypy_cache", "dist", "build", ".next", ".nuxt",
            "coverage", ".idea", ".vscode", ".agentic_traces", ".agentic_cache"
        ]
    )

    # Guardrails
    GUARDRAILS_ENABLED: bool = Field(default=True, description="Enable input and output safety guardrails")
    ALLOW_DANGEROUS_COMMANDS: bool = Field(default=False, description="Strictly block destructive shell commands")

    # Caching
    CACHE_ENABLED: bool = Field(default=True, description="Enable multi-tier response and RAG caching")
    CACHE_DIR: str = Field(default=".agentic_cache", description="Directory to persist cache files")
    CACHE_TTL_SECONDS: int = Field(default=86400, description="Cache time to live in seconds (default 24h)")

    # Human-in-the-Loop (HITL)
    HITL_ENABLED: bool = Field(default=True, description="Require human approval before applying changes/running commands")
    HITL_MODE: str = Field(default="on_modify", description="always, on_modify, or never")

    # Observability
    OBSERVABILITY_ENABLED: bool = Field(default=True, description="Enable tracing and metrics collection")
    LOG_LEVEL: str = Field(default="INFO", description="Console log level (DEBUG, INFO, WARNING, ERROR)")
    TRACES_DIR: str = Field(default=".agentic_traces", description="Directory to store execution traces")

    # RAG Settings
    RAG_TOP_K: int = Field(default=5, description="Number of code chunks to retrieve per search")
    RAG_CHUNK_SIZE: int = Field(default=60, description="Target lines per code chunk")
    RAG_CHUNK_OVERLAP: int = Field(default=10, description="Line overlap between chunks")

    # Enterprise Integrations Settings
    # 1. GitLab
    GITLAB_URL: str = Field(default="https://gitlab.com", description="GitLab instance URL (e.g. https://gitlab.mycompany.com)")
    GITLAB_TOKEN: Optional[str] = Field(default=None, description="GitLab Personal Access Token")
    GITLAB_PROJECT_ID: Optional[str] = Field(default=None, description="Default GitLab Project ID or URL-encoded path")

    # 2. GitHub
    GITHUB_TOKEN: Optional[str] = Field(default=None, description="GitHub Personal Access Token")
    GITHUB_API_URL: str = Field(default="https://api.github.com", description="GitHub REST API URL")
    GITHUB_REPOSITORY: Optional[str] = Field(default=None, description="Default GitHub repository (e.g. owner/repo)")

    # 3. Jira
    JIRA_URL: Optional[str] = Field(default=None, description="Jira instance URL (e.g. https://mycompany.atlassian.net)")
    JIRA_EMAIL: Optional[str] = Field(default=None, description="Jira user email or username")
    JIRA_API_TOKEN: Optional[str] = Field(default=None, description="Jira API token or password")

    # 4. Gmail
    GMAIL_USER: Optional[str] = Field(default=None, description="Gmail address for sending/replying")
    GMAIL_APP_PASSWORD: Optional[str] = Field(default=None, description="Gmail 16-character App Password")
    GMAIL_SMTP_HOST: str = Field(default="smtp.gmail.com", description="SMTP server host")
    GMAIL_SMTP_PORT: int = Field(default=587, description="SMTP server port (587 TLS or 465 SSL)")

    # 5. Slack
    SLACK_BOT_TOKEN: Optional[str] = Field(default=None, description="Slack Bot Token (xoxb-...)")
    SLACK_DEFAULT_CHANNEL: Optional[str] = Field(default=None, description="Default Slack channel (e.g. C12345678 or #general)")

    def get_target_path(self) -> Path:
        """Return resolved target project Path (always a directory)."""
        p = Path(self.TARGET_PROJECT_PATH).resolve()
        if p.is_file():
            # If user passed a specific file path, resolve to the project directory
            parent = p.parent
            if parent.name in ("tests", "test", "src"):
                return parent.parent
            return parent
        return p


# Singleton instance
settings = FrameworkSettings()
