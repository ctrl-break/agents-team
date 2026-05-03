"""Tests for agents.quality — quality metrics and thresholds."""

import pytest

from agents.quality import (
    ReviewCriterion,
    PLAN_REVIEW_CRITERIA,
    IMPL_REVIEW_CRITERIA,
    PipelineThresholds,
    DEFAULT_THRESHOLDS,
    compute_iteration_score,
    meets_threshold,
    compute_validation_pct,
    compute_overall_quality,
    is_pipeline_successful,
)
from agents.state import ValidationReport, ValidationCheck


class TestReviewCriterion:
    def test_default_weight(self):
        c = ReviewCriterion(key="test", label="Test", description="Desc")
        assert c.weight == 1.0

    def test_custom_weight(self):
        c = ReviewCriterion(key="test", label="Test", description="Desc", weight=0.5)
        assert c.weight == 0.5


class TestCriteriaPresence:
    def test_plan_criteria_have_required_fields(self):
        for c in PLAN_REVIEW_CRITERIA:
            assert c.key
            assert c.label
            assert c.description
            assert c.weight > 0

    def test_impl_criteria_have_required_fields(self):
        for c in IMPL_REVIEW_CRITERIA:
            assert c.key
            assert c.label
            assert c.description
            assert c.weight > 0


class TestComputeIterationScore:
    def test_weighted_average_basic(self):
        scores = {"completeness": 8, "clarity": 6, "edge_cases": 9}
        result = compute_iteration_score(scores, PLAN_REVIEW_CRITERIA)
        # Weights: 1.0, 1.0, 0.8 → (8*1 + 6*1 + 9*0.8) / (1+1+0.8) = 21.2/2.8 ≈ 7.57
        assert 7.5 <= result <= 7.6

    def test_empty_scores_returns_zero(self):
        assert compute_iteration_score({}) == 0.0

    def test_custom_criteria(self):
        custom = [ReviewCriterion(key="a", label="A", description="", weight=2.0)]
        assert compute_iteration_score({"a": 10}, custom) == 10.0

    def test_unknown_keys_get_default_weight(self):
        scores = {"unknown_key": 10}
        result = compute_iteration_score(scores)
        assert result == 10.0

    def test_mixed_known_and_unknown(self):
        scores = {"completeness": 4, "unknown": 10}
        result = compute_iteration_score(scores, PLAN_REVIEW_CRITERIA)
        # completeness weight=1.0, unknown weight=1.0 (default)
        # (4*1 + 10*1) / 2 = 7.0
        assert result == 7.0


class TestMeetsThreshold:
    def test_exceeds(self):
        assert meets_threshold(8.0, 7.0) is True

    def test_equals(self):
        assert meets_threshold(7.0, 7.0) is True

    def test_below(self):
        assert meets_threshold(6.9, 7.0) is False


class TestComputeValidationPct:
    def test_all_passed(self):
        checks = [
            ValidationCheck(name="a", passed=True),
            ValidationCheck(name="b", passed=True),
        ]
        report = ValidationReport.from_checks(checks)
        assert compute_validation_pct(report) == 100.0

    def test_half_passed(self):
        checks = [
            ValidationCheck(name="a", passed=True),
            ValidationCheck(name="b", passed=False),
        ]
        report = ValidationReport.from_checks(checks)
        assert compute_validation_pct(report) == 50.0

    def test_empty_checks(self):
        report = ValidationReport.from_checks([])
        assert compute_validation_pct(report) == 100.0


class TestComputeOverallQuality:
    def test_perfect_scores(self):
        result = compute_overall_quality(
            review_score=10.0,
            validation_pct=100.0,
            qa_coverage_pct=100.0,
            cross_review_issues=0,
        )
        # 40 + 30 + 20 + 10 = 100
        assert result == 100.0

    def test_zero_scores(self):
        result = compute_overall_quality(
            review_score=0.0,
            validation_pct=0.0,
            qa_coverage_pct=0.0,
            cross_review_issues=10,
        )
        # 0 + 0 + 0 + max(0, 10-50) = 0
        assert result >= 0.0

    def test_mid_range(self):
        result = compute_overall_quality(
            review_score=7.5,
            validation_pct=80.0,
            qa_coverage_pct=90.0,
            cross_review_issues=2,
        )
        # review: (7.5/10)*100*0.4 = 30
        # validation: 80*0.3 = 24
        # qa: 90*0.2 = 18
        # cross_review: max(0, 10-10) = 0
        # Total: 30 + 24 + 18 + 0 = 72
        assert result == 72.0

    def test_cross_review_penalty_capped(self):
        result = compute_overall_quality(
            review_score=10.0,
            validation_pct=100.0,
            qa_coverage_pct=100.0,
            cross_review_issues=10,
        )
        # cross_review: max(0, 10-50) = 0
        # Total: 40+30+20+0 = 90
        assert result == 90.0


class TestIsPipelineSuccessful:
    def test_above_threshold(self):
        assert is_pipeline_successful(90.0) is True

    def test_below_threshold(self):
        assert is_pipeline_successful(70.0) is False

    def test_exact_threshold(self):
        assert is_pipeline_successful(85.0) is True

    def test_custom_thresholds(self):
        custom = PipelineThresholds(final_quality_threshold_pct=70.0)
        assert is_pipeline_successful(75.0, custom) is True
        assert is_pipeline_successful(65.0, custom) is False


class TestPipelineThresholds:
    def test_defaults(self):
        assert DEFAULT_THRESHOLDS.plan_max_iterations == 3
        assert DEFAULT_THRESHOLDS.plan_review_score_threshold == 7.0
        assert DEFAULT_THRESHOLDS.final_quality_threshold_pct == 85.0
        assert DEFAULT_THRESHOLDS.max_errors_before_abort == 5

    def test_custom_override(self):
        custom = PipelineThresholds(
            plan_max_iterations=5,
            impl_review_score_threshold=8.5,
            final_quality_threshold_pct=90.0,
        )
        assert custom.plan_max_iterations == 5
        assert custom.impl_review_score_threshold == 8.5
        assert custom.final_quality_threshold_pct == 90.0
        # Unchanged defaults
        assert custom.max_errors_before_abort == 5