# nodes/output.py
# ============================================================
# OUTPUT NODE — Final answer formatting.
# Polishes synthesis into user-facing response.
#
# Input  : synthesis, critique_score, tool_results, reasoning_trace
# Output : final_output, confidence, sources_used, reasoning_trace
# ============================================================

from graph.state import ReasoningState


def output_node(state: ReasoningState) -> dict:
    """Format the final answer for the user."""

    synthesis     = state.get("synthesis", "No answer generated.")
    critique_score = state.get("critique_score", 0.0)
    tool_results  = state.get("tool_results", [])
    problem_type  = state.get("problem_type", "unknown")
    refine_count  = state.get("refine_count", 0)

    print(f"  [OUTPUT] Formatting final answer...")

    # Extract sources from web_search results
    sources = []
    for r in tool_results:
        if r.get("tool_name") == "web_search" and r.get("success"):
            # Pull URLs from web search output
            import re
            urls = re.findall(r"Source:\s*(https?://\S+)", r.get("output", ""))
            sources.extend(urls)

    # Build refinement note if answer was refined
    refine_note = ""
    if refine_count > 0:
        refine_note = f"\n[Answer refined {refine_count}x to meet quality threshold]"

    final_output = synthesis.strip() + refine_note

    print(f"  [OUTPUT] ✓ Ready | confidence={critique_score:.0%} | "
          f"sources={len(sources)} | refined={refine_count}x")

    return {
        "final_output":    final_output,
        "confidence":      critique_score,
        "sources_used":    sources,
        "reasoning_trace": [
            f"[OUTPUT] Delivered | type={problem_type} | "
            f"confidence={critique_score:.0%} | sources={len(sources)}"
        ],
    }