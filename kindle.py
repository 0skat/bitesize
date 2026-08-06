"""
Kindle delivery — emails an EPUB to the user's @kindle.com address via SMTP.

Amazon's Send to Kindle accepts attachments from approved sender addresses.
The sender address must be whitelisted in Amazon's Kindle settings.
"""

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from config import console
from settings_store import Settings


def _smtp_settings(settings: Settings) -> tuple[str, str, str, str, int]:
    return (
        settings.kindle_email.strip(),
        settings.smtp_user.strip(),
        settings.smtp_password.strip(),
        settings.smtp_host.strip() or "smtp.gmail.com",
        int(settings.smtp_port or 587),
    )


def send_test_email(settings: Settings) -> tuple[bool, str]:
    """Send a small plaintext test email using current SMTP settings."""
    kindle_email, smtp_user, smtp_password, smtp_host, smtp_port = _smtp_settings(
        settings
    )
    missing = [
        name
        for name, val in [
            ("kindle_email", kindle_email),
            ("smtp_user", smtp_user),
            ("smtp_password", smtp_password),
        ]
        if not val
    ]
    if missing:
        return False, f"Missing settings: {', '.join(missing)}"

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = kindle_email
    msg["Subject"] = "BiteSIze SMTP test"
    msg.attach(
        MIMEText(
            "This is a test email from the BiteSIze settings dashboard.\n"
            "If you received this on your Kindle, SMTP is configured correctly.",
            "plain",
        )
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, kindle_email, msg.as_string())
        return True, "Test email sent"
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP authentication failed — check user/password"
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {e}"
    except OSError as e:
        return False, f"Connection error: {e}"


def send_to_kindle(epub_path: Path, settings: Settings | None = None) -> bool:
    """
    Email epub_path as an attachment to kindle_email.

    Returns True on success, False on any failure (with a console message).
    Never raises — Kindle delivery is best-effort and should not abort the run.
    """
    if settings is None:
        from config import get_settings

        settings = get_settings()

    kindle_email, smtp_user, smtp_password, smtp_host, smtp_port = _smtp_settings(
        settings
    )

    missing = [
        name
        for name, val in [
            ("KINDLE_EMAIL", kindle_email),
            ("SMTP_USER", smtp_user),
            ("SMTP_PASSWORD", smtp_password),
        ]
        if not val
    ]

    if missing:
        console.print(
            f"  [yellow]⚠  Kindle delivery skipped — missing settings: "
            f"{', '.join(missing)}[/yellow]"
        )
        return False

    if not epub_path.exists():
        console.print(
            f"  [yellow]⚠  Kindle delivery skipped — file not found: {epub_path}[/yellow]"
        )
        return False

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = kindle_email
    msg["Subject"] = epub_path.stem

    with epub_path.open("rb") as f:
        attachment = MIMEApplication(f.read(), _subtype="epub+zip")
        attachment.add_header(
            "Content-Disposition", "attachment", filename=epub_path.name
        )
        msg.attach(attachment)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, kindle_email, msg.as_string())
        console.print(
            f"  [green]✓[/green]  Sent to Kindle: [dim]{epub_path.name}[/dim]"
        )
        return True
    except smtplib.SMTPAuthenticationError:
        console.print(
            "  [red]✗  Kindle delivery failed:[/red] SMTP authentication error. "
            "Check SMTP_USER / SMTP_PASSWORD. For Gmail, use an App Password."
        )
    except smtplib.SMTPException as e:
        console.print(f"  [red]✗  Kindle delivery failed:[/red] SMTP error: {e}")
    except OSError as e:
        console.print(f"  [red]✗  Kindle delivery failed:[/red] Connection error: {e}")

    return False
