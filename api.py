# api.py
# ============================================================
# ARIA — FastAPI Web Backend
#
# Endpoints:
#   GET  /           → Chat UI (HTML)
#   POST /chat       → Send message, get Aria's response
#   GET  /audio/{id} → Get TTS audio file
#   GET  /status     → System status
#
# Run:
#   uvicorn api:app --reload --port 8080
# ============================================================

import uuid
import os
import tempfile
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import cfg, validate_config
from identity.aria import Aria
from voice.tts import TTSEngine

# ── App setup ────────────────────────────────────────────────
app  = FastAPI(title="Aria — Digital Human", version="2.0")
aria = Aria()
tts  = TTSEngine()

# Audio files temp storage
AUDIO_DIR = Path(tempfile.gettempdir()) / "aria_audio"
AUDIO_DIR.mkdir(exist_ok=True)


# ── Request/Response models ──────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: str = ""

class ChatResponse(BaseModel):
    response: str
    language: str
    mode: str
    audio_id: str = ""   # empty if TTS failed


# ── Routes ───────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the chat UI."""
    html_path = Path(__file__).parent / "ui" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>UI not found — place index.html in ui/ folder</h1>")


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Send message to Aria, get response + audio."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Get Aria's response
    result   = aria.chat(req.message)
    response = result["response"]

    # Generate TTS audio
    audio_id = ""
    try:
        audio_path = AUDIO_DIR / f"{uuid.uuid4()}.mp3"
        saved      = tts.speak(response, save_path=str(audio_path))
        if saved:
            audio_id = audio_path.name
        else:
            print("  [API] TTS returned no audio for /chat")
    except Exception as e:
        print(f"  [API] TTS failed: {e}")

    return ChatResponse(
        response  = response,
        language  = result["language"],
        mode      = result["mode"],
        audio_id  = audio_id,
    )


@app.get("/audio/{audio_id}")
async def get_audio(audio_id: str):
    """Return TTS audio file."""
    # Security: only allow simple filenames
    if "/" in audio_id or "\\" in audio_id or ".." in audio_id:
        raise HTTPException(status_code=400, detail="Invalid audio ID")

    audio_path = AUDIO_DIR / audio_id
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")

    return FileResponse(
        path         = str(audio_path),
        media_type   = "audio/mpeg",
        filename     = audio_id,
    )


@app.post("/greet", response_model=ChatResponse)
async def greet():
    """Get Aria's opening greeting."""
    try:
        greeting = aria.greet()
    except Exception:
        greeting = "Namaste! Main Aria hoon, aapki AC service mein madad ke liye."

    audio_id = ""
    try:
        audio_path = AUDIO_DIR / f"{uuid.uuid4()}.mp3"
        saved      = tts.speak(greeting, save_path=str(audio_path))
        if saved:
            audio_id = audio_path.name
    except Exception:
        pass

    return ChatResponse(
        response = greeting,
        language = "hindi",
        mode     = "greeting",
        audio_id = audio_id,
    )


@app.post("/reset")
async def reset():
    """Reset Aria's conversation history."""
    aria.reset()
    return {"status": "ok", "message": "Session reset"}


@app.get("/status")
async def status():
    """System health check."""
    return {
        "aria":     "ready",
        "tts":      "ready" if tts.is_ready() else "elevenlabs_not_ready",
        "provider": cfg.LLM_PROVIDER,
        "voice":    cfg.VOICE_READY,
        "persona":  f"{aria.persona.name} — {aria.persona.company}",
    }


# ── Run directly ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    validate_config()
    print("\n" + "="*50)
    print("ARIA Web UI starting...")
    print("Open: http://localhost:8080")
    print("="*50 + "\n")
    uvicorn.run("api:app", host="0.0.0.0", port=8080, reload=True)
