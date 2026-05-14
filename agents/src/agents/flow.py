"""
SpecPipeline Flow — центральный оркестратор пайплайна.

Управляет последовательностью из 6 фаз:
  0. ANALYSIS — разбор запроса
  1. PLANNING — генерация спецификации (+ итерации review)
  2. HUMAN APPROVAL — утверждение человеком
  3. IMPLEMENTATION — backend + frontend + cross-review
  4. QA & ARCHITECTURE — QA-отчёт + архитектурный обзор
  5. VALIDATION — автоматические проверки + итоговое качество

Поддерживает:
- Итерации с review и возвратом на доработку при низких оценках
- Human-in-the-loop: утверждение/отклонение/редактирование плана
- Автоматические проверки (validation_crew)
- Скоринг и пороги качества из quality.py
- Сериализуемое состояние PipelineState
- Файловый workflow: --from-file, --continue, --fixes
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agents.artifacts import build_artifact_paths
from agents.config.pipeline_config import load_pipeline_config
from agents.crews.planning_crew.planning_crew import build_planning_crew
from agents.crews.delivery_crew.delivery_crew import build_delivery_crew
from agents.crews.review_crew.review_crew import (
    build_tech_review_crew,
    build_cross_review_crew,
)
from agents.crews.validation_crew.validation_crew import (
    validate_planning_artifacts,
    validate_all_delivery_artifacts,
    run_validation,
)
from agents.quality import (
    PipelineThresholds,
    compute_iteration_score,
    compute_overall_quality,
    is_pipeline_successful,
)
from agents.state import (
    CrossReviewResult,
    IterationResult,
    Phase,
    PipelineState,
    QualitySummary,
    ValidationReport,
    ReviewDecision,
)

ARTIFACTS = build_artifact_paths()

DEFAULT_STATE_FILE = Path("docs/state.json")


# ──────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────

def _save_state(state: PipelineState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")


def _load_state(path: Path) -> PipelineState:
    """Load PipelineState from a JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"State file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    return PipelineState.model_validate_json(raw)


def _crew_raw(result) -> str:
    return getattr(result, "raw", str(result))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _print_phase_header(phase: str, iteration: int = 0) -> None:
    header = f" PHASE: {phase} "
    if iteration > 0:
        header += f"(iter {iteration}) "
    print(f"\n{'=' * 60}")
    print(f"{header:=^60}")
    print(f"{'=' * 60}\n")


def _print_quality(final_quality: QualitySummary) -> None:
    verdict = "✅ PASSED" if final_quality.passed else "❌ FAILED"
    print(f"\n{'─' * 40}")
    print(f"  Overall score:       {final_quality.overall_score_pct:.1f}%")
    print(f"  Review score:        {final_quality.final_review_score:.1f}/10")
    print(f"  Cross-review issues: {final_quality.cross_review_issues}")
    print(f"  QA coverage:         {final_quality.qa_coverage_pct:.1f}%")
    print(f"  Plan iterations:     {final_quality.plan_iterations}")
    print(f"  Sections complete:   {final_quality.sections_complete}/{final_quality.sections_expected}")
    print(f"  Broken links:        {final_quality.broken_links}")
    print(f"  Verdict:             {verdict}")
    print(f"{'─' * 40}\n")


def _ask_for_approval(request_dir: Optional[Path] = None) -> tuple[bool, Optional[str]]:
    """
    Ask user to approve the plan.

    Returns (approved, edited_plan_text).
    - ('y') → (True, None) — approved as-is
    - ('n') → (False, None) — rejected
    - ('e') → (True, edited_text) — user wants to edit the plan manually
    """
    while True:
        answer = input("\nApprove this plan? [y/n/e]: ").strip().lower()
        if answer in ("y", "yes"):
            return True, None
        if answer in ("n", "no"):
            return False, None
        if answer in ("e", "edit"):
            return _handle_edit_plan(request_dir)
        print("Please enter 'y', 'n', or 'e' (edit).")


