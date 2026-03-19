"""
emailer.py — Sends the war monitor report via Gmail SMTP
Uses App Password (no OAuth needed)
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


def send_report_email(
    html_body: str,
    subject: str = None,
    to_email: str = None
) -> bool:
    """
    Sends an HTML email via Gmail SMTP.

    Required environment variables:
      GMAIL_ADDRESS   — your Gmail address (e.g. you@gmail.com)
      GMAIL_APP_PASS  — Gmail App Password (16 chars, no spaces)
      REPORT_TO_EMAIL — recipient email (can be same as GMAIL_ADDRESS)
    """

    gmail_user = os.environ.get("GMAIL_ADDRESS")
    gmail_pass = os.environ.get("GMAIL_APP_PASS")
    recipient = to_email or os.environ.get("REPORT_TO_EMAIL") or gmail_user

    if not gmail_user or not gmail_pass:
        print("[ERROR] GMAIL_ADDRESS and GMAIL_APP_PASS env vars not set.")
        print("        See README.md for setup instructions.")
        return False

    if not subject:
        subject = f"War Monitor Report — {datetime.utcnow().strftime('%b %d, %Y %H:%M UTC')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"War Monitor Bot <{gmail_user}>"
    msg["To"] = recipient

    # Plain text fallback
    plain = "Your war monitor report is ready. Please view in an HTML-capable email client."
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, recipient, msg.as_string())
        print(f"[OK] Email sent to {recipient}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("[ERROR] Gmail auth failed. Make sure you're using an App Password, not your normal password.")
        print("        Go to: myaccount.google.com > Security > App Passwords")
        return False

    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False


if __name__ == "__main__":
    # Quick test
    test_html = "<h1>Test</h1><p>Email is working correctly!</p>"
    send_report_email(test_html, subject="War Bot Test Email")