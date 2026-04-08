# nodes/intake.py  (Week 5 update — real memory retrieval added)
# Changes from Week 2:
#   _retrieve_memories() now calls EpisodicMemory.search() for real

import json
import re
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import ReasoningState
from graph.llm import get_llm
from memory.episodic import EpisodicMemory
from config import cfg


CLASSIFICATION_PROMPT = """You are an expert query classifier for an AI reasoning system.

Analyze the user's query and return a JSON object with EXACTLY these fields:

{
  "problem_type": "<one of: reasoning | coding | analysis | factual | multi_step | creative | unknown>",
  "complexity": "<one of: simple | moderate | complex>",
  "requires_tools": <true | false>,
  "suggested_tools": ["<tool names if requires_tools is true, else empty list>"],
  "language": "<detected language code, e.g. en | hi | es>",
  "reasoning": "<one sentence explaining your classification>"
}

Tool names available: web_search, calculator, code_executor, db_query

IMPORTANT: Return ONLY the JSON object. No explanation. No markdown. No code blocks."""


def _clean_input(raw: str) -> str:
    return " ".join(raw.strip().split())


def _parse_classification(llm_response: str) -> dict:
    try:
        cleaned = llm_response.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned)
        cleaned = re.sub(r"^```\s*",     "", cleaned)
        cleaned = re.sub(r"\s*```$",     "", cleaned)
        data = json.loads(cleaned)
        return {
            "problem_type":    data.get("problem_type", "reasoning"),
            "complexity":      data.get("complexity", "moderate"),
            "requires_tools":  bool(data.get("requires_tools", False)),
            "suggested_tools": data.get("suggested_tools", []),
            "language":        data.get("language", "en"),
            "reasoning":       data.get("reasoning", ""),
        }
    except Exception as e:
        print(f"  [INTAKE] Warning: JSON parse failed ({e}) — using defaults")
        return {
            "problem_type": "reasoning", "complexity": "moderate",
            "requires_tools": False, "suggested_tools": [],
            "language": "en", "reasoning": "Fallback",
        }


def _retrieve_memories(session_id: str, query: str) -> tuple[list, str]:
    """
    Week 5: Real ChromaDB episodic memory retrieval.
    """
    try:
        episodic  = EpisodicMemory()
        memories  = episodic.search(query, top_k=3)

        if not memories:
            return [], "No relevant past experiences found."

        # Build context summary for LLM prompts
        lines = [f"Relevant past experiences ({len(memories)} found):"]
        for m in memories:
            lines.append(
                f"- [{m['source']}] relevance={m['relevance']:.2f}: {m['content'][:150]}"
            )
        context_summary = "\n".join(lines)
        print(f"  [INTAKE] Memory: {len(memories)} relevant episode(s) retrieved")
        return memories, context_summary

    except Exception as e:
        print(f"  [INTAKE] Memory retrieval failed: {e}")
        return [], "Memory unavailable."


def intake_node(state: ReasoningState) -> dict:
    raw     = state["raw_input"]
    session = state["session_id"]
    cleaned = _clean_input(raw)

    print(f"  [INTAKE] Input: '{cleaned[:70]}{'...' if len(cleaned) > 70 else ''}'")

    # ── LLM Classification ───────────────────────────────────
    llm = get_llm(fast=True)
    messages = [
        SystemMessage(content=CLASSIFICATION_PROMPT),
        HumanMessage(content=f"Classify this query: {cleaned}"),
    ]
    print(f"  [INTAKE] Classifying with {cfg.LLM_PROVIDER}...")

    try:
        response       = llm.invoke(messages)
        classification = _parse_classification(response.content)
    except Exception as e:
        print(f"  [INTAKE] LLM call failed: {e} — using fallback")
        classification = {
            "problem_type": "reasoning", "complexity": "moderate",
            "requires_tools": False, "suggested_tools": [],
            "language": "en", "reasoning": f"LLM unavailable: {str(e)[:50]}",
        }

    # ── Memory Retrieval ─────────────────────────────────────
    memories, context_summary = _retrieve_memories(session, cleaned)

    trace_entry = (
        f"[INTAKE] type={classification['problem_type']} | "
        f"complexity={classification['complexity']} | "
        f"tools={classification['requires_tools']} | "
        f"memories={len(memories)}"
    )
    print(f"  [INTAKE] → type={classification['problem_type']} | "
          f"complexity={classification['complexity']} | "
          f"tools={classification['requires_tools']}")

    return {
        "problem_type":       classification["problem_type"],
        "complexity":         classification["complexity"],
        "requires_tools":     classification["requires_tools"],
        "language":           classification["language"],
        "retrieved_memories": memories,
        "context_summary":    context_summary,
        "reasoning_trace":    [trace_entry],
    }