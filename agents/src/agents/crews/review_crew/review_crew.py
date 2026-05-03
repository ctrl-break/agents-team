"""Build the review crew — Technical Reviewer + Cross-Reviewer with numeric scoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from crewai import Agent, Task, Crew, Process

from agents.artifacts import build_artifact_paths
from agents.llm_factory import build_llm
from agents.tools.file_tools import list_files, read_text_file
from agents.tools.common_tools import (
    check_markdown_links,
    count_lines,
    extract_headings,
    search_code,
)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
ARTIFACTS = build_artifact_paths()

REVIEW_OUTPUT_DIR = ARTIFACTS.approved_spec.parent.parent / "reviews"


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_tech_reviewer_agent() -> Agent:
    agents_cfg = _load_yaml(CONFIG_DIR / "agents.yaml")
    return Agent(
        config=agents_cfg["technical_reviewer"],
        llm=build_llm(),
        tools=[read_text_file, list_files, search_code, extract_headings, count_lines],
        verbose=True,
    )


def _build_cross_reviewer_agent() -> Agent:
    agents_cfg = _load_yaml(CONFIG_DIR / "agents.yaml")
    return Agent(
        config=agents_cfg["cross_reviewer"],
        llm=build_llm(),
        tools=[read_text_file, list_files, search_code, check_markdown_links, extract_headings],
        verbose=True,
    )


def build_tech_review_crew(artifact_paths: list[str], artifact_kind: str = "plan") -> Crew:
    """
    Build a Crew that runs the Technical Reviewer against one or more artifacts.

    Args:
        artifact_paths: Relative or absolute paths to artifact files to review.
        artifact_kind: Label for the kind of artifacts ("plan" or "implementation").

    Returns:
        Crew configured with the technical review task.
    """
    agent = _build_tech_reviewer_agent()
    tasks_cfg = _load_yaml(CONFIG_DIR / "tasks.yaml")

    artifact_lines = "\n".join(f"  - {p}" for p in artifact_paths)
    description = (
        tasks_cfg["tech_review_task"]["description"]
        + "\n\n"
        + f"Artifact kind: {artifact_kind}\n\n"
        + f"Artifacts to review:\n{artifact_lines}\n\n"
        + "IMPORTANT: Read each artifact file before scoring it. "
        + "Use read_text_file to read the files, and extract_headings to check structure. "
        + "Use count_lines to verify document length is adequate."
    )

    task = Task(
        description=description,
        expected_output=tasks_cfg["tech_review_task"]["expected_output"],
        agent=agent,
        output_file=str(REVIEW_OUTPUT_DIR / "tech-review.md"),
        markdown=True,
    )

    return Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )


def build_cross_review_crew(artifact_paths: list[str]) -> Crew:
    """
    Build a Crew that runs the Cross-Reviewer to check consistency across artifacts.

    Expected artifact_paths order: [backend_plan, frontend_plan, qa_report, architecture_report]

    Args:
        artifact_paths: Paths to all implementation artifacts.

    Returns:
        Crew configured with the cross-review task.
    """
    agent = _build_cross_reviewer_agent()
    tasks_cfg = _load_yaml(CONFIG_DIR / "tasks.yaml")

    artifact_lines = "\n".join(f"  - {p}" for p in artifact_paths)
    description = (
        tasks_cfg["cross_review_task"]["description"]
        + "\n\n"
        + f"Artifacts to cross-review:\n{artifact_lines}\n\n"
        + "IMPORTANT: Read ALL artifact files before comparing them. "
        + "Use read_text_file to read each file. "
        + "Use extract_headings to compare document structures. "
        + "Use check_markdown_links to validate internal cross-references between artifacts."
    )

    task = Task(
        description=description,
        expected_output=tasks_cfg["cross_review_task"]["expected_output"],
        agent=agent,
        output_file=str(REVIEW_OUTPUT_DIR / "cross-review.md"),
        markdown=True,
    )

    return Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )