"""Build the delivery crew — Backend, Frontend, QA, Architect produce implementation plans."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from crewai import Agent, Task, Crew, Process

from agents.artifacts import build_artifact_paths
from agents.llm_factory import build_llm
from agents.tools.file_tools import list_files, read_text_file

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
ARTIFACTS = build_artifact_paths()


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_agents() -> dict[str, Agent]:
    agents_cfg = _load_yaml(CONFIG_DIR / "agents.yaml")
    llm = build_llm()
    tools = [read_text_file, list_files]

    return {
        "backend_engineer": Agent(config=agents_cfg["backend_engineer"], llm=llm, tools=tools, verbose=True),
        "frontend_engineer": Agent(config=agents_cfg["frontend_engineer"], llm=llm, tools=tools, verbose=True),
        "qa_engineer": Agent(config=agents_cfg["qa_engineer"], llm=llm, tools=tools, verbose=True),
        "architect_devops": Agent(config=agents_cfg["architect_devops"], llm=llm, tools=tools, verbose=True),
    }


def build_delivery_crew(user_request: str | None, approved_plan: str) -> Crew:
    """Return a Crew that produces implementation plans from an approved specification."""
    agents = _build_agents()
    tasks_cfg = _load_yaml(CONFIG_DIR / "tasks.yaml")

    common_context = (
        f"\n\nApproved specification location:\n{ARTIFACTS.approved_spec.as_posix()}"
        f"\n\nApproved specification content:\n{approved_plan}"
    )
    if user_request:
        common_context = f"\n\nOriginal project request:\n{user_request}" + common_context

    backend_task = Task(
        description=tasks_cfg["backend_task"]["description"] + common_context,
        expected_output=tasks_cfg["backend_task"]["expected_output"],
        agent=agents["backend_engineer"],
        output_file=str(ARTIFACTS.backend_plan),
        markdown=True,
    )

    frontend_task = Task(
        description=tasks_cfg["frontend_task"]["description"] + common_context,
        expected_output=tasks_cfg["frontend_task"]["expected_output"],
        agent=agents["frontend_engineer"],
        context=[backend_task],
        output_file=str(ARTIFACTS.frontend_plan),
        markdown=True,
    )

    qa_task = Task(
        description=tasks_cfg["qa_task"]["description"] + common_context,
        expected_output=tasks_cfg["qa_task"]["expected_output"],
        agent=agents["qa_engineer"],
        context=[backend_task, frontend_task],
        output_file=str(ARTIFACTS.qa_report),
        markdown=True,
    )

    architecture_task = Task(
        description=tasks_cfg["architecture_task"]["description"] + common_context,
        expected_output=tasks_cfg["architecture_task"]["expected_output"],
        agent=agents["architect_devops"],
        context=[backend_task, frontend_task, qa_task],
        output_file=str(ARTIFACTS.architecture_report),
        markdown=True,
    )

    return Crew(
        agents=list(agents.values()),
        tasks=[backend_task, frontend_task, qa_task, architecture_task],
        process=Process.sequential,
        verbose=True,
    )