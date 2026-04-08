# nodes/critique.py
# ============================================================
# CRITIQUE NODE — Self-evaluates the synthesis quality.
# Returns score 0.0-1.0 + detailed notes on what's wrong.
#
# Input  : raw_input, synthesis, problem_type
# Output : critique_score, critique_notes, reasoning_trace
# ============================================================

import re
from langchain_core.messages import HumanMessage, SystemMessage
from graph.state import ReasoningState
from graph.llm import get_llm


CRITIQUE_PROMPT = """You are a strict answer quality evaluator.

Evaluate the given answer against the original query on these criteria:
1. ACCURACY    — Is the information correct and factual?
2. COMPLETENESS — Does it fully address the question?
3. CLARITY     — Is it well-structured and easy to understand?
4. RELEVANCE   — Does it stay on topic without padding?

Return EXACTLY this format (no other text):
SCORE: 0.XX
ISSUES: <comma-separated list of issues, or 'none' if score >= 0.8>
IMPROVEMENT: <one specific action to improve the answer, or 'none needed'>

Score guide:
0.9-1.0 = Excellent — complete, accurate, clear
0.8-0.89 = Good — minor gaps but acceptable
0.6-0.79 = Needs work — missing key info or clarity issues
0.0-0.59 = Poor — wrong, incomplete, or off-topic"""


def _parse_critique(response: str) -> tuple[float, str]:
    """
    Parse SCORE and ISSUES from LLM response.
    Returns (score, notes).
    """
    try:
        score_match = re.search(r"SCORE:\s*([0-9.]+)", response)
        issues_match = re.search(r"ISSUES:\s*(.+?)(?:\n|$)", response)
        improve_match = re.search(r"IMPROVEMENT:\s*(.+?)(?:\n|$)", response)

        score  = float(score_match.group(1)) if score_match else 0.7
        score  = max(0.0, min(1.0, score))   # clamp to 0-1

        issues  = issues_match.group(1).strip()  if issues_match  else "Unknown"
        improve = improve_match.group(1).strip() if improve_match else "Review answer"

        notes = f"Issues: {issues} | Fix: {improve}"
        return score, notes

    except Exception:
        return 0.7, "Parse error — defaulting to moderate score"


def critique_node(state: ReasoningState) -> dict:
    """Self-evaluate the synthesis and assign a quality score."""

    raw_input  = state["raw_input"]
    synthesis  = state.get("synthesis", "")
    prob_type  = state.get("problem_type", "reasoning")

    print(f"  [CRITIQUE] Evaluating answer quality...")

    if not synthesis:
        print(f"  [CRITIQUE] No synthesis to evaluate — score 0.0")
        return {
            "critique_score":  0.0,
            "critique_notes":  "No synthesis generated",
            "reasoning_trace": ["[CRITIQUE] Score: 0.0 — empty synthesis"],
        }

    user_message = f"""Original query: {raw_input}
Problem type: {prob_type}

Answer to evaluate:
{'-' * 40}
{synthesis}
{'-' * 40}

Evaluate this answer."""

    llm = get_llm(fast=False)
    messages = [
        SystemMessage(content=CRITIQUE_PROMPT),
        HumanMessage(content=user_message),
    ]

    try:
        response        = llm.invoke(messages)
        score, notes    = _parse_critique(response.content)
    except Exception as e:
        score, notes = 0.75, f"Critique LLM failed: {str(e)[:60]}"

    threshold = 0.8
    verdict   = "PASS" if score >= threshold else "NEEDS REFINE"
    print(f"  [CRITIQUE] Score: {score:.2f} → {verdict}")
    if score < threshold:
        print(f"  [CRITIQUE] Notes: {notes[:80]}")

    return {
        "critique_score":  score,
        "critique_notes":  notes,
        "reasoning_trace": [f"[CRITIQUE] Score={score:.2f} | {verdict}"],
    }