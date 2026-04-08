# nodes/refine.py
# ============================================================
# REFINE NODE — Fixes weak answers using critique_notes.
# Called when critique_score < QUALITY_THRESHOLD.
#
# Input  : raw_input, synthesis, critique_notes, refine_count
# Output : synthesis (improved), refine_count, reasoning_trace
# ============================================================

from langchain_core.messages import HumanMessage, SystemMessage
from graph.state import ReasoningState
from graph.llm import get_llm


REFINE_PROMPT = """You are an expert answer refiner.

You receive:
1. The original query
2. A draft answer that has quality issues
3. Specific critique notes explaining what's wrong

Your job: Produce an IMPROVED version of the answer that fixes the issues.

Rules:
- Fix EXACTLY what the critique notes say
- Keep what was already good in the original
- Do NOT add unnecessary padding
- Return ONLY the improved answer — no preamble"""


def refine_node(state: ReasoningState) -> dict:
    """Refine the synthesis based on critique feedback."""

    raw_input     = state["raw_input"]
    synthesis     = state.get("synthesis", "")
    critique_notes = state.get("critique_notes", "")
    refine_count  = state.get("refine_count", 0) + 1

    print(f"  [REFINE] Improvement attempt {refine_count}...")
    print(f"  [REFINE] Fixing: {critique_notes[:80]}")

    user_message = f"""Original query: {raw_input}

Draft answer (needs improvement):
{'-' * 40}
{synthesis}
{'-' * 40}

Quality issues to fix:
{critique_notes}

Write the improved answer."""

    llm = get_llm(fast=False)
    messages = [
        SystemMessage(content=REFINE_PROMPT),
        HumanMessage(content=user_message),
    ]

    try:
        response = llm.invoke(messages)
        improved = response.content
        print(f"  [REFINE] ✓ Answer improved ({len(improved)} chars)")
    except Exception as e:
        improved = synthesis   # keep original if refinement fails
        print(f"  [REFINE] LLM failed ({e}) — keeping original synthesis")

    return {
        "synthesis":       improved,
        "refine_count":    refine_count,
        "reasoning_trace": [f"[REFINE] Attempt {refine_count} complete"],
    }