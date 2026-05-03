"""Tests for agents.state — PipelineState model."""

import pytest

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
        r = IterationResult(iteration=1, output="draft plan", score=7.5)
        assert r.score == 7.5
        assert r.iteration == 1
        assert r.output == "draft plan"
        assert r.criteria_scores == {}
        assert r.issues == []
        assert r.suggestions == []
        assert r.decision == ReviewDecision.REVISIONS_NEEDED

    def test_custom(self):
        r = IterationResult(
            iteration=2,
            output="improved plan",
            score=8.0,
            criteria_scores={"completeness": 9, "clarity": 7},
            issues=["bad format"],
            suggestions=["add section"],
        )
        assert r.score == 8.0
        assert r.iteration == 2
        assert r.output == "improved plan"
        assert len(r.issues) == 1
        assert len(r.suggestions) == 1
        assert r.criteria_scores["completeness"] == 9

    def test_passed_false_below_threshold(self):
        r = IterationResult(iteration=1, output="bad plan", score=3.0)
        assert r.score < 6.0

    def test_passed_true_above_threshold(self):
        r = IterationResult(iteration=1, output="good plan", score=8.0)
        assert r.score >= 6.0


class TestCrossReviewResult:
    def test_defaults(self):
        cr = CrossReviewResult()
        assert cr.conflicts == []
        assert cr.resolved is False
        assert cr.backend_review_of_frontend == ""
        assert cr.frontend_review_of_backend == ""

    def test_with_conflicts(self):
        cr = CrossReviewResult(
            conflicts=["api_version mismatch", "db_schema conflict"],
            resolved=False,
        )
        assert len(cr.conflicts) == 2
        assert cr.resolved is False

    def test_all_resolved(self):
        cr = CrossReviewResult(
            conflicts=["api_version mismatch"],
            resolved=True,
        )
        assert cr.resolved is True
        assert len(cr.conflicts) == 1


class TestValidationCheck:
    def test_defaults(self):
        vc = ValidationCheck(name="broken_links", passed=True)
        assert vc.name == "broken_links"
        assert vc.passed is True
        assert vc.details == ""

    def test_failed_check(self):
        vc = ValidationCheck(name="yaml_valid", passed=False, details="parse error")
        assert vc.passed is False
        assert vc.details == "parse error"


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

    def test_is_clean(self):
        checks = [ValidationCheck(name="x", passed=True)]
        report = ValidationReport.from_checks(checks)
        assert report.is_clean is True


class TestQualitySummary:
    def test_defaults(self):
        qs = QualitySummary()
        assert qs.overall_score_pct == 0.0
        assert qs.passed is False
        assert qs.plan_iterations == 0
        assert qs.final_review_score == 0.0
        assert qs.cross_review_issues == 0

    def test_computes_overall(self):
        qs = QualitySummary(
            overall_score_pct=87.5,
            final_review_score=8.2,
            cross_review_issues=1,
            qa_coverage_pct=85.0,
            passed=True,
        )
        assert qs.overall_score_pct == 87.5
        assert qs.passed is True

    def test_sections(self):
        qs = QualitySummary(
            sections_complete=4,
            sections_expected=5,
            broken_links=2,
        )
        assert qs.sections_complete == 4
        assert qs.sections_expected == 5
        assert qs.broken_links == 2


class TestPipelineState:
    def test_initial_state(self):
        ps = PipelineState(request="Test project")
        assert ps.request == "Test project"
        assert ps.current_phase == Phase.ANALYSIS
        assert ps.errors == []
        assert ps.quality == QualitySummary()

    def test_default_request_is_empty(self):
        ps = PipelineState()
        assert ps.request == ""

    def test_phase_can_be_changed(self):
        ps = PipelineState(request="Test")
        ps.current_phase = Phase.PLANNING
        assert ps.current_phase == Phase.PLANNING

    def test_add_error(self):
        ps = PipelineState(request="Test")
        ps.errors.append("Something went wrong")
        assert len(ps.errors) == 1
        assert ps.errors[0] == "Something went wrong"

    def test_has_errors(self):
        ps = PipelineState(request="Test")
        assert ps.has_errors is False
        ps.errors.append("fail")
        assert ps.has_errors is True

    def test_is_plan_approved(self):
        ps = PipelineState(request="Test")
        assert ps.is_plan_approved is False
        ps.approved_spec = "approved plan content"
        assert ps.is_plan_approved is True

    def test_set_final_quality(self):
        ps = PipelineState(request="Test")
        qs = QualitySummary(
            overall_score_pct=90.0,
            final_review_score=9.0,
            cross_review_issues=0,
            qa_coverage_pct=88.0,
            passed=True,
        )
        ps.quality = qs
        assert ps.quality is not None
        assert ps.quality.passed is True

    def test_latest_plan_score_empty(self):
        ps = PipelineState(request="Test")
        assert ps.latest_plan_score == 0.0

    def test_latest_plan_score_has_value(self):
        ps = PipelineState(request="Test")
        ps.plan_iterations = [
            IterationResult(iteration=1, output="draft1", score=5.0),
            IterationResult(iteration=2, output="draft2", score=8.0),
        ]
        assert ps.latest_plan_score == 8.0

    def test_serialization_roundtrip(self):
        ps = PipelineState(
            request="Build a todo app",
            current_phase=Phase.PLANNING,
            analysis_brief="Analyzed",
            errors=["warning: incomplete"],
        )
        json_str = ps.model_dump_json()
        restored = PipelineState.model_validate_json(json_str)
        assert restored.request == "Build a todo app"
        assert restored.current_phase == Phase.PLANNING
        assert restored.errors == ["warning: incomplete"]