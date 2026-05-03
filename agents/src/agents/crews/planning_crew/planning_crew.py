"""Build the planning crew — PM analyses request → specification."""

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
    extract_headings,
    search_code,
)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
ARTIFACTS = build_artifact_paths()


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_pm_agent() -> Agent:
    agents_cfg = _load_yaml(CONFIG_DIR / "agents.yaml")
    return Agent(
        config=agents_cfg["product_manager"],
        llm=build_llm(),
        tools=[read_text_file, list_files, search_code, check_markdown_links, extract_headings],
        verbose=True,
    )


def build_planning_crew(user_request: str, feedback: str = "") -> Crew:
    """Return a Crew that generates a draft specification for the given request.

    Args:
        user_request: The original project request text.
        feedback: Optional human feedback from a rejected plan iteration.
                  When provided, the agent will incorporate this feedback
                  into the regenerated specification.
    """
    agent = _build_pm_agent()
    tasks_cfg = _load_yaml(CONFIG_DIR / "tasks.yaml")

    description = tasks_cfg["pm_spec_task"]["description"]
    description += f"\n\nProject request:\n{user_request}"

    if feedback.strip():
        description += (
            f"\n\n⚠️ IMPORTANT: The previous plan was rejected with the following feedback."
            f"\nPlease address ALL of these concerns in the revised specification:\n\n"
            f"{feedback}"
        )

    description += (
        f"\n\nSave the draft specification to: {ARTIFACTS.pending_spec.as_posix()}"
    )

    task = Task(
        description=description,
        expected_output=tasks_cfg["pm_spec_task"]["expected_output"],
        agent=agent,
        output_file=str(ARTIFACTS.pending_spec),
        markdown=True,
    )

    return Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )
