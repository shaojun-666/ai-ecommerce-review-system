"""Email sending utility using SMTP."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """Send an email via SMTP. Returns True on success."""
    cfg = current_app.config
    server = cfg.get("SMTP_SERVER", "")
    port = cfg.get("SMTP_PORT", 587)
    username = cfg.get("SMTP_USERNAME", "")
    password = cfg.get("SMTP_PASSWORD", "")
    use_tls = cfg.get("SMTP_USE_TLS", True)
    mail_from = cfg.get("MAIL_FROM", "noreply@ecommerce-review.local")
    mail_from_name = cfg.get("MAIL_FROM_NAME", "AI E-Commerce Review System")

    if not server or not username:
        logger.warning("SMTP not configured, skipping email to %s", to)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{mail_from_name} <{mail_from}>"
    msg["To"] = to

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(server, port, timeout=15) as smtp:
            if use_tls:
                smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to, e)
        return False


def send_report_email(to: str, subject: str, html_content: str):
    """Send a formatted report email."""
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #409eff; color: #fff; padding: 16px 24px; border-radius: 4px 4px 0 0;">
  <h2 style="margin: 0;">{subject}</h2>
</div>
<div style="border: 1px solid #e0e0e0; border-top: none; padding: 24px; border-radius: 0 0 4px 4px;">
{html_content}
</div>
<div style="margin-top: 16px; font-size: 12px; color: #999; text-align: center;">
  <p>AI E-Commerce Review Analysis System · 自动生成报告</p>
</div>
</body>
</html>"""
    return send_email(to, subject, html)
