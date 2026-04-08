# graph/builder.py
# ============================================================
# LangGraph graph construction — ALL nodes now REAL.
# Week 2-4 complete: every node has real LLM implementation.
# ============================================================

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import ReasoningState
from graph.router import route_execution, route_quality

# ── All real nodes ───────────────────────────────────────────
from nodes.intake        import intake_node
from nodes.decompose     import decompose_node
from nodes.execute       import execute_node
from nodes.direct_reason import direct_reason_node
from nodes.synthesize    import synthesize_node
from nodes.critique      import critique_node
from nodes.refine        import refine_node
from nodes.output        import output_node
from nodes.memory_write  import memory_write_node


def build_graph(use_memory: bool = False) -> StateGraph:
    """Assembles and compiles the full Reasoning Core graph."""

    graph = StateGraph(ReasoningState)

    # Register ALL real nodes
    graph.add_node("intake",        intake_node)
    graph.add_node("decompose",     decompose_node)
    graph.add_node("execute",       execute_node)
    graph.add_node("direct_reason", direct_reason_node)
    graph.add_node("synthesize",    synthesize_node)
    graph.add_node("critique",      critique_node)
    graph.add_node("refine",        refine_node)
    graph.add_node("output",        output_node)
    graph.add_node("memory_write",  memory_write_node)

    # Edges
    graph.add_edge(START,    "intake")
    graph.add_edge("intake", "decompose")

    graph.add_conditional_edges(
        "decompose", route_execution,
        {"execute": "execute", "direct_reason": "direct_reason"}
    )

    graph.add_edge("execute",       "synthesize")
    graph.add_edge("direct_reason", "synthesize")
    graph.add_edge("synthesize",    "critique")

    graph.add_conditional_edges(
        "critique", route_quality,
        {"output": "output", "refine": "refine"}
    )

    graph.add_edge("refine",       "synthesize")
    graph.add_edge("output",       "memory_write")
    graph.add_edge("memory_write", END)

    checkpointer = MemorySaver() if use_memory else None
    compiled = graph.compile(checkpointer=checkpointer)
    print("✓ Reasoning Core graph compiled successfully")
    return compiled