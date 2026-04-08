# main.py
# ============================================================
# Entry point for Vision AGI.
#
# Two modes:
#   python main.py "What is the capital of France?"
#       → Runs raw Reasoning Core (Phase 1)
#
#   python main.py --aria "Mera AC thanda nahi kar raha"
#       → Runs as Aria — AC Service Digital Human (Phase 2)
# ============================================================

import uuid
import sys
from config import cfg, validate_config
from graph.builder import build_graph
from graph.state import ReasoningState


# ── MODE 1: Raw Reasoning Core ───────────────────────────────
def run(query: str) -> dict:
    """
    Run one query through the full Reasoning Core graph.
    Returns final state dict after all nodes have run.
    """
    initial_state: ReasoningState = {
        "raw_input":          query,
        "session_id":         str(uuid.uuid4()),
        "problem_type":       "",
        "complexity":         "",
        "requires_tools":     False,
        "language":           "en",
        "retrieved_memories": [],
        "context_summary":    "",
        "sub_problems":       [],
        "execution_plan":     [],
        "tool_results":       [],
        "current_step_id":    0,
        "synthesis":          "",
        "critique_score":     0.0,
        "critique_notes":     "",
        "refine_count":       0,
        "messages":           [],
        "final_output":       "",
        "confidence":         0.0,
        "reasoning_trace":    [],
        "sources_used":       [],
        "what_worked":        "",
        "what_failed":        "",
        "memory_written":     False,
    }
    graph  = build_graph()
    result = graph.invoke(initial_state)
    return result


def print_result(result: dict) -> None:
    """Print Reasoning Core result in readable format."""
    print("\n" + "="*60)
    print("FINAL OUTPUT")
    print("="*60)
    print(result.get("final_output", "No output generated."))
    print(f"\nConfidence : {result.get('confidence', 0):.0%}")
    print(f"Problem type: {result.get('problem_type', 'unknown')}")
    trace = result.get("reasoning_trace", [])
    if trace:
        print("\nReasoning trace:")
        for step in trace:
            print(f"  {step}")
    print("="*60)


# ── MODE 2: Aria — Digital Human ─────────────────────────────
def run_aria(query: str = None) -> None:
    """
    Run Aria in interactive chat mode.
    If query is passed → single response.
    If no query → full interactive session.
    """
    from identity.aria import Aria

    aria = Aria()

    print("\n" + "="*60)
    print("ARIA — AC Service Digital Human")
    print("="*60)

    # Single query mode
    if query:
        print(f"Customer : {query}")
        result = aria.chat(query)
        print(f"Aria     : {result['response']}")
        print(f"\n[Language: {result['language']} | Mode: {result['mode']}]")
        print("="*60)
        return

    # Interactive session mode
    print("Type your message | 'quit' to exit | 'reset' to start over")
    print("="*60)

    # Aria greets first
    try:
        greeting = aria.greet()
        print(f"\nAria : {greeting}\n")
    except Exception:
        print(f"\nAria : {aria.persona.hindi_greeting}\n")

    # Chat loop
    while True:
        try:
            user_input = input("You  : ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nAria : Shukriya! Aapka din shubh ho. 🙏")
            break

        if not user_input:
            continue

        if user_input.lower() == "quit":
            print("Aria : Shukriya! Koi bhi zarurat ho toh zaroor contact karein. 🙏")
            break

        if user_input.lower() == "reset":
            aria.reset()
            print("Aria : Namaste! Main Aria hoon, aapki madad ke liye. Kya problem hai?\n")
            continue

        result = aria.chat(user_input)
        print(f"\nAria : {result['response']}")
        print(f"       [lang={result['language']} | mode={result['mode']}]\n")


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":

    validate_config()
    print()

    args = sys.argv[1:]

    # -- Aria mode --
    if args and args[0] == "--aria":
        query = " ".join(args[1:]) if len(args) > 1 else None
        run_aria(query)

    # -- Reasoning Core mode --
    else:
        query = " ".join(args) if args else \
                "What is the capital of France and why is it significant?"
        print(f"Query: {query}\n")
        print("Running Reasoning Core...\n")
        result = run(query)
        print_result(result)