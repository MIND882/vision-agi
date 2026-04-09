# tools/email_tool.py
# ============================================================
# EMAIL TOOL — Send confirmation emails
#
# Provider: Gmail SMTP (free) or SendGrid (free tier)
# Default: Gmail SMTP — no extra package needed!
#
# Setup (.env mein add karein):
#   EMAIL_FROM=tumhara@gmail.com
#   EMAIL_PASSWORD=gmail_app_password  (not regular password!)
#   EMAIL_PROVIDER=gmail               (or 'sendgrid')
#
# Gmail App Password kaise banayein:
#   1. myaccount.google.com → Security
#   2. 2-Step Verification ON karo
#   3. App Passwords → Generate
#   4. 16-char password milega → .env mein daalo
#
# Usage:
#   from tools.email_tool import EmailTool
#   email = EmailTool()
#   email.send_booking_confirm(to="customer@gmail.com", booking={...})
# ============================================================

from pathlib import Path
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from config import cfg
except ModuleNotFoundError:
    # Allow running this file directly via `python tools/email_tool.py`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from config import cfg


# ── Email templates ──────────────────────────────────────────
BOOKING_CONFIRM_HTML = """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: linear-gradient(135deg, #6c63ff, #4ecdc4); padding: 24px; border-radius: 12px 12px 0 0;">
    <h1 style="color: white; margin: 0; font-size: 22px;">Appointment Confirmed! ✅</h1>
    <p style="color: rgba(255,255,255,0.85); margin: 4px 0 0;">AC Service</p>
  </div>
  <div style="background: #f9f9f9; padding: 24px; border-radius: 0 0 12px 12px;">
    <p>Namaste <strong>{name}</strong> ji,</p>
    <p>Aapka appointment confirm ho gaya hai. Details neeche hain:</p>
    <table style="width:100%; border-collapse: collapse; margin: 16px 0;">
      <tr style="background: white;">
        <td style="padding: 10px; border: 1px solid #eee; color: #666;">Booking ID</td>
        <td style="padding: 10px; border: 1px solid #eee; font-weight: bold;">{booking_id}</td>
      </tr>
      <tr style="background: #fafafa;">
        <td style="padding: 10px; border: 1px solid #eee; color: #666;">Service</td>
        <td style="padding: 10px; border: 1px solid #eee;">{service}</td>
      </tr>
      <tr style="background: white;">
        <td style="padding: 10px; border: 1px solid #eee; color: #666;">Date</td>
        <td style="padding: 10px; border: 1px solid #eee;">{date}</td>
      </tr>
      <tr style="background: #fafafa;">
        <td style="padding: 10px; border: 1px solid #eee; color: #666;">Time</td>
        <td style="padding: 10px; border: 1px solid #eee;">{slot}</td>
      </tr>
      <tr style="background: white;">
        <td style="padding: 10px; border: 1px solid #eee; color: #666;">Address</td>
        <td style="padding: 10px; border: 1px solid #eee;">{address}</td>
      </tr>
    </table>
    <p style="background: #fffbeb; padding: 12px; border-radius: 8px; border-left: 4px solid #f59e0b;">
      📞 Koi sawaal ho toh humse contact karein. Humare technician time par aayenge.
    </p>
    <p style="color: #666; font-size: 13px;">— Aria, {company}</p>
  </div>
</div>
"""

FOLLOW_UP_HTML = """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
  <h2>Namaste {name} ji! 🙏</h2>
  <p>Main Aria hoon, <strong>{company}</strong> se.</p>
  <p>Aapki recent AC service ke baare mein follow up kar rahi hoon.</p>
  <p>Kya aapka AC sahi kaam kar raha hai? Koi problem ho toh batayein!</p>
  <p>Hum hamesha madad ke liye ready hain.</p>
  <p style="color: #666; font-size: 13px;">— Aria</p>
</div>
"""


class EmailTool:
    """
    Sends email confirmations and follow-ups.
    """

    def __init__(self):
        self.from_email = getattr(cfg, "EMAIL_FROM", "")
        self.password   = getattr(cfg, "EMAIL_PASSWORD", "")
        self.provider   = getattr(cfg, "EMAIL_PROVIDER", "gmail")
        self.company    = getattr(cfg, "ARIA_COMPANY", "AC Service")

    def is_ready(self) -> bool:
        return bool(self.from_email and self.password)

    def send(self, to: str, subject: str, html_body: str) -> dict:
        """Send an email."""
        if not self.is_ready():
            # Dev mode
            print(f"  [EMAIL] (dev mode) To: {to}")
            print(f"  [EMAIL] Subject: {subject}")
            return {"success": True, "mode": "dev"}

        try:
            msg                    = MIMEMultipart("alternative")
            msg["Subject"]         = subject
            msg["From"]            = self.from_email
            msg["To"]              = to
            msg.attach(MIMEText(html_body, "html"))

            if self.provider == "gmail":
                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                    server.login(self.from_email, self.password)
                    server.sendmail(self.from_email, to, msg.as_string())

            elif self.provider == "sendgrid":
                # SendGrid SMTP
                with smtplib.SMTP("smtp.sendgrid.net", 587) as server:
                    server.starttls()
                    server.login("apikey", self.password)
                    server.sendmail(self.from_email, to, msg.as_string())

            print(f"  [EMAIL] Sent to {to}")
            return {"success": True, "to": to}

        except Exception as e:
            print(f"  [EMAIL] Failed: {e}")
            return {"success": False, "error": str(e)}

    def send_booking_confirm(self, to: str, booking: dict) -> dict:
        """Send booking confirmation email."""
        html = BOOKING_CONFIRM_HTML.format(
            name       = booking.get("name", "Customer"),
            booking_id = booking.get("booking_id", "N/A"),
            service    = booking.get("service", "AC Service"),
            date       = booking.get("date", ""),
            slot       = booking.get("slot", ""),
            address    = booking.get("address", ""),
            company    = self.company,
        )
        return self.send(
            to      = to,
            subject = f"✅ Appointment Confirmed — {booking.get('booking_id', '')}",
            html_body = html,
        )

    def send_follow_up(self, to: str, name: str) -> dict:
        """Send post-service follow up email."""
        html = FOLLOW_UP_HTML.format(
            name    = name,
            company = self.company,
        )
        return self.send(
            to        = to,
            subject   = f"Aapki AC service kaisi rahi? — {self.company}",
            html_body = html,
        )


# ── Quick test ───────────────────────────────────────────────
if __name__ == "__main__":
    et = EmailTool()
    print(f"Email Ready: {et.is_ready()}")

    result = et.send_booking_confirm(
        to      = "test@example.com",
        booking = {
            "name":       "Rahul Sharma",
            "booking_id": "AC260408AB12",
            "service":    "AC Repair",
            "date":       "09 April 2026",
            "slot":       "10:00 AM",
            "address":    "123 MG Road, Delhi",
        }
    )
    print(f"Result: {result}")