def _handle_edit_plan(request_dir: Optional[Path]) -> tuple[bool, Optional[str]]:
    """
    Save plan to an editable file, let user edit it, read it back.

    Returns (True, edited_text) or (False, None) if user aborts.
    """
    target_dir = request_dir or Path("requests/_adhoc")
    target_dir.mkdir(parents=True, exist_ok=True)

    # Find the next version number
    existing = sorted(target_dir.glob("plan_v*.md"))
    version = len(existing) + 1
    edit_path = target_dir / f"plan_v{version}.md"

    # Copy current plan to edit file
    plan_text = ARTIFACTS.pending_spec.read_text(encoding="utf-8")
    edit_path.write_text(plan_text, encoding="utf-8")

    print(f"\n  📝 Plan saved to: {edit_path}")
    print(f"  Edit this file in your text editor, save it, then press Enter here.")
    print(f"  (Or type 'abort' and press Enter to cancel editing.)")

    user_input = input(f"  Waiting for you to finish editing [{edit_path}]: ").strip()
    if user_input.lower() == "abort":
        print("  Edit aborted.")
        return False, None

    if not edit_path.exists():
        print(f"  ⚠ File not found: {edit_path}. Using original plan.")
        return True, plan_text

    edited = edit_path.read_text(encoding="utf-8").strip()
    if not edited:
        print("  ⚠ Edited file is empty. Using original plan.")
        return True, plan_text

    # Update pending_spec with edited version
    ARTIFACTS.pending_spec.write_text(edited, encoding="utf-8")
    print(f"  ✅ Edited plan accepted ({len(edited)} chars).")
    return True, edited


# ──────────────────────────────────────────────────────────────────────
#  Phase implementations
# ──────────────────────────────────────────────────────────────────────

def _phase_analysis(state: PipelineState) -> PipelineState:
    """Phase 0: Quick analysis (no LLM — just validation of input)."""
    _print_phase_header("0: ANALYSIS")

    state.current_phase = Phase.ANALYSIS
    if state.started_at is None:
        state.started_at = _now_iso()

    if not state.request.strip():
        state.errors.append("Empty request received")
        return state

    state.analysis_brief = (
        f"Request length: {len(state.request)} chars. "
        "Proceeding to automated planning."
    )
    state.clarifications = []

    print(f"  Request accepted ({len(state.request)} chars).")
    return state


def _phase_planning(
    state: PipelineState, thresholds: PipelineThresholds
) -> PipelineState:
    """Phase 1: Generate spec → review → iterate until threshold met."""
    _print_phase_header("1: PLANNING")
    state.current_phase = Phase.PLANNING

    for iteration in range(1, thresholds.plan_max_iterations + 1):
        _print_phase_header("1: PLANNING", iteration)

        # Build and run planning crew
        planning_crew = build_planning_crew(user_request=state.request)
        plan_result = planning_crew.kickoff()
        plan_text = _crew_raw(plan_result)

        # Save to pending
        ARTIFACTS.pending_spec.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACTS.pending_spec.write_text(plan_text, encoding="utf-8")
        print(f"  Plan saved to: {ARTIFACTS.pending_spec}")

        # Run technical review
        print("  → Running technical review...")
        tech_review_crew = build_tech_review_crew(
            artifact_paths=[str(ARTIFACTS.pending_spec)],
            artifact_kind="plan",
        )
        tech_result = tech_review_crew.kickoff()
        tech_review_text = _crew_raw(tech_result)
        print(f"  Technical review saved to docs/reviews/tech-review.md")

        # Auto-validation
        validation_report = validate_planning_artifacts()

        # Parse a simple score from validation
        plan_score = validation_report.passed_pct / 10.0

        # Build iteration result
        iter_result = IterationResult(
            iteration=iteration,
            output=plan_text[:200],
            score=plan_score,
            issues=[c.details for c in validation_report.checks if not c.passed],
            suggestions=[],
            decision=(
                ReviewDecision.APPROVED
                if plan_score >= thresholds.plan_review_score_threshold
                else ReviewDecision.REVISIONS_NEEDED
            ),
        )
        state.plan_iterations.append(iter_result)
        print(f"  Score: {iter_result.score:.1f}/10 ({len(iter_result.issues)} issues)")

        # Check threshold
        if plan_score >= thresholds.plan_review_score_threshold:
            print(f"  ✅ Plan meets quality threshold ({thresholds.plan_review_score_threshold}).")
            break

        if iteration < thresholds.plan_max_iterations:
            print(f"  ⚠ Score below threshold, re-iterating...")
        else:
            print(f"  ⚠ Max iterations ({thresholds.plan_max_iterations}) reached.")

    # Validation check
    validation_report = validate_planning_artifacts()
    state.validation = validation_report
    print(f"  Auto-validation: {validation_report.passed_pct}% "
          f"({validation_report.passed}/{validation_report.total})")

    return state


