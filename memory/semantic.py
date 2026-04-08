# memory/semantic.py
# ============================================================
# SEMANTIC MEMORY — structured facts via PostgreSQL.
# "What facts and rules has the system learned?"
#
# Stores: facts, session summaries, success/failure patterns.
# ============================================================

from datetime import datetime
from typing import Optional
import psycopg2
import psycopg2.extras

from config import cfg


def _get_conn():
    """Get PostgreSQL connection."""
    return psycopg2.connect(cfg.POSTGRES_DSN)


class SemanticMemory:
    """
    Stores structured knowledge in PostgreSQL.
    Fast keyword search — complements ChromaDB's similarity search.
    """

    def store_session(
        self,
        session_id:   str,
        raw_input:    str,
        problem_type: str,
        final_score:  float,
        what_worked:  str,
        what_failed:  str,
    ) -> None:
        """Save a completed session summary to PostgreSQL."""
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO sessions
                            (session_id, raw_input, problem_type,
                             final_score, what_worked, what_failed)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (session_id) DO UPDATE
                            SET final_score = EXCLUDED.final_score,
                                what_worked = EXCLUDED.what_worked,
                                what_failed = EXCLUDED.what_failed
                    """, (
                        session_id, raw_input, problem_type,
                        final_score, what_worked, what_failed,
                    ))
            print(f"  [SEMANTIC] Session stored: {session_id[:16]}...")
        except Exception as e:
            print(f"  [SEMANTIC] Store session failed: {e}")

    def store_fact(
        self,
        session_id: str,
        query:      str,
        fact:       str,
        confidence: float = 1.0,
    ) -> None:
        """Store a discovered fact for future retrieval."""
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO facts (session_id, query, fact, confidence)
                        VALUES (%s, %s, %s, %s)
                    """, (session_id, query, fact, confidence))
            print(f"  [SEMANTIC] Fact stored: '{fact[:60]}'")
        except Exception as e:
            print(f"  [SEMANTIC] Store fact failed: {e}")

    def store_learning(
        self,
        session_id: str,
        pattern:    str,
        outcome:    str,    # 'success' | 'failure'
        score:      float,
    ) -> None:
        """Store a learned pattern — what worked or failed."""
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO learnings (session_id, pattern, outcome, score)
                        VALUES (%s, %s, %s, %s)
                    """, (session_id, pattern, outcome, score))
        except Exception as e:
            print(f"  [SEMANTIC] Store learning failed: {e}")

    def get_recent_sessions(self, limit: int = 5) -> list[dict]:
        """Get recent session summaries for context."""
        try:
            with _get_conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute("""
                        SELECT session_id, raw_input, problem_type,
                               final_score, what_worked, created_at
                        FROM sessions
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, (limit,))
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            print(f"  [SEMANTIC] Get sessions failed: {e}")
            return []

    def search_facts(self, keyword: str, limit: int = 5) -> list[dict]:
        """Simple keyword search in facts table."""
        try:
            with _get_conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute("""
                        SELECT query, fact, confidence, created_at
                        FROM facts
                        WHERE fact ILIKE %s OR query ILIKE %s
                        ORDER BY confidence DESC, created_at DESC
                        LIMIT %s
                    """, (f"%{keyword}%", f"%{keyword}%", limit))
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            print(f"  [SEMANTIC] Search facts failed: {e}")
            return []

    def test_connection(self) -> bool:
        """Test if PostgreSQL is reachable — called at startup."""
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return True
        except Exception as e:
            print(f"  [SEMANTIC] Connection failed: {e}")
            return False