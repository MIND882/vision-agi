# nodes/synthesize.py
# ============================================================
# SYNTHESIZE NODE — Merges all tool_results into one answer.
#
# Input  : raw_input, tool_results, sub_problems, problem_type
# Output : synthesis, reasoning_trace
#
# FIXES in this version:
#   - Hard ban on "without access to real-time data"
#   - Forces specific numbers/facts from tool results
#   - Shorter, more direct answers (no filler)
#   - Tool results explicitly highlighted for LLM
# ============================================================

from langchain_core.messages import HumanMessage, SystemMessage
from graph.state import ReasoningState
from graph.llm import get_llm


SYNTHESIZE_PROMPT = """You are an expert answer synthesizer for an AI reasoning system.

You receive tool results and must produce ONE clear, specific, complete answer.

=== STRICT OUTPUT RULES ===

DO:
✓ Use SPECIFIC numbers, percentages, company names from tool results
✓ Answer the original query DIRECTLY in the first sentence
✓ Structure with short paragraphs or bullet points
✓ Cite concrete data: "India's IT exports = $194B, US share = 62%..."
✓ If tool gave real data → USE IT specifically in your answer
✓ Be concise — say more with fewer words

DO NOT (these phrases are BANNED — never write them):
✗ "without access to real-time data"
✗ "based on past experience"
✗ "reliability has been verified"
✗ "it is challenging to provide"
✗ "I don't have access to"
✗ "as an AI language model"
✗ "based on the information provided"
✗ Any meta-commentary about HOW you found the answer

=== ANSWER FORMAT ===
- Start with direct answer to the query (1-2 sentences)
- Support with specific data from tool results
- End with key insight or recommendation
- Max 300 words for simple queries, 500 for complex
- No filler sentences — every sentence must add value

If a tool failed or returned no data — work with what succeeded.
Never apologize for missing data. Just answer with what you have."""


def synthesize_node(state: ReasoningState) -> dict:
    """Merge all tool_results into one coherent, specific draft answer."""

    raw_input    = state["raw_input"]
    tool_results = state.get("tool_results", [])
    problem_type = state.get("problem_type", "reasoning")

    print(f"  [SYNTHESIZE] Merging {len(tool_results)} result(s)...")

    if not tool_results:
        return {
            "synthesis":       "No results available to synthesize.",
            "reasoning_trace": ["[SYNTHESIZE] No tool results — empty synthesis"],
        }

    # ── Build rich results context for LLM ───────────────────
    results_sections = []
    successful_count = 0

    for r in tool_results:
        status = "✓ SUCCESS" if r["success"] else "✗ FAILED"
        tool   = r.get("tool_name", "unknown")
        output = r.get("output", "No output")

        if r["success"]:
            successful_count += 1
            # Trim very long outputs but keep the meat
            if len(output) > 1500:
                output = output[:1500] + "\n... [truncated]"

        results_sections.append(
            f"[{status}] Step {r['step_id']} — Tool: {tool}\n"
            f"{'─' * 40}\n"
            f"{output}\n"
        )

    results_block = "\n".join(results_sections)

    # ── Contextual instruction based on problem type ──────────
    type_guidance = {
        "factual":   "Give the direct fact. One sentence if possible.",
        "analysis":  "Use specific numbers and data. Show cause → effect chain.",
        "coding":    "Show the solution with code. Explain key decisions briefly.",
        "math":      "Show the calculation result clearly with units.",
        "research":  "Summarize key findings with sources/data mentioned.",
        "reasoning": "Walk through the logic clearly. State your conclusion.",
    }.get(problem_type, "Answer directly using the data provided.")

    user_message = f"""Original query: {raw_input}
Problem type: {problem_type}
Type guidance: {type_guidance}
Successful tool results: {successful_count}/{len(tool_results)}

=== TOOL RESULTS ===
{results_block}
=== END RESULTS ===

Now synthesize these into ONE complete, specific answer.
Use the actual data from the results above — numbers, facts, specifics.
Start with the direct answer to the query."""

    llm = get_llm(fast=False)
    messages = [
        SystemMessage(content=SYNTHESIZE_PROMPT),
        HumanMessage(content=user_message),
    ]

    try:
        response  = llm.invoke(messages)
        synthesis = response.content

        # ── Post-process: catch banned phrases ────────────────
        # If LLM still used banned phrases despite instructions,
        # flag it so critique node scores it lower
        banned_phrases = [
            "without access to real-time data",
            "it is challenging to provide",
            "as an AI language model",
            "based on past experience",
            "reliability has been verified",
        ]
        found_banned = [p for p in banned_phrases if p.lower() in synthesis.lower()]
        if found_banned:
            print(f"  [SYNTHESIZE] ⚠ Banned phrase detected: {found_banned[0][:40]}")
            # Append correction note so critique fails it
            synthesis += "\n[QUALITY_FLAG: Generic language detected — needs refinement]"

        print(f"  [SYNTHESIZE] ✓ Draft answer ready ({len(synthesis)} chars)")

    except Exception as e:
        # Fallback — join raw outputs if LLM fails
        synthesis = "\n\n".join(
            r["output"] for r in tool_results if r.get("success")
        ) or "Synthesis failed — no successful tool results."
        print(f"  [SYNTHESIZE] LLM failed ({e}) — using raw join fallback")

    return {
        "synthesis":       synthesis,
        "reasoning_trace": [
            f"[SYNTHESIZE] Merged {len(tool_results)} results "
            f"({successful_count} successful)"
        ],
    }