"""Tests for agents.state — PipelineState model."""

import pytest
from datetime import datetime

from agents.state import (
    Phase,
    ReviewDecision,
    IterationResult,
    CrossReviewResult,
    ValidationCheck,
    ValidationReport,
    QualitySummary,
    PipelineState,
)


class TestIterationResult:
    def test_defaults(self):
        r = IterationResult(score=7.5)
        assert r.score == 7.5
        assert r.criteria_scores == {}
        assert r.delta_applied is False
        assert r.delta_summary == ""

    def test_custom(self):
        r = IterationResult(
            score=8.0,
            criteria_scores={"completeness": 9, "clarity": 7},
            issues=["bad format"],
            suggestions=["add section"],
            delta_applied=True,
            delta_summary="added error handling",
        )
        assert r.score == 8.0
        assert len(r.issues) == 1
        assert len(r.suggestions) == 1

    def test_passed_false_below_threshold(self):
        r = IterationResult(score=3.0)
        assert r.passed is False

    def test_passed_true_above_threshold(self):
        r = IterationResult(score=6.0, passed=True)
        assert r.passed is True


class TestCrossReviewResult:
    def test_defaults(self):
        cr = CrossReviewResult(total_issues=5)
        assert cr.total_issues == 5
        assert cr.resolved == 0
        assert cr.remaining == 5
        assert cr.is_consistent is False

    def test_all_resolved(self):
        cr = CrossReviewResult(total_issues=3, resolved=3, is_consistent=True)
        assert cr.remaining == 0
        assert cr.is_consistent is True


class TestValidationCheck:
    def test_defaults(self):
        vc = ValidationCheck(name="broken_links", passed=True)
        assert vc.name == "broken_links"
        assert vc.passed is True
        assert vc.details == ""


class TestValidationReport:
    def test_creates_from_checks(self):
        checks = [
            ValidationCheck(name="a", passed=True),
            ValidationCheck(name="b", passed=False, details="failed"),
            ValidationCheck(name="c", passed=True),
        ]
        report = ValidationReport.from_checks(checks)
        assert report.total == 3
        assert report.passed == 2
        assert report.failed == 1
        assert report.failing_names() == ["b"]

    def test_passed_pct(self):
        checks = [ValidationCheck(name="x", passed=False)]
        report = ValidationReport.from_checks(checks)
        assert report.passed_pct == 0.0

    def test_all_passed(self):
        report = ValidationReport.from_checks([])
        assert report.all_passed is True
        assert report.passed_pct == 100.0


class TestQualitySummary:
    def test_computes_overall(self):
        qs = QualitySummary(
            overall_quality_pct=87.5,
            final_review_score=8.2,
            validation_pct=90.0,
            qa_coverage_pct=85.0,
            cross_review_issues=1,
            pipeline_passed=True,
        )
        assert qs.overall_quality_pct == 87.5
        assert qs.pipeline_passed is True


class TestPipelineState:
    def test_initial_state(self):
        ps = PipelineState(input_description="Test project")
        assert ps.input_description == "Test project"
        assert ps.current_phase == Phase.ANALYSIS
        assert ps.errors == []
        assert ps.final_quality is None

    def test_phase_transition(self):
        ps = PipelineState(input_description="Test")
        ps.transition_to(Phase.PLANNING)
        assert ps.current_phase == Phase.PLANNING

    def test_add_error(self):
        ps = PipelineState(input_description="Test")
        ps.add_error("Something went wrong")
        assert len(ps.errors) == 1
        assert ps.errors[0] == "Something went wrong"

    def test_has_errors(self):
        ps = PipelineState(input_description="Test")
        assert ps.has_errors is False
        ps.add_error("fail")
        assert ps.has_errors is True

    def test_is_plan_approved(self):
        ps = PipelineState(input_description="Test")
        assert ps.is_plan_approved is False
        ps.human_approval_decision = ReviewDecision.APPROVE
        assert ps.is_plan_approved is True

    def test_set_final_quality(self):
        ps = PipelineState(input_description="Test")
        qs = QualitySummary(
            overall_quality_pct=90.0,
            final_review_score=9.0,
            validation_pct=95.0,
            qa_coverage_pct=88.0,
            cross_review_issues=0,
            pipeline_passed=True,
        )
        ps.set_final_quality(qs)
        assert ps.final_quality is not None
        assert ps.final_quality.pipeline_passed is True

    def test_latest_plan_score_empty(self):
        ps = PipelineState(input_description="Test")
        assert ps.latest_plan_score is None

    def test_latest_plan_score_has_value(self):
        ps = PipelineState(input_description="Test")
        ps.plan_iterations = [
            IterationResult(score=5.0),
            IterationResult(score=8.0),
        ]
        assert ps.latest_plan_score == 8.0