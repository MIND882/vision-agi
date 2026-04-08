# voice/voice_pipeline.py
# ============================================================
# VOICE PIPELINE — TTS + STT for Aria
#
# TTS : ElevenLabs  — text → speech (Aria ki awaaz)
# STT : Deepgram    — speech → text (customer ki awaaz sunna)
#
# Phase 2 Week 3:
#   pip install elevenlabs deepgram-sdk pyaudio
#   Add to .env: ELEVENLABS_API_KEY, DEEPGRAM_API_KEY
# ============================================================

import os
import tempfile
from pathlib import Path
from config import cfg


class TTSEngine:
    """
    Text-to-Speech using ElevenLabs.
    Converts Aria's text response to audio.
    """

    def __init__(self):
        self.api_key  = cfg.ELEVENLABS_API_KEY
        self.voice_id = cfg.ELEVENLABS_VOICE_ID

    def speak(self, text: str, save_path: str = None) -> str:
        """
        Convert text to speech.
        Returns: path to saved audio file.
        """
        if not self.api_key:
            print("  [TTS] ELEVENLABS_API_KEY not set — skipping audio")
            return ""

        try:
            from elevenlabs.client import ElevenLabs
            from elevenlabs import save

            client = ElevenLabs(api_key=self.api_key)
            audio  = client.generate(
                text  = text,
                voice = self.voice_id,
                model = "eleven_multilingual_v2",   # supports Hindi!
            )

            # Save to temp file if no path given
            if not save_path:
                tmp = tempfile.NamedTemporaryFile(
                    suffix=".mp3", delete=False
                )
                save_path = tmp.name

            save(audio, save_path)
            print(f"  [TTS] Audio saved: {save_path}")
            return save_path

        except ImportError:
            print("  [TTS] elevenlabs not installed — run: pip install elevenlabs")
            return ""
        except Exception as e:
            print(f"  [TTS] Failed: {e}")
            return ""

    def play(self, text: str) -> None:
        """Speak text aloud directly (blocking)."""
        if not self.api_key:
            print(f"  [TTS] Would say: {text[:80]}...")
            return

        try:
            from elevenlabs.client import ElevenLabs
            from elevenlabs import play

            client = ElevenLabs(api_key=self.api_key)
            audio  = client.generate(
                text  = text,
                voice = self.voice_id,
                model = "eleven_multilingual_v2",
            )
            play(audio)
        except Exception as e:
            print(f"  [TTS] Play failed: {e}")


class STTEngine:
    """
    Speech-to-Text using Deepgram.
    Converts customer's voice to text for Aria to process.
    """

    def __init__(self):
        self.api_key = cfg.DEEPGRAM_API_KEY

    def transcribe_file(self, audio_path: str) -> str:
        """
        Transcribe an audio file to text.
        Supports: mp3, wav, mp4, m4a
        """
        if not self.api_key:
            print("  [STT] DEEPGRAM_API_KEY not set")
            return ""

        try:
            from deepgram import DeepgramClient, PrerecordedOptions

            client  = DeepgramClient(self.api_key)
            options = PrerecordedOptions(
                model        = "nova-2",
                smart_format = True,
                language     = "hi-en",   # Hindi + English (code-switching)
            )

            with open(audio_path, "rb") as f:
                buffer_data = f.read()

            response = client.listen.prerecorded.v("1").transcribe_file(
                {"buffer": buffer_data},
                options,
            )
            transcript = (
                response["results"]["channels"][0]
                ["alternatives"][0]["transcript"]
            )
            print(f"  [STT] Transcribed: '{transcript[:80]}'")
            return transcript

        except ImportError:
            print("  [STT] deepgram-sdk not installed — run: pip install deepgram-sdk")
            return ""
        except Exception as e:
            print(f"  [STT] Failed: {e}")
            return ""

    def transcribe_mic(self, duration_seconds: int = 5) -> str:
        """
        Record from microphone and transcribe.
        Requires: pip install pyaudio
        """
        if not self.api_key:
            print("  [STT] DEEPGRAM_API_KEY not set")
            return ""

        try:
            import pyaudio
            import wave

            print(f"  [STT] Recording for {duration_seconds}s... speak now")

            # Record audio
            p      = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024,
            )

            frames = []
            for _ in range(0, int(16000 / 1024 * duration_seconds)):
                data = stream.read(1024)
                frames.append(data)

            stream.stop_stream()
            stream.close()
            p.terminate()

            # Save to temp wav
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(b"".join(frames))

            return self.transcribe_file(tmp.name)

        except ImportError:
            print("  [STT] pyaudio not installed — run: pip install pyaudio")
            return input("  [STT] Type your message instead: ")
        except Exception as e:
            print(f"  [STT] Mic failed: {e}")
            return ""


class VoicePipeline:
    """
    Combined voice pipeline for Aria.
    Handles full voice conversation loop.
    """

    def __init__(self):
        self.tts = TTSEngine()
        self.stt = STTEngine()

    def listen(self, duration: int = 5) -> str:
        """Listen to customer and return text."""
        return self.stt.transcribe_mic(duration)

    def speak(self, text: str) -> None:
        """Aria speaks the response."""
        self.tts.play(text)

    def is_ready(self) -> bool:
        """Check if both TTS and STT are configured."""
        return bool(self.tts.api_key and self.stt.api_key)

    def status(self) -> dict:
        """Return voice pipeline status."""
        return {
            "tts_ready": bool(self.tts.api_key),
            "stt_ready": bool(self.stt.api_key),
            "mode":      "full_voice" if self.is_ready() else "text_only",
        }