"""
Email Notifier — sends HTML email notifications for new job postings.
Uses stdlib smtplib (no extra dependencies).
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone


def _build_html_email(new_jobs: list[dict]) -> str:
    """Build a nicely formatted HTML email body for new job postings."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Group jobs by company
    by_company: dict[str, list[dict]] = {}
    for job in new_jobs:
        company = job.get("company", "Unknown")
        by_company.setdefault(company, []).append(job)

    rows = ""
    for company, jobs in sorted(by_company.items()):
        for job in jobs:
            title = job.get("title", "Unknown")
            location = job.get("location", "—")
            url = job.get("url", "#")
            source = job.get("source", "—")
            link = f'<a href="{url}" style="color:#2563eb;text-decoration:none;">{title}</a>' if url else title

            rows += f"""
            <tr style="border-bottom:1px solid #e5e7eb;">
                <td style="padding:10px 12px;">{link}</td>
                <td style="padding:10px 12px;">{company}</td>
                <td style="padding:10px 12px;">{location}</td>
                <td style="padding:10px 12px;color:#6b7280;font-size:13px;">{source}</td>
            </tr>"""

    html = f"""
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f9fafb;padding:20px;">
        <div style="max-width:700px;margin:0 auto;background:#fff;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,0.1);overflow:hidden;">
            <div style="background:linear-gradient(135deg,#1e40af,#7c3aed);padding:24px 28px;">
                <h1 style="color:#fff;margin:0;font-size:22px;">🔍 Job Scout — New Postings</h1>
                <p style="color:#c7d2fe;margin:6px 0 0;font-size:14px;">{len(new_jobs)} new job(s) found • {now}</p>
            </div>
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
                <thead>
                    <tr style="background:#f3f4f6;text-align:left;">
                        <th style="padding:10px 12px;font-weight:600;">Title</th>
                        <th style="padding:10px 12px;font-weight:600;">Company</th>
                        <th style="padding:10px 12px;font-weight:600;">Location</th>
                        <th style="padding:10px 12px;font-weight:600;">Source</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
            <div style="padding:16px 28px;background:#f9fafb;color:#9ca3af;font-size:12px;text-align:center;">
                Sent by Job Scout • <a href="https://github.com" style="color:#6b7280;">Unsubscribe</a>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def send_email_notification(
    new_jobs: list[dict],
    recipient: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    sender: str = None,
) -> bool:
    """
    Send an HTML email with new job postings.

    Args:
        new_jobs: List of new job dicts.
        recipient: Email address to send to.
        smtp_host: SMTP server hostname (e.g. smtp.gmail.com, email-smtp.us-east-1.amazonaws.com).
        smtp_port: SMTP port (587 for TLS, 465 for SSL).
        smtp_user: SMTP username.
        smtp_password: SMTP password or app-specific password.
        sender: Sender email address (defaults to smtp_user).

    Returns:
        True if email was sent successfully, False otherwise.
    """
    if not new_jobs:
        print("[Notifier] No new jobs to email.")
        return False

    sender = sender or smtp_user

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🔍 Job Scout: {len(new_jobs)} new job posting(s)"
        msg["From"] = sender
        msg["To"] = recipient

        # Plain text fallback
        plain_text = f"Job Scout found {len(new_jobs)} new job(s):\n\n"
        for job in new_jobs:
            plain_text += f"• {job.get('title', '?')} at {job.get('company', '?')} — {job.get('location', '?')}\n"
            if job.get("url"):
                plain_text += f"  {job['url']}\n"
            plain_text += "\n"

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(_build_html_email(new_jobs), "html"))

        # Connect and send
        print(f"[Notifier] Connecting to {smtp_host}:{smtp_port}...")

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
            server.starttls()

        server.login(smtp_user, smtp_password)
        server.sendmail(sender, [recipient], msg.as_string())
        server.quit()

        print(f"[Notifier] ✅ Email sent to {recipient} ({len(new_jobs)} jobs)")
        return True

    except Exception as e:
        print(f"[Notifier] ❌ Failed to send email: {e}")
        return False
