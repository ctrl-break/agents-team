from pathlib import Path
import os
from typing import Any

import yaml
from crewai import Agent, Task, Crew, Process, LLM

from agents.artifacts import build_artifact_paths
from agents.tools.file_tools import (
    create_app_directory,
    list_files,
    read_text_file,
    write_app_file,
    write_docs_file,
)


BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
ARTIFACTS = build_artifact_paths()


def load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_configs() -> tuple[dict[str, Any], dict[str, Any]]:
    agents_config = load_yaml(CONFIG_DIR / "agents.yaml")
    tasks_config = load_yaml(CONFIG_DIR / "tasks.yaml")
    return agents_config, tasks_config


def build_agents() -> dict[str, Agent]:
    agents_config, _ = load_configs()
    llm = build_llm()

    product_manager = Agent(
        config=agents_config["product_manager"],
        llm=llm,
        tools=[write_docs_file, read_text_file, list_files],
        verbose=True,
    )

    backend_engineer = Agent(
        config=agents_config["backend_engineer"],
        llm=llm,
        tools=[create_app_directory, write_app_file, read_text_file, list_files],
        verbose=True,
    )

    frontend_engineer = Agent(
        config=agents_config["frontend_engineer"],
        llm=llm,
        tools=[create_app_directory, write_app_file, read_text_file, list_files],
        verbose=True,
    )

    qa_engineer = Agent(
        config=agents_config["qa_engineer"],
        llm=llm,
        tools=[read_text_file, list_files, write_docs_file],
        verbose=True,
    )

    architect_devops = Agent(
        config=agents_config["architect_devops"],
        llm=llm,
        tools=[read_text_file, list_files, write_docs_file],
        verbose=True,
    )

    return {
        "product_manager": product_manager,
        "backend_engineer": backend_engineer,
        "frontend_engineer": frontend_engineer,
        "qa_engineer": qa_engineer,
        "architect_devops": architect_devops,
    }


def build_planning_crew(user_request: str) -> Crew:
    agents = build_agents()
    _, tasks_config = load_configs()

    pm_task = Task(
        description=(
            tasks_config["pm_spec_task"]["description"]
            + f"\n\nProject request:\n{user_request}"
            + f"\n\nSave the draft specification to: {ARTIFACTS.pending_spec.as_posix()}"
        ),
        expected_output=tasks_config["pm_spec_task"]["expected_output"],
        agent=agents["product_manager"],
        output_file=str(ARTIFACTS.pending_spec),
        markdown=True,
    )

    crew = Crew(
        agents=[agents["product_manager"]],
        tasks=[pm_task],
        process=Process.sequential,
        verbose=True,
    )

    return crew


def build_delivery_crew(user_request: str, approved_plan: str) -> Crew:
    agents = build_agents()
    _, tasks_config = load_configs()

    common_context = (
        f"\n\nOriginal project request:\n{user_request}"
        f"\n\nApproved specification location:\n{ARTIFACTS.approved_spec.as_posix()}"
        f"\n\nApproved specification content:\n{approved_plan}"
    )

    backend_task = Task(
        description=tasks_config["backend_task"]["description"] + common_context,
        expected_output=tasks_config["backend_task"]["expected_output"],
        agent=agents["backend_engineer"],
        output_file=str(ARTIFACTS.backend_plan),
        markdown=True,
    )

    frontend_task = Task(
        description=tasks_config["frontend_task"]["description"] + common_context,
        expected_output=tasks_config["frontend_task"]["expected_output"],
        agent=agents["frontend_engineer"],
        context=[backend_task],
        output_file=str(ARTIFACTS.frontend_plan),
        markdown=True,
    )

    qa_task = Task(
        description=tasks_config["qa_task"]["description"] + common_context,
        expected_output=tasks_config["qa_task"]["expected_output"],
        agent=agents["qa_engineer"],
        context=[backend_task, frontend_task],
        output_file=str(ARTIFACTS.qa_report),
        markdown=True,
    )

    architecture_task = Task(
        description=tasks_config["architecture_task"]["description"] + common_context,
        expected_output=tasks_config["architecture_task"]["expected_output"],
        agent=agents["architect_devops"],
        context=[backend_task, frontend_task, qa_task],
        output_file=str(ARTIFACTS.architecture_report),
        markdown=True,
    )

    crew = Crew(
        agents=[
            agents["backend_engineer"],
            agents["frontend_engineer"],
            agents["qa_engineer"],
            agents["architect_devops"],
        ],
        tasks=[
            backend_task,
            frontend_task,
            qa_task,
            architecture_task,
        ],
        process=Process.sequential,
        verbose=True,
    )

    return crew


def build_llm() -> LLM:
    model_name = os.getenv("OPENAI_MODEL_NAME") or os.getenv(
        "MODEL", "openai/gpt-5.4-mini"
    )

    if "/" not in model_name:
        provider = os.getenv("LLM_PROVIDER", "openai")
        model_name = f"{provider}/{model_name}"

    return LLM(model=model_name, max_completion_tokens=2000)
