"""
Interactive CLI for SpecPipeline.

Provides a menu-driven TUI that allows users to:
- Create new projects from natural language descriptions
- Browse and manage existing projects
- View project status and artifacts
- Resume, fix, or re-run specific pipeline phases
- Navigate with numbered menus and back options

Usage:
    python -m agents.interactive
    python -m agents.interactive --auto-approve
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agents.flow import (
    _load_state,
    _read_request_from_file,
    run_pipeline,
)
from agents.state import Phase, PipelineState


# ── Constants ─────────────────────────────────────────────────────────────────

REQUESTS_DIR = Path("requests")
DOCS_DIR = Path("docs")
APPS_DIR = Path("apps")
STATE_FILE = "state.json"

STAGES_ORDER: list[Phase] = [
    Phase.ANALYSIS,
    Phase.PLANNING,
    Phase.HUMAN_APPROVAL,
    Phase.IMPLEMENTATION,
    Phase.QA_ARCHITECTURE,
    Phase.VALIDATION,
    Phase.CODING_BACKEND,
    Phase.CODING_FRONTEND,
    Phase.CODING_TESTS,
    Phase.CODING_DEVOPS,
]

STAGE_LABELS: dict[Phase, str] = {
    Phase.ANALYSIS: "Analysis",
    Phase.PLANNING: "Planning (spec generation)",
    Phase.HUMAN_APPROVAL: "Human Approval",
    Phase.IMPLEMENTATION: "Implementation (backend + frontend plans)",
    Phase.QA_ARCHITECTURE: "QA & Architecture Review",
    Phase.VALIDATION: "Validation",
    Phase.CODING_BACKEND: "Coding: Backend",
    Phase.CODING_FRONTEND: "Coding: Frontend",
    Phase.CODING_TESTS: "Coding: Tests",
    Phase.CODING_DEVOPS: "Coding: DevOps",
}

# ── Helpers ───────────────────────────────────────────────────────────────────


def clear_screen() -> None:
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def print_header(title: str) -> None:
    """Print a styled header."""
    width = 60
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)
    print()


def print_menu(options: list[str], start_index: int = 1) -> None:
    """Print a numbered menu."""
    for i, option in enumerate(options, start=start_index):
        print(f"  [{i}] {option}")
    print()


def get_choice(max_val: int, allow_back: bool = True) -> int:
    """Get a numeric choice from the user. Returns -1 for back (0)."""
    while True:
        try:
            if allow_back:
                raw = input(f"  Choice (0=back, 1-{max_val}): ").strip()
            else:
                raw = input(f"  Choice (1-{max_val}): ").strip()
            if not raw:
                continue
            val = int(raw)
            if allow_back and val == 0:
                return -1
            if 1 <= val <= max_val:
                return val
            print(f"  Please enter a number between 1 and {max_val}")
        except ValueError:
            print("  Please enter a valid number")
        except (EOFError, KeyboardInterrupt):
            print("\n  Exiting...")
            sys.exit(0)


def get_multiline_input(prompt: str) -> str:
    """Read multi-line input from the user."""
    print(prompt)
    print("  (Enter empty line to finish)")
    lines = []
    while True:
        try:
            line = input()
            if not line.strip():
                break
            lines.append(line)
        except (EOFError, KeyboardInterrupt):
            print("\n  Exiting...")
            sys.exit(0)
    return "\n".join(lines).strip()


def get_yes_no(prompt: str) -> bool:
    """Ask a yes/no question."""
    while True:
        try:
            raw = input(f"{prompt} [y/n]: ").strip().lower()
            if raw in ("y", "yes"):
                return True
            if raw in ("n", "no"):
                return False
        except (EOFError, KeyboardInterrupt):
            print("\n  Exiting...")
            sys.exit(0)


def wait_enter() -> None:
    """Wait for Enter key."""
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        print("\n  Exiting...")
        sys.exit(0)


def _get_state_file(project_dir: Path) -> Path:
    """Get path to state.json for a project directory."""
    return project_dir / STATE_FILE


def _has_state(project_dir: Path) -> bool:
    """Check if a project directory has a state.json file."""
    return _get_state_file(project_dir).exists()


def _get_completed_phase(state: PipelineState) -> Phase:
    """
    Determine which phase was the last completed.
    Returns the phase the pipeline is currently at (next to be done).
    """
    # If state has approved_spec, planning+approval is done
    # If backend_code_files exist, coding is done for backend
    # etc.
    current = state.current_phase
    return current


def _list_project_dirs() -> list[Path]:
    """
    Discover all existing project directories.
    Searches in requests/ and the root docs/ directory.
    """
    projects: list[Path] = []

    # Look in requests/ directory
    if REQUESTS_DIR.exists():
        for item in sorted(REQUESTS_DIR.iterdir()):
            if item.is_dir() and _has_state(item):
                projects.append(item)

    # Look for root-level state (legacy projects in docs/)
    root_state = Path(STATE_FILE)
    if root_state.exists():
        projects.append(Path(".").resolve())

    return projects


def _get_phase_index(phase: Phase) -> int:
    """Get the index of a phase in STAGES_ORDER."""
    try:
        return STAGES_ORDER.index(phase)
    except ValueError:
        return -1


def _get_status_summary(state: PipelineState) -> str:
    """Build a human-readable status summary from pipeline state."""
    lines = []
    current = state.current_phase

    # Check what's done
    has_request = bool(state.request.strip())
    has_spec = bool(state.approved_spec.strip())
    has_backend_plan = bool(state.backend_plan.strip())
    has_frontend_plan = bool(state.frontend_plan.strip())
    has_qa = bool(state.qa_report.strip())
    has_validation = state.validation.total > 0
    has_backend_code = bool(state.backend_code_files)
    has_frontend_code = bool(state.frontend_code_files)
    has_tests = bool(state.test_files)
    has_devops = bool(state.devops_files)
    has_quality = state.quality.overall_score_pct > 0

    # Build summary
    if has_request:
        lines.append(f"  📝 Request: {state.request[:100]}{'...' if len(state.request) > 100 else ''}")

    for phase in STAGES_ORDER:
        idx = _get_phase_index(phase)
        # Determine if this phase is completed
        completed = False
        in_progress = phase == current

        if phase == Phase.ANALYSIS:
            completed = bool(state.analysis_brief.strip())
        elif phase == Phase.PLANNING:
            completed = len(state.plan_iterations) > 0
            if completed and state.plan_iterations:
                score = state.plan_iterations[-1].score
                lines.append(f"  ✅ Planning: {len(state.plan_iterations)} iteration(s), score {score:.1f}/10")
                continue
        elif phase == Phase.HUMAN_APPROVAL:
            completed = has_spec
        elif phase == Phase.IMPLEMENTATION:
            completed = has_backend_plan or has_frontend_plan
        elif phase == Phase.QA_ARCHITECTURE:
            completed = has_qa
        elif phase == Phase.VALIDATION:
            completed = has_validation
        elif phase == Phase.CODING_BACKEND:
            completed = has_backend_code
        elif phase == Phase.CODING_FRONTEND:
            completed = has_frontend_code
        elif phase == Phase.CODING_TESTS:
            completed = has_tests
        elif phase == Phase.CODING_DEVOPS:
            completed = has_devops

        status = "✅" if completed else ("🔄" if in_progress else "⬜")
        label = STAGE_LABELS.get(phase, phase.value)

        if completed:
            if phase == Phase.CODING_BACKEND:
                lines.append(f"  {status} {label}: {len(state.backend_code_files)} file(s)")
            elif phase == Phase.CODING_FRONTEND:
                lines.append(f"  {status} {label}: {len(state.frontend_code_files)} file(s)")
            elif phase == Phase.CODING_TESTS:
                lines.append(f"  {status} {label}: {len(state.test_files)} file(s)")
            elif phase == Phase.CODING_DEVOPS:
                lines.append(f"  {status} {label}: {len(state.devops_files)} file(s)")
            else:
                lines.append(f"  {status} {label}")
        else:
            lines.append(f"  {status} {label}")

    if has_quality:
        lines.append(f"\n  📊 Quality Score: {state.quality.overall_score_pct:.1f}% {'✅ PASS' if state.quality.passed else '⚠️ BELOW THRESHOLD'}")

    if state.errors:
        lines.append(f"\n  ⚠️  {len(state.errors)} error(s) recorded")

    return "\n".join(lines)


def _show_artifacts(state: PipelineState, project_dir: Path) -> list[str]:
    """Show generated artifacts and return list of file paths for display."""
    files: list[str] = []

    # Determine which docs/ directory to use
    if project_dir == Path(".").resolve():
        docs_base = DOCS_DIR
    else:
        # Look for state.json location patterns
        docs_base = project_dir / "docs"

    # Check for spec files
    pending = project_dir / "plan_v1.md" if project_dir != Path(".").resolve() else (DOCS_DIR / "specs" / "pending-plan.md")
    approved_spec = project_dir / "plan_v1.md" if project_dir == Path(".").resolve() else (project_dir / "approved_spec.md")

    possible_artifacts = [
        ("Specification", docs_base / "specs" / "latest-plan.md" if docs_base != project_dir else project_dir / "approved_plan.md"),
        ("Pending Plan", docs_base / "specs" / "pending-plan.md" if (docs_base / "specs" / "pending-plan.md").exists() else pending),
        ("Backend Plan", docs_base / "implementation" / "backend-plan.md"),
        ("Frontend Plan", docs_base / "implementation" / "frontend-plan.md"),
        ("QA Report", docs_base / "qa" / "qa-report.md"),
        ("Architecture Review", docs_base / "architecture" / "architecture-review.md"),
        ("Tech Review", docs_base / "reviews" / "tech-review.md"),
        ("Cross Review", docs_base / "reviews" / "cross-review.md"),
    ]

    found_any = False
    for label, path in possible_artifacts:
        if path.exists():
            if not found_any:
                print("\n  📄 Generated Documentation:")
                found_any = True
            print(f"    - {label}: {path}")

    # Generated code
    apps_base = project_dir / "apps" if project_dir != Path(".").resolve() else APPS_DIR
    found_code = False
    for subdir_name, label in [
        ("backend", "Backend Code"),
        ("frontend", "Frontend Code"),
        ("tests", "Test Files"),
    ]:
        subdir = apps_base / subdir_name
        if subdir.exists():
            py_files = list(subdir.rglob("*.py"))
            ts_files = list(subdir.rglob("*.ts")) + list(subdir.rglob("*.tsx"))
            js_files = list(subdir.rglob("*.js")) + list(subdir.rglob("*.jsx"))
            all_files = py_files + ts_files + js_files
            if all_files:
                if not found_code:
                    print("\n  💻 Generated Code:")
                    found_code = True
                print(f"    - {label}: {len(all_files)} file(s) in {subdir}")
                for f in sorted(all_files)[:8]:
                    print(f"      · {f.relative_to(subdir)}")
                if len(all_files) > 8:
                    print(f"      · ... and {len(all_files) - 8} more")

    # DevOps
    devops_items = []
    for fname in ["Dockerfile.backend", "Dockerfile.frontend", "docker-compose.yml", ".env.example", "README.md"]:
        fpath = apps_base / fname
        if fpath.exists():
            devops_items.append(fname)
    if devops_items:
        print(f"\n  🐳 DevOps Files: {', '.join(devops_items)}")

    return files


# ── Phase-Specific Actions ────────────────────────────────────────────────────


def _action_continue_pipeline(
    state: PipelineState,
    project_dir: Path,
    auto_approve: bool = False,
) -> PipelineState:
    """Continue the pipeline from where it left off."""
    print_header("▶ Continuing Pipeline")

    print(f"  Resuming from phase: {STAGE_LABELS.get(state.current_phase, state.current_phase.value)}")
    print()

    state = run_pipeline(
        request=state.request,
        auto_approve=auto_approve,
        state_dir=project_dir,
        resume_from=state,
    )

    if state.quality.passed:
        print("\n  ✅ Pipeline completed successfully!")
    else:
        print(f"\n  ⚠️  Pipeline completed with quality score: {state.quality.overall_score_pct:.1f}%")

    wait_enter()
    return state


def _action_replan_spec(state: PipelineState, project_dir: Path, auto_approve: bool) -> PipelineState:
    """Re-generate the specification from scratch."""
    print_header("🔄 Re-Planning Specification")

    print("  This will regenerate the specification from the original request.")
    print(f"  Request: {state.request[:150]}{'...' if len(state.request) > 150 else ''}")
    print()

    confirm = get_yes_no("  Proceed with re-planning?")
    if not confirm:
        return state

    # Reset planning-related state
    state.current_phase = Phase.PLANNING
    state.approved_spec = ""
    state.plan_iterations = []
    state.human_feedback = ""
    state.approval_rounds = 0
    state.backend_plan = ""
    state.frontend_plan = ""
    state.backend_iterations = []
    state.frontend_iterations = []
    state.cross_review = None
    state.qa_report = ""
    state.architecture_review = ""
    state.validation = None
    state.quality = None
    state.backend_code_files = []
    state.frontend_code_files = []
    state.test_files = []
    state.devops_files = []
    state.code_summary = ""

    state = run_pipeline(
        request=state.request,
        auto_approve=auto_approve,
        state_dir=project_dir,
        resume_from=state,
    )

    if state.is_plan_approved:
        print("\n  ✅ Specification re-generated and approved!")
    else:
        print("\n  ⚠️  Planning completed but not yet approved")

    wait_enter()
    return state


def _action_edit_and_approve(state: PipelineState, project_dir: Path, auto_approve: bool) -> PipelineState:
    """Present the current plan for approval (human-in-the-loop)."""
    print_header("📋 Review & Approve Plan")

    if not state.plan_iterations:
        print("  No plan has been generated yet.")
        wait_enter()
        return state

    last_iteration = state.plan_iterations[-1]
    print(f"  Plan generated in {len(state.plan_iterations)} iteration(s)")
    print(f"  Review score: {last_iteration.score:.1f}/10")
    print()

    # Show plan excerpt
    plan_text = last_iteration.output
    if plan_text:
        print("  ── Plan Preview (first 500 chars) ──")
        print(f"  {plan_text[:500]}{'...' if len(plan_text) > 500 else ''}")
        print("  ──────────────────────────────────────")
        print()

    # Approve / Edit / Reject
    options = [
        "Approve plan and continue to implementation",
        "Edit plan in external editor (saves to file, you edit, press Enter)",
        "Reject and re-plan with feedback",
    ]
    print_menu(options)
    choice = get_choice(3, allow_back=True)
    if choice == -1:
        return state

    if choice == 1:
        # Approve
        state.approved_spec = plan_text
        state.current_phase = Phase.IMPLEMENTATION
        print("\n  ✅ Plan approved! Proceeding to implementation...")
        state = run_pipeline(
            request=state.request,
            auto_approve=auto_approve,
            state_dir=project_dir,
            resume_from=state,
        )
        wait_enter()
        return state

    elif choice == 2:
        # Edit externally
        plan_file = project_dir / "plan_v1.md"
        plan_file.write_text(plan_text, encoding="utf-8")
        print(f"\n  📝 Plan saved to: {plan_file}")
        print("  Open and edit this file in your editor.")
        print("  When done, save the file and press Enter to continue...")
        wait_enter()

        try:
            edited = plan_file.read_text(encoding="utf-8").strip()
        except Exception:
            edited = ""
        if not edited:
            print("  Error: file is empty. Plan not updated.")
            wait_enter()
            return state

        state.approved_spec = edited
        state.current_phase = Phase.IMPLEMENTATION
        print(f"\n  ✅ Edited plan approved ({len(edited)} chars)! Proceeding to implementation...")
        state = run_pipeline(
            request=state.request,
            auto_approve=auto_approve,
            state_dir=project_dir,
            resume_from=state,
        )
        wait_enter()
        return state

    elif choice == 3:
        # Reject with feedback
        feedback = get_multiline_input("\n  Enter feedback for re-planning (what to improve):")
        if not feedback:
            print("  No feedback provided. Using default re-plan.")
        state.human_feedback = feedback
        state.current_phase = Phase.PLANNING
        state.approved_spec = ""
        state.approval_rounds += 1
        print("\n  🔄 Re-planning with feedback...")
        state = run_pipeline(
            request=state.request,
            auto_approve=auto_approve,
            state_dir=project_dir,
            resume_from=state,
        )
        wait_enter()
        return state

    return state


def _action_code_backend(state: PipelineState, project_dir: Path, auto_approve: bool) -> PipelineState:
    """Re-run backend code generation."""
    print_header("💻 Generate Backend Code")

    if not state.approved_spec:
        print("  ⚠️  No approved specification. Please complete planning first.")
        wait_enter()
        return state

    print("  Regenerating backend code...")
    state.current_phase = Phase.CODING_BACKEND
    state.backend_code_files = []

    state = run_pipeline(
        request=state.request,
        auto_approve=auto_approve,
        state_dir=project_dir,
        resume_from=state,
    )

    print(f"\n  ✅ Backend code generated: {len(state.backend_code_files)} file(s)")
    wait_enter()
    return state


def _action_code_frontend(state: PipelineState, project_dir: Path, auto_approve: bool) -> PipelineState:
    """Re-run frontend code generation."""
    print_header("💻 Generate Frontend Code")

    if not state.approved_spec:
        print("  ⚠️  No approved specification. Please complete planning first.")
        wait_enter()
        return state

    print("  Regenerating frontend code...")
    state.current_phase = Phase.CODING_FRONTEND
    state.frontend_code_files = []

    state = run_pipeline(
        request=state.request,
        auto_approve=auto_approve,
        state_dir=project_dir,
        resume_from=state,
    )

    print(f"\n  ✅ Frontend code generated: {len(state.frontend_code_files)} file(s)")
    wait_enter()
    return state


def _action_code_tests(state: PipelineState, project_dir: Path, auto_approve: bool) -> PipelineState:
    """Re-run test code generation."""
    print_header("🧪 Generate Tests")

    if not state.approved_spec:
        print("  ⚠️  No approved specification. Please complete planning first.")
        wait_enter()
        return state

    print("  Regenerating test files...")
    state.current_phase = Phase.CODING_TESTS
    state.test_files = []

    state = run_pipeline(
        request=state.request,
        auto_approve=auto_approve,
        state_dir=project_dir,
        resume_from=state,
    )

    print(f"\n  ✅ Tests generated: {len(state.test_files)} file(s)")
    wait_enter()
    return state


def _action_code_devops(state: PipelineState, project_dir: Path, auto_approve: bool) -> PipelineState:
    """Re-run DevOps code generation."""
    print_header("🐳 Generate DevOps Files")

    if not state.approved_spec:
        print("  ⚠️  No approved specification. Please complete planning first.")
        wait_enter()
        return state

    print("  Regenerating DevOps files...")
    state.current_phase = Phase.CODING_DEVOPS
    state.devops_files = []

    state = run_pipeline(
        request=state.request,
        auto_approve=auto_approve,
        state_dir=project_dir,
        resume_from=state,
    )

    print(f"\n  ✅ DevOps files generated: {len(state.devops_files)} file(s)")
    wait_enter()
    return state


def _action_apply_fixes(state: PipelineState, project_dir: Path, auto_approve: bool) -> PipelineState:
    """Apply fixes/improvements from a file."""
    print_header("🔧 Apply Fixes")

    print("  Enter the path to a fixes file (markdown with improvement instructions):")
    print("  (e.g., fixes_1.md in the project directory)")
    print()
    fixes_path = input("  Fixes file path: ").strip()

    if not fixes_path:
        print("  No path provided.")
        wait_enter()
        return state

    fixes_file = Path(fixes_path)
    if not fixes_file.is_absolute():
        fixes_file = project_dir / fixes_file

    if not fixes_file.exists():
        print(f"  Error: file not found: {fixes_file}")
        wait_enter()
        return state

    fixes_text = fixes_file.read_text(encoding="utf-8").strip()
    if not fixes_text:
        print(f"  Error: file is empty: {fixes_file}")
        wait_enter()
        return state

    print(f"\n  📋 Fixes loaded: {len(fixes_text)} chars")
    print(f"  First 200 chars: {fixes_text[:200]}...")

    confirm = get_yes_no("\n  Apply these fixes and re-run implementation?")
    if not confirm:
        return state

    # Reset implementation phases
    state.current_phase = Phase.IMPLEMENTATION
    state.backend_plan = ""
    state.frontend_plan = ""
    state.backend_iterations = []
    state.frontend_iterations = []
    state.cross_review = None
    state.qa_report = ""
    state.architecture_review = ""
    state.validation = None
    state.quality = None
    state.backend_code_files = []
    state.frontend_code_files = []
    state.test_files = []
    state.devops_files = []
    state.code_summary = ""

    state = run_pipeline(
        request=state.request,
        auto_approve=auto_approve,
        state_dir=project_dir,
        resume_from=state,
        fixes_text=fixes_text,
    )

    print(f"\n  ✅ Fixes applied. Quality score: {state.quality.overall_score_pct:.1f}%")
    wait_enter()
    return state


def _action_code_all(state: PipelineState, project_dir: Path, auto_approve: bool) -> PipelineState:
    """Run all coding phases (backend + frontend + tests + devops)."""
    print_header("💻 Generate All Code")

    if not state.approved_spec:
        print("  ⚠️  No approved specification. Please complete planning first.")
        wait_enter()
        return state

    print("  Running all coding phases (backend → frontend → tests → devops)...")

    state.current_phase = Phase.CODING_BACKEND
    state.backend_code_files = []
    state.frontend_code_files = []
    state.test_files = []
    state.devops_files = []

    state = run_pipeline(
        request=state.request,
        auto_approve=auto_approve,
        state_dir=project_dir,
        resume_from=state,
    )

    print(f"\n  ✅ All code generated:")
    print(f"    Backend: {len(state.backend_code_files)} file(s)")
    print(f"    Frontend: {len(state.frontend_code_files)} file(s)")
    print(f"    Tests: {len(state.test_files)} file(s)")
    print(f"    DevOps: {len(state.devops_files)} file(s)")
    wait_enter()
    return state


def _action_view_plan(state: PipelineState) -> None:
    """View the full plan text."""
    print_header("📄 View Plan / Specification")

    if state.approved_spec:
        print("  ── Approved Specification ──")
        print(state.approved_spec)
        print("  ────────────────────────────")
    elif state.plan_iterations:
        last = state.plan_iterations[-1]
        print(f"  ── Latest Plan (Iteration {last.iteration}, Score: {last.score:.1f}/10) ──")
        print(last.output)
        print("  ───────────────────────────────────────────────────────────")
    else:
        print("  No plan available yet.")

    wait_enter()


# ── Menus ─────────────────────────────────────────────────────────────────────


def _menu_new_project(auto_approve: bool) -> None:
    """Menu flow for creating a new project."""
    clear_screen()
    print_header("✨ New Project")

    print("  Choose how to provide the project description:")
    print()
    options = [
        "Type description here (interactive multi-line)",
        "Read from a markdown file (e.g., requests/my-project/request.md)",
    ]
    print_menu(options)
    choice = get_choice(2, allow_back=True)
    if choice == -1:
        return

    request_text = ""
    state_dir: Optional[Path] = None

    if choice == 1:
        request_text = get_multiline_input("\n  Enter your project description:")
        if not request_text:
            print("  Error: empty description.")
            wait_enter()
            return
        state_dir = None  # Use default docs/ location
    elif choice == 2:
        file_path = input("\n  Path to request file: ").strip()
        if not file_path:
            print("  No path provided.")
            wait_enter()
            return
        req_file = Path(file_path)
        if not req_file.exists():
            print(f"  Error: file not found: {req_file}")
            wait_enter()
            return
        request_text = _read_request_from_file(req_file)
        state_dir = req_file.parent
        print(f"\n  📄 Request loaded from: {req_file}")
        print(f"  📁 State will be saved to: {state_dir}")
    else:
        return

    print(f"\n  📝 Request: {request_text[:200]}{'...' if len(request_text) > 200 else ''}")
    print()

    if not auto_approve:
        print("  Pipeline will run with human approval (you'll be asked to approve the plan).")
        print("  Use --auto-approve flag for fully automated runs.")
    else:
        print("  Pipeline will run in auto-approve mode (no human interaction).")
    print()

    confirm = get_yes_no("  Start pipeline?")
    if not confirm:
        return

    print_header("🚀 Running Pipeline")
    state = run_pipeline(
        request=request_text,
        auto_approve=auto_approve,
        state_dir=state_dir,
    )

    if state.quality.passed:
        print(f"\n  ✅ Pipeline completed successfully!")
        print(f"  Quality Score: {state.quality.overall_score_pct:.1f}%")
    else:
        print(f"\n  ⚠️  Pipeline completed with quality score: {state.quality.overall_score_pct:.1f}%")

    wait_enter()


def _menu_project(project_dir: Path, auto_approve: bool) -> None:
    """Main project menu — shows status and offers contextual actions."""
    state_file = _get_state_file(project_dir)
    if not state_file.exists():
        print(f"  Error: state.json not found in {project_dir}")
        wait_enter()
        return

    state = _load_state(state_file)
    if state is None:
        print(f"  Error: could not load state from {state_file}")
        wait_enter()
        return

    while True:
        clear_screen()
        print_header(f"📁 Project: {project_dir.name if project_dir.name else 'root'}")

        # Show status
        print(_get_status_summary(state))
        print()

        # Build contextual menu
        menu_options: list[tuple[str, str, callable]] = []

        # Always available
        current_phase = state.current_phase

        # --- Planning related ---
        if not state.is_plan_approved and current_phase in (Phase.PLANNING, Phase.HUMAN_APPROVAL):
            if state.plan_iterations:
                menu_options.append(("approve", "Review & Approve / Edit / Reject Plan", _action_edit_and_approve))
            menu_options.append(("replan", "Re-plan specification from scratch", _action_replan_spec))

        # --- Continue pipeline ---
        if not state.quality.passed or current_phase != Phase.CODING_DEVOPS:
            if state.is_plan_approved and current_phase not in (Phase.PLANNING, Phase.HUMAN_APPROVAL):
                menu_options.append(("continue", "▶ Continue pipeline from current phase", _action_continue_pipeline))

        # --- Coding sub-phases ---
        if state.is_plan_approved:
            menu_options.append(("code_all", "💻 Generate All Code (backend+frontend+tests+devops)", _action_code_all))
            menu_options.append(("code_backend", "💻 Re-generate Backend Code", _action_code_backend))
            menu_options.append(("code_frontend", "💻 Re-generate Frontend Code", _action_code_frontend))
            menu_options.append(("code_tests", "🧪 Re-generate Tests", _action_code_tests))
            menu_options.append(("code_devops", "🐳 Re-generate DevOps Files", _action_code_devops))

        # --- Fixes ---
        menu_options.append(("fixes", "🔧 Apply Fixes from file", _action_apply_fixes))

        # --- View plan ---
        if state.plan_iterations or state.approved_spec:
            menu_options.append(("view", "📄 View full plan / specification", _action_view_plan))

        # --- Show artifacts ---
        menu_options.append(("artifacts", "📋 Show generated artifacts", None))

        # Build display menu
        print("  Available actions:")
        print()
        labels = []
        for i, (key, label, _) in enumerate(menu_options, 1):
            labels.append(label)
            print(f"  [{i}] {label}")
        print(f"  [0] Back to main menu")
        print()

        choice = get_choice(len(labels), allow_back=True)
        if choice == -1:
            return

        selected_key, selected_label, selected_fn = menu_options[choice - 1]

        if selected_key == "artifacts":
            _show_artifacts(state, project_dir)
            wait_enter()
        elif selected_fn is not None:
            new_state = selected_fn(state, project_dir, auto_approve)
            if new_state is not None:
                state = new_state


def _menu_existing_projects(auto_approve: bool) -> None:
    """Menu for selecting and managing existing projects."""
    while True:
        clear_screen()
        print_header("📂 Existing Projects")

        projects = _list_project_dirs()

        if not projects:
            print("  No existing projects found.")
            print()
            print("  Create a new project from the main menu.")
            print()
            wait_enter()
            return

        options = []
        for p in projects:
            if p == Path(".").resolve():
                name = "root (legacy project)"
            else:
                name = p.name

            # Try to get a short description from the state
            try:
                state = _load_state(p / STATE_FILE)
                request_preview = state.request[:80] if state.request else "no request"
            except Exception:
                request_preview = "unknown"

            options.append((p, f"{name} — {request_preview}"))

        for i, (_, label) in enumerate(options, 1):
            print(f"  [{i}] {label}")
        print(f"  [0] Back to main menu")
        print()

        choice = get_choice(len(options), allow_back=True)
        if choice == -1:
            return

        project_dir = options[choice - 1][0]
        _menu_project(project_dir, auto_approve)


def main_menu(auto_approve: bool = False) -> None:
    """Main interactive menu loop."""
    while True:
        clear_screen()
        print_header("🚀 SpecPipeline — Interactive Mode")
        print("  What would you like to do?")
        print()
        options = [
            "✨ Create a new project",
            "📂 Work with existing projects",
            "🚪 Exit",
        ]
        print_menu(options)

        choice = get_choice(3, allow_back=False)
        if choice == 1:
            _menu_new_project(auto_approve)
        elif choice == 2:
            _menu_existing_projects(auto_approve)
        elif choice == 3:
            print("\n  Goodbye! 👋")
            sys.exit(0)


def main():
    """Entry point for interactive CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SpecPipeline Interactive Mode — menu-driven project management.",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Skip all interactive approval prompts during pipeline execution.",
    )
    args = parser.parse_args()

    try:
        main_menu(auto_approve=args.auto_approve)
    except KeyboardInterrupt:
        print("\n\n  Interrupted. Goodbye! 👋")
        sys.exit(0)


if __name__ == "__main__":
    main()