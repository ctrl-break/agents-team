"""
Quality metrics and thresholds for the SpecPipeline.

Defines scoring criteria, quality thresholds, and helper functions
for computing the overall quality of generated artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from agents.state import ValidationReport


# ── Scoring Criteria ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ReviewCriterion:
    """A single criterion used by the Review Crew."""

    key: str
    label: str
    description: str
    weight: float = 1.0  # relative weight in overall score


# Критерии для ревью спецификации (Planning Phase)
PLAN_REVIEW_CRITERIA: list[ReviewCriterion] = [
    ReviewCriterion(
        key="completeness",
        label="Completeness",
        description="All required sections are present and fully addressed",
        weight=1.0,
    ),
    ReviewCriterion(
        key="clarity",
        label="Clarity",
        description="Requirements are unambiguous and well-structured",
        weight=1.0,
    ),
    ReviewCriterion(
        key="edge_cases",
        label="Edge Cases",
        description="Error states, boundary conditions, and edge cases are covered",
        weight=0.8,
    ),
    ReviewCriterion(
        key="feasibility",
        label="Feasibility",
        description="The spec is realistically implementable with described resources",
        weight=0.7,
    ),
    ReviewCriterion(
        key="consistency",
        label="Consistency",
        description="No internal contradictions between sections",
        weight=1.0,
    ),
]

# Критерии для ревью backend/frontend планов
IMPL_REVIEW_CRITERIA: list[ReviewCriterion] = [
    ReviewCriterion(
        key="spec_alignment",
        label="Spec Alignment",
        description="Every requirement from the approved spec is addressed",
        weight=1.5,
    ),
    ReviewCriterion(
        key="technical_depth",
        label="Technical Depth",
        description="Technology choices, architecture decisions, and rationale are detailed",
        weight=1.0,
    ),
    ReviewCriterion(
        key="api_contract",
        label="API Contract",
        description="API endpoints are fully specified (method, path, request/response schemas)",
        weight=1.2,
    ),
    ReviewCriterion(
        key="security",
        label="Security & Auth",
        description="Authentication, authorization, and security considerations are addressed",
        weight=0.8,
    ),
    ReviewCriterion(
        key="error_handling",
        label="Error Handling",
        description="Error scenarios and fallback strategies are described",
        weight=0.5,
    ),
]


# ── Thresholds ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PipelineThresholds:
    """All configurable quality thresholds for the pipeline."""

    # Planning phase
    plan_max_iterations: int = 3
    plan_review_score_threshold: float = 7.0  # 0-10, below → re-iterate

    # Human approval
    max_approval_rounds: int = 3

    # Implementation phase
    impl_max_iterations: int = 2
    impl_review_score_threshold: float = 7.0

    # Cross-review
    cross_review_max_iterations: int = 2

    # Final validation (Phase 5)
    final_quality_threshold_pct: float = 85.0  # percentage

    # QA
    qa_min_coverage_pct: float = 80.0

    # General
    max_errors_before_abort: int = 5


# Default thresholds — can be overridden via pipeline.yaml
DEFAULT_THRESHOLDS = PipelineThresholds()


# ── Quality Computation ──────────────────────────────────────────────────────


def compute_iteration_score(
    criteria_scores: dict[str, float],
    criteria_defs: Optional[list[ReviewCriterion]] = None,
) -> float:
    """
    Compute weighted average score from individual criterion scores.

    Args:
        criteria_scores: Dict mapping criterion key → score (0-10).
        criteria_defs: List of criteria with weights. Uses PLAN_REVIEW_CRITERIA
                       if not provided.

    Returns:
        Weighted average score (0.0–10.0).
    """
    if not criteria_scores:
        return 0.0

    defs = criteria_defs or PLAN_REVIEW_CRITERIA
    weight_map = {c.key: c.weight for c in defs}

    total_weight = 0.0
    weighted_sum = 0.0

    for key, score in criteria_scores.items():
        weight = weight_map.get(key, 1.0)
        weighted_sum += score * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return round(weighted_sum / total_weight, 2)


def meets_threshold(score: float, threshold: float) -> bool:
    """Check if a score meets the threshold."""
    return score >= threshold


def compute_validation_pct(report: ValidationReport) -> float:
    """
    Compute validation score as percentage of passed checks.

    Args:
        report: ValidationReport with checks and their pass/fail status.

    Returns:
        Percentage (0.0–100.0).
    """
    if report.total == 0:
        return 100.0
    return round((report.passed / report.total) * 100.0, 1)


def compute_overall_quality(
    review_score: float,
    validation_pct: float,
    qa_coverage_pct: float = 0.0,
    cross_review_issues: int = 0,
) -> float:
    """
    Compute overall quality percentage from weighted components.

    Weights:
        - Review score (0-10 → mapped to 0-100): 40%
        - Validation checks passed: 30%
        - QA coverage: 20%
        - Cross-review cleanliness: 10%

    Args:
        review_score: Final review score (0-10).
        validation_pct: Percentage of validation checks passed.
        qa_coverage_pct: QA test coverage percentage.
        cross_review_issues: Number of unresolved cross-review issues.

    Returns:
        Overall quality percentage (0–100).
    """
    review_component = (review_score / 10.0) * 100.0 * 0.4
    validation_component = validation_pct * 0.3
    qa_component = qa_coverage_pct * 0.2

    cross_review_penalty = min(cross_review_issues * 5, 10)
    cross_review_component = max(0, 10 - cross_review_penalty)

    return round(review_component + validation_component + qa_component + cross_review_component, 1)


def is_pipeline_successful(
    overall_quality_pct: float,
    thresholds: Optional[PipelineThresholds] = None,
) -> bool:
    """
    Determine if the pipeline produced acceptable results.

    Args:
        overall_quality_pct: Overall quality percentage.
        thresholds: PipelineThresholds to compare against.

    Returns:
        True if quality meets or exceeds the threshold.
    """
    t = thresholds or DEFAULT_THRESHOLDS
    return overall_quality_pct >= t.final_quality_threshold_pct