def _phase_human_approval(
    state: PipelineState,
    thresholds: PipelineThresholds,
    request_dir: Optional[Path] = None,
) -> PipelineState:
    """Phase 2: Show plan to human, get approval (or reject/edit with feedback)."""
    _print_phase_header("2: HUMAN APPROVAL")
    state.current_phase = Phase.HUMAN_APPROVAL

    plan_text = ARTIFACTS.pending_spec.read_text(encoding="utf-8")

    print("Generated Plan:")
    print(plan_text)
    print()

    for round_num in range(1, thresholds.max_approval_rounds + 1):
        if state.auto_approve:
            print(f"  [auto-approve] Plan approved automatically.")
            ARTIFACTS.approved_spec.parent.mkdir(parents=True, exist_ok=True)
            ARTIFACTS.approved_spec.write_text(plan_text, encoding="utf-8")
            state.approved_spec = plan_text
            state.approval_rounds = round_num
            return state

        approved, edited_plan = _ask_for_approval(request_dir=request_dir)

        if approved:
            if edited_plan is not None:
                # User edited the plan — use edited version
                plan_text = edited_plan
                ARTIFACTS.pending_spec.write_text(plan_text, encoding="utf-8")

            ARTIFACTS.approved_spec.parent.mkdir(parents=True, exist_ok=True)
            ARTIFACTS.approved_spec.write_text(plan_text, encoding="utf-8")
            state.approved_spec = plan_text
            state.approval_rounds = round_num
            print(f"  ✅ Plan approved.")
            return state

        print(f"  ❌ Plan rejected. Round {round_num}/{thresholds.max_approval_rounds}.")
        if round_num < thresholds.max_approval_rounds:
            feedback = input("  Enter revision feedback (or press Enter to abort): ").strip()
            if not feedback:
                print("  No feedback provided. Aborting.")
                return state

            # Save feedback to file if request_dir exists
            if request_dir:
                _save_feedback(request_dir, feedback, round_num)

            # Regenerate plan with feedback
            state.human_feedback = feedback
            print("  🔄 Regenerating plan with feedback...")
            planning_crew = build_planning_crew(
                user_request=state.request,
                feedback=feedback,
            )
            plan_result = planning_crew.kickoff()
            plan_text = _crew_raw(plan_result)
            ARTIFACTS.pending_spec.write_text(plan_text, encoding="utf-8")
            print("  Regenerated plan:")
            print(plan_text)
        else:
            print(f"  Max approval rounds ({thresholds.max_approval_rounds}) reached. Aborting.")
            state.errors.append("Max approval rounds exceeded")
            return state

    return state


def _save_feedback(request_dir: Path, feedback: str, round_num: int) -> None:
    """Save human feedback to a file for history."""
    feedback_path = request_dir / f"feedback_{round_num}.md"
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    feedback_path.write_text(feedback, encoding="utf-8")
    print(f"  💾 Feedback saved to: {feedback_path}")


