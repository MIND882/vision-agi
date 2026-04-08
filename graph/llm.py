# graph/llm.py
# ============================================================
# LLM factory — with automatic provider fallback.
#
# Priority order (set LLM_PROVIDER in .env as primary):
#   1. gemini    — Google, free 1M tokens/day
#   2. groq      — free 100k tokens/day
#   3. anthropic — paid, production quality
#
# If primary hits rate limit → auto switches to next provider.
#
# HOW TO USE:
#   from graph.llm import get_llm
#   llm = get_llm()           # main model
#   llm = get_llm(fast=True)  # fast model
# ============================================================

from config import cfg

def _make_deepseek(fast: bool = False):
    from langchain_openai import ChatOpenAI  # DeepSeek OpenAI-compatible hai!
    return ChatOpenAI(
        api_key=cfg.DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        temperature=cfg.LLM_TEMPERATURE,
        max_tokens=cfg.LLM_MAX_TOKENS,
    )

def _make_groq(fast: bool = False):
    from langchain_groq import ChatGroq
    return ChatGroq(
        api_key=cfg.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=cfg.LLM_TEMPERATURE,
        max_tokens=cfg.LLM_MAX_TOKENS,
    )


def _make_gemini(fast: bool = False):
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        google_api_key=cfg.GEMINI_API_KEY,
        model="gemini-2.0-flash",
        temperature=cfg.LLM_TEMPERATURE,
        max_output_tokens=cfg.LLM_MAX_TOKENS,
    )


def _make_anthropic(fast: bool = False):
    from langchain_anthropic import ChatAnthropic
    model = cfg.LLM_MODEL_FAST if fast else cfg.LLM_MODEL_MAIN
    return ChatAnthropic(
        api_key=cfg.ANTHROPIC_API_KEY,
        model=model,
        temperature=cfg.LLM_TEMPERATURE,
        max_tokens=cfg.LLM_MAX_TOKENS,
    )

# ── Provider map ─────────────────────────────────────────────
_PROVIDERS = {
    "deepseek":  _make_deepseek,
    "gemini":    _make_gemini,
    "groq":      _make_groq,
    "anthropic": _make_anthropic,
    
}

_FALLBACK_ORDER = ["deepseek", "gemini", "groq", "anthropic"]


class FallbackLLM:
    """
    Wraps multiple LLM providers.
    On rate limit (429) → auto switches to next provider.
    Transparent to all nodes — same .invoke() interface.
    """

    def __init__(self, fast: bool = False):
        self.fast    = fast
        self.primary = cfg.LLM_PROVIDER
        # Build order: primary first, then rest
        order = [self.primary] + [p for p in _FALLBACK_ORDER if p != self.primary]
        self.providers = [p for p in order if p in _PROVIDERS]

    def invoke(self, messages, **kwargs):
        last_error = None

        for provider_name in self.providers:
            # Skip unconfigured providers
            if provider_name == "deepseek"  and not cfg.DEEPSEEK_API_KEY:   continue
            if provider_name == "gemini"    and not cfg.GEMINI_API_KEY:      continue
            if provider_name == "groq"      and not cfg.GROQ_API_KEY:        continue
            if provider_name == "anthropic" and not cfg.ANTHROPIC_API_KEY:   continue
          

            try:
                llm    = _PROVIDERS[provider_name](self.fast)
                result = llm.invoke(messages, **kwargs)
                if provider_name != self.primary:
                    print(f"  [LLM] Fallback used: {provider_name} ✓")
                return result

            except Exception as e:
                err = str(e)
                is_rate_limit = (
                            "429" in err or
                            "402" in err or          # ← ye add karo
                            "rate_limit" in err.lower() or
                            "RESOURCE_EXHAUSTED" in err or
                            "quota" in err.lower() or
                            "balance" in err.lower() or   # ← ye add karo
                             "insufficient" in err.lower() # ← ye add karo
                            )
                if is_rate_limit:
                    print(f"  [LLM] {provider_name} rate limited → trying next provider...")
                    last_error = e
                    continue
                raise e  # non-rate-limit error → raise immediately

        raise Exception(
            f"All LLM providers exhausted.\n"
            f"Last error: {last_error}\n"
            f"Solutions:\n"
            f"  1. Wait a few minutes (rate limit resets)\n"
            f"  2. Add another API key to .env\n"
            f"  3. Add ANTHROPIC_API_KEY for paid fallback"
        )


def get_llm(fast: bool = False) -> FallbackLLM:
    """
    Returns FallbackLLM instance.
    Drop-in replacement — same .invoke() interface as before.
    """
    return FallbackLLM(fast=fast)