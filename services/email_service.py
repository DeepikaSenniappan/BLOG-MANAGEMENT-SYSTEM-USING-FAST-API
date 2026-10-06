"""SMTP email delivery service."""

import logging
import smtplib
import ssl
from email.message import EmailMessage

from settings import get_email_settings

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send an email via SMTP. Failures are logged and never propagated."""
    try:
        config = get_email_settings()
        if not config.smtp_host:
            logger.info("Email notification (SMTP not configured) to %s: %s\n%s", to_email, subject, body)
            return False

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = config.smtp_from
        message["To"] = to_email
        message.set_content(body)

        if config.smtp_use_ssl:
            with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=20, context=ssl.create_default_context()) as smtp:
                smtp.ehlo()
                _authenticate(smtp, config.smtp_username, config.smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=20) as smtp:
                smtp.ehlo()
                if config.smtp_use_starttls:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                _authenticate(smtp, config.smtp_username, config.smtp_password)
                smtp.send_message(message)
        return True
    except (smtplib.SMTPException, OSError, ValueError) as exc:
        logger.error("Email notification delivery failed for %s: %s: %s", to_email, type(exc).__name__, exc)
        return False
    except Exception:
        logger.exception("Unexpected email notification error for %s", to_email)
        return False


def _authenticate(smtp: smtplib.SMTP, username: str | None, password: str | None) -> None:
    if username:
        smtp.login(username, password or "")