def _phase_implementation(
    state: PipelineState,
    thresholds: PipelineThresholds,
    fixes_text: str = "",
) -> PipelineState:
    """Phase 3: Generate backend + frontend plans, cross-review, iterate."""
    _print_phase_header("3: IMPLEMENTATION")
    state.current_phase = Phase.IMPLEMENTATION

    approved_plan = state.approved_spec or ARTIFACTS.approved_spec.read_text(encoding="utf-8")

    # Build delivery crew (with optional fixes feedback)
    delivery_crew = build_delivery_crew(
        user_request=state.request,
        approved_plan=approved_plan,
        feedback=fixes_text,
    )
    delivery_result = delivery_crew.kickoff()
    delivery_text = _crew_raw(delivery_result)

    # Gather artifact paths for cross-review
    artifact_paths = [
        str(ARTIFACTS.backend_plan),
        str(ARTIFACTS.frontend_plan),
    ]

    # Cross-review
    print("  → Running cross-review...")
    cross_crew = build_cross_review_crew(
        artifact_paths=artifact_paths,
    )
    cross_result = cross_crew.kickoff()
    cross_text = _crew_raw(cross_result)
    print(f"  Cross-review saved to docs/reviews/cross-review.md")

    # Parse backend plan
    if ARTIFACTS.backend_plan.exists():
        state.backend_plan = ARTIFACTS.backend_plan.read_text(encoding="utf-8")

    # Parse frontend plan
    if ARTIFACTS.frontend_plan.exists():
        state.frontend_plan = ARTIFACTS.frontend_plan.read_text(encoding="utf-8")

    # Estimate cross-review issues
    cross_issues = cross_text.count("MISALIGNED") + cross_text.count("BLOCKED")
    state.cross_review = CrossReviewResult(
        conflicts=[],
        resolved=(cross_issues == 0),
        backend_review_of_frontend=cross_text[:500] if ARTIFACTS.frontend_plan.exists() else "",
        frontend_review_of_backend=cross_text[:500] if ARTIFACTS.backend_plan.exists() else "",
    )

    print(f"  Backend plan: {'✅' if state.backend_plan else '❌'}")
    print(f"  Frontend plan: {'✅' if state.frontend_plan else '❌'}")
    print(f"  Cross-review issues: {cross_issues}")

    return state


def _phase_qa_architecture(state: PipelineState) -> PipelineState:
    """Phase 4: QA report and architecture review (generated by delivery crew already)."""
    _print_phase_header("4: QA & ARCHITECTURE")
    state.current_phase = Phase.QA_ARCHITECTURE

    if ARTIFACTS.qa_report.exists():
        state.qa_report = ARTIFACTS.qa_report.read_text(encoding="utf-8")
        print(f"  QA report: ✅ ({len(state.qa_report)} chars)")
    else:
        print(f"  QA report: ❌ not found")
        state.errors.append("QA report missing")

    if ARTIFACTS.architecture_report.exists():
        state.architecture_review = ARTIFACTS.architecture_report.read_text(encoding="utf-8")
        print(f"  Architecture review: ✅ ({len(state.architecture_review)} chars)")
    else:
        print(f"  Architecture review: ❌ not found")
        state.errors.append("Architecture review missing")

    return state


def _phase_validation(
    state: PipelineState, thresholds: PipelineThresholds
) -> PipelineState:
    """Phase 5: Full validation + final quality calculation."""
    _print_phase_header("5: VALIDATION")
    state.current_phase = Phase.VALIDATION

    delivery_report = validate_all_delivery_artifacts()
    state.validation = delivery_report

    print(f"  Validation: {delivery_report.passed}/{delivery_report.total} passed "
          f"({delivery_report.passed_pct}%)")

    broken_links = sum(
        1 for c in delivery_report.checks
        if "markdown_links" in c.name and not c.passed
    )

    sections_checks = [
        c for c in delivery_report.checks if "required_sections" in c.name
    ]
    sections_complete = sum(1 for c in sections_checks if c.passed)
    sections_expected = len(sections_checks)

    qa_coverage = 100.0 if ARTIFACTS.qa_report.exists() else 0.0
    cross_review_issues = len(state.cross_review.conflicts) if state.cross_review else 0

    review_score = state.latest_plan_score or (delivery_report.passed_pct / 10.0)
    overall_score = compute_overall_quality(
        review_score=review_score,
        validation_pct=delivery_report.passed_pct,
        qa_coverage_pct=qa_coverage,
        cross_review_issues=cross_review_issues,
    )

    passed = is_pipeline_successful(overall_score, thresholds)

    state.quality = QualitySummary(
        plan_iterations=len(state.plan_iterations),
        final_review_score=round(review_score, 1),
        cross_review_issues=cross_review_issues,
        qa_coverage_pct=qa_coverage,
        broken_links=broken_links,
        sections_complete=sections_complete,
        sections_expected=sections_expected,
        overall_score_pct=overall_score,
        passed=passed,
    )

    state.completed_at = _now_iso()
    _print_quality(state.quality)

    return state


