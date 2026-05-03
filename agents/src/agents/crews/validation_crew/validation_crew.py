"""Validation crew — автоматические проверки артефактов без AI.

Runs programmatic checks on generated artifacts: syntax, links, structure,
completeness, and cross-references. Produces a ValidationReport.
"""

from __future__ import annotations

from pathlib import Path

from agents.artifacts import build_artifact_paths
from agents.state import ValidationCheck, ValidationReport
from agents.tools.common_tools import (
    check_markdown_links,
    count_lines,
    extract_headings,
    validate_json,
    validate_yaml,
)

ARTIFACTS = build_artifact_paths()

# Minimum expected line counts for each artifact type
MIN_LINES: dict[str, int] = {
    "pending_plan": 30,
    "backend_plan": 40,
    "frontend_plan": 30,
    "qa_report": 20,
    "architecture_report": 30,
}

# Required heading keywords that should appear in each artifact
REQUIRED_SECTIONS: dict[str, list[str]] = {
    "pending_plan": ["overview", "requirements", "scope"],
    "backend_plan": ["endpoint", "api", "database", "schema"],
    "frontend_plan": ["component", "page", "state", "routing"],
    "qa_report": ["test case", "scenario", "coverage"],
    "architecture_report": ["deployment", "architecture", "monitoring"],
}


def _artifact_label(file_path: Path) -> str:
    """Map artifact path to a short label."""
    mapping = {
        ARTIFACTS.pending_spec: "pending_plan",
        ARTIFACTS.approved_spec: "approved_plan",
        ARTIFACTS.backend_plan: "backend_plan",
        ARTIFACTS.frontend_plan: "frontend_plan",
        ARTIFACTS.qa_report: "qa_report",
        ARTIFACTS.architecture_report: "architecture_report",
    }
    resolved_path = file_path.resolve()
    for artifact_path, label in mapping.items():
        if artifact_path.resolve() == resolved_path:
            return label
    return file_path.name


def _validate_single_artifact(file_path: Path) -> list[ValidationCheck]:
    """Run all automated checks against a single artifact file."""
    checks: list[ValidationCheck] = []
    label = _artifact_label(file_path)

    if not file_path.exists():
        checks.append(
            ValidationCheck(
                name=f"{label}: file_exists",
                passed=False,
                details=f"File not found: {file_path}",
            )
        )
        return checks

    if not file_path.is_file():
        checks.append(
            ValidationCheck(
                name=f"{label}: is_file",
                passed=False,
                details=f"Path is not a file: {file_path}",
            )
        )
        return checks

    checks.append(
        ValidationCheck(
            name=f"{label}: file_exists",
            passed=True,
            details=str(file_path),
        )
    )

    # 1. Not empty
    content = file_path.read_text(encoding="utf-8").strip()
    not_empty = len(content) > 0
    checks.append(
        ValidationCheck(
            name=f"{label}: not_empty",
            passed=not_empty,
            details=f"{len(content)} chars" if not_empty else "File is empty",
        )
    )

    if not not_empty:
        return checks

    relative_path = str(file_path)

    # 2. YAML/JSON syntax check for config files
    if file_path.suffix in (".yaml", ".yml"):
        result = validate_yaml(relative_path)
        passed = not result.startswith("Error") and not result.startswith("YAML parse error")
        checks.append(
            ValidationCheck(
                name=f"{label}: yaml_syntax",
                passed=passed,
                details=result[:200],
            )
        )
    elif file_path.suffix == ".json":
        result = validate_json(relative_path)
        passed = not result.startswith("Error") and not result.startswith("JSON parse error")
        checks.append(
            ValidationCheck(
                name=f"{label}: json_syntax",
                passed=passed,
                details=result[:200],
            )
        )

    # 3. Markdown links check
    if file_path.suffix in (".md", ".markdown"):
        result = check_markdown_links(relative_path)
        has_broken = "[BROKEN]" in result
        checks.append(
            ValidationCheck(
                name=f"{label}: markdown_links",
                passed=not has_broken,
                details=result[:300],
            )
        )

    # 4. Line count minimum
    lines_result = count_lines(str(file_path.parent), file_glob=file_path.name)
    line_count = 0
    try:
        # Parse total lines from count_lines output
        for line_text in lines_result.splitlines():
            if "Total lines:" in line_text:
                line_count = int(line_text.split("Total lines:")[1].strip().split()[0])
                break
    except (ValueError, IndexError):
        line_count = len(content.splitlines())

    min_required = MIN_LINES.get(label, 20)
    checks.append(
        ValidationCheck(
            name=f"{label}: min_lines",
            passed=line_count >= min_required,
            details=f"{line_count} lines (minimum: {min_required})",
        )
    )

    # 5. Required sections check
    if label in REQUIRED_SECTIONS:
        headings_result = extract_headings(relative_path)
        headings_lower = headings_result.lower()
        missing_sections: list[str] = []
        for keyword in REQUIRED_SECTIONS[label]:
            if keyword.lower() not in headings_lower:
                missing_sections.append(keyword)

        checks.append(
            ValidationCheck(
                name=f"{label}: required_sections",
                passed=len(missing_sections) == 0,
                details=(
                    "All required sections present"
                    if not missing_sections
                    else f"Missing sections: {', '.join(missing_sections)}"
                ),
            )
        )

    return checks


def run_validation(artifact_paths: list[Path]) -> ValidationReport:
    """
    Run all automated checks across given artifacts and return a ValidationReport.

    Args:
        artifact_paths: List of artifact file paths to validate.

    Returns:
        ValidationReport with checks, totals, and score_pct.
    """
    all_checks: list[ValidationCheck] = []

    for path in artifact_paths:
        all_checks.extend(_validate_single_artifact(path))

    total = len(all_checks)
    passed = sum(1 for c in all_checks if c.passed)
    failed = total - passed
    score_pct = round((passed / total) * 100.0, 1) if total > 0 else 100.0

    return ValidationReport(
        checks=all_checks,
        total=total,
        passed=passed,
        failed=failed,
        score_pct=score_pct,
    )


def validate_planning_artifacts() -> ValidationReport:
    """Validate the plan specification artifact."""
    return run_validation([ARTIFACTS.pending_spec])


def validate_all_delivery_artifacts() -> ValidationReport:
    """Validate all delivery phase artifacts."""
    return run_validation(
        [
            ARTIFACTS.backend_plan,
            ARTIFACTS.frontend_plan,
            ARTIFACTS.qa_report,
            ARTIFACTS.architecture_report,
        ]
    )