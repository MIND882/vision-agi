# tools/booking.py
# ============================================================
# BOOKING TOOL — Appointment management for AC Service
#
# Storage: PostgreSQL (same DB as semantic memory)
# Features:
#   - Book appointment
#   - Check available slots
#   - Get customer appointments
#   - Cancel appointment
#
# Usage:
#   from tools.booking import BookingTool
#   booking = BookingTool()
#   result = booking.book(name="Rahul", phone="9876543210",
#                        address="Delhi", service="AC Repair",
#                        preferred_date="2026-04-10", slot="10:00 AM")
# ============================================================

from datetime import datetime, date
from pathlib import Path
import sys
import psycopg2
import psycopg2.extras

try:
    from config import cfg
except ModuleNotFoundError:
    # Allow running this file directly via `python tools/booking.py`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from config import cfg


# ── Available slots ──────────────────────────────────────────
AVAILABLE_SLOTS = [
    "9:00 AM", "10:00 AM", "11:00 AM",
    "12:00 PM", "2:00 PM",  "3:00 PM",
    "4:00 PM",  "5:00 PM",
]

# ── Service types ─────────────────────────────────────────────
SERVICE_TYPES = [
    "AC Repair",
    "AC Service / Cleaning",
    "Gas Refilling",
    "AC Installation",
    "AMC - Annual Maintenance",
    "Emergency Breakdown",
    "Inspection / Diagnosis",
]


def _get_conn():
    return psycopg2.connect(cfg.POSTGRES_DSN)


def _ensure_table():
    """Create appointments table if not exists."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS appointments (
                    id              SERIAL PRIMARY KEY,
                    booking_id      TEXT UNIQUE NOT NULL,
                    customer_name   TEXT NOT NULL,
                    phone           TEXT NOT NULL,
                    address         TEXT NOT NULL,
                    service_type    TEXT NOT NULL,
                    preferred_date  DATE NOT NULL,
                    time_slot       TEXT NOT NULL,
                    status          TEXT DEFAULT 'confirmed',
                    notes           TEXT DEFAULT '',
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)


class BookingTool:
    """
    Handles AC service appointment booking.
    Called by Aria when customer wants to book service.
    """

    def __init__(self):
        try:
            _ensure_table()
        except Exception as e:
            print(f"  [BOOKING] DB setup failed: {e}")

    def book(
        self,
        name:           str,
        phone:          str,
        address:        str,
        service:        str = "AC Repair",
        preferred_date: str = "",    # "YYYY-MM-DD" or "today"/"tomorrow"
        slot:           str = "10:00 AM",
        notes:          str = "",
    ) -> dict:
        """
        Book an appointment.
        Returns: {success, booking_id, message}
        """
        try:
            # Parse date
            if not preferred_date or preferred_date.lower() == "today":
                appt_date = date.today()
            elif preferred_date.lower() == "tomorrow":
                from datetime import timedelta
                appt_date = date.today() + timedelta(days=1)
            else:
                appt_date = datetime.strptime(preferred_date, "%Y-%m-%d").date()

            # Generate booking ID
            import uuid
            booking_id = f"AC{datetime.now().strftime('%y%m%d')}{str(uuid.uuid4())[:4].upper()}"

            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO appointments
                            (booking_id, customer_name, phone, address,
                             service_type, preferred_date, time_slot, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        booking_id, name, phone, address,
                        service, appt_date, slot, notes
                    ))

            msg = (
                f"Appointment confirmed! "
                f"Booking ID: {booking_id} | "
                f"Date: {appt_date.strftime('%d %B %Y')} | "
                f"Time: {slot} | "
                f"Service: {service}"
            )
            print(f"  [BOOKING] Booked: {booking_id} for {name}")
            return {"success": True, "booking_id": booking_id, "message": msg}

        except Exception as e:
            print(f"  [BOOKING] Book failed: {e}")
            return {
                "success": False,
                "booking_id": "",
                "message": f"Booking failed: {e}"
            }

    def get_slots(self, for_date: str = "today") -> dict:
        """Get available slots for a date."""
        try:
            if for_date.lower() == "today":
                check_date = date.today()
            elif for_date.lower() == "tomorrow":
                from datetime import timedelta
                check_date = date.today() + timedelta(days=1)
            else:
                check_date = datetime.strptime(for_date, "%Y-%m-%d").date()

            # Get booked slots for this date
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT time_slot FROM appointments
                        WHERE preferred_date = %s AND status = 'confirmed'
                    """, (check_date,))
                    booked = {row[0] for row in cur.fetchall()}

            available = [s for s in AVAILABLE_SLOTS if s not in booked]
            return {
                "date":      check_date.strftime("%d %B %Y"),
                "available": available,
                "booked":    len(booked),
            }

        except Exception as e:
            print(f"  [BOOKING] Slots failed: {e}")
            return {"date": for_date, "available": AVAILABLE_SLOTS, "booked": 0}

    def get_by_phone(self, phone: str) -> list:
        """Get all appointments for a customer by phone."""
        try:
            with _get_conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute("""
                        SELECT booking_id, customer_name, service_type,
                               preferred_date, time_slot, status, created_at
                        FROM appointments
                        WHERE phone = %s
                        ORDER BY preferred_date DESC
                        LIMIT 5
                    """, (phone,))
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            print(f"  [BOOKING] Get by phone failed: {e}")
            return []

    def cancel(self, booking_id: str) -> dict:
        """Cancel an appointment."""
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE appointments SET status = 'cancelled'
                        WHERE booking_id = %s
                    """, (booking_id,))
                    if cur.rowcount == 0:
                        return {"success": False, "message": "Booking ID not found"}

            return {"success": True, "message": f"Appointment {booking_id} cancelled"}
        except Exception as e:
            return {"success": False, "message": f"Cancel failed: {e}"}

    def get_all_today(self) -> list:
        """Get all appointments for today — for admin dashboard."""
        try:
            with _get_conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute("""
                        SELECT booking_id, customer_name, phone, address,
                               service_type, time_slot, status
                        FROM appointments
                        WHERE preferred_date = CURRENT_DATE
                        ORDER BY time_slot
                    """)
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            print(f"  [BOOKING] Today's appointments failed: {e}")
            return []


# ── Quick test ───────────────────────────────────────────────
if __name__ == "__main__":
    bt = BookingTool()

    print("Testing booking...")
    result = bt.book(
        name           = "Rahul Sharma",
        phone          = "9876543210",
        address        = "123 MG Road, Delhi",
        service        = "AC Repair",
        preferred_date = "tomorrow",
        slot           = "10:00 AM",
    )
    print(f"Result: {result}")

    print("\nAvailable slots tomorrow:")
    slots = bt.get_slots("tomorrow")
    print(f"Date: {slots['date']}")
    print(f"Available: {slots['available']}")

    print("\nToday's appointments:")
    today = bt.get_all_today()
    for appt in today:
        print(f"  {appt['time_slot']} — {appt['customer_name']} — {appt['service_type']}")
