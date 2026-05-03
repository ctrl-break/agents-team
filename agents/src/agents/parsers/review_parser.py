"""Parse structured review outputs into Python dataclasses.

Extracts numeric scores, verdicts, and issues from markdown review artifacts
produced by the Technical Reviewer and Cross-Reviewer agents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DimensionScore:
    """A single scored dimension from a review."""

    dimension: str
    score: float
    notes: str = ""


@dataclass
class ArtifactReview:
    """Per-artifact review result parsed from tech-review.md."""

    artifact_path: str
    dimensions: list[DimensionScore] = field(default_factory=list)
    average_score: float = 0.0
    verdict: str = ""  # APPROVE / REVISE / REJECT
    risks: list[str] = field(default_factory=list)


@dataclass
class PairScore:
    """A single cross-review pair score."""

    pair: str
    score: float
    gaps: str = ""


@dataclass
class ParsedCrossReview:
    """Parsed cross-review output from markdown."""

    pairs: list[PairScore] = field(default_factory=list)
    average_score: float = 0.0
    blocking_count: int = 0
    misaligned_count: int = 0
    consistent_count: int = 0
    verdict: str = ""  # CONSISTENT / MISALIGNED / BLOCKED
    blocking_items: list[str] = field(default_factory=list)

    @property
    def issues_count(self) -> int:
        """Total non-consistent issues."""
        return self.misaligned_count + self.blocking_count


# ── Table parsing helpers ──────────────────────────────────────────────


def _parse_score_table(markdown_text: str) -> list[DimensionScore]:
    """Parse a markdown table with columns: Dimension | Score | Notes.

    Expects rows like:
      | clarity    | 8 | justification text |
      | completeness | 7 | notes here       |
    """
    dimensions: list[DimensionScore] = []

    # Match table rows: | name | number | text |
    row_pattern = re.compile(
        r"^\|\s*([a-zA-Z_↔\s-]+?)\s*\|\s*(\d+(?:\.\d+)?)\s*\|\s*(.+?)\s*\|",
        re.MULTILINE,
    )

    for match in row_pattern.finditer(markdown_text):
        dim_name = match.group(1).strip()
        # Skip header rows
        if dim_name.lower() in ("dimension", "pair", "---", ":-"):
            continue
        try:
            score = float(match.group(2))
        except ValueError:
            continue
        notes = match.group(3).strip()
        dimensions.append(
            DimensionScore(dimension=dim_name, score=score, notes=notes)
        )

    return dimensions


def _parse_average(text: str, section: str = "") -> Optional[float]:
    """Extract 'average score: X.X' or 'average: X.X' from text.

    Handles markdown bold like **Average Score:** 7.5.

    Args:
        text: The text to search.
        section: Optional section label to narrow search (e.g. 'Summary').

    Returns:
        Parsed float or None.
    """
    # Strip markdown bold markers for pattern matching
    clean = re.sub(r"\*{1,2}", "", text)

    patterns = [
        r"average\s+score\s*[:：]\s*(\d+(?:\.\d+)?)",
        r"average\s*[:：]\s*(\d+(?:\.\d+)?)",
        r"overall\s+average\s*[:：]\s*(\d+(?:\.\d+)?)",
        r"cross-review\s+average\s*[:：]\s*(\d+(?:\.\d+)?)",
    ]

    search_text = text
    if section:
        # Find the section first
        section_match = re.search(
            rf"#+\s*{re.escape(section)}.*?(?=#+\s|\Z)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if section_match:
            search_text = section_match.group(0)

    for pat in patterns:
        m = re.search(pat, search_text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue

    return None


def _parse_verdict(text: str) -> str:
    """Extract verdict: APPROVE / REVISE / REJECT or CONSISTENT / MISALIGNED / BLOCKED.

    Handles markdown formatting like **Overall Verdict:** APPROVE
    where bold markers may wrap the entire phrase including the colon.
    """
    # Strip all markdown bold/italic markers for reliable pattern matching
    clean = re.sub(r"\*{1,2}", "", text)

    verdict_pattern = re.compile(
        r"(?:overall\s+)?verdict\s*[:：]\s*(APPROVE|REVISE|REJECT|CONSISTENT|MISALIGNED|BLOCKED)",
        re.IGNORECASE,
    )
    m = verdict_pattern.search(clean)
    if m:
        return m.group(1).upper()
    return ""


def _parse_risks(text: str) -> list[str]:
    """Extract bullet-point risks from a 'key risks' or 'risks' section.

    Handles markdown bold like **Key Risks:** or **Key Risks**:
    """
    risks: list[str] = []

    # Strip bold markers for section header matching
    clean = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)

    # Find risks section
    section_match = re.search(
        r"(?:key\s+)?risks?\s*[:：]?\s*\n((?:\s*[-*]\s*.+\n?)+)",
        clean,
        re.IGNORECASE,
    )
    if section_match:
        risk_text = section_match.group(1)
        for line in risk_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("-") or stripped.startswith("*"):
                risk = stripped.lstrip("-* ").strip()
                if risk:
                    risks.append(risk)

    return risks


def _parse_blocking_items(text: str) -> list[str]:
    """Extract blocking inconsistency items.

    Handles markdown bold like **Blocking Inconsistencies:**
    """
    items: list[str] = []

    # Strip bold markers for section header matching
    clean = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)

    section_match = re.search(
        r"(?:blocking\s+inconsistencies?|blocked\s+items?)\s*[:：]?\s*\n((?:\s*[-*]\s*.+\n?)+)",
        clean,
        re.IGNORECASE,
    )
    if section_match:
        item_text = section_match.group(1)
        for line in item_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("-") or stripped.startswith("*"):
                item = stripped.lstrip("-* ").strip()
                if item:
                    items.append(item)

    return items


# ── Public API ─────────────────────────────────────────────────────────


def parse_tech_review(text: str) -> list[ArtifactReview]:
    """Parse tech-review.md output into structured ArtifactReview objects.

    The tech review contains one section per artifact, each with:
    - A scoring table (dimension → score → notes)
    - A summary with average score, verdict, and risks.

    Args:
        text: Raw markdown output from the technical reviewer.

    Returns:
        List of ArtifactReview, one per reviewed artifact.
    """
    artifacts: list[ArtifactReview] = []

    # Split by artifact sections: "## Artifact: <path>"
    artifact_pattern = re.compile(
        r"##\s+Artifact:\s*(.+?)\n(.*?)(?=##\s+Artifact:|\Z)",
        re.DOTALL,
    )

    for match in artifact_pattern.finditer(text):
        artifact_path = match.group(1).strip()
        section_text = match.group(2)

        dimensions = _parse_score_table(section_text)
        avg = _parse_average(section_text) or 0.0
        verdict = _parse_verdict(section_text)
        risks = _parse_risks(section_text)

        # If no explicit average, compute from dimensions
        if avg == 0.0 and dimensions:
            avg = sum(d.score for d in dimensions) / len(dimensions)

        artifacts.append(
            ArtifactReview(
                artifact_path=artifact_path,
                dimensions=dimensions,
                average_score=round(avg, 1),
                verdict=verdict,
                risks=risks,
            )
        )

    return artifacts


def parse_cross_review(text: str) -> ParsedCrossReview:
    """Parse cross-review.md output into structured ParsedCrossReview.

    Extracts pair scores, average, verdict, and blocking inconsistencies.

    Args:
        text: Raw markdown output from the cross-reviewer.

    Returns:
        ParsedCrossReview with all parsed metrics.
    """
    pairs: list[PairScore] = []

    # Parse pair table (same format as dimension table but with pair names)
    dimensions = _parse_score_table(text)
    for d in dimensions:
        pairs.append(PairScore(pair=d.dimension, score=d.score, gaps=d.notes))

    avg = _parse_average(text) or 0.0

    # Compute from pairs if no explicit average
    if avg == 0.0 and pairs:
        avg = sum(p.score for p in pairs) / len(pairs)

    verdict = _parse_verdict(text)

    # Count blocking/misaligned mentions
    blocking_count = len(re.findall(r"\bBLOCKED\b", text))
    misaligned_count = len(re.findall(r"\bMISALIGNED\b", text, re.IGNORECASE))
    consistent_count = len(re.findall(r"\bCONSISTENT\b", text, re.IGNORECASE))

    blocking_items = _parse_blocking_items(text)

    return ParsedCrossReview(
        pairs=pairs,
        average_score=round(avg, 1),
        blocking_count=blocking_count,
        misaligned_count=misaligned_count,
        consistent_count=consistent_count,
        verdict=verdict,
        blocking_items=blocking_items,
    )


def parse_review_file(file_path: str | Path) -> list[ArtifactReview]:
    """Convenience: read and parse a tech-review file from disk."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Review file not found: {path}")
    text = path.read_text(encoding="utf-8")
    return parse_tech_review(text)


def parse_cross_review_file(file_path: str | Path) -> ParsedCrossReview:
    """Convenience: read and parse a cross-review file from disk."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Cross-review file not found: {path}")
    text = path.read_text(encoding="utf-8")
    return parse_cross_review(text)
