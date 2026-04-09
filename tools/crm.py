# tools/crm.py
# ============================================================
# CRM TOOL — Lead & Customer Management
#
# Storage: PostgreSQL (local, no external API needed!)
# Features:
#   - Save new lead
#   - Update lead status
#   - Get customer history
#   - Pipeline overview
#
# Lead stages:
#   new → contacted → qualified → appointment → closed → lost
#
# Usage:
#   from tools.crm import CRMTool
#   crm = CRMTool()
#   crm.save_lead(name="Rahul", phone="9876543210",
#                 issue="AC not cooling", source="website")
# ============================================================

from datetime import datetime
from pathlib import Path
from typing import Optional
import sys
import psycopg2
import psycopg2.extras

try:
    from config import cfg
except ModuleNotFoundError:
    # Allow running this file directly via `python tools/crm.py`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from config import cfg


LEAD_STAGES = [
    "new",
    "contacted",
    "qualified",
    "appointment_booked",
    "service_done",
    "closed_won",
    "closed_lost",
]


def _get_conn():
    return psycopg2.connect(cfg.POSTGRES_DSN)


def _ensure_table():
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id            SERIAL PRIMARY KEY,
                    lead_id       TEXT UNIQUE NOT NULL,
                    name          TEXT NOT NULL,
                    phone         TEXT NOT NULL,
                    email         TEXT DEFAULT '',
                    address       TEXT DEFAULT '',
                    issue         TEXT DEFAULT '',
                    ac_brand      TEXT DEFAULT '',
                    ac_age        TEXT DEFAULT '',
                    source        TEXT DEFAULT 'chat',
                    stage         TEXT DEFAULT 'new',
                    score         INTEGER DEFAULT 0,
                    notes         TEXT DEFAULT '',
                    booking_id    TEXT DEFAULT '',
                    created_at    TIMESTAMPTZ DEFAULT NOW(),
                    updated_at    TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # Auto-update updated_at
            cur.execute("""
                CREATE OR REPLACE FUNCTION update_leads_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
                $$ LANGUAGE plpgsql
            """)
            cur.execute("""
                DROP TRIGGER IF EXISTS trg_leads_updated_at ON leads
            """)
            cur.execute("""
                CREATE TRIGGER trg_leads_updated_at
                BEFORE UPDATE ON leads
                FOR EACH ROW EXECUTE FUNCTION update_leads_updated_at()
            """)


class CRMTool:
    """
    Manages customer leads and pipeline.
    Aria calls this when she captures a new lead.
    """

    def __init__(self):
        try:
            _ensure_table()
        except Exception as e:
            print(f"  [CRM] DB setup failed: {e}")

    def save_lead(
        self,
        name:     str,
        phone:    str,
        issue:    str    = "",
        address:  str    = "",
        email:    str    = "",
        ac_brand: str    = "",
        ac_age:   str    = "",
        source:   str    = "chat",
        notes:    str    = "",
    ) -> dict:
        """
        Save a new lead. If phone already exists → update instead.
        Returns: {success, lead_id, is_new}
        """
        try:
            import uuid
            lead_id = f"L{datetime.now().strftime('%y%m%d')}{str(uuid.uuid4())[:4].upper()}"

            with _get_conn() as conn:
                with conn.cursor() as cur:
                    # Check if exists
                    cur.execute("SELECT lead_id FROM leads WHERE phone = %s", (phone,))
                    existing = cur.fetchone()

                    if existing:
                        # Update existing lead
                        cur.execute("""
                            UPDATE leads SET
                                name     = %s,
                                issue    = CASE WHEN %s != '' THEN %s ELSE issue END,
                                address  = CASE WHEN %s != '' THEN %s ELSE address END,
                                notes    = CASE WHEN %s != '' THEN notes || ' | ' || %s ELSE notes END
                            WHERE phone = %s
                        """, (name, issue, issue, address, address, notes, notes, phone))
                        print(f"  [CRM] Updated existing lead: {existing[0]}")
                        return {"success": True, "lead_id": existing[0], "is_new": False}
                    else:
                        # Score the lead
                        score = self._score_lead(issue, address, ac_brand)
                        cur.execute("""
                            INSERT INTO leads
                                (lead_id, name, phone, email, address, issue,
                                 ac_brand, ac_age, source, score, notes)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """, (lead_id, name, phone, email, address, issue,
                              ac_brand, ac_age, source, score, notes))
                        print(f"  [CRM] New lead saved: {lead_id} — {name} (score={score})")
                        return {"success": True, "lead_id": lead_id, "is_new": True}

        except Exception as e:
            print(f"  [CRM] Save failed: {e}")
            return {"success": False, "lead_id": "", "is_new": False}

    def update_stage(self, phone: str, stage: str, notes: str = "") -> dict:
        """Move lead to next stage."""
        if stage not in LEAD_STAGES:
            return {"success": False, "error": f"Invalid stage: {stage}"}
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE leads SET stage = %s,
                            notes = CASE WHEN %s != '' THEN notes || ' | ' || %s ELSE notes END
                        WHERE phone = %s
                    """, (stage, notes, notes, phone))
            print(f"  [CRM] Stage updated: {phone} → {stage}")
            return {"success": True, "stage": stage}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_by_phone(self, phone: str) -> Optional[dict]:
        """Get customer info by phone."""
        try:
            with _get_conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM leads WHERE phone = %s ORDER BY created_at DESC LIMIT 1",
                        (phone,)
                    )
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            print(f"  [CRM] Get failed: {e}")
            return None

    def get_pipeline(self) -> dict:
        """Get pipeline overview — count per stage."""
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT stage, COUNT(*) as count
                        FROM leads GROUP BY stage ORDER BY count DESC
                    """)
                    rows = cur.fetchall()
                    return {row[0]: row[1] for row in rows}
        except Exception as e:
            print(f"  [CRM] Pipeline failed: {e}")
            return {}

    def get_hot_leads(self, limit: int = 10) -> list:
        """Get highest scored leads — for follow up."""
        try:
            with _get_conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute("""
                        SELECT lead_id, name, phone, issue, stage, score, created_at
                        FROM leads
                        WHERE stage NOT IN ('closed_won', 'closed_lost')
                        ORDER BY score DESC, created_at DESC
                        LIMIT %s
                    """, (limit,))
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            print(f"  [CRM] Hot leads failed: {e}")
            return []

    def _score_lead(self, issue: str, address: str, ac_brand: str) -> int:
        """Simple lead scoring 0-100."""
        score = 50  # base
        issue_lower = issue.lower()

        # High urgency = high score
        urgent = ["band", "nahi chal", "not working", "gas", "leak",
                  "emergency", "bahut garmi", "urgent"]
        if any(w in issue_lower for w in urgent):
            score += 30

        # Has address = more likely to convert
        if address:
            score += 10

        # Has AC brand info = qualified lead
        if ac_brand:
            score += 10

        return min(score, 100)


# ── Quick test ───────────────────────────────────────────────
if __name__ == "__main__":
    crm = CRMTool()

    print("Saving test lead...")
    result = crm.save_lead(
        name     = "Rahul Sharma",
        phone    = "9876543210",
        issue    = "AC band ho gaya, gas leak lag rahi hai",
        address  = "Delhi",
        ac_brand = "Voltas",
        source   = "website",
    )
    print(f"Result: {result}")

    print("\nPipeline:")
    pipeline = crm.get_pipeline()
    for stage, count in pipeline.items():
        print(f"  {stage}: {count}")

    print("\nHot leads:")
    for lead in crm.get_hot_leads(5):
        print(f"  {lead['name']} — {lead['stage']} — score={lead['score']}")
