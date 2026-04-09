# tools/whatsapp.py
# ============================================================
# WHATSAPP TOOL — Send messages via WhatsApp Business API
#
# Provider: Twilio WhatsApp API (free sandbox for testing)
# Alt: Meta WhatsApp Business API (production)
#
# Setup (free sandbox):
#   1. twilio.com → sign up free
#   2. WhatsApp sandbox activate karein
#   3. .env mein add karein:
#      TWILIO_ACCOUNT_SID=xxx
#      TWILIO_AUTH_TOKEN=xxx
#      TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
#
# Usage:
#   from tools.whatsapp import WhatsAppTool
#   wa = WhatsAppTool()
#   wa.send(to="9876543210", message="Aapka appointment confirm hua!")
# ============================================================

from importlib import import_module
from pathlib import Path
import sys

try:
    from config import cfg
except ModuleNotFoundError:
    # Allow running this file directly via `python tools/whatsapp.py`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from config import cfg


# ── Message templates ────────────────────────────────────────
TEMPLATES = {
    "booking_confirm": """✅ *Appointment Confirmed!*

Booking ID: {booking_id}
Name: {name}
Service: {service}
Date: {date}
Time: {slot}
Address: {address}

Humare technician aapke paas aayenge.
Koi sawaal ho toh reply karein.

— Aria, {company}""",

    "booking_reminder": """🔔 *Appointment Reminder*

Kal aapka appointment hai:
📅 {date} | ⏰ {slot}
🔧 {service}

Technician ka number: {tech_phone}
— {company}""",

    "booking_cancel": """❌ *Appointment Cancelled*

Booking ID: {booking_id} cancel ho gayi.
Naya appointment lene ke liye reply karein.
— {company}""",

    "follow_up": """Namaste {name} ji! 🙏

Main Aria hoon, {company} se.
Aapki recent AC service ke baare mein follow up kar rahi hoon.

Kya AC theek kaam kar raha hai?
Koi problem ho toh batayein — hum madad karenge!

— Aria""",
}


class WhatsAppTool:
    """
    Sends WhatsApp messages to customers.
    Used by Aria for confirmations, reminders, follow-ups.
    """

    def __init__(self):
        self.account_sid = getattr(cfg, "TWILIO_ACCOUNT_SID", "")
        self.auth_token  = getattr(cfg, "TWILIO_AUTH_TOKEN", "")
        self.from_number = getattr(cfg, "TWILIO_WHATSAPP_FROM",
                                   "whatsapp:+14155238886")
        self.company     = cfg.ARIA_COMPANY if hasattr(cfg, "ARIA_COMPANY") else "AC Service"

    def is_ready(self) -> bool:
        return bool(self.account_sid and self.auth_token)

    def send(self, to: str, message: str) -> dict:
        """
        Send WhatsApp message.
        to: phone number (with or without country code)
        """
        # Format number
        if not to.startswith("+"):
            to = f"+91{to}"   # India default
        to_wa = f"whatsapp:{to}"

        if not self.is_ready():
            # Dev mode — just print
            print(f"  [WHATSAPP] (dev mode) To: {to}")
            print(f"  [WHATSAPP] Message: {message[:100]}...")
            return {"success": True, "mode": "dev", "to": to}

        try:
            Client = import_module("twilio.rest").Client
            client = Client(self.account_sid, self.auth_token)
            msg    = client.messages.create(
                from_ = self.from_number,
                to    = to_wa,
                body  = message,
            )
            print(f"  [WHATSAPP] Sent to {to} — SID: {msg.sid}")
            return {"success": True, "sid": msg.sid, "to": to}

        except ImportError:
            print("  [WHATSAPP] Run: pip install twilio")
            return {"success": False, "error": "twilio not installed"}
        except Exception as e:
            print(f"  [WHATSAPP] Failed: {e}")
            return {"success": False, "error": str(e)}

    def send_booking_confirm(self, to: str, booking: dict) -> dict:
        """Send booking confirmation message."""
        msg = TEMPLATES["booking_confirm"].format(
            booking_id = booking.get("booking_id", "N/A"),
            name       = booking.get("name", "Customer"),
            service    = booking.get("service", "AC Service"),
            date       = booking.get("date", ""),
            slot       = booking.get("slot", ""),
            address    = booking.get("address", ""),
            company    = self.company,
        )
        return self.send(to, msg)

    def send_reminder(self, to: str, booking: dict) -> dict:
        """Send appointment reminder."""
        msg = TEMPLATES["booking_reminder"].format(
            date       = booking.get("date", ""),
            slot       = booking.get("slot", ""),
            service    = booking.get("service", "AC Service"),
            tech_phone = booking.get("tech_phone", "Will be shared soon"),
            company    = self.company,
        )
        return self.send(to, msg)

    def send_follow_up(self, to: str, name: str) -> dict:
        """Send post-service follow up."""
        msg = TEMPLATES["follow_up"].format(
            name    = name,
            company = self.company,
        )
        return self.send(to, msg)


# ── Quick test ───────────────────────────────────────────────
if __name__ == "__main__":
    wa = WhatsAppTool()
    print(f"WhatsApp Ready: {wa.is_ready()}")

    # Dev mode test
    result = wa.send_booking_confirm(
        to      = "9876543210",
        booking = {
            "booking_id": "AC260408AB12",
            "name":       "Rahul Sharma",
            "service":    "AC Repair",
            "date":       "09 April 2026",
            "slot":       "10:00 AM",
            "address":    "123 MG Road, Delhi",
        }
    )
    print(f"Result: {result}")
