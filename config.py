# config.py
# ============================================================
# Central configuration for the entire Reasoning Core.
# Reads from .env file automatically via pydantic-settings.
#
# HOW TO USE in any file:
#   from config import cfg
#   model = cfg.LLM_MODEL_MAIN
#   threshold = cfg.QUALITY_THRESHOLD
# ============================================================

from pydantic_settings import BaseSettings
from pydantic import Field, computed_field
from functools import lru_cache


class Settings(BaseSettings):

    # ── DEEPSEEK ─────────────────────────────────────────────
    DEEPSEEK_API_KEY: str = Field(
        default="",
        description="Required when LLM_PROVIDER=deepseek"
    )

    # ── ANTHROPIC ────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = Field(
        default="",
        description="Required when LLM_PROVIDER=anthropic"
    )
    LLM_MODEL_MAIN: str = Field(
        default="claude-sonnet-4-6",
        description="Heavy reasoning model"
    )
    LLM_MODEL_FAST: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Fast/cheap model for classification"
    )
    LLM_MAX_TOKENS: int = Field(default=4096)
    LLM_TEMPERATURE: float = Field(
        default=0.1,
        description="0.0-1.0. Low = deterministic"
    )

    # ── GROQ (free tier for development) ─────────────────────
    GROQ_API_KEY: str = Field(
        default="",
        description="Required when LLM_PROVIDER=groq"
    )

    # ── GEMINI (Google — free 1M tokens/day) ─────────────────
    GEMINI_API_KEY: str = Field(
        default="",
        description="Required when LLM_PROVIDER=gemini"
    )

    # ── PROVIDER SWITCH ───────────────────────────────────────
    LLM_PROVIDER: str = Field(
        default="gemini",
        description="'gemini' | 'groq' | 'anthropic' | 'deepseek'"
    )

    # ── LANGSMITH ────────────────────────────────────────────
    LANGCHAIN_API_KEY: str = Field(default="")
    LANGCHAIN_TRACING_V2: bool = Field(default=False)
    LANGCHAIN_PROJECT: str = Field(default="reasoning-core-v1")
    LANGCHAIN_ENDPOINT: str = Field(default="https://api.smith.langchain.com")

    # ── TAVILY ───────────────────────────────────────────────
    TAVILY_API_KEY: str = Field(default="", description="Needed Week 3+")
    TAVILY_MAX_RESULTS: int = Field(default=5)

    # ── POSTGRESQL ───────────────────────────────────────────
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB:   str = Field(default="reasoning_core")
    POSTGRES_USER: str = Field(default="rc_user")
    POSTGRES_PASSWORD: str = Field(default="")

    # ── CHROMADB ─────────────────────────────────────────────
    CHROMA_MODE: str = Field(default="local")
    CHROMA_PERSIST_DIR: str = Field(default="./data/chromadb")
    CHROMA_HOST: str = Field(default="localhost")
    CHROMA_PORT: int = Field(default=8000)

    # ── VOICE — TTS + STT ────────────────────────────────────
    # ElevenLabs — Aria ki awaaz (TTS)
    # Sign up: elevenlabs.io → free tier 10k chars/month
    ELEVENLABS_API_KEY: str = Field(
        default="",
        description="TTS — ElevenLabs | elevenlabs.io | Aria ki awaaz"
    )
    ELEVENLABS_VOICE_ID: str = Field(
        default="21m00Tcm4TlvDq8ikWAM",
        description="Voice ID — default=Rachel (warm, professional, works for Hindi too)"
    )
    # Deepgram — Customer ki awaaz sunna (STT)
    # Sign up: deepgram.com → $200 free credits on signup
    DEEPGRAM_API_KEY: str = Field(
        default="",
        description="STT — Deepgram | deepgram.com | customer ki awaaz sunna"
    )
    VOICE_ENABLED: bool = Field(
        default=False,
        description="True karo jab dono keys set ho jayen"
    )

    # ── REASONING BEHAVIOR ───────────────────────────────────
    QUALITY_THRESHOLD: float = Field(default=0.8)
    MAX_REFINE_LOOPS: int = Field(default=3)
    MAX_SUB_PROBLEMS: int = Field(default=5)

    # ── LOGGING ──────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="DEBUG")
    LOG_FORMAT: str = Field(default="pretty")
    APP_ENV: str = Field(default="development")

    # ── COMPUTED FIELDS ──────────────────────────────────────
    @computed_field
    @property
    def POSTGRES_DSN(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def IS_DEVELOPMENT(self) -> bool:
        return self.APP_ENV == "development"

    @computed_field
    @property
    def IS_PRODUCTION(self) -> bool:
        return self.APP_ENV == "production"

    @computed_field
    @property
    def TRACING_ENABLED(self) -> bool:
        return self.LANGCHAIN_TRACING_V2 and bool(self.LANGCHAIN_API_KEY)

    @computed_field
    @property
    def VOICE_READY(self) -> bool:
        """True only when both TTS and STT keys are present."""
        return bool(self.ELEVENLABS_API_KEY and self.DEEPGRAM_API_KEY)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


cfg = get_settings()


def validate_config() -> None:
    """
    Checks all required values before graph starts.
    Call this at top of main.py.
    """
    error_list = []

    # ── Provider-specific key checks ─────────────────────────
    if cfg.LLM_PROVIDER == "deepseek" and not cfg.DEEPSEEK_API_KEY:
        error_list.append("DEEPSEEK_API_KEY is missing — add it to .env")

    if cfg.LLM_PROVIDER == "groq" and not cfg.GROQ_API_KEY:
        error_list.append("GROQ_API_KEY is missing — add it to .env")

    if cfg.LLM_PROVIDER == "anthropic" and not cfg.ANTHROPIC_API_KEY:
        error_list.append("ANTHROPIC_API_KEY is missing — add it to .env")

    if cfg.LLM_PROVIDER == "gemini" and not cfg.GEMINI_API_KEY:
        error_list.append("GEMINI_API_KEY is missing — add it to .env")

    if cfg.LLM_PROVIDER not in ["deepseek", "groq", "anthropic", "gemini"]:
        error_list.append("LLM_PROVIDER must be 'deepseek', 'groq', 'gemini', or 'anthropic'")

    # ── General checks ────────────────────────────────────────
    if not (0.0 <= cfg.QUALITY_THRESHOLD <= 1.0):
        error_list.append("QUALITY_THRESHOLD must be between 0.0 and 1.0")

    if cfg.MAX_REFINE_LOOPS < 1:
        error_list.append("MAX_REFINE_LOOPS must be at least 1")

    if not (0.0 <= cfg.LLM_TEMPERATURE <= 1.0):
        error_list.append("LLM_TEMPERATURE must be between 0.0 and 1.0")

    if error_list:
        raise ValueError(
            "\n\nConfig errors — fix your .env:\n"
            + "\n".join(f"  x {e}" for e in error_list)
        )

    print("✓ Config loaded successfully")
    print(f"  App env           : {cfg.APP_ENV}")
    print(f"  LLM provider      : {cfg.LLM_PROVIDER}")
    print(f"  Main model        : {cfg.LLM_MODEL_MAIN}")
    print(f"  Fast model        : {cfg.LLM_MODEL_FAST}")
    print(f"  Quality threshold : {cfg.QUALITY_THRESHOLD}")
    print(f"  Max refine loops  : {cfg.MAX_REFINE_LOOPS}")
    print(f"  Tracing enabled   : {cfg.TRACING_ENABLED}")
    print(f"  Voice ready       : {cfg.VOICE_READY}")