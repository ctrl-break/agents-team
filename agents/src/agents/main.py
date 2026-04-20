import argparse
import sys

from pathlib import Path

from agents.crews.content_crew.content_crew import build_delivery_crew, build_planning_crew

def save_plan(plan_text: str):
    path = Path(__file__).resolve().parents[3] / "docs" / "specs" / "latest-plan.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plan_text, encoding="utf-8")
    print(f"\nPlan saved to: {path}")

def ask_for_approval() -> bool:
    while True:
        answer = input("\nApprove this plan? [y/n]: ").strip().lower()

        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False

        print("Please enter 'y' or 'n'.")


def read_request_from_args() -> str:
    parser = argparse.ArgumentParser(
        description="Run agent team with approval before delivery."
    )
    parser.add_argument(
        "request",
        nargs="?",
        help="Project request text. If omitted, interactive input mode is used.",
    )

    args = parser.parse_args()

    if args.request:
        return args.request.strip()

    print("Enter your project request. Finish with an empty line:")
    lines = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)

    request = "\n".join(lines).strip()

    if not request:
        print("Error: empty request.")
        sys.exit(1)

    return request


def main():
    user_request = read_request_from_args()

    print("\n=== PHASE 1: PLANNING ===\n")
    planning_crew = build_planning_crew(user_request=user_request)
    plan_result = planning_crew.kickoff()
    plan_text = str(plan_result)
    save_plan(plan_text)

    print("\n=== GENERATED PLAN ===\n")
    print(plan_text)

    approved = ask_for_approval()

    if not approved:
        print("\nPlan was not approved. Stopping execution.")
        return

    print("\n=== PHASE 2: DELIVERY ===\n")
    delivery_crew = build_delivery_crew(
        user_request=user_request,
        approved_plan=plan_text,
    )
    delivery_result = delivery_crew.kickoff()

    print("\n=== FINAL RESULT ===\n")
    print(delivery_result)


if __name__ == "__main__":
    main()