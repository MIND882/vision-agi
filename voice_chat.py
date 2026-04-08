# voice_chat.py
# ============================================================
# ARIA — Full Voice Chat (mic in + voice out)
#
# Usage:
#   python voice_chat.py          # voice mode
#   python voice_chat.py --text   # text mode (fallback)
# ============================================================

import sys
from identity.aria import Aria
from voice.tts import TTSEngine
from voice.stt import STTEngine
from config import cfg, validate_config


def run_voice_chat(text_mode: bool = False):
    validate_config()
    print()

    aria = Aria()
    tts  = TTSEngine()
    stt  = STTEngine()

    mode_label = "Text mode" if text_mode else "Voice mode"
    print("=" * 60)
    print(f"ARIA — {mode_label}")
    print("=" * 60)
    print(f"Voice out (TTS) : {'Ready' if tts.is_ready() else 'Not ready'}")
    print(f"Voice in  (STT) : {'Ready' if stt.is_ready() else 'Text fallback'}")
    if not text_mode:
        print("\nCommands: 'quit' | 'reset' | 'text' (switch to text mode)")
    print("=" * 60)

    # ── Aria greets ──────────────────────────────────────────
    try:
        greeting = aria.greet()
    except Exception:
        greeting = "Namaste! Main Aria hoon. Aapki AC service mein kaise madad kar sakti hoon?"

    print(f"\nAria : {greeting}\n")
    tts.play(greeting)

    # ── Chat loop ─────────────────────────────────────────────
    while True:
        try:
            if text_mode:
                user_input = input("Aap  : ").strip()
            else:
                print("Aap  : [Press Enter to speak / type to skip mic]")
                # Give option to type or use mic
                import threading
                typed = [None]

                def get_typed():
                    typed[0] = input()

                t = threading.Thread(target=get_typed)
                t.daemon = True
                t.start()
                t.join(timeout=1.5)

                if typed[0] is not None and typed[0].strip():
                    user_input = typed[0].strip()
                else:
                    # Use mic
                    user_input = stt.listen(duration_seconds=5)

        except (KeyboardInterrupt, EOFError):
            bye = "Shukriya! Aapka din shubh ho."
            print(f"\nAria : {bye}")
            tts.play(bye)
            break

        if not user_input:
            continue

        if user_input.lower() == "quit":
            bye = "Shukriya! Koi zarurat ho toh call karein."
            print(f"Aria : {bye}")
            tts.play(bye)
            break

        if user_input.lower() == "reset":
            aria.reset()
            msg = "Naya session shuru. Kaise madad kar sakti hoon?"
            print(f"Aria : {msg}\n")
            tts.play(msg)
            continue

        if user_input.lower() == "text":
            text_mode = True
            print("  [Switched to text mode]\n")
            continue

        # ── Aria responds ────────────────────────────────────
        print("Aria : (soch rahi hoon...)")
        result   = aria.chat(user_input)
        response = result["response"]

        print(f"\rAria : {response}")
        print(f"       [lang={result['language']} | mode={result['mode']}]\n")
        tts.play(response)


if __name__ == "__main__":
    text_mode = "--text" in sys.argv
    run_voice_chat(text_mode=text_mode)