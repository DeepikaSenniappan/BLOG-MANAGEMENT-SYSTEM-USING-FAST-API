import logging
import os
import smtplib
from email.message import EmailMessage

from models import User

logger = logging.getLogger(__name__)


def send_notification(recipient: User, subject: str, body: str) -> None:
    """Send mail when SMTP is configured; otherwise log the event for local development."""
    host = os.getenv("SMTP_HOST")
    if not host:
        logger.info("Email notification (SMTP not configured) to %s: %s — %s", recipient.email, subject, body)
        return
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USERNAME", "blog@example.com"))
    message["To"] = recipient.email
    message.set_content(body)
    port = int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=10) as smtp:
        smtp.starttls()
        username = os.getenv("SMTP_USERNAME")
        if username:
            smtp.login(username, os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(message)
