"""Entry point — runs the full Planning → Delivery pipeline with PipelineState."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from agents.artifacts import build_artifact_paths
from agents.crews.planning_crew.planning_crew import (
    build_planning_crew,
    parse_tech_stack,
    parse_directory_layout,
)
from agents.crews.delivery_crew.delivery_crew import build_delivery_crew
from agents.state import PipelineState, Phase, QualitySummary, ValidationReport
from agents.tools.file_tools import read_text_file

ARTIFACTS = build_artifact_paths()

# ── Helpers ──────────────────────────────────────────────────────────────────

def save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def save_pending_plan(plan_text: str) -> None:
    save_text(ARTIFACTS.pending_spec, plan_text)
    print(f"\nDraft plan saved to: {ARTIFACTS.pending_spec}")


def promote_pending_plan(plan_text: str) -> None:
    save_text(ARTIFACTS.approved_spec, plan_text)
    print(f"\nApproved plan saved to: {ARTIFACTS.approved_spec}")


def load_approved_plan(path: Path) -> str:
    if not path.exists():
        print(f"Error: approved plan not found: {path}")
        sys.exit(1)
    if not path.is_file():
        print(f"Error: approved plan path is not a file: {path}")
        sys.exit(1)
    plan_text = path.read_text(encoding="utf-8").strip()
    if not plan_text:
        print(f"Error: approved plan is empty: {path}")
        sys.exit(1)
    return plan_text


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


def read_request_from_args() -> Tuple[Optional[str], bool, bool, Path]:
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
    parser.add_argument(
        "--delivery-only",
        action="store_true",
        help="Skip planning and run delivery using an existing approved plan.",
    )
    parser.add_argument(
        "--plan-file",
        default=str(ARTIFACTS.approved_spec),
        help="Path to an approved plan file used with --delivery-only.",
    )
    args = parser.parse_args()

    if args.delivery_only:
        request = (args.request or "").strip() or None
        return request, args.auto_approve, args.delivery_only, Path(args.plan_file)

    if args.request:
        return args.request.strip(), args.auto_approve, args.delivery_only, Path(
            args.plan_file
        )

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
    return request, args.auto_approve, args.delivery_only, Path(args.plan_file)


# ── Validation ───────────────────────────────────────────────────────────────

def validate_artifacts(state: PipelineState) -> ValidationReport:
    """Быстрая проверка, что ключевые артефакты кодинга создались."""
    from agents.tools.file_tools import list_files as _list_files

    checks = []
    # Check source files exist on disk
    for label, file_list in [
        ("backend_code_files", state.backend_code_files),
        ("frontend_code_files", state.frontend_code_files),
        ("test_files", state.test_files),
        ("devops_files", state.devops_files),
    ]:
        missing = [f for f in file_list if not Path(f).exists()]
        checks.append({
            "name": f"{label}_on_disk",
            "passed": len(missing) == 0,
            "details": f"missing: {missing}" if missing else f"all {len(file_list)} files present",
        })
    return ValidationReport.from_checks(
        [__import__("agents.state").state.ValidationCheck(**c) for c in checks]
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    user_request, auto_approve, delivery_only, plan_file = read_request_from_args()

    # Инициализируем состояние пайплайна
    state = PipelineState(
        request=user_request or "",
        auto_approve=auto_approve,
        started_at=datetime.now(tz=timezone.utc).isoformat(),
    )

    # ── Delivery-only mode ───────────────────────────────────────────────
    if delivery_only:
        plan_text = load_approved_plan(plan_file)
        state.approved_spec = plan_text
        state.current_phase = Phase.DELIVERY
        state.tech_stack = parse_tech_stack(plan_text)
        state.directory_layout = parse_directory_layout(plan_text)

        print("\n=== PHASE 2: DELIVERY ===\n")
        print("Технологический стек (из спецификации):")
        print(state.tech_stack.to_context_string())
        print()

        delivery_crew = build_delivery_crew(
            user_request=state.request or None,
            approved_plan=plan_text,
            tech_stack=state.tech_stack,
            directory_layout=state.directory_layout,
        )
        delivery_result = delivery_crew.kickoff()
        delivery_text = getattr(delivery_result, "raw", str(delivery_result))

        state.delivery_summary = delivery_text
        state.completed_at = datetime.now(tz=timezone.utc).isoformat()

        # Validate
        state.validation = validate_artifacts(state)
        if not state.validation.is_clean:
            print(f"\n⚠️ Validation found {state.validation.failed} failed checks:")
            for name in state.validation.failing_names():
                print(f"  - {name}")

        print("\n=== FINAL RESULT ===\n")
        print(delivery_text)
        return

    # ── PHASE 1: PLANNING ────────────────────────────────────────────────
    state.current_phase = Phase.PLANNING
    print("\n=== PHASE 1: PLANNING ===\n")

    planning_crew = build_planning_crew(user_request=state.request)
    plan_result = planning_crew.kickoff()
    plan_text = getattr(plan_result, "raw", str(plan_result))
    save_pending_plan(plan_text)

    # Парсим технологический стек и структуру
    state.tech_stack = parse_tech_stack(plan_text)
    state.directory_layout = parse_directory_layout(plan_text)
    state.approved_spec = plan_text

    print("\n=== GENERATED PLAN ===\n")
    print(plan_text)
    print("\n--- Технологический стек (распознанный) ---")
    print(state.tech_stack.to_context_string())
    print("--- Структура проекта ---")
    print(f"  Project Type: {state.directory_layout.project_type}")
    print(f"  Backend Dir: {state.directory_layout.backend_dir}")
    print(f"  Frontend Dir: {state.directory_layout.frontend_dir}")
    print(f"  Test Dir: {state.directory_layout.test_dir}")
    print()

    # ── PHASE 2: HUMAN APPROVAL ──────────────────────────────────────────
    state.current_phase = Phase.HUMAN_APPROVAL
    approved = ask_for_approval(auto_approve=state.auto_approve)

    if not approved:
        print("\nPlan was not approved. Stopping execution.")
        state.completed_at = datetime.now(tz=timezone.utc).isoformat()
        return

    promote_pending_plan(plan_text)

    # ── PHASE 3: DELIVERY ────────────────────────────────────────────────
    state.current_phase = Phase.DELIVERY
    print("\n=== PHASE 2: DELIVERY ===\n")
    print("Технологический стек (передаётся delivery crew):")
    print(state.tech_stack.to_context_string())
    print()

    delivery_crew = build_delivery_crew(
        user_request=state.request,
        approved_plan=plan_text,
        tech_stack=state.tech_stack,
        directory_layout=state.directory_layout,
    )
    delivery_result = delivery_crew.kickoff()
    delivery_text = getattr(delivery_result, "raw", str(delivery_result))

    state.delivery_summary = delivery_text
    state.completed_at = datetime.now(tz=timezone.utc).isoformat()

    # Validate
    state.validation = validate_artifacts(state)
    if not state.validation.is_clean:
        print(f"\n⚠️ Validation found {state.validation.failed} failed checks:")
        for name in state.validation.failing_names():
            print(f"  - {name}")
    else:
        print(f"\n✅ Validation passed: {state.validation.passed}/{state.validation.total} checks")

    print("\n=== FINAL RESULT ===\n")
    print(delivery_text)


if __name__ == "__main__":
    main()