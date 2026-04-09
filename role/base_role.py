# roles/base_role.py
# ============================================================
# BASE ROLE — Abstract blueprint for every Digital Human.
#
# Every role (Aria, Max, Priya, Rohan) inherits from this.
# Same Brain (Reasoning Core) + different Soul (Role config).
#
# To create a new role:
#   1. Inherit from BaseRole
#   2. Override: name, company, role, personality, etc.
#   3. Override: _detect_mode() if needed
#   4. Done — brain is auto-wired
# ============================================================

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import uuid

from graph.llm import get_llm
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from langchain_core.messages import HumanMessage, SystemMessage


# ── Role Configuration ───────────────────────────────────────

@dataclass
class RoleConfig:
    """
    Complete configuration for one Digital Human role.
    Fill these fields to define a new persona.
    """
    # Identity
    name:               str           # "Aria", "Max", "Priya", "Rohan"
    role:               str           # "AC Service Executive", "Sales Agent"
    company:            str           # Client's company name
    industry:           str           # "HVAC", "SaaS", "HR", "E-commerce"

    # Personality
    personality:        str           # "empathetic, professional, solution-focused"
    communication_style: str          # "consultative", "direct", "friendly"
    language_preference: str = "hindi+english"   # Hinglish by default

    # Greetings
    hindi_greeting:     str = ""      # Opening line in Hindi
    english_greeting:   str = ""      # Opening line in English

    # Domain knowledge
    domain_expertise:   list[str] = field(default_factory=list)
    # e.g. ["AC repair", "gas refill", "AMC plans", "installation"]

    # Mode keywords — override in subclass if needed
    support_phrases:    list[str] = field(default_factory=list)
    support_words:      set = field(default_factory=set)
    sales_phrases:      list[str] = field(default_factory=list)
    sales_words:        set = field(default_factory=set)

    # Tools available to this role
    tools_enabled:      list[str] = field(default_factory=list)
    # e.g. ["booking", "crm", "whatsapp", "email"]


# ── Base Role Class ───────────────────────────────────────────

