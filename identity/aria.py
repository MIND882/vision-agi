# identity/aria.py
# ============================================================
# ARIA — Digital Human Entry Point
# Phase 2 Week 2 Update:
#   + EpisodicMemory wired — Aria ab past customers yaad rakhti hai
#   + SemanticMemory wired — session DB mein save hota hai
#   + session_id added — har conversation traceable hai
#   + memory_context auto-inject — relevant past injected in prompt
# ============================================================

import uuid
from identity.persona import get_persona
from identity.prompt_builder import build_system_prompt, detect_language
from graph.llm import get_llm
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from langchain_core.messages import HumanMessage, SystemMessage


class Aria:
    """
    Aria — AC Service Digital Human.
    Brain (Reasoning Core) + Soul (Identity) + Memory = Aria

    Phase 2 Week 1: Direct LLM + persona           ✅
    Phase 2 Week 2: Memory wired                   ✅ (this update)
    Phase 2 Week 3: Voice (TTS/STT)                → next
    Phase 2 Week 5: CRM tool integration           → next
    """

    def __init__(self):
        self.persona    = get_persona()
        self.llm        = get_llm(fast=False)
        self.history    = []
        self.session_id = str(uuid.uuid4())   # unique per Aria instance
        self.turn_count = 0

        # Memory systems
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()

        print(f"  [ARIA] Session started: {self.session_id[:16]}...")

    def chat(
        self,
        user_message: str,
        mode: str = "auto",
        context: str = "",
    ) -> dict:
        """
        Send a message to Aria and get her response.

        Returns dict with:
            response : Aria's reply text
            language : detected language
            mode     : mode used
            persona  : Aria's name + company
            memory   : how many past episodes retrieved
        """
        self.turn_count += 1

        # ── Detect language + mode ───────────────────────────
        lang = detect_language(user_message)
        if mode == "auto":
            mode = self._detect_mode(user_message)

        # ── Retrieve relevant memories ───────────────────────
        memory_context = ""
        memory_count   = 0
        if self.turn_count == 1:    # only on first turn — avoid noise
            try:
                memories = self.episodic.search(user_message, top_k=2)
                if memories:
                    memory_count = len(memories)
                    lines = ["Relevant past customer interactions:"]
                    for m in memories:
                        lines.append(f"- {m['content'][:150]}")
                    memory_context = "\n".join(lines)
            except Exception:
                pass    # memory failure never crashes Aria

        # ── Build system prompt ──────────────────────────────
        full_context = "\n\n".join(filter(None, [context, memory_context]))
        system_prompt = build_system_prompt(
            persona=self.persona,
            context=full_context,
            mode=mode,
        )

        # ── Add to history + call LLM ────────────────────────
        self.history.append(HumanMessage(content=user_message))
        messages = [SystemMessage(content=system_prompt)] + self.history

        try:
            response = self.llm.invoke(messages)
            reply    = response.content
            self.history.append(response)
        except Exception as e:
            reply = (
                "Aapki baat samajh gayi, lekin abhi ek technical issue aa rahi hai. "
                "Kripya thoda wait karein."
                if lang == "hindi"
                else "I understand your concern but facing a technical issue. Please wait."
            )

        return {
            "response": reply,
            "language": lang,
            "mode":     mode,
            "persona":  f"{self.persona.name} — {self.persona.company}",
            "memory":   memory_count,
        }

    def greet(self) -> str:
        """Aria's opening greeting."""
        system_prompt = build_system_prompt(
            persona=self.persona,
            mode="greeting",
        )
        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content="Greet the customer warmly as Aria."),
            ])
            return response.content
        except Exception:
            return self.persona.hindi_greeting

    def end_session(self, final_score: float = 0.9) -> None:
        """
        Save this session to memory when conversation ends.
        Call this on 'quit' command in main.py.
        """
        if not self.history:
            return

        # Build conversation summary for memory
        convo_text = " | ".join([
            msg.content[:100]
            for msg in self.history
            if hasattr(msg, "content")
        ])

        try:
            # Save to ChromaDB — so Aria recognizes similar customers next time
            self.episodic.store(
                session_id   = self.session_id,
                raw_input    = convo_text[:300],
                synthesis    = f"AC service conversation — {self.turn_count} turns",
                what_worked  = f"Mode detection + {self.turn_count} turn conversation",
                what_failed  = "",
                score        = final_score,
                problem_type = "customer_service",
            )

            # Save to PostgreSQL — structured record
            self.semantic.store_session(
                session_id   = self.session_id,
                raw_input    = convo_text[:300],
                problem_type = "customer_service",
                final_score  = final_score,
                what_worked  = f"{self.turn_count} turns completed",
                what_failed  = "",
            )
            print(f"  [ARIA] Session saved to memory ✓ ({self.turn_count} turns)")
        except Exception as e:
            print(f"  [ARIA] Memory save failed: {e}")

    def reset(self):
        """Clear history — start fresh session."""
        self.end_session()          # save before reset
        self.history    = []
        self.turn_count = 0
        self.session_id = str(uuid.uuid4())
        print(f"  [ARIA] Session reset. New session: {self.session_id[:16]}...")

    def _detect_mode(self, text: str) -> str:
        """Auto-detect conversation mode — phrase + word matching."""
        text_lower = text.lower()

        # ── Phrase check pehle (multi-word) ──────────────────────
        support_phrases = [
            "thanda nahi", "not working", "kaam nahi", "band ho",
            "cooling nahi", "problem hai", "kharab ho", "gas khatam",
        ]
        sales_phrases = [
            "amc plan", "service plan", "new ac", "install karna",
            "kitne ka", "price kya", "book karna",
        ]

        for phrase in support_phrases:
            if phrase in text_lower:
                return "support"

        for phrase in sales_phrases:
            if phrase in text_lower:
                return "sales"

        # ── Single word check baad mein ──────────────────────────
        words = set(text_lower.split())

        support_words = {
            "band", "problem", "issue", "broken", "leak", "noise",
            "error", "help", "madad", "complaint", "cooling", "repair",
            "fix", "gas", "service", "thanda", "working"
        }
        sales_words = {
            "install", "new", "price", "cost", "kitna", "quote",
            "amc", "contract", "buy", "purchase", "lena", "book",
            "appointment", "plan", "offer", "chahiye"
        }

        if words & support_words:
            return "support"
        if words & sales_words:
            return "sales"

        return "general"