# ──────────────────────────────────────────────────────────────────────
#  Resumable pipeline runner
# ──────────────────────────────────────────────────────────────────────

def _phase_order() -> list[Phase]:
    """Return phases in execution order."""
    return [
        Phase.ANALYSIS,
        Phase.PLANNING,
        Phase.HUMAN_APPROVAL,
        Phase.IMPLEMENTATION,
        Phase.QA_ARCHITECTURE,
        Phase.VALIDATION,
    ]


def run_pipeline(
    request: str,
    auto_approve: bool = False,
    thresholds: Optional[PipelineThresholds] = None,
    state_dir: Optional[Path] = None,
    resume_from: Optional[PipelineState] = None,
    fixes_text: str = "",
) -> PipelineState:
    """
    Run the full SpecPipeline.

    Args:
        request: User's project request text.
        auto_approve: If True, skip human approval.
        thresholds: Quality thresholds (uses defaults if None).
        state_dir: Directory for saving state.json and feedback files.
        resume_from: If provided, resume from this state's current_phase.
        fixes_text: Feedback/improvements to pass to delivery crew.

    Returns:
        Final PipelineState with all artifacts and quality metrics.
    """
    if thresholds is None:
        thresholds = load_pipeline_config()

    state_file = (state_dir / "state.json") if state_dir else DEFAULT_STATE_FILE

    # Determine starting state
    if resume_from is not None:
        state = resume_from
        print(f"\n  🔄 Resuming from phase: {state.current_phase.value}")
    else:
        state = PipelineState(
            request=request,
            auto_approve=auto_approve or thresholds.max_approval_rounds == 0,
        )

    phases = _phase_order()
    start_index = phases.index(state.current_phase) if state.current_phase in phases else 0

    try:
        for i in range(start_index, len(phases)):
            phase = phases[i]
            state.current_phase = phase

            if phase == Phase.ANALYSIS:
                state = _phase_analysis(state)
                if state.has_errors:
                    _save_state(state, state_file)
                    return state

            elif phase == Phase.PLANNING:
                state = _phase_planning(state, thresholds)

            elif phase == Phase.HUMAN_APPROVAL:
                state = _phase_human_approval(state, thresholds, request_dir=state_dir)
                if not state.approved_spec:
                    print("\n  ⛔ Pipeline stopped: plan not approved.")
                    _save_state(state, state_file)
                    return state

            elif phase == Phase.IMPLEMENTATION:
                state = _phase_implementation(state, thresholds, fixes_text=fixes_text)

            elif phase == Phase.QA_ARCHITECTURE:
                state = _phase_qa_architecture(state)

            elif phase == Phase.VALIDATION:
                state = _phase_validation(state, thresholds)

    except KeyboardInterrupt:
        print("\n\n  ⛔ Pipeline interrupted by user.")
        state.errors.append("Interrupted by user")
    except Exception as e:
        print(f"\n  ❌ Pipeline error: {e}")
        state.errors.append(str(e))

    _save_state(state, state_file)

    print(f"\n{'=' * 60}")
    print(f"  Pipeline finished. State saved to {state_file}")
    print(f"  Verdict: {'✅ PASSED' if state.quality.passed else '❌ FAILED'}")
    print(f"{'=' * 60}\n")

    return state


# ──────────────────────────────────────────────────────────────────────
#  CLI entry point
# ──────────────────────────────────────────────────────────────────────

