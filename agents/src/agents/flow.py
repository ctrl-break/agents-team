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
- Human-in-the-loop: утверждение/отклонение плана
- Автоматические проверки (validation_crew)
- Скоринг и пороги качества из quality.py
- Сериализуемое состояние PipelineState
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
    ReviewDecision,
)

ARTIFACTS = build_artifact_paths()

STATE_FILE = Path("docs/state.json")


# ──────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────

def _save_state(state: PipelineState) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(state.model_dump_json(indent=2), encoding="utf-8")


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


def _ask_for_approval() -> bool:
    while True:
        answer = input("\nApprove this plan? [y/n]: ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please enter 'y' or 'n'.")


# ──────────────────────────────────────────────────────────────────────
#  Phase implementations
# ──────────────────────────────────────────────────────────────────────

def _phase_analysis(state: PipelineState) -> PipelineState:
    """Phase 0: Quick analysis (no LLM — just validation of input)."""
    _print_phase_header("0: ANALYSIS")

    state.current_phase = Phase.ANALYSIS
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

        # Parse a simple score from validation (if no LLM score parsing)
        # For now use validation passed_pct / 10 as proxy; in production parse LLM output
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


def _phase_human_approval(state: PipelineState, thresholds: PipelineThresholds) -> PipelineState:
    """Phase 2: Show plan to human, get approval (or reject with feedback)."""
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

        if _ask_for_approval():
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

            # If feedback provided, regenerate plan
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


def _phase_implementation(
    state: PipelineState, thresholds: PipelineThresholds
) -> PipelineState:
    """Phase 3: Generate backend + frontend plans, cross-review, iterate."""
    _print_phase_header("3: IMPLEMENTATION")
    state.current_phase = Phase.IMPLEMENTATION

    approved_plan = state.approved_spec or ARTIFACTS.approved_spec.read_text(encoding="utf-8")

    # Build delivery crew
    delivery_crew = build_delivery_crew(
        user_request=state.request,
        approved_plan=approved_plan,
    )
    delivery_result = delivery_crew.kickoff()
    delivery_text = _crew_raw(delivery_result)

    # Save backend/frontend/qa/arch artifacts (they should be saved by delivery crew)
    # Check which files were produced
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

    # Estimate cross-review issues (count "BLOCKED" or "MISALIGNED" in output)
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
    state.current_phase = Phase.QA

    # These should already exist from delivery crew output
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

    # Validate all artifacts
    delivery_report = validate_all_delivery_artifacts()
    state.validation = delivery_report

    print(f"  Validation: {delivery_report.passed}/{delivery_report.total} passed "
          f"({delivery_report.passed_pct}%)")

    # Count broken links
    broken_links = sum(
        1 for c in delivery_report.checks
        if "markdown_links" in c.name and not c.passed
    )

    # Count sections
    sections_checks = [
        c for c in delivery_report.checks if "required_sections" in c.name
    ]
    sections_complete = sum(1 for c in sections_checks if c.passed)
    sections_expected = len(sections_checks)

    # QA coverage estimate (simplified)
    qa_coverage = 100.0 if ARTIFACTS.qa_report.exists() else 0.0

    # Cross-review issues count
    cross_review_issues = len(state.cross_review.conflicts) if state.cross_review else 0

    # Overall quality
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
#  Main Flow
# ──────────────────────────────────────────────────────────────────────

def run_pipeline(
    request: str,
    auto_approve: bool = False,
    thresholds: Optional[PipelineThresholds] = None,
) -> PipelineState:
    """
    Run the full SpecPipeline.

    Args:
        request: User's project request text.
        auto_approve: If True, skip human approval.
        thresholds: Quality thresholds (uses defaults if None).

    Returns:
        Final PipelineState with all artifacts and quality metrics.
    """
    if thresholds is None:
        thresholds = load_pipeline_config()

    # Initialize state
    state = PipelineState(
        request=request,
        auto_approve=auto_approve or thresholds.max_approval_rounds == 0,
    )

    try:
        # Phase 0: Analysis
        state = _phase_analysis(state)
        if state.has_errors:
            _save_state(state)
            return state

        # Phase 1: Planning
        state = _phase_planning(state, thresholds)

        # Phase 2: Human Approval
        state = _phase_human_approval(state, thresholds)
        if not state.approved_spec:
            print("\n  ⛔ Pipeline stopped: plan not approved.")
            _save_state(state)
            return state

        # Phase 3: Implementation
        state = _phase_implementation(state, thresholds)

        # Phase 4: QA & Architecture
        state = _phase_qa_architecture(state)

        # Phase 5: Validation
        state = _phase_validation(state, thresholds)

    except KeyboardInterrupt:
        print("\n\n  ⛔ Pipeline interrupted by user.")
        state.errors.append("Interrupted by user")
    except Exception as e:
        print(f"\n  ❌ Pipeline error: {e}")
        state.errors.append(str(e))

    _save_state(state)

    print(f"\n{'=' * 60}")
    print(f"  Pipeline finished. State saved to {STATE_FILE}")
    print(f"  Verdict: {'✅ PASSED' if state.quality.passed else '❌ FAILED'}")
    print(f"{'=' * 60}\n")

    return state


# ──────────────────────────────────────────────────────────────────────
#  CLI entry point
# ──────────────────────────────────────────────────────────────────────

def main():
    """CLI entry point matching original main.py interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SpecPipeline — AI-driven specification and implementation generator."
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
        request = args.request.strip()
    else:
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

    state = run_pipeline(request=request, auto_approve=args.auto_approve)

    if state.quality.passed:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()