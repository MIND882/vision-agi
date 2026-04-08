# voice/tts.py
# ============================================================
# TTS — Text to Speech using gTTS (Google)
# Free, no API key, Hindi + English support!
#
# pip install gtts pygame
# ============================================================

import tempfile
import subprocess
import sys
from config import cfg


class TTSEngine:

    def __init__(self):
        # gTTS ke liye koi API key nahi chahiye
        self.api_key  = cfg.ELEVENLABS_API_KEY  # future use
        self.voice_id = cfg.ELEVENLABS_VOICE_ID  # future use

    def is_ready(self) -> bool:
        # gTTS hamesha ready hai — no key needed
        try:
            from gtts import gTTS
            return True
        except ImportError:
            return False

    def _detect_lang(self, text: str) -> str:
        """Hindi ya English detect karo."""
        hindi_words = {
            "hai", "hain", "kya", "nahi", "aap", "main", "mera",
            "meri", "hoga", "karo", "se", "ko", "ke", "ka", "toh",
            "bhi", "aur", "agar", "namaste", "shukriya", "ji"
        }
        words = set(text.lower().split())
        if len(words & hindi_words) >= 2:
            return "hi"
        return "en"

    def speak(self, text: str, save_path: str = None) -> str:
        """
        Convert text to speech, save to mp3.
        Returns: file path
        """
        try:
            from gtts import gTTS

            lang = self._detect_lang(text)

            if not save_path:
                tmp       = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                save_path = tmp.name

            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(save_path)
            print(f"  [TTS] Saved ({lang}): {save_path}")
            return save_path

        except ImportError:
            print("  [TTS] Run: pip install gtts")
            return ""
        except Exception as e:
            print(f"  [TTS] Error: {e}")
            return ""

    def play(self, text: str) -> None:
        """Speak text aloud — Aria bolti hai!"""
        print(f"  [TTS] Speaking: '{text[:60]}...'")
        path = self.speak(text)
        if path:
            self._os_play(path)

    def _os_play(self, path: str) -> None:
        """Play mp3 using OS default player."""
        try:
            if sys.platform == "win32":
                subprocess.Popen(f'start "" "{path}"', shell=True)
            elif sys.platform == "darwin":
                subprocess.run(["afplay", path])
            else:
                subprocess.run(["mpg123", path])
        except Exception as e:
            print(f"  [TTS] OS play failed: {e}")
            print(f"  [TTS] Audio at: {path} — open manually!")


# ── Quick test ───────────────────────────────────────────────
if __name__ == "__main__":
    tts = TTSEngine()
    print(f"TTS Ready : {tts.is_ready()}")

    if tts.is_ready():
        print("\nTesting Hindi...")
        tts.play("Namaste! Main Aria hoon, aapki AC service mein madad ke liye.")
        print("\nTesting English...")
        tts.play("Hello! I am Aria. How can I help you today?")
    else:
        print("Run: pip install gtts")