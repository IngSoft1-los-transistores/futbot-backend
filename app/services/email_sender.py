import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from app.core.config import get_settings


class EmailSender(Protocol):
    def send_verification(self, email: str, url: str) -> None: ...


class SMTPEmailSender:
    def send_verification(self, email: str, url: str) -> None:
        settings = get_settings()
        message = EmailMessage()
        message["Subject"] = "Confirmá tu cuenta de FutBot"
        message["From"] = settings.smtp_from
        message["To"] = email
        message.set_content(
            f"Confirmá tu correo entrando a este enlace:\n{url}\n"
            "Si no creaste esta cuenta, ignorá este mensaje."
        )
        with smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
        ) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)


def get_email_sender() -> EmailSender:
    if get_settings().email_sender != "smtp":
        raise ValueError("EMAIL_SENDER no soportado")
    return SMTPEmailSender()
