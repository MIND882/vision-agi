# nodes/decompose.py
# ============================================================
# DECOMPOSE NODE — Second node in the graph.
#
# Responsibilities:
#   1. Break the problem into sub-problems
#   2. Build a structured execution_plan (list of steps)
#   3. Each step knows: what to do, which tool (if any), priority
#
# Input state fields read  : raw_input, problem_type, complexity,
#                            requires_tools, context_summary
# Output state fields set  : sub_problems, execution_plan,
#                            current_step_id, reasoning_trace
# ============================================================

import json
import re
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import ReasoningState
from graph.llm import get_llm
from config import cfg


# ── System prompt ────────────────────────────────────────────
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
      "priority": 1,
      "depends_on": []
    },
    {
      "step_id": 2,
      "description": "What this step does",
      "tool_needed": true,
      "tool_name": "web_search",
      "priority": 2,
      "depends_on": [1]
    }
  ]
}

Available tools:
- web_search     : search the internet for current information, news, facts
- calculator     : math calculations, formulas, number crunching
- code_executor  : run and test Python code
- db_query       : query internal database for stored knowledge

Rules:
- simple   complexity → 1-2 steps max
- moderate complexity → 2-4 steps max
- complex  complexity → 4-6 steps max
- If requires_tools=false → all steps have tool_needed=false, tool_name=null
- If requires_tools=true  → at least one step must have tool_needed=true
- depends_on = list of step_ids that must complete before this step
- priority 1 = highest (run first)
- Return ONLY the JSON. No explanation. No markdown. No code blocks."""


def _parse_plan(llm_response: str, raw_input: str) -> dict:
    """
    Safely parse LLM JSON response.
    Falls back to single-step plan if parsing fails.
    """
    try:
        cleaned = llm_response.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned)
        cleaned = re.sub(r"^```\s*",     "", cleaned)
        cleaned = re.sub(r"\s*```$",     "", cleaned)

        data = json.loads(cleaned)

        # Validate and sanitize execution_plan
        plan = []
        for step in data.get("execution_plan", []):
            plan.append({
                "step_id":     int(step.get("step_id", 1)),
                "description": str(step.get("description", "")),
                "tool_needed": bool(step.get("tool_needed", False)),
                "tool_name":   step.get("tool_name", None),
                "priority":    int(step.get("priority", 1)),
                "depends_on":  list(step.get("depends_on", [])),
            })

        sub_problems = [str(p) for p in data.get("sub_problems", [raw_input])]

        return {
            "sub_problems":   sub_problems if sub_problems else [raw_input],
            "execution_plan": plan if plan else _fallback_plan(raw_input, False),
        }

    except (json.JSONDecodeError, Exception) as e:
        print(f"  [DECOMPOSE] Warning: JSON parse failed ({e}) — using fallback")
        return {
            "sub_problems":   [raw_input],
            "execution_plan": _fallback_plan(raw_input, False),
        }


def _fallback_plan(description: str, tool_needed: bool) -> list:
    """Single-step fallback plan when LLM parse fails."""
    return [{
        "step_id":     1,
        "description": description,
        "tool_needed": tool_needed,
        "tool_name":   None,
        "priority":    1,
        "depends_on":  [],
    }]


# ── Main node function ───────────────────────────────────────

def decompose_node(state: ReasoningState) -> dict:
    """
    DECOMPOSE node — builds real execution plan using LLM.
    Uses the MAIN model (heavier) because planning quality
    directly impacts everything downstream.
    """
    raw_input      = state["raw_input"]
    problem_type   = state.get("problem_type",  "reasoning")
    complexity     = state.get("complexity",    "moderate")
    requires_tools = state.get("requires_tools", False)
    context        = state.get("context_summary", "")

    print(f"  [DECOMPOSE] Planning for type={problem_type} | "
          f"complexity={complexity} | tools={requires_tools}")

    # ── LLM call ─────────────────────────────────────────────
    llm = get_llm(fast=False)   # main model — quality matters here

    user_message = f"""Query: {raw_input}

Classification:
- problem_type: {problem_type}
- complexity: {complexity}
- requires_tools: {requires_tools}
- context: {context if context else 'No prior context'}

Build the execution plan."""

    messages = [
        SystemMessage(content=DECOMPOSE_PROMPT),
        HumanMessage(content=user_message),
    ]

    try:
        response = llm.invoke(messages)
        result   = _parse_plan(response.content, raw_input)

    except Exception as e:
        print(f"  [DECOMPOSE] LLM call failed: {e} — using fallback")
        result = {
            "sub_problems":   [raw_input],
            "execution_plan": _fallback_plan(raw_input, requires_tools),
        }

    # ── Log the plan ─────────────────────────────────────────
    plan = result["execution_plan"]
    print(f"  [DECOMPOSE] → {len(plan)} steps | "
          f"{len(result['sub_problems'])} sub-problems")

    for step in plan:
        tool_info = f"[{step['tool_name']}]" if step["tool_needed"] else "[LLM]"
        print(f"    Step {step['step_id']}: {step['description'][:55]} {tool_info}")

    trace_entry = (
        f"[DECOMPOSE] {len(plan)} steps created | "
        f"sub-problems: {len(result['sub_problems'])}"
    )

    return {
        "sub_problems":    result["sub_problems"],
        "execution_plan":  result["execution_plan"],
        "current_step_id": 1,
        "reasoning_trace": [trace_entry],
    }