# graph/state.py
# ============================================================
# ReasoningState — the single source of truth for the entire graph.
# Every node reads from this and writes back to this.
# Think of it as the "working memory" of one reasoning session.
#
# RULE: if data needs to travel between two nodes → it lives here.
# RULE: no node imports from another node — only from state.
# ============================================================

from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages
import operator

# ── Sub-types used inside the state ─────────────────────────

class ExecutionStep(TypedDict):
    """One step inside the execution plan built by DECOMPOSE node."""
    step_id:      int        # 1, 2, 3 ... ordering
    description:  str        # what this step does
    tool_needed:  bool       # True → goes to EXECUTE node, False → DIRECT_REASON
    tool_name:    Optional[str]  # "web_search" | "calculator" | "code_executor" | "db_query" | None
    priority:     int        # 1 = highest, used to sort execution order
    depends_on:   list[int]  # step_ids that must complete before this one

class ToolResult(TypedDict):
    """Result from one tool call or one direct reasoning step."""
    step_id:    int          # matches ExecutionStep.step_id
    tool_name:  str          # which tool ran (or "direct_reason")
    success:    bool         # did it succeed?
    output:     str          # the actual result content
    error:      Optional[str]  # error message if success=False

class Memory(TypedDict):
    """One memory unit retrieved from ChromaDB or PostgreSQL."""
    memory_id:   str         # unique ID from the DB
    source:      str         # "episodic" | "semantic"
    content:     str         # the actual memory text
    relevance:   float       # cosine similarity score 0.0–1.0
    created_at:  str         # ISO timestamp

# ── The main state ───────────────────────────────────────────
class ReasoningState(TypedDict):
    """
    Central state passed through every node in the graph.
    LangGraph passes this dict from node to node, each node
    reads what it needs and returns ONLY the keys it changed.

    Annotated fields use reducer functions:
      - add_messages → appends new messages to the list
      - operator.add  → appends new items to the list
    Plain fields → last-write-wins (node just returns new value)
    """

    # --INPUT---------------------------
    #  SET ONCE BY MAIN.PY BEFORE THE GRAPH STARTS. NEVER MUTATED
    raw_input: str 
    # The original user query exactly as received.
    # Example: "What is the GDP of India in 2024 and how does it compare to China?"
    
    session_id: str
     # Unique ID for this reasoning session. Used by memory nodes
    # to group related interactions. Format: UUID4 string.

    #  --- CLASSIFICATION (SET BY INTAKE NODE)---------
    problem_type: str
    # One of: "reasoning" | "coding" | "analysis" | "factual" | "multi_step" | "unknown"
    # INTAKE node classifies this. ROUTER uses it to decide path.
    complexity: str
    # One of: "simple" | "moderate" | "complex"
    # Drives how many sub-problems DECOMPOSE creates.

    requires_tools: bool
    # True if INTAKE determines external tools are needed.
    # ROUTER reads this to decide EXECUTE vs DIRECT_REASON path.

    language: str
    # Detected language of the input. Default: "en"
    # Future: multilingual Digital Human support.

    #  --- MEMORY (SET BY intake node via memory retrieval) --------

    retrieved_memories: Annotated[list[Memory], operator.add]
     # Relevant past memories fetched from ChromaDB + PostgreSQL.
    # operator.add means each node can append more memories
    # without overwriting what INTAKE already fetched.

    context_summary: str
       # A short summary of retrieved_memories for LLM consumption.
    # INTAKE node generates this to avoid stuffing raw memories
    # into every prompt. Keeps token usage controlled.

 # ── PLANNING (set by DECOMPOSE node) ────────────────────

    sub_problems:     Annotated[list[str], operator.add]
    # List of sub-questions/tasks the problem was broken into.
    # Example: ["What is India's GDP in 2024?",
    #            "What is China's GDP in 2024?",
    #            "Calculate the percentage difference"]

    execution_plan:   list[ExecutionStep]
    # Ordered list of steps to execute. Built by DECOMPOSE.
    # EXECUTE node iterates this list.
    # Last-write-wins — DECOMPOSE sets the full plan at once.


    # ── EXECUTION (set by EXECUTE / DIRECT_REASON nodes) ────

    tool_results:     Annotated[list[ToolResult], operator.add]
    # Accumulates results as each step runs.
    # operator.add = EXECUTE appends one result at a time,
    # safe for parallel execution in future versions.

    current_step_id:  int
    # Tracks which ExecutionStep is currently running.
    # EXECUTE node updates this as it iterates the plan.


    # ── SYNTHESIS (set by SYNTHESIZE node) ──────────────────

    synthesis:        str
    # A single coherent draft response merging all tool_results.
    # Input to CRITIQUE node.
    # Last-write-wins — SYNTHESIZE (or REFINE) sets this fresh.


    # ── QUALITY LOOP (set by CRITIQUE and REFINE nodes) ─────

    critique_score:   float
    # Self-evaluation score from CRITIQUE node. Range: 0.0 to 1.0.
    # QUALITY ROUTER checks: score >= QUALITY_THRESHOLD → OUTPUT
    #                         score <  QUALITY_THRESHOLD → REFINE

    critique_notes:   str
    # Detailed feedback from CRITIQUE explaining WHY the score
    # is what it is. What's missing, wrong, or incomplete.
    # REFINE node uses this to know exactly what to fix.

    refine_count:     int
    # How many times REFINE has run this session.
    # QUALITY ROUTER uses this to enforce MAX_REFINE_LOOPS.
    # Prevents infinite loops on genuinely hard problems.


    # ── CONVERSATION (for multi-turn future support) ─────────

    messages: Annotated[list, add_messages]
    # Full conversation history using LangGraph's add_messages reducer.
    # add_messages handles deduplication + proper message ordering.
    # Currently used by INTAKE and OUTPUT nodes.


    # ── OUTPUT (set by OUTPUT node) ──────────────────────────

    final_output:     str
    # The polished, user-facing answer. Set by OUTPUT node.
    # This is what main.py displays to the user.

    confidence:       float
    # Final confidence in the answer. Derived from critique_score.
    # Range: 0.0 to 1.0. Displayed alongside final_output.

    reasoning_trace:  list[str]
    # Ordered list of reasoning steps taken — for transparency.
    # Example: ["Classified as: multi_step",
    #            "Decomposed into 3 sub-problems",
    #            "Used web_search for steps 1 and 2",
    #            "Critique score: 0.87 — passed"]
    # Useful for debugging and future explainability features.

    sources_used:     list[str]
    # URLs or DB references used in the answer.
    # Collected from tool_results by OUTPUT node.


    # ── LEARNING (set by MEMORY_WRITE node) ─────────────────

    what_worked:      str
    # Patterns/approaches that led to high critique_score.
    # Extracted by MEMORY_WRITE and persisted to ChromaDB.

    what_failed:      str
    # Approaches that got low critique scores or tool errors.
    # Persisted to ChromaDB so the system avoids these next time.

    memory_written:   bool
    # Flag set to True once MEMORY_WRITE has persisted learnings.
    # Prevents double-writes if the graph is retried.

