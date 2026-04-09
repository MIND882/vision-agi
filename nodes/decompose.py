# nodes/decompose.py
# ============================================================
# DECOMPOSE NODE — Second node in the graph.
#
# Responsibilities:
#   1. Break the problem into sub-problems
#   2. Build a structured execution_plan (list of steps)
#   3. Each step knows: what to do, which tool, priority
#
# FIXES in this version:
#   - db_query REMOVED from available tools (it's a stub)
#   - calculator gets REAL contextual formulas, not '25*.01'
#   - Strict tool list enforced in prompt
#   - synthesize rules injected at plan time
# ============================================================

import json
import re
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import ReasoningState
from graph.llm import get_llm
from config import cfg


# ── System prompt ─────────────────────────────────────────────
DECOMPOSE_PROMPT = """You are a strategic problem decomposition engine for an AI reasoning system.

You receive a query along with its classification and must break it into clear execution steps.

Return a JSON object with EXACTLY this structure:
{
  "sub_problems": [
    "sub-problem 1 as a clear question or task",
    "sub-problem 2 as a clear question or task"
  ],
  "execution_plan": [
    {
      "step_id": 1,
      "description": "What this step does",
      "tool_needed": false,
      "tool_name": null,
      "tool_input": null,
      "priority": 1,
      "depends_on": []
    },
    {
      "step_id": 2,
      "description": "What this step does",
      "tool_needed": true,
      "tool_name": "web_search",
      "tool_input": "specific search query here",
      "priority": 2,
      "depends_on": [1]
    }
  ]
}

=== AVAILABLE TOOLS (ONLY THESE — NOTHING ELSE) ===
- web_search     : Search internet for current data, news, facts, trends
                   tool_input = specific search query string (max 80 chars)

- calculator     : Math calculations with REAL, CONTEXTUAL numbers
                   tool_input = valid Python math expression
                   GOOD: "0.25 * 150_000_000_000"  (25% of India IT exports $150B)
                   GOOD: "1200 * 0.18"              (GST on Rs 1200)
                   BAD:  "25*.01"                   (meaningless, no context)
                   BAD:  "x * y"                    (variables not allowed)
                   RULE: Only use calculator when you have REAL numbers to calculate.
                         If you don't know the actual numbers, use web_search first
                         to find them, then calculate in a later step.

- code_executor  : Run Python code for data processing, analysis, algorithms
                   tool_input = complete Python code as a string

- llm            : Pure reasoning — no tool needed, LLM thinks directly
                   tool_input = null

=== RULES ===
1. simple   complexity → 1-2 steps max
2. moderate complexity → 2-4 steps max  
3. complex  complexity → 4-6 steps max
4. If requires_tools=false → ALL steps tool_needed=false, tool_name=null
5. If requires_tools=true  → at least one step tool_needed=true
6. NEVER use: db_query, database, sql, postgres, internal_db, or any unlisted tool
7. depends_on = list of step_ids that must complete before this step
8. priority 1 = highest (run first)
9. tool_input MUST be specific and usable — not vague or generic
10. For calculator: use REAL domain numbers (look them up mentally or search first)

=== SYNTHESIS GUIDANCE ===
When building the plan, ensure the final LLM step will:
- Use specific numbers and data from tool results
- Never say "without access to real-time data" (tools provide it)
- Never say "based on past experience"
- Give concrete, specific, actionable answer

Return ONLY the JSON. No explanation. No markdown. No code blocks."""