def _read_request_from_file(path: Path) -> str:
    """Read project request from a markdown file."""
    if not path.exists():
        print(f"Error: request file not found: {path}")
        sys.exit(1)
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        print(f"Error: request file is empty: {path}")
        sys.exit(1)
    return content


def _read_fixes_file(path: Path) -> str:
    """Read fixes/feedback from a markdown file."""
    if not path.exists():
        print(f"Error: fixes file not found: {path}")
        sys.exit(1)
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        print(f"Error: fixes file is empty: {path}")
        sys.exit(1)
    return content


def _interactive_request() -> str:
    """Read multi-line request from stdin."""
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
    """CLI entry point with file-based workflow support."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SpecPipeline — AI-driven specification and implementation generator.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # New task from CLI argument
  python -m agents.flow "Create a REST API for a blog"

  # New task from file
  python -m agents.flow --from-file requests/blog-api/request.md

  # New task from file, auto-approve everything
  python -m agents.flow --from-file requests/blog-api/request.md --auto-approve

  # Resume after interruption or continue from saved state
  python -m agents.flow --continue requests/blog-api/

  # Apply fixes to a completed pipeline (re-run implementation phase)
  python -m agents.flow --continue requests/blog-api/ --fixes requests/blog-api/fixes_1.md
        """,
    )
    parser.add_argument(
        "request",
        nargs="?",
        help="Project request text. If omitted, interactive input mode is used.",
    )
    parser.add_argument(
        "--from-file",
        type=Path,
        metavar="PATH",
        help="Read project request from a markdown file.",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Skip interactive approval and continue directly to delivery.",
    )
    parser.add_argument(
        "--continue",
        type=Path,
        metavar="DIR",
        dest="continue_dir",
        help="Resume pipeline from a saved state directory.",
    )
    parser.add_argument(
        "--fixes",
        type=Path,
        metavar="PATH",
        help="Apply fixes/improvements file (requires --continue).",
    )

    args = parser.parse_args()

    # --- Mode 1: Continue from saved state ---
    if args.continue_dir:
        continue_dir = args.continue_dir.resolve()
        state_file = continue_dir / "state.json"

        if not state_file.exists():
            print(f"Error: state.json not found in {continue_dir}")
            print("Make sure you are pointing to a directory with a saved state file.")
            sys.exit(1)

        state = _load_state(state_file)

        # Read fixes if provided
        fixes_text = ""
        if args.fixes:
            fixes_text = _read_fixes_file(args.fixes)
            print(f"  📋 Fixes loaded from: {args.fixes} ({len(fixes_text)} chars)")

        state = run_pipeline(
            request=state.request,
            auto_approve=state.auto_approve,
            state_dir=continue_dir,
            resume_from=state,
            fixes_text=fixes_text,
        )

        if state.quality.passed:
            sys.exit(0)
        else:
            sys.exit(1)

    # --- Mode 2: New task from file ---
    if args.from_file:
        request_file = args.from_file.resolve()
        request_text = _read_request_from_file(request_file)

        # Determine state directory (same dir as request file)
        state_dir = request_file.parent
        state_dir.mkdir(parents=True, exist_ok=True)

        print(f"  📄 Request loaded from: {request_file}")
        print(f"  📁 State will be saved to: {state_dir}")

        state = run_pipeline(
            request=request_text,
            auto_approve=args.auto_approve,
            state_dir=state_dir,
        )

        if state.quality.passed:
            sys.exit(0)
        else:
            sys.exit(1)

    # --- Mode 3: CLI argument (backward compatible) ---
    if args.request:
        request_text = args.request.strip()
        state = run_pipeline(
            request=request_text,
            auto_approve=args.auto_approve,
        )

        if state.quality.passed:
            sys.exit(0)
        else:
            sys.exit(1)

    # --- Mode 4: Interactive input (backward compatible) ---
    request_text = _interactive_request()
    state = run_pipeline(
        request=request_text,
        auto_approve=args.auto_approve,
    )

    if state.quality.passed:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()