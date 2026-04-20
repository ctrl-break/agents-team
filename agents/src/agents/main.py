import argparse
import sys
from typing import Tuple

from pathlib import Path

from agents.artifacts import build_artifact_paths
from agents.crews.content_crew.content_crew import build_delivery_crew, build_planning_crew

ARTIFACTS = build_artifact_paths()


def save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def save_pending_plan(plan_text: str) -> None:
    save_text(ARTIFACTS.pending_spec, plan_text)
    print(f"\nDraft plan saved to: {ARTIFACTS.pending_spec}")


def promote_pending_plan(plan_text: str) -> None:
    save_text(ARTIFACTS.approved_spec, plan_text)
    print(f"\nApproved plan saved to: {ARTIFACTS.approved_spec}")


def ask_for_approval(auto_approve: bool) -> bool:
    if auto_approve:
        return True

    while True:
        answer = input("\nApprove this plan? [y/n]: ").strip().lower()

        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False

        print("Please enter 'y' or 'n'.")


def read_request_from_args() -> Tuple[str, bool]:
    parser = argparse.ArgumentParser(
        description="Run agent team with approval before delivery."
    )
    parser.add_argument(
        "request",
        nargs="?",
        help="Project request text. If omitted, interactive input mode is used.",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Skip interactive approval and continue directly to delivery.",
    )

    args = parser.parse_args()

    if args.request:
        return args.request.strip(), args.auto_approve

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

    return request, args.auto_approve


def main():
    user_request, auto_approve = read_request_from_args()

    print("\n=== PHASE 1: PLANNING ===\n")
    planning_crew = build_planning_crew(user_request=user_request)
    plan_result = planning_crew.kickoff()
    plan_text = getattr(plan_result, "raw", str(plan_result))
    save_pending_plan(plan_text)

    print("\n=== GENERATED PLAN ===\n")
    print(plan_text)

    approved = ask_for_approval(auto_approve=auto_approve)

    if not approved:
        print("\nPlan was not approved. Stopping execution.")
        return

    promote_pending_plan(plan_text)

    print("\n=== PHASE 2: DELIVERY ===\n")
    delivery_crew = build_delivery_crew(
        user_request=user_request,
        approved_plan=plan_text,
    )
    delivery_result = delivery_crew.kickoff()
    delivery_text = getattr(delivery_result, "raw", str(delivery_result))

    print("\n=== FINAL RESULT ===\n")
    print(delivery_text)


if __name__ == "__main__":
    main()