def _parse_plan(llm_response: str, raw_input: str, requires_tools: bool) -> dict:
    """
    Safely parse LLM JSON response.
    Falls back to single-step plan if parsing fails.
    Also sanitizes tool names — rejects any not in ALLOWED_TOOLS.
    """
    ALLOWED_TOOLS = {"web_search", "calculator", "code_executor", "llm", None}

    try:
        cleaned = llm_response.strip()
        # Strip markdown code fences if present
        cleaned = re.sub(r"^```json\s*", "", cleaned)
        cleaned = re.sub(r"^```\s*",     "", cleaned)
        cleaned = re.sub(r"\s*```$",     "", cleaned)

        data = json.loads(cleaned)

        plan = []
        for step in data.get("execution_plan", []):
            tool_name = step.get("tool_name", None)

            # ── ENFORCE tool whitelist ────────────────────────
            if tool_name not in ALLOWED_TOOLS:
                print(f"  [DECOMPOSE] Rejected unknown tool '{tool_name}' → switching to LLM")
                tool_name = None
                step["tool_needed"] = False

            # ── Reject vague calculator inputs ────────────────
            tool_input = step.get("tool_input", None)
            if tool_name == "calculator" and tool_input:
                # Reject inputs with no real numbers (e.g. "25*.01" with no context)
                has_real_number = bool(re.search(r'\d{3,}', str(tool_input)))
                is_too_short = len(str(tool_input).replace(" ", "")) < 5
                if not has_real_number or is_too_short:
                    print(f"  [DECOMPOSE] Rejected vague calculator input '{tool_input}' → LLM")
                    tool_name  = None
                    tool_input = None
                    step["tool_needed"] = False

            plan.append({
                "step_id":     int(step.get("step_id", 1)),
                "description": str(step.get("description", "")),
                "tool_needed": bool(step.get("tool_needed", False)),
                "tool_name":   tool_name,
                "tool_input":  tool_input,
                "priority":    int(step.get("priority", 1)),
                "depends_on":  list(step.get("depends_on", [])),
            })

        sub_problems = [str(p) for p in data.get("sub_problems", [raw_input])]

        return {
            "sub_problems":   sub_problems if sub_problems else [raw_input],
            "execution_plan": plan if plan else _fallback_plan(raw_input, requires_tools),
        }

    except (json.JSONDecodeError, Exception) as e:
        print(f"  [DECOMPOSE] Warning: JSON parse failed ({e}) — using fallback")
        return {
            "sub_problems":   [raw_input],
            "execution_plan": _fallback_plan(raw_input, requires_tools),
        }


def _fallback_plan(description: str, tool_needed: bool) -> list:
    """Single-step fallback plan when LLM parse fails."""
    return [{
        "step_id":     1,
        "description": description,
        "tool_needed": False,   # safe default — no unknown tool
        "tool_name":   None,
        "tool_input":  None,
        "priority":    1,
        "depends_on":  [],
    }]


# ── Main node function ────────────────────────────────────────

def decompose_node(state: ReasoningState) -> dict:
    """
    DECOMPOSE node — builds structured execution plan using LLM.
    Uses MAIN model because plan quality impacts everything downstream.
    """
    raw_input      = state["raw_input"]
    problem_type   = state.get("problem_type",   "reasoning")
    complexity     = state.get("complexity",     "moderate")
    requires_tools = state.get("requires_tools",  False)
    context        = state.get("context_summary", "")

    print(f"  [DECOMPOSE] Planning for type={problem_type} | "
          f"complexity={complexity} | tools={requires_tools}")

    llm = get_llm(fast=False)   # main model — planning quality matters

    user_message = f"""Query: {raw_input}

Classification:
- problem_type: {problem_type}
- complexity: {complexity}
- requires_tools: {requires_tools}
- context: {context if context else 'No prior context'}

Build the execution plan. Remember:
- Only use tools from the allowed list
- calculator needs REAL numbers with context
- web_search tool_input must be a specific, focused query
- Final synthesis step must produce specific, data-backed answer"""

    messages = [
        SystemMessage(content=DECOMPOSE_PROMPT),
        HumanMessage(content=user_message),
    ]

    try:
        response = llm.invoke(messages)
        result   = _parse_plan(response.content, raw_input, requires_tools)

    except Exception as e:
        print(f"  [DECOMPOSE] LLM call failed: {e} — using fallback")
        result = {
            "sub_problems":   [raw_input],
            "execution_plan": _fallback_plan(raw_input, requires_tools),
        }

    # ── Log the plan ──────────────────────────────────────────
    plan = result["execution_plan"]
    print(f"  [DECOMPOSE] → {len(plan)} steps | "
          f"{len(result['sub_problems'])} sub-problems")

    for step in plan:
        tool_label = f"[{step['tool_name']}]" if step["tool_needed"] else "[LLM]"
        tip = ""
        if step.get("tool_input"):
            tip = f" | input='{str(step['tool_input'])[:40]}'"
        print(f"    Step {step['step_id']}: {step['description'][:50]} {tool_label}{tip}")

    trace_entry = (
        f"[DECOMPOSE] {len(plan)} steps | "
        f"sub-problems: {len(result['sub_problems'])}"
    )

    return {
        "sub_problems":    result["sub_problems"],
        "execution_plan":  result["execution_plan"],
        "current_step_id": 1,
        "reasoning_trace": [trace_entry],
    }