class BaseRole(ABC):
    """
    Abstract base for all Digital Human roles.
    Provides: chat, greet, memory, session management.
    Subclasses provide: role config + mode detection.
    """

    def __init__(self):
        self.config     = self._build_config()
        self.llm        = get_llm(fast=False)
        self.history    = []
        self.session_id = str(uuid.uuid4())
        self.turn_count = 0
        self.episodic   = EpisodicMemory()
        self.semantic   = SemanticMemory()
        print(f"  [{self.config.name.upper()}] Session: {self.session_id[:16]}...")

    @abstractmethod
    def _build_config(self) -> RoleConfig:
        """
        Subclass must return a fully filled RoleConfig.
        This is what makes each role unique.
        """
        pass

    def _build_system_prompt(self, mode: str, context: str = "") -> str:
        """Build the system prompt from role config + mode."""
        cfg = self.config

        base = f"""You are {cfg.name}, a {cfg.role} at {cfg.company}.

Personality: {cfg.personality}
Communication style: {cfg.communication_style}
Industry expertise: {cfg.industry}
Domain knowledge: {', '.join(cfg.domain_expertise)}

Language: Respond in Hindi if customer speaks Hindi, English if English.
          Mix naturally (Hinglish) if customer mixes languages.

Current mode: {mode}"""

        mode_instructions = {
            "greeting": f"\nGreet warmly as {cfg.name}. Be welcoming and helpful.",
            "support":  "\nFocus on solving the customer's problem. Be empathetic. Ask clarifying questions.",
            "sales":    "\nHighlight value and benefits. Address objections. Guide toward booking/purchase.",
            "general":  "\nBe helpful and friendly. Understand the customer's need first.",
        }
        base += mode_instructions.get(mode, mode_instructions["general"])

        if context:
            base += f"\n\nRelevant context:\n{context}"

        base += f"\n\nAlways stay in character as {cfg.name}. Never reveal you are an AI unless directly asked."

        return base

    def _detect_mode(self, text: str) -> str:
        """
        Detect conversation mode from text.
        Subclasses can override for role-specific keywords.
        """
        text_lower = text.lower()
        cfg        = self.config

        # Phrase check first (multi-word)
        for phrase in cfg.support_phrases:
            if phrase in text_lower:
                return "support"
        for phrase in cfg.sales_phrases:
            if phrase in text_lower:
                return "sales"

        # Word check
        words = set(text_lower.split())
        if words & cfg.support_words:
            return "support"
        if words & cfg.sales_words:
            return "sales"

        return "general"

    def _detect_language(self, text: str) -> str:
        """Detect Hindi vs English."""
        hindi_indicators = {
            "namaste", "namaskar", "shukriya", "dhanyawad",
            "mera", "meri", "mere", "aap", "apka", "apki",
            "hai", "hain", "tha", "thi", "main", "hum",
            "kya", "kaise", "kab", "kyun", "nahi", "nhi",
            "acha", "theek", "kar", "karo", "ho", "hoga",
            "se", "ko", "ka", "ki", "ke", "thanda", "madad",
            "ji", "bhi", "aur", "agar", "toh", "woh",
        }
        words = set(text.lower().split())
        if words & hindi_indicators:
            return "hindi"
        return "english"

    def _get_memory_context(self, query: str) -> tuple[str, int]:
        """Retrieve relevant past episodes for context."""
        try:
            memories = self.episodic.search(query, top_k=2)
            if not memories:
                return "", 0
            lines = [f"Past relevant interactions ({len(memories)}):"]
            for m in memories:
                lines.append(f"- {m['content'][:150]}")
            return "\n".join(lines), len(memories)
        except Exception:
            return "", 0

    # ── Public API ───────────────────────────────────────────

    def chat(self, user_message: str, mode: str = "auto", context: str = "") -> dict:
        """
        Send message, get response.
        Same interface for ALL roles — swappable.
        """
        self.turn_count += 1
        lang = self._detect_language(user_message)

        if mode == "auto":
            mode = self._detect_mode(user_message)

        # Memory on first turn
        memory_context, memory_count = "", 0
        if self.turn_count == 1:
            memory_context, memory_count = self._get_memory_context(user_message)

        full_context = "\n\n".join(filter(None, [context, memory_context]))
        system_prompt = self._build_system_prompt(mode, full_context)

        self.history.append(HumanMessage(content=user_message))
        messages = [SystemMessage(content=system_prompt)] + self.history

        try:
            response = self.llm.invoke(messages)
            reply    = response.content
            self.history.append(response)
        except Exception as e:
            reply = (
                "Aapki baat samajh gayi, lekin abhi ek technical issue aa rahi hai."
                if lang == "hindi"
                else "I understand, but facing a technical issue right now."
            )
            print(f"  [{self.config.name.upper()}] LLM error: {e}")

        return {
            "response": reply,
            "language": lang,
            "mode":     mode,
            "persona":  f"{self.config.name} — {self.config.company}",
            "role":     self.config.role,
            "memory":   memory_count,
        }

    def greet(self) -> str:
        """Opening greeting."""
        lang          = self.config.language_preference
        system_prompt = self._build_system_prompt("greeting")
        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Greet the customer warmly as {self.config.name}."),
            ])
            return response.content
        except Exception:
            return (
                self.config.hindi_greeting
                or f"Namaste! Main {self.config.name} hoon, {self.config.role}."
            )

    def end_session(self, score: float = 0.9) -> None:
        """Save session to memory on conversation end."""
        if not self.history:
            return
        convo = " | ".join([
            m.content[:80] for m in self.history if hasattr(m, "content")
        ])
        try:
            self.episodic.store(
                session_id   = self.session_id,
                raw_input    = convo[:300],
                synthesis    = f"{self.config.role} — {self.turn_count} turns",
                what_worked  = f"Mode detection across {self.turn_count} turns",
                what_failed  = "",
                score        = score,
                problem_type = self.config.industry.lower(),
            )
            self.semantic.store_session(
                session_id   = self.session_id,
                raw_input    = convo[:300],
                problem_type = self.config.industry.lower(),
                final_score  = score,
                what_worked  = f"{self.turn_count} turns",
                what_failed  = "",
            )
            print(f"  [{self.config.name.upper()}] Session saved ✓")
        except Exception as e:
            print(f"  [{self.config.name.upper()}] Memory save failed: {e}")

    def reset(self) -> None:
        """Clear history, save to memory first."""
        self.end_session()
        self.history    = []
        self.turn_count = 0
        self.session_id = str(uuid.uuid4())

    # ── Properties ───────────────────────────────────────────
    @property
    def name(self) -> str:
        return self.config.name

    @property
    def persona(self):
        """Backward compat with Aria's old .persona.name pattern."""
        return self.config