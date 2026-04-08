# nodes/execute.py
# ============================================================
# EXECUTE NODE — Runs tools based on the execution_plan.
# Iterates each step, calls the right tool, saves result.
#
# Input  : execution_plan, raw_input, sub_problems
# Output : tool_results, reasoning_trace
# ============================================================

from graph.state import ReasoningState
from graph.llm import get_llm
from tools.web_search import web_search
from tools.calculator import calculator
from tools.code_executor import code_executor
from langchain_core.messages import HumanMessage, SystemMessage


# ── Tool registry — add new tools here ──────────────────────
TOOL_REGISTRY = {
    "web_search":    web_search,
    "calculator":    calculator,
    "code_executor": code_executor,
}

# db_query added Week 5 when Postgres is wired up


def _extract_tool_input(step: dict, state: ReasoningState) -> str:
    """
    Use LLM to generate the correct input for a tool based on the step.
    Example: step says 'search for capital of France' → query = 'capital of France'
    """
    llm = get_llm(fast=True)

    messages = [
        SystemMessage(content=(
            "You generate precise tool inputs. "
            "Return ONLY the tool input string — nothing else. "
            "No explanation, no quotes, no labels."
        )),
        HumanMessage(content=(
            f"Original query: {state['raw_input']}\n"
            f"Step to execute: {step['description']}\n"
            f"Tool to use: {step['tool_name']}\n\n"
            f"What is the exact input to pass to this tool?"
        )),
    ]

    try:
        response = llm.invoke(messages)
        return response.content.strip()
    except Exception:
        # Fallback to step description if LLM fails
        return step["description"]


def execute_node(state: ReasoningState) -> dict:
    """
    EXECUTE node — runs tools for each step in the execution_plan.
    Only executes steps where tool_needed=True.
    """
    plan    = state.get("execution_plan", [])
    results = []

    # Filter only tool steps, sort by priority
    tool_steps = sorted(
        [s for s in plan if s.get("tool_needed", False)],
        key=lambda x: x.get("priority", 1)
    )

    if not tool_steps:
        print(f"  [EXECUTE] No tool steps found in plan")
        return {
            "tool_results":    [],
            "reasoning_trace": ["[EXECUTE] No tool steps — skipped"],
        }

    print(f"  [EXECUTE] Running {len(tool_steps)} tool step(s)...")

    for step in tool_steps:
        tool_name = step.get("tool_name", "")
        step_id   = step.get("step_id", 0)

        # Get the tool function
        tool_fn = TOOL_REGISTRY.get(tool_name)

        if not tool_fn:
            print(f"  [EXECUTE] Unknown tool: {tool_name} — skipping")
            results.append({
                "step_id":   step_id,
                "tool_name": tool_name,
                "success":   False,
                "output":    f"Tool '{tool_name}' not found in registry",
                "error":     f"Unknown tool: {tool_name}",
            })
            continue

        # Generate tool input using LLM
        tool_input = _extract_tool_input(step, state)
        print(f"  [EXECUTE] Step {step_id}: {tool_name}('{tool_input[:50]}')")

        try:
            output  = tool_fn(tool_input)
            success = True
            print(f"  [EXECUTE] Step {step_id} ✓")
        except Exception as e:
            output  = f"Tool execution failed: {str(e)}"
            success = False
            print(f"  [EXECUTE] Step {step_id} ✗ — {e}")

        results.append({
            "step_id":   step_id,
            "tool_name": tool_name,
            "success":   success,
            "output":    output,
            "error":     None if success else output,
        })

    successful = sum(1 for r in results if r["success"])
    return {
        "tool_results":    results,
        "reasoning_trace": [
            f"[EXECUTE] {successful}/{len(results)} tools succeeded"
        ],
    }
