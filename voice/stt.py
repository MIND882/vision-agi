# voice/stt.py
# ============================================================
# STT — Speech to Text
# Primary  : Deepgram nova-2 (Hindi+English)
# Fallback : Google SpeechRecognition (free, no key needed)
# ============================================================

import tempfile
import wave
from config import cfg


class STTEngine:

    def __init__(self):
        self.api_key = cfg.DEEPGRAM_API_KEY
        self.model   = "nova-2"
        self.lang    = "hi-en"

    def is_ready(self) -> bool:
        try:
            import speech_recognition
            return True
        except ImportError:
            pass
        try:
            from deepgram import DeepgramClient
            return bool(self.api_key)
        except ImportError:
            pass
        return False

    def _transcribe_deepgram(self, audio_path: str) -> str:
        try:
            from deepgram import DeepgramClient, PrerecordedOptions
            client  = DeepgramClient(self.api_key)
            options = PrerecordedOptions(
                model        = self.model,
                smart_format = True,
                language     = self.lang,
            )
            with open(audio_path, "rb") as f:
                buffer_data = f.read()
            response = client.listen.prerecorded.v("1").transcribe_file(
                {"buffer": buffer_data, "mimetype": "audio/wav"},
                options,
            )
            transcript = (
                response["results"]["channels"][0]
                ["alternatives"][0]["transcript"]
            )
            return transcript.strip()
        except Exception as e:
            print(f"  [STT] Deepgram failed: {e}")
            return ""

    def _transcribe_google(self, audio_path: str) -> str:
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(audio_path) as source:
                audio = recognizer.record(source)
            try:
                return recognizer.recognize_google(audio, language="hi-IN").strip()
            except Exception:
                return recognizer.recognize_google(audio, language="en-IN").strip()
        except ImportError:
            print("  [STT] Run: pip install SpeechRecognition")
            return ""
        except Exception as e:
            print(f"  [STT] Google STT failed: {e}")
            return ""

    def _record_mic(self, duration_seconds: int = 5) -> str:
        try:
            import pyaudio
            print(f"  [STT] Recording {duration_seconds}s... BOLO ABHI!")
            p      = pyaudio.PyAudio()
            stream = p.open(
                format            = pyaudio.paInt16,
                channels          = 1,
                rate              = 16000,
                input             = True,
                frames_per_buffer = 1024,
            )
            frames = []
            for _ in range(0, int(16000 / 1024 * duration_seconds)):
                data = stream.read(1024)
                frames.append(data)
            stream.stop_stream()
            stream.close()
            p.terminate()
            print("  [STT] Recording done!")
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(b"".join(frames))
            return tmp.name
        except ImportError:
            print("  [STT] pyaudio not installed — run: pip install pyaudio")
            return ""
        except Exception as e:
            print(f"  [STT] Mic error: {e}")
            return ""

    def listen(self, duration_seconds: int = 5) -> str:
        """Record from mic and transcribe. Main method."""
        audio_path = self._record_mic(duration_seconds)
        if not audio_path:
            return input("  Aap (type karein): ").strip()

        text = ""
        if self.api_key:
            text = self._transcribe_deepgram(audio_path)

        if not text:
            print("  [STT] Trying Google STT...")
            text = self._transcribe_google(audio_path)

        if text:
            print(f"  [STT] Heard: '{text}'")
        else:
            print("  [STT] Samajh nahi aaya — dobara bolein")

        return text


if __name__ == "__main__":
    stt = STTEngine()
    print(f"STT Ready : {stt.is_ready()}")
    print(f"Deepgram  : {'yes' if stt.api_key else 'no — Google fallback use hoga'}")
    print()
    print("5 second test — kuch bolo:")
    text = stt.listen(duration_seconds=5)
    print(f"\nResult: '{text}'" if text else "\nKuch nahi suna!")