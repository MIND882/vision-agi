# nodes/direct_reason.py
# ============================================================
# DIRECT REASON NODE — Pure LLM reasoning, no tools needed.
# Called when ROUTER decides requires_tools=False.
#
# Input  : raw_input, sub_problems, execution_plan, context_summary
# Output : tool_results, reasoning_trace
# ============================================================

from langchain_core.messages import HumanMessage, SystemMessage
from graph.state import ReasoningState
from graph.llm import get_llm


REASONING_PROMPT = """You are an expert reasoning engine. 
Solve the given problem step by step with clear logic.
Be precise, accurate, and thorough.
If it's a math problem — show calculations.
If it's an explanation — be clear and structured.
If it's a comparison — cover all key differences."""


def direct_reason_node(state: ReasoningState) -> dict:
    """Pure LLM reasoning — no external tools needed."""

    raw_input    = state["raw_input"]
    sub_problems = state.get("sub_problems", [raw_input])
    context      = state.get("context_summary", "")

    print(f"  [DIRECT_REASON] Solving {len(sub_problems)} sub-problem(s) with LLM...")

    llm     = get_llm(fast=False)
    results = []

    for i, problem in enumerate(sub_problems, 1):
        user_msg = f"""Problem: {problem}

{f'Context: {context}' if context else ''}

Solve this completely and accurately."""

        messages = [
            SystemMessage(content=REASONING_PROMPT),
            HumanMessage(content=user_msg),
        ]

        try:
            response = llm.invoke(messages)
            output   = response.content
            success  = True
            print(f"  [DIRECT_REASON] Step {i}/{len(sub_problems)} solved ✓")

        except Exception as e:
            output  = f"Reasoning failed: {str(e)}"
            success = False
            print(f"  [DIRECT_REASON] Step {i} failed: {e}")

        results.append({
            "step_id":   i,
            "tool_name": "direct_reason",
            "success":   success,
            "output":    output,
            "error":     None if success else output,
        })

    return {
        "tool_results":    results,
        "reasoning_trace": [
            f"[DIRECT_REASON] Solved {len(results)} sub-problem(s) via LLM"
        ],
    }
