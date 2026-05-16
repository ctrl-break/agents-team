"""Build the planning crew — PM analyses request → specification."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from crewai import Agent, Task, Crew, Process

from agents.artifacts import build_artifact_paths
from agents.llm_factory import build_llm
from agents.state import TechStack, DirectoryLayout
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


def parse_tech_stack(spec_text: str) -> TechStack:
    """Extract Technology Stack from a generated specification.

    Parses the "## Technology Stack" section formatted as:
        - Backend Language: <value>
        - Backend Framework: <value>
        ...

    Returns a TechStack with parsed values (defaults kept for missing keys).
    """
    stack = TechStack()

    # Найти секцию "## Technology Stack"
    section_match = re.search(
        r"##\s*Technology\s*Stack\s*\n(.*?)(?=\n##\s|\Z)",
        spec_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not section_match:
        return stack

    section = section_match.group(1)

    # Mapping from markdown key → TechStack field
    field_map: dict[str, str] = {
        "backend language": "backend_language",
        "backend framework": "backend_framework",
        "frontend language": "frontend_language",
        "frontend framework": "frontend_framework",
        "css approach": "frontend_css",
        "database": "database",
        "orm": "orm",
        "migration tool": "migration_tool",
        "backend test framework": "backend_test_framework",
        "frontend test framework": "frontend_test_framework",
        "container runtime": "container_runtime",
        "backend server": "backend_server",
        "frontend server": "frontend_server",
        "e2e framework": "e2e_framework",
        "backend package manager": "backend_package_manager",
        "backend build tool": "backend_build_tool",
        "frontend build tool": "frontend_build_tool",
        "frontend router": "frontend_router",
        "component test library": "frontend_component_test_lib",
        "ci/cd": "ci_cd",
        "ci cd": "ci_cd",
    }

    for line in section.split("\n"):
        # Match "- Key: value" or "- **Key**: value"
        match = re.match(r"-\s*(?:\*\*)?([^*:\n]+?)(?:\*\*)?:\s*(.+)", line.strip())
        if not match:
            continue
        key = match.group(1).strip().lower()
        value = match.group(2).strip()

        # Normalise "none" → ""
        if value.lower() in ("none", "n/a"):
            value = ""

        if key in field_map:
            setattr(stack, field_map[key], value)

    return stack


def parse_directory_layout(spec_text: str) -> DirectoryLayout:
    """Extract Project Structure from a generated specification.

    Parses the "## Project Structure" section formatted as:
        - Project Type: <value>
        - Source Root: <value>
        ...
    """
    layout = DirectoryLayout()

    section_match = re.search(
        r"##\s*Project\s*Structure\s*\n(.*?)(?=\n##\s|\Z)",
        spec_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not section_match:
        return layout

    section = section_match.group(1)

    field_map: dict[str, str] = {
        "project type": "project_type",
        "source root": "source_root",
        "backend directory": "backend_dir",
        "frontend directory": "frontend_dir",
        "test directory": "test_dir",
    }

    for line in section.split("\n"):
        match = re.match(r"-\s*(?:\*\*)?([^*:\n]+?)(?:\*\*)?:\s*(.+)", line.strip())
        if not match:
            continue
        key = match.group(1).strip().lower()
        value = match.group(2).strip()

        if value.lower() in ("none", "n/a"):
            value = ""

        if key in field_map:
            setattr(layout, field_map[key], value)

    return layout


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
