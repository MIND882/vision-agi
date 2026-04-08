-- scripts/init_db.sql
-- ============================================================
-- Reasoning Core — PostgreSQL Schema
-- Runs automatically when Docker starts for the first time.
-- ============================================================

-- Facts table — stores domain knowledge
-- Example: "Paris is the capital of France"
CREATE TABLE IF NOT EXISTS facts (
    id           SERIAL PRIMARY KEY,
    session_id   VARCHAR(64),
    query        TEXT NOT NULL,
    fact         TEXT NOT NULL,
    confidence   FLOAT DEFAULT 1.0,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- Sessions table — tracks every reasoning session
CREATE TABLE IF NOT EXISTS sessions (
    id           SERIAL PRIMARY KEY,
    session_id   VARCHAR(64) UNIQUE NOT NULL,
    raw_input    TEXT,
    problem_type VARCHAR(32),
    final_score  FLOAT,
    what_worked  TEXT,
    what_failed  TEXT,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- Learnings table — what worked and what didn't
CREATE TABLE IF NOT EXISTS learnings (
    id           SERIAL PRIMARY KEY,
    session_id   VARCHAR(64),
    pattern      TEXT NOT NULL,
    outcome      VARCHAR(16),   -- 'success' | 'failure'
    score        FLOAT,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_facts_query       ON facts(query);
CREATE INDEX IF NOT EXISTS idx_sessions_id       ON sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_learnings_outcome ON learnings(outcome);