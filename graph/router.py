# graph/router.py
# ============================================================
# Conditional edge functions — these are the decision points
# in the graph. LangGraph calls them after a node runs and
# uses the return string to pick the next node.
#
# Each function receives the full state and returns a string
# that matches one of the keys in add_conditional_edges().
# ============================================================

from graph.state import ReasoningState
from config import cfg


def route_execution(state: ReasoningState) -> str:
    """
    ROUTER 1 — called after DECOMPOSE node.
    Decides: does this query need external tools?

    Returns:
        "execute"       → go to EXECUTE node (tools needed)
        "direct_reason" → go to DIRECT_REASON node (pure LLM)
    """
    requires_tools = state.get("requires_tools", False)

    if requires_tools:
        print(f"  [ROUTER] → EXECUTE (tools needed)")
        return "execute"
    else:
        print(f"  [ROUTER] → DIRECT_REASON (no tools needed)")
        return "direct_reason"


def route_quality(state: ReasoningState) -> str:
    """
    ROUTER 2 — called after CRITIQUE node.
    Decides: is the answer good enough to output?

    Logic:
        score >= QUALITY_THRESHOLD (0.8) → output
        score <  QUALITY_THRESHOLD       → refine (unless max loops hit)

    Returns:
        "output" → go to OUTPUT node (answer is good)
        "refine" → go to REFINE node  (answer needs work)
    """
    score       = state.get("critique_score", 0.0)
    refine_count = state.get("refine_count", 0)
    threshold   = cfg.QUALITY_THRESHOLD
    max_loops   = cfg.MAX_REFINE_LOOPS

    # Force output if we've hit the max refine loops
    # (prevents infinite loops on genuinely hard problems)
    if refine_count >= max_loops:
        print(f"  [ROUTER] → OUTPUT (max refine loops {max_loops} reached)")
        return "output"

    if score >= threshold:
        print(f"  [ROUTER] → OUTPUT (score {score:.2f} >= threshold {threshold})")
        return "output"
    else:
        print(f"  [ROUTER] → REFINE (score {score:.2f} < threshold {threshold})")
        return "refine"