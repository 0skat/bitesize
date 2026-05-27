"""
Kindle delivery — emails an EPUB to the user's @kindle.com address via SMTP.

Amazon's Send to Kindle accepts attachments from approved sender addresses.
The sender address must be whitelisted in Amazon's Kindle settings.

Required env vars (see .env.example):
    KINDLE_EMAIL   — your @kindle.com address
    SMTP_USER      — sender email address (must be approved in Amazon settings)
    SMTP_PASSWORD  — sender email password or app password
    SMTP_HOST      — SMTP server host (default: smtp.gmail.com)
    SMTP_PORT      — SMTP server port (default: 587)
"""

import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from config import console


def send_to_kindle(epub_path: Path) -> bool:
    """
    Email epub_path as an attachment to KINDLE_EMAIL.

    Returns True on success, False on any failure (with a console message).
    Never raises — Kindle delivery is best-effort and should not abort the run.
    """
    kindle_email = os.getenv("KINDLE_EMAIL", "").strip()
    smtp_user    = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_host    = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    smtp_port    = int(os.getenv("SMTP_PORT", "587"))

    missing = [v for v, val in [
        ("KINDLE_EMAIL",   kindle_email),
        ("SMTP_USER",      smtp_user),
        ("SMTP_PASSWORD",  smtp_password),
    ] if not val]

    if missing:
        console.print(
            f"  [yellow]⚠  Kindle delivery skipped — missing env vars: "
            f"{', '.join(missing)}[/yellow]"
        )
        return False

    if not epub_path.exists():
        console.print(f"  [yellow]⚠  Kindle delivery skipped — file not found: {epub_path}[/yellow]")
        return False

    msg = MIMEMultipart()
    msg["From"]    = smtp_user
    msg["To"]      = kindle_email
    msg["Subject"] = epub_path.stem  # Amazon uses the subject as the document title

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
        console.print(f"  [green]✓[/green]  Sent to Kindle: [dim]{epub_path.name}[/dim]")
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
