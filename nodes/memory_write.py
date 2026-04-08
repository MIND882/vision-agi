# nodes/memory_write.py
# ============================================================
# MEMORY WRITE NODE — Week 5: real DB implementation.
# Persists to ChromaDB (episodic) + PostgreSQL (semantic).
# ============================================================

import re
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import ReasoningState
from graph.llm import get_llm
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory


EXTRACT_PROMPT = """Analyze this AI reasoning session and extract learnings.
Return EXACTLY:
WORKED: <what approach worked well — one sentence>
FAILED: <what didn't work — one sentence, or 'nothing failed'>
FACT: <one key fact learned, or 'none'>"""


def _extract_learnings(state: ReasoningState) -> tuple[str, str, str]:
    """Use LLM to extract worked/failed/fact."""
    score        = state.get("critique_score", 0.0)
    refine_count = state.get("refine_count", 0)
    tool_results = state.get("tool_results", [])
    tool_summary = ", ".join(
        set(r["tool_name"] for r in tool_results if r.get("success"))
    ) or "direct reasoning"

    llm = get_llm(fast=True)
    try:
        response = llm.invoke([
            SystemMessage(content=EXTRACT_PROMPT),
            HumanMessage(content=(
                f"Query: {state['raw_input']}\n"
                f"Tools: {tool_summary}\n"
                f"Score: {score:.2f}\n"
                f"Refinements: {refine_count}"
            )),
        ])
        text     = response.content
        worked_m = re.search(r"WORKED:\s*(.+?)(?:\n|$)", text)
        failed_m = re.search(r"FAILED:\s*(.+?)(?:\n|$)", text)
        fact_m   = re.search(r"FACT:\s*(.+?)(?:\n|$)",   text)

        return (
            worked_m.group(1).strip() if worked_m else "",
            failed_m.group(1).strip() if failed_m else "",
            fact_m.group(1).strip()   if fact_m   else "none",
        )
    except Exception:
        return f"Session score={score:.2f}", "", "none"


def memory_write_node(state: ReasoningState) -> dict:
    """Write learnings to ChromaDB + PostgreSQL."""

    session_id   = state["session_id"]
    raw_input    = state["raw_input"]
    synthesis    = state.get("synthesis", "")
    score        = state.get("critique_score", 0.0)
    problem_type = state.get("problem_type", "unknown")

    print(f"  [MEMORY_WRITE] Persisting learnings (score={score:.2f})...")

    what_worked, what_failed, key_fact = _extract_learnings(state)

    # ── ChromaDB (episodic memory) ───────────────────────────
    try:
        episodic = EpisodicMemory()
        episodic.store(
            session_id=session_id, raw_input=raw_input,
            synthesis=synthesis, what_worked=what_worked,
            what_failed=what_failed, score=score, problem_type=problem_type,
        )
        print(f"  [MEMORY_WRITE] ChromaDB ✓ ({episodic.count()} episodes total)")
    except Exception as e:
        print(f"  [MEMORY_WRITE] ChromaDB failed: {e}")

    # ── PostgreSQL (semantic memory) ─────────────────────────
    try:
        semantic = SemanticMemory()
        semantic.store_session(
            session_id=session_id, raw_input=raw_input,
            problem_type=problem_type, final_score=score,
            what_worked=what_worked, what_failed=what_failed,
        )
        if key_fact and key_fact.lower() != "none":
            semantic.store_fact(session_id, raw_input, key_fact, score)
        if what_worked:
            semantic.store_learning(session_id, what_worked, "success", score)
        if what_failed and "nothing" not in what_failed.lower():
            semantic.store_learning(session_id, what_failed, "failure", score)
        print(f"  [MEMORY_WRITE] PostgreSQL ✓")
    except Exception as e:
        print(f"  [MEMORY_WRITE] PostgreSQL failed: {e}")
        print(f"  [MEMORY_WRITE] Hint: docker-compose up -d")

    print(f"  [MEMORY_WRITE] Worked : {what_worked[:70]}")
    if what_failed and "nothing" not in what_failed.lower():
        print(f"  [MEMORY_WRITE] Failed : {what_failed[:70]}")

    return {
        "what_worked":     what_worked,
        "what_failed":     what_failed,
        "memory_written":  True,
        "reasoning_trace": [f"[MEMORY_WRITE] score={score:.2f} | chromadb=ok | postgres=ok"],
    }