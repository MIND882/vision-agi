# main.py — updated with multi-role support
# Usage:
#   python main.py "query"            # Reasoning Core
#   python main.py --aria             # Aria chat
#   python main.py --role max         # Max (Sales)
#   python main.py --role priya       # Priya (HR)
#   python main.py --role rohan       # Rohan (Support)
#   python main.py --list-roles       # Show all

import uuid, sys
from config import cfg, validate_config
from graph.builder import build_graph
from graph.state import ReasoningState


def run_reasoning(query: str) -> dict:
    initial_state: ReasoningState = {
        "raw_input": query, "session_id": str(uuid.uuid4()),
        "problem_type": "", "complexity": "", "requires_tools": False,
        "language": "en", "retrieved_memories": [], "context_summary": "",
        "sub_problems": [], "execution_plan": [], "tool_results": [],
        "current_step_id": 0, "synthesis": "", "critique_score": 0.0,
        "critique_notes": "", "refine_count": 0, "messages": [],
        "final_output": "", "confidence": 0.0, "reasoning_trace": [],
        "sources_used": [], "what_worked": "", "what_failed": "",
        "memory_written": False,
    }
    return build_graph().invoke(initial_state)


def print_result(result: dict) -> None:
    print("\n" + "="*60 + "\nFINAL OUTPUT\n" + "="*60)
    print(result.get("final_output", "No output."))
    print(f"\nConfidence   : {result.get('confidence', 0):.0%}")
    print(f"Problem type : {result.get('problem_type', 'unknown')}")
    for step in result.get("reasoning_trace", []):
        print(f"  {step}")
    print("="*60)


def run_digital_human(role_name: str, one_shot: str = None) -> None:
    from role.role_factory import RoleFactory
    try:
        agent = RoleFactory.create(role_name)
    except ValueError as e:
        print(f"Error: {e}"); return

    print(f"\n{'='*60}\n{agent.name.upper()} — {agent.config.role}\n{'='*60}")

    if one_shot:
        result = agent.chat(one_shot)
        print(f"Customer : {one_shot}")
        print(f"{agent.name:8} : {result['response']}")
        print(f"\n[Language: {result['language']} | Mode: {result['mode']}]\n{'='*60}")
        return

    print("Type your message | 'quit' to exit | 'reset' to start over")
    print("="*60)
    print(f"\n{agent.name:8} : {agent.greet()}\n")

    while True:
        try:
            user_input = input("You  : ").strip()
        except (KeyboardInterrupt, EOFError):
            user_input = "quit"

        if not user_input: continue

        if user_input.lower() == "quit":
            print(f"{agent.name:8} : Shukriya! Zaroor contact karein.")
            agent.end_session(); break

        if user_input.lower() == "reset":
            agent.reset()
            print(f"{agent.name:8} : Naya session. Kaise madad kar sakta/sakti hoon?\n")
            continue

        result = agent.chat(user_input)
        print(f"{agent.name:8} : {result['response']}")
        print(f"       [lang={result['language']} | mode={result['mode']}]\n")


if __name__ == "__main__":
    validate_config(); print()
    args = sys.argv[1:]

    if "--list-roles" in args:
        from role.role_factory import RoleFactory
        print("Available Digital Human roles:\n")
        for name, d in RoleFactory.list_all().items():
            print(f"  --role {name:8} → {d['name']:8} | {d['role']}")
            print(f"              Industry: {d['industry']} | Tools: {d['tools']}\n")
        sys.exit(0)

    if "--aria" in args:
        idx = args.index("--aria")
        run_digital_human("aria", " ".join(args[idx+1:]) or None); sys.exit(0)

    if "--role" in args:
        idx  = args.index("--role")
        role = args[idx+1] if len(args) > idx+1 else "aria"
        msg  = " ".join(args[idx+2:]) or None
        run_digital_human(role, msg); sys.exit(0)

    query = " ".join(args) if args else "What is the capital of France?"
    print(f"Query: {query}\n\nRunning Reasoning Core...\n")
    print_result(run_reasoning(query))