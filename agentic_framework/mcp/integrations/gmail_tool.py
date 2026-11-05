"""Gmail Enterprise Integration Tool.

Automates sending new emails and replying to existing email threads
using secure SMTP with Gmail App Passwords or enterprise credentials.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, List, Union
from agentic_framework.config import settings
from agentic_framework.observability.logger import logger


class GmailIntegration:
    """Manages composing and sending emails and threaded replies."""

    def __init__(
        self,
        user: Optional[str] = None,
        app_password: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
    ):
        self.user = user or settings.GMAIL_USER
        self.app_password = app_password or settings.GMAIL_APP_PASSWORD
        self.smtp_host = smtp_host or settings.GMAIL_SMTP_HOST
        self.smtp_port = smtp_port or settings.GMAIL_SMTP_PORT

    def _ensure_configured(self) -> Optional[str]:
        if not self.user or not self.app_password:
            return (
                "⚠️ Gmail not configured. Please set 'GMAIL_USER' and 'GMAIL_APP_PASSWORD' "
                "(16-character App Password from Google Account Security) in your .env file."
            )
        return None

    def send_email(
        self,
        to_email: Union[str, List[str]],
        subject: str,
        body: str,
        cc: Optional[Union[str, List[str]]] = None,
        is_html: bool = False,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
    ) -> str:
        """Send an email or threaded reply via SMTP."""
        err = self._ensure_configured()
        if err or not self.user or not self.app_password:
            return err or (
                "⚠️ Gmail not configured. Please set 'GMAIL_USER' and 'GMAIL_APP_PASSWORD' "
                "(16-character App Password from Google Account Security) in your .env file."
            )

        user = self.user
        app_password = self.app_password

        # Normalize recipients list
        recipients: List[str] = []
        if isinstance(to_email, list):
            recipients.extend([e.strip() for e in to_email if e.strip()])
        elif isinstance(to_email, str):
            recipients.extend([e.strip() for e in to_email.split(",") if e.strip()])

        if not recipients:
            return "Error: 'to_email' must specify at least one valid recipient address."

        cc_list: List[str] = []
        if cc:
            if isinstance(cc, list):
                cc_list.extend([e.strip() for e in cc if e.strip()])
            elif isinstance(cc, str):
                cc_list.extend([e.strip() for e in cc.split(",") if e.strip()])

        # Build MIME Message
        msg = MIMEMultipart("alternative")
        msg["From"] = user
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        if cc_list:
            msg["Cc"] = ", ".join(cc_list)

        # Threading headers for replies
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = references

        mime_type = "html" if is_html else "plain"
        msg.attach(MIMEText(body, mime_type, "utf-8"))

        all_targets = recipients + cc_list

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=25.0) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(user, app_password)
                server.sendmail(user, all_targets, msg.as_string())

            dest_str = ", ".join(recipients)
            return f"📧 Successfully sent email to '{dest_str}' with subject: '{subject}'"

        except smtplib.SMTPAuthenticationError:
            return (
                "❌ Gmail SMTP Authentication Error: Invalid credentials. "
                "Ensure GMAIL_USER is your address and GMAIL_APP_PASSWORD is a generated 16-character App Password."
            )
        except Exception as e:
            return f"❌ Failed to send email via SMTP ({self.smtp_host}:{self.smtp_port}): {e}"

    def reply_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
        message_id: Optional[str] = None,
        cc: Optional[Union[str, List[str]]] = None,
    ) -> str:
        """Reply to an existing email thread setting In-Reply-To and Re: subject."""
        # Ensure subject starts with "Re: "
        clean_subj = subject.strip()
        if not clean_subj.lower().startswith("re:"):
            clean_subj = f"Re: {clean_subj}"

        reply_id = in_reply_to or message_id
        ref_id = references or reply_id
        return self.send_email(
            to_email=to_email,
            subject=clean_subj,
            body=body,
            cc=cc,
            in_reply_to=reply_id,
            references=ref_id,
        )


gmail_integration = GmailIntegration()
