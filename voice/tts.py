# voice/tts.py
# ============================================================
# TTS — Text to Speech using ElevenLabs
# Natural, human-like voice — Hindi + English support!
#
# Model: eleven_multilingual_v2
# Default voice: Jessica (cgSgspJ2msm6clMCkdW9) — warm + bright
# ============================================================

import tempfile
import sys
import subprocess
from config import cfg


class TTSEngine:

    def __init__(self):
        self.api_key  = cfg.ELEVENLABS_API_KEY
        self.voice_id = cfg.ELEVENLABS_VOICE_ID
        self.model    = "eleven_multilingual_v2"

    def is_ready(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        from elevenlabs.client import ElevenLabs
        return ElevenLabs(api_key=self.api_key)

    def speak(self, text: str, save_path: str = None) -> str:
        """
        Convert text to speech, save to mp3.
        Returns: file path or ""
        """
        if not self.api_key:
            print("  [TTS] ELEVENLABS_API_KEY not set — using gTTS fallback")
            return self._gtts_fallback(text, save_path)

        try:
            client = self._get_client()
            audio  = client.text_to_speech.convert(
                voice_id                          = self.voice_id,
                text                              = text,
                model_id                          = self.model,
                output_format                     = "mp3_44100_128",
            )

            if not save_path:
                tmp       = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                save_path = tmp.name

            with open(save_path, "wb") as f:
                for chunk in audio:
                    if chunk:
                        f.write(chunk)

            print(f"  [TTS] ElevenLabs saved: {save_path}")
            return save_path

        except Exception as e:
            err = str(e)
            print(f"  [TTS] Error: {e}")
            return self._gtts_fallback(text, save_path)

    def _gtts_fallback(self, text: str, save_path: str = None) -> str:
        """Google TTS fallback — free but robotic."""
        try:
            from gtts import gTTS

            # Simple Hindi detection
            hindi_words = {"hai", "hain", "kya", "nahi", "aap", "main",
                          "mera", "meri", "hoga", "se", "ko", "ke", "ka",
                          "toh", "bhi", "aur", "namaste", "ji", "karo"}
            words = set(text.lower().split())
            lang  = "hi" if len(words & hindi_words) >= 2 else "en"

            if not save_path:
                tmp       = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                save_path = tmp.name

            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(save_path)
            print(f"  [TTS] gTTS fallback saved ({lang}): {save_path}")
            return save_path

        except Exception as e:
            print(f"  [TTS] gTTS also failed: {e}")
            return ""

    def play(self, text: str) -> None:
        """Speak text aloud."""
        print(f"  [TTS] Speaking: '{text[:60]}...'")
        path = self.speak(text)
        if path:
            self._os_play(path)

    def _os_play(self, path: str) -> None:
        """Play audio using OS."""
        try:
            if sys.platform == "win32":
                subprocess.Popen(f'start "" "{path}"', shell=True)
            elif sys.platform == "darwin":
                subprocess.run(["afplay", path])
            else:
                subprocess.run(["mpg123", path])
        except Exception as e:
            print(f"  [TTS] Play failed: {e}")
            print(f"  [TTS] Audio at: {path}")

    def list_voices(self) -> list:
        """List ElevenLabs voices."""
        if not self.api_key:
            return []
        try:
            client = self._get_client()
            voices = client.voices.get_all()
            return [{"id": v.voice_id, "name": v.name} for v in voices.voices]
        except Exception as e:
            print(f"  [TTS] List failed: {e}")
            return []


# ── Quick test ───────────────────────────────────────────────
if __name__ == "__main__":
    tts = TTSEngine()
    print(f"TTS Ready  : {tts.is_ready()}")
    print(f"Voice ID   : {tts.voice_id}")
    print(f"API Key    : {'set' if tts.api_key else 'NOT SET'}")

    if tts.is_ready():
        print("\nTesting Hindi...")
        tts.play("Namaste! Main Aria hoon, aapki AC service mein madad ke liye. Aap kaise hain?")
        import time; time.sleep(3)
        print("\nTesting English...")
        tts.play("Hello! I'm Aria, your AC service executive. How can I help you today?")
    else:
        print("Add ELEVENLABS_API_KEY to .env first!")