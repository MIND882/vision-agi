# voice_chat.py
# ============================================================
# ARIA — Full Voice Chat (mic in + voice out)
#
# Usage:
#   python voice_chat.py          # voice mode (mic + speaker)
#   python voice_chat.py --text   # text mode (keyboard only)
#
# Fix from v1:
#   - Threading race condition removed
#   - Simple push-to-talk approach (press Enter → speak)
#   - Cleaner exit handling
# ============================================================

import sys
from identity.aria import Aria
from voice.tts import TTSEngine
from voice.stt import STTEngine
from config import cfg, validate_config


def _get_user_input(stt: STTEngine, text_mode: bool) -> str:
    """
    Get input from user — mic or keyboard.
    Simple approach: Enter pehle, phir bolo.
    No threading race condition.
    """
    if text_mode:
        try:
            return input("Aap  : ").strip()
        except (KeyboardInterrupt, EOFError):
            return "quit"

    # Voice mode — press Enter then speak
    try:
        print("Aap  : [Enter dabao phir bolo | ya seedha type karo + Enter]")
        user_input = input("     > ").strip()

        # Kuch type kiya → direct use karo
        if user_input:
            return user_input

        # Kuch nahi type kiya → mic use karo
        text = stt.listen(duration_seconds=5)
        return text if text else ""

    except (KeyboardInterrupt, EOFError):
        return "quit"


def run_voice_chat(text_mode: bool = False):
    validate_config()
    print()

    aria = Aria()
    tts  = TTSEngine()
    stt  = STTEngine()

    # ── Status display ───────────────────────────────────────
    mode_label = "Text mode" if text_mode else "Voice mode"
    print("=" * 60)
    print(f"ARIA — {mode_label}")
    print("=" * 60)
    print(f"TTS (Aria ki awaaz) : {'ElevenLabs ✓' if tts.api_key else 'gTTS (fallback)'}")
    print(f"STT (Aapki awaaz)   : {'Deepgram ✓' if stt.api_key else 'Google STT (fallback)'}")
    print(f"LLM                 : {cfg.LLM_PROVIDER}")
    print()
    print("Commands: 'quit' | 'reset' | 'voice' | 'text'")
    print("=" * 60)

    # ── Aria greeting ────────────────────────────────────────
    try:
        greeting = aria.greet()
    except Exception:
        greeting = "Namaste! Main Aria hoon. Aapki AC service mein kaise madad kar sakti hoon?"

    print(f"\nAria : {greeting}\n")
    tts.play(greeting)

    # ── Main chat loop ───────────────────────────────────────
    while True:

        user_input = _get_user_input(stt, text_mode)

        # Empty input — try again
        if not user_input:
            print("  (Kuch samajh nahi aaya — dobara bolein)\n")
            continue

        # ── Commands ─────────────────────────────────────────
        cmd = user_input.lower().strip()

        if cmd == "quit":
            bye = "Shukriya! Aapka din shubh ho. Koi zarurat ho toh call karein."
            print(f"\nAria : {bye}")
            tts.play(bye)
            aria.end_session()
            break

        if cmd == "reset":
            aria.reset()
            msg = "Naya session shuru. Main Aria hoon — kaise madad kar sakti hoon?"
            print(f"Aria : {msg}\n")
            tts.play(msg)
            continue

        if cmd == "text":
            text_mode = True
            print("  [Text mode on]\n")
            continue

        if cmd == "voice":
            text_mode = False
            print("  [Voice mode on — Enter dabao phir bolo]\n")
            continue

        # ── Aria responds ─────────────────────────────────────
        print("Aria : ...")   # thinking indicator

        try:
            result   = aria.chat(user_input)
            response = result["response"]
        except Exception as e:
            response = "Maafi chahti hoon, abhi ek technical issue aa rahi hai. Thoda wait karein."
            print(f"  [ERROR] {e}")

        # Clear "..." and print response
        print(f"\rAria : {response}")
        print(f"       [lang={result.get('language','?')} | mode={result.get('mode','?')}]\n")

        # Speak response
        tts.play(response)


if __name__ == "__main__":
    text_mode = "--text" in sys.argv
    run_voice_chat(text_mode=text_mode)