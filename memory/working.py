# memory/working.py
# ============================================================
# WORKING MEMORY — in-context session state.
# Lives inside ReasoningState — no DB needed.
# Cleared after every session automatically.
#
# Think of it as: "what happened in THIS conversation"
# ============================================================

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WorkingMemory:
    """
    Holds everything relevant to the CURRENT reasoning session.
    Created fresh for each query in main.py.
    """
    session_id:    str
    raw_input:     str
    problem_type:  str        = ""
    complexity:    str        = ""
    turn_count:    int        = 0
    tool_calls:    list       = field(default_factory=list)
    key_facts:     list[str]  = field(default_factory=list)

    def add_tool_call(self, tool_name: str, output: str, success: bool) -> None:
        """Record a tool call that happened this session."""
        self.tool_calls.append({
            "tool":    tool_name,
            "success": success,
            "output":  output[:200],   # truncate for memory efficiency
        })

    def add_key_fact(self, fact: str) -> None:
        """Store an important fact discovered during reasoning."""
        if fact and fact not in self.key_facts:
            self.key_facts.append(fact)

    def as_context_string(self) -> str:
        """
        Format working memory as a string for LLM prompts.
        Injected into INTAKE context_summary.
        """
        if not self.key_facts and not self.tool_calls:
            return "No prior context in this session."

        lines = [f"Session context (turn {self.turn_count}):"]
        if self.key_facts:
            lines.append("Key facts found:")
            lines.extend(f"  - {f}" for f in self.key_facts[-5:])  # last 5
        if self.tool_calls:
            successful = [t for t in self.tool_calls if t["success"]]
            lines.append(f"Tools used: {len(successful)} successful calls")
        return "\n".join(lines)


def create_working_memory(session_id: str, raw_input: str) -> WorkingMemory:
    """Create a fresh working memory for a new session."""
    return WorkingMemory(session_id=session_id, raw_input=raw_input)