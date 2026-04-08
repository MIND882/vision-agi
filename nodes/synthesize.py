# nodes/synthesize.py
# ============================================================
# SYNTHESIZE NODE — Merges all tool_results into one answer.
#
# Input  : raw_input, tool_results, sub_problems, problem_type
# Output : synthesis, reasoning_trace
# ============================================================

from langchain_core.messages import HumanMessage, SystemMessage
from graph.state import ReasoningState
from graph.llm import get_llm


SYNTHESIZE_PROMPT = """You are an expert answer synthesizer.

You receive:
1. The original user query
2. Results from multiple reasoning steps or tool calls

Your job: Combine all results into ONE clear, complete, well-structured answer.

Rules:
- Address the original query directly
- Integrate ALL relevant information from the results
- Remove duplicates and contradictions
- Structure the answer clearly (use paragraphs or bullet points as appropriate)
- If any step failed, work with what succeeded
- Be concise but complete — do not pad with filler"""


def synthesize_node(state: ReasoningState) -> dict:
    """Merge all tool_results into one coherent draft answer."""

    raw_input    = state["raw_input"]
    tool_results = state.get("tool_results", [])
    problem_type = state.get("problem_type", "reasoning")

    print(f"  [SYNTHESIZE] Merging {len(tool_results)} result(s)...")

    if not tool_results:
        return {
            "synthesis":       "No results available to synthesize.",
            "reasoning_trace": ["[SYNTHESIZE] No tool results found"],
        }

    # Build results summary for LLM
    results_text = []
    for r in tool_results:
        status = "SUCCESS" if r["success"] else "FAILED"
        results_text.append(
            f"[{status}] Step {r['step_id']} via {r['tool_name']}:\n{r['output']}"
        )

    user_message = f"""Original query: {raw_input}
Problem type: {problem_type}

Results from execution:
{'=' * 40}
{chr(10).join(results_text)}
{'=' * 40}

Synthesize these into one complete, accurate answer."""

    llm = get_llm(fast=False)
    messages = [
        SystemMessage(content=SYNTHESIZE_PROMPT),
        HumanMessage(content=user_message),
    ]

    try:
        response  = llm.invoke(messages)
        synthesis = response.content
        print(f"  [SYNTHESIZE] ✓ Draft answer ready ({len(synthesis)} chars)")
    except Exception as e:
        # Fallback — join raw outputs if LLM fails
        synthesis = "\n\n".join(
            r["output"] for r in tool_results if r["success"]
        )
        print(f"  [SYNTHESIZE] LLM failed ({e}) — using raw join fallback")

    return {
        "synthesis":       synthesis,
        "reasoning_trace": [f"[SYNTHESIZE] Merged {len(tool_results)} results"],
    }