"""Slack Enterprise Integration Tool.

Automates sending messages, editing messages, and deleting messages
in Slack channels or threads via Slack Web API.
"""

from typing import Dict, Any, Optional
import httpx

from agentic_framework.config import settings
from agentic_framework.observability.logger import logger


class SlackIntegration:
    """Manages Slack chat operations (send, edit, delete)."""

    SLACK_API_BASE = "https://slack.com/api"

    def __init__(
        self,
        bot_token: Optional[str] = None,
        default_channel: Optional[str] = None,
    ):
        self.bot_token = bot_token or settings.SLACK_BOT_TOKEN
        self.default_channel = default_channel or settings.SLACK_DEFAULT_CHANNEL

    def _get_headers(self) -> Dict[str, str]:
        """Generate Slack authorization headers."""
        if not self.bot_token:
            raise ValueError(
                "Missing Slack token. Please configure 'SLACK_BOT_TOKEN' in your .env file."
            )
        return {
            "Authorization": f"Bearer {self.bot_token.strip()}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _ensure_configured(self) -> Optional[str]:
        if not self.bot_token:
            return (
                "⚠️ Slack not configured. Please set 'SLACK_BOT_TOKEN' (e.g. xoxb-...) "
                "in your .env file."
            )
        return None

    def send_message(
        self,
        text: str,
        channel: Optional[str] = None,
        thread_ts: Optional[str] = None,
    ) -> str:
        """Send a message to a Slack channel or reply in a thread.

        Args:
            text: Message body (supports Slack mrkdwn).
            channel: Target channel ID (e.g., C01234567) or name (#general).
                     Defaults to SLACK_DEFAULT_CHANNEL if omitted.
            thread_ts: Parent message timestamp if replying inside a thread.

        Returns:
            Status summary with message timestamp and channel.
        """
        err = self._ensure_configured()
        if err:
            return err

        target_channel = channel or self.default_channel
        if not target_channel:
            return "⚠️ No Slack channel specified and SLACK_DEFAULT_CHANNEL is not set."

        endpoint = f"{self.SLACK_API_BASE}/chat.postMessage"
        payload: Dict[str, Any] = {
            "channel": target_channel.strip(),
            "text": text,
        }
        if thread_ts:
            payload["thread_ts"] = thread_ts.strip()

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(endpoint, json=payload, headers=self._get_headers())
                data = resp.json()

                if not data.get("ok"):
                    error_msg = data.get("error", "Unknown Slack error")
                    logger.error(f"Slack postMessage failed: {error_msg}")
                    return f"❌ Failed to post Slack message: {error_msg}"

                ts = data.get("ts", "")
                chan = data.get("channel", target_channel)
                thread_info = f" (thread: {thread_ts})" if thread_ts else ""
                logger.info(f"Slack message posted to {chan} (ts: {ts})")
                return (
                    f"✅ Message sent successfully to Slack!\n"
                    f"- Channel: `{chan}`\n"
                    f"- Timestamp (ts): `{ts}`{thread_info}\n"
                    f"- Text: {text[:100]}..."
                )
        except Exception as exc:
            logger.error(f"Slack postMessage error: {exc}")
            return f"❌ Error sending Slack message: {str(exc)}"

    def edit_message(
        self,
        timestamp: str,
        text: str,
        channel: Optional[str] = None,
    ) -> str:
        """Edit an existing Slack message.

        Args:
            timestamp: The 'ts' string identifier of the message to update.
            text: Updated message content.
            channel: Channel ID where the message exists.
                     Defaults to SLACK_DEFAULT_CHANNEL.

        Returns:
            Status summary of the edit.
        """
        err = self._ensure_configured()
        if err:
            return err

        target_channel = channel or self.default_channel
        if not target_channel:
            return "⚠️ No Slack channel specified and SLACK_DEFAULT_CHANNEL is not set."

        if not timestamp:
            return "⚠️ Missing message timestamp 'ts' to edit."

        endpoint = f"{self.SLACK_API_BASE}/chat.update"
        payload = {
            "channel": target_channel.strip(),
            "ts": timestamp.strip(),
            "text": text,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(endpoint, json=payload, headers=self._get_headers())
                data = resp.json()

                if not data.get("ok"):
                    error_msg = data.get("error", "Unknown Slack error")
                    logger.error(f"Slack update failed: {error_msg}")
                    return f"❌ Failed to edit Slack message: {error_msg}"

                logger.info(f"Slack message {timestamp} updated in {target_channel}")
                return (
                    f"✅ Message updated successfully in Slack!\n"
                    f"- Channel: `{target_channel}`\n"
                    f"- Timestamp (ts): `{timestamp}`\n"
                    f"- New Text: {text[:100]}..."
                )
        except Exception as exc:
            logger.error(f"Slack update error: {exc}")
            return f"❌ Error editing Slack message: {str(exc)}"

    def delete_message(
        self,
        timestamp: str,
        channel: Optional[str] = None,
    ) -> str:
        """Delete an existing message in a Slack channel.

        Args:
            timestamp: The 'ts' string identifier of the message to delete.
            channel: Channel ID where the message exists.
                     Defaults to SLACK_DEFAULT_CHANNEL.

        Returns:
            Status summary of the deletion.
        """
        err = self._ensure_configured()
        if err:
            return err

        target_channel = channel or self.default_channel
        if not target_channel:
            return "⚠️ No Slack channel specified and SLACK_DEFAULT_CHANNEL is not set."

        if not timestamp:
            return "⚠️ Missing message timestamp 'ts' to delete."

        endpoint = f"{self.SLACK_API_BASE}/chat.delete"
        payload = {
            "channel": target_channel.strip(),
            "ts": timestamp.strip(),
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(endpoint, json=payload, headers=self._get_headers())
                data = resp.json()

                if not data.get("ok"):
                    error_msg = data.get("error", "Unknown Slack error")
                    logger.error(f"Slack delete failed: {error_msg}")
                    return f"❌ Failed to delete Slack message: {error_msg}"

                logger.info(f"Slack message {timestamp} deleted from {target_channel}")
                return (
                    f"✅ Message deleted successfully from Slack!\n"
                    f"- Channel: `{target_channel}`\n"
                    f"- Timestamp (ts): `{timestamp}`"
                )
        except Exception as exc:
            logger.error(f"Slack delete error: {exc}")
            return f"❌ Error deleting Slack message: {str(exc)}"


# Global singleton instance
slack_integration = SlackIntegration()

