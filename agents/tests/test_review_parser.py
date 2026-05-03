"""Tests for review_parser.py — parsing markdown scoring tables."""

import textwrap

from agents.parsers.review_parser import (
    parse_tech_review,
    parse_cross_review,
    ArtifactReview,
    ParsedCrossReview,
)


# ── Sample markdown outputs (matching expected format from tasks.yaml) ──

SAMPLE_TECH_REVIEW = textwrap.dedent("""\
    # Technical Review

    ## Artifact: docs/backend-plan.md

    | Dimension     | Score | Notes                                |
    |---------------|-------|--------------------------------------|
    | clarity       | 8     | Well-structured, minor ambiguity     |
    | completeness  | 7     | Missing edge case for auth flow      |
    | technical_depth | 6   | Needs more detail on DB schema       |
    | actionability | 9     | Clear tasks, ready to implement      |
    | consistency   | 7     | Aligns with spec, one contradiction  |

    **Average Score:** 7.4

    **Overall Verdict:** APPROVE

    **Key Risks:**
    - DB schema design may need revision
    - Auth flow not fully specified

    ## Artifact: docs/frontend-plan.md

    | Dimension     | Score | Notes                                |
    |---------------|-------|--------------------------------------|
    | clarity       | 5     | Component tree is confusing          |
    | completeness  | 4     | Missing states documentation         |
    | technical_depth | 4   | API integration lacks detail         |
    | actionability | 3     | Cannot start from this               |
    | consistency   | 5     | Conflicts with backend-plan on API   |

    **Average Score:** 4.2

    **Overall Verdict:** REJECT

    **Key Risks:**
    - Component structure undefined
    - State management unclear
    - API contract mismatch
""")


SAMPLE_CROSS_REVIEW = textwrap.dedent("""\
    # Cross-Review

    | Pair                    | Score | Notes                                    |
    |-------------------------|-------|------------------------------------------|
    | backend↔frontend        | 6     | API contract mostly aligned, minor gaps  |
    | qa↔backend             | 7     | Test scenarios cover backend well         |
    | qa↔frontend            | 8     | Frontend tests are comprehensive          |
    | architecture↔backend   | 5     | DB choice conflicts with arch guidelines  |
    | architecture↔frontend  | 7     | Component structure follows arch pattern  |

    **Cross-Review Average:** 6.6

    **Overall Verdict:** MISALIGNED

    **Blocking Inconsistencies:**
    - DB choice (SQLite vs Postgres) conflicts with architecture doc
    - API versioning not consistent across backend and frontend plans
""")


# ── Tests ──────────────────────────────────────────────────────────────


class TestParseTechReview:
    def test_parses_two_artifacts(self):
        reviews = parse_tech_review(SAMPLE_TECH_REVIEW)
        assert len(reviews) == 2

    def test_first_artifact_path(self):
        reviews = parse_tech_review(SAMPLE_TECH_REVIEW)
        assert reviews[0].artifact_path == "docs/backend-plan.md"

    def test_first_artifact_dimensions(self):
        reviews = parse_tech_review(SAMPLE_TECH_REVIEW)
        assert len(reviews[0].dimensions) == 5
        assert reviews[0].dimensions[0].dimension == "clarity"
        assert reviews[0].dimensions[0].score == 8.0
        assert "Well-structured" in reviews[0].dimensions[0].notes

    def test_first_artifact_average(self):
        reviews = parse_tech_review(SAMPLE_TECH_REVIEW)
        assert reviews[0].average_score == 7.4

    def test_first_artifact_verdict(self):
        reviews = parse_tech_review(SAMPLE_TECH_REVIEW)
        assert reviews[0].verdict == "APPROVE"

    def test_first_artifact_risks(self):
        reviews = parse_tech_review(SAMPLE_TECH_REVIEW)
        assert len(reviews[0].risks) == 2
        assert "DB schema" in reviews[0].risks[0]
        assert "Auth flow" in reviews[0].risks[1]

    def test_second_artifact_verdict_reject(self):
        reviews = parse_tech_review(SAMPLE_TECH_REVIEW)
        assert reviews[1].verdict == "REJECT"

    def test_second_artifact_low_scores(self):
        reviews = parse_tech_review(SAMPLE_TECH_REVIEW)
        assert reviews[1].average_score == 4.2
        assert reviews[1].dimensions[3].score == 3.0  # actionability

    def test_empty_text_returns_empty(self):
        reviews = parse_tech_review("")
        assert reviews == []

    def test_no_artifact_sections_returns_empty(self):
        reviews = parse_tech_review("# No artifacts here")
        assert reviews == []


class TestParseCrossReview:
    def test_parses_pairs(self):
        result = parse_cross_review(SAMPLE_CROSS_REVIEW)
        assert len(result.pairs) == 5

    def test_pair_names(self):
        result = parse_cross_review(SAMPLE_CROSS_REVIEW)
        names = [p.pair for p in result.pairs]
        assert "backend↔frontend" in names
        assert "qa↔backend" in names

    def test_pair_scores(self):
        result = parse_cross_review(SAMPLE_CROSS_REVIEW)
        scores = {p.pair: p.score for p in result.pairs}
        assert scores["backend↔frontend"] == 6.0
        assert scores["architecture↔backend"] == 5.0

    def test_average_score(self):
        result = parse_cross_review(SAMPLE_CROSS_REVIEW)
        assert result.average_score == 6.6

    def test_verdict(self):
        result = parse_cross_review(SAMPLE_CROSS_REVIEW)
        assert result.verdict == "MISALIGNED"

    def test_blocking_items(self):
        result = parse_cross_review(SAMPLE_CROSS_REVIEW)
        assert len(result.blocking_items) == 2
        assert any("DB choice" in item for item in result.blocking_items)

    def test_issues_count(self):
        result = parse_cross_review(SAMPLE_CROSS_REVIEW)
        assert result.issues_count >= 1

    def test_empty_text(self):
        result = parse_cross_review("")
        assert result.pairs == []
        assert result.average_score == 0.0
        assert result.verdict == ""