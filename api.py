# api.py
# ============================================================
# ARIA — FastAPI Web Backend (Production-Ready)
#
# Changes from v1:
#   + Session isolation — har user ki apni Aria instance
#   + CORS enabled — frontend se call ho sake
#   + Session cleanup — memory leak prevent
#   + Better error handling
#   + /sessions endpoint for debugging
#
# Run:
#   uvicorn api:app --reload --port 8080
# ============================================================

import uuid
import os
import tempfile
import time
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from config import cfg, validate_config
from identity.aria import Aria
from voice.tts import TTSEngine

# ── App setup ────────────────────────────────────────────────
validate_config()
app = FastAPI(title="Aria — Digital Human", version="2.1")

# CORS — frontend (React/HTML) se API call allow karo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # production mein specific domain lagao
    allow_methods=["*"],
    allow_headers=["*"],
)

# TTS engine — shared (stateless, safe)
tts = TTSEngine()

# Audio temp storage
AUDIO_DIR = Path(tempfile.gettempdir()) / "aria_audio"
AUDIO_DIR.mkdir(exist_ok=True)

# ── Session store — har user ki apni Aria ────────────────────
# { session_id: {"aria": Aria(), "last_used": timestamp} }
_sessions: Dict[str, dict] = {}
SESSION_TIMEOUT = 30 * 60   # 30 minutes inactive = cleanup


def get_or_create_session(session_id: str) -> Aria:
    """
    Get existing Aria for this session, or create new one.
    Prevents user A seeing user B's conversation history.
    """
    now = time.time()

    # Cleanup stale sessions (simple GC)
    stale = [
        sid for sid, data in _sessions.items()
        if now - data["last_used"] > SESSION_TIMEOUT
    ]
    for sid in stale:
        try:
            _sessions[sid]["aria"].end_session()
        except Exception:
            pass
        del _sessions[sid]
        print(f"  [API] Session expired: {sid[:16]}")

    # Get or create
    if session_id not in _sessions:
        _sessions[session_id] = {
            "aria":      Aria(),
            "last_used": now,
        }
        print(f"  [API] New session: {session_id[:16]}")
    else:
        _sessions[session_id]["last_used"] = now

    return _sessions[session_id]["aria"]


# ── Request/Response models ──────────────────────────────────
class ChatRequest(BaseModel):
    message:    str
    session_id: str = ""   # empty = auto-generate

class ChatResponse(BaseModel):
    response:   str
    language:   str
    mode:       str
    session_id: str
    audio_id:   str = ""


# ── Helper ───────────────────────────────────────────────────
def _generate_audio(text: str) -> str:
    """Generate TTS audio, return audio_id or empty string."""
    try:
        audio_path = AUDIO_DIR / f"{uuid.uuid4()}.mp3"
        saved = tts.speak(text, save_path=str(audio_path))
        return audio_path.name if saved else ""
    except Exception as e:
        print(f"  [API] TTS failed: {e}")
        return ""


# ── Routes ───────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the chat UI."""
    html_path = Path(__file__).parent / "ui" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("""
        <h2>Aria API is running!</h2>
        <p>Place <code>index.html</code> in <code>ui/</code> folder for the chat UI.</p>
        <p><a href="/docs">API Docs →</a></p>
    """)


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Send message to Aria — session-isolated."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Session management
    session_id = req.session_id or str(uuid.uuid4())
    aria       = get_or_create_session(session_id)

    # Aria responds
    result   = aria.chat(req.message)
    response = result["response"]

    # TTS audio
    audio_id = _generate_audio(response)

    return ChatResponse(
        response   = response,
        language   = result["language"],
        mode       = result["mode"],
        session_id = session_id,
        audio_id   = audio_id,
    )


@app.post("/greet", response_model=ChatResponse)
async def greet(req: ChatRequest = None):
    """Get Aria's opening greeting — creates new session."""
    session_id = str(uuid.uuid4())
    aria       = get_or_create_session(session_id)

    try:
        greeting = aria.greet()
    except Exception:
        greeting = "Namaste! Main Aria hoon, aapki AC service mein madad ke liye."

    audio_id = _generate_audio(greeting)

    return ChatResponse(
        response   = greeting,
        language   = "hindi",
        mode       = "greeting",
        session_id = session_id,
        audio_id   = audio_id,
    )


@app.post("/reset/{session_id}")
async def reset(session_id: str):
    """Reset a session — saves to memory before clearing."""
    if session_id in _sessions:
        _sessions[session_id]["aria"].reset()
        return {"status": "ok", "session_id": session_id}
    return {"status": "not_found", "session_id": session_id}


@app.get("/audio/{audio_id}")
async def get_audio(audio_id: str):
    """Return TTS audio file."""
    if "/" in audio_id or "\\" in audio_id or ".." in audio_id:
        raise HTTPException(status_code=400, detail="Invalid audio ID")

    audio_path = AUDIO_DIR / audio_id
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")

    return FileResponse(
        path       = str(audio_path),
        media_type = "audio/mpeg",
        filename   = audio_id,
    )


@app.get("/status")
async def status():
    """System health check."""
    return {
        "status":          "ok",
        "aria":            "ready",
        "tts_engine":      "elevenlabs" if tts.api_key else "gtts",
        "voice_ready":     cfg.VOICE_READY,
        "llm_provider":    cfg.LLM_PROVIDER,
        "active_sessions": len(_sessions),
        "version":         "2.1",
    }
# ── Admin routes — add these to api.py ──────────────────────
# Copy karo api.py mein, /status route ke baad

@app.get("/admin")
async def admin():
    """Serve admin dashboard."""
    html_path = Path(__file__).parent / "ui" / "admin.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>admin.html not found in ui/ folder</h2>")


@app.get("/admin/bookings")
async def admin_bookings():
    """All bookings for admin dashboard."""
    try:
        import psycopg2
        import psycopg2.extras
        from config import cfg
        with psycopg2.connect(cfg.POSTGRES_DSN) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # All bookings
                cur.execute("""
                    SELECT booking_id, customer_name, phone, service_type,
                           preferred_date::text, time_slot, status, created_at::text
                    FROM appointments
                    ORDER BY created_at DESC LIMIT 20
                """)
                bookings = [dict(r) for r in cur.fetchall()]

                # Today count
                cur.execute("SELECT COUNT(*) AS today FROM appointments WHERE preferred_date = CURRENT_DATE")
                today_row = cur.fetchone()
                today = int(today_row["today"]) if today_row else 0

                # Total
                cur.execute("SELECT COUNT(*) AS total FROM appointments")
                total_row = cur.fetchone()
                total = int(total_row["total"]) if total_row else 0

        return {"bookings": bookings, "today": today, "total": total}
    except Exception as e:
        return {"bookings": [], "today": 0, "total": 0, "error": str(e)}


@app.get("/admin/leads")
async def admin_leads():
    """Leads + pipeline for admin dashboard."""
    try:
        import psycopg2
        import psycopg2.extras
        from config import cfg
        with psycopg2.connect(cfg.POSTGRES_DSN) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Hot leads
                cur.execute("""
                    SELECT lead_id, name, phone, issue, stage, score, created_at::text
                    FROM leads
                    WHERE stage NOT IN ('closed_won', 'closed_lost')
                    ORDER BY score DESC, created_at DESC
                    LIMIT 20
                """)
                leads = [dict(r) for r in cur.fetchall()]

                # Pipeline
                cur.execute("SELECT stage, COUNT(*) AS count FROM leads GROUP BY stage")
                pipeline = {row["stage"]: int(row["count"]) for row in cur.fetchall()}

                # Total
                cur.execute("SELECT COUNT(*) AS total FROM leads")
                total_row = cur.fetchone()
                total = int(total_row["total"]) if total_row else 0

        return {"leads": leads, "pipeline": pipeline, "total": total}
    except Exception as e:
        return {"leads": [], "pipeline": {}, "total": 0, "error": str(e)}

@app.get("/sessions")
async def sessions():
    """Debug — active sessions list."""
    return {
        "count": len(_sessions),
        "sessions": [
            {
                "id":         sid[:16],
                "turns":      data["aria"].turn_count,
                "idle_mins":  round((time.time() - data["last_used"]) / 60, 1),
            }
            for sid, data in _sessions.items()
        ]
    }


# ── Run directly ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*50)
    print("ARIA Web Backend v2.1")
    print("UI  : http://localhost:8080")
    print("Docs: http://localhost:8080/docs")
    print("="*50 + "\n")
    uvicorn.run("api:app", host="0.0.0.0", port=8080, reload=True)
