"""Build the delivery crew — Backend, Frontend, QA, Architect produce implementation plans
and (in coding mode) actual source code."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from crewai import Agent, Task, Crew, Process

from agents.artifacts import build_artifact_paths
from agents.llm_factory import build_llm
from agents.state import TechStack, DirectoryLayout
from agents.tools.file_tools import (
    list_files,
    read_text_file,
    write_app_file,
    write_text_file,
    create_app_directory,
)
from agents.tools.common_tools import (
    check_markdown_links,
    count_lines,
    extract_headings,
    search_code,
    validate_json,
    validate_yaml,
)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
ARTIFACTS = build_artifact_paths()


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_agents(*, coding_mode: bool = False) -> dict[str, Agent]:
    agents_cfg = _load_yaml(CONFIG_DIR / "agents.yaml")
    llm = build_llm()

    read_tools = [read_text_file, list_files, search_code]
    write_tools = [write_app_file, write_text_file, create_app_directory]

    if coding_mode:
        return {
            "backend_engineer": Agent(
                config=agents_cfg["backend_engineer"],
                llm=llm,
                tools=read_tools + write_tools + [validate_yaml, validate_json, extract_headings],
                verbose=True,
                allow_code_execution=False,
            ),
            "frontend_engineer": Agent(
                config=agents_cfg["frontend_engineer"],
                llm=llm,
                tools=read_tools + write_tools + [validate_json, extract_headings],
                verbose=True,
                allow_code_execution=False,
            ),
            "qa_engineer": Agent(
                config=agents_cfg["qa_engineer"],
                llm=llm,
                tools=read_tools + write_tools + [check_markdown_links, count_lines, extract_headings],
                verbose=True,
                allow_code_execution=False,
            ),
            "architect_devops": Agent(
                config=agents_cfg["architect_devops"],
                llm=llm,
                tools=read_tools + write_tools
                + [validate_yaml, validate_json, check_markdown_links, count_lines, extract_headings],
                verbose=True,
                allow_code_execution=False,
            ),
        }

    # Planning mode — read-only common tools
    common_tools = read_tools

    return {
        "backend_engineer": Agent(
            config=agents_cfg["backend_engineer"],
            llm=llm,
            tools=common_tools + [validate_yaml, validate_json, extract_headings],
            verbose=True,
        ),
        "frontend_engineer": Agent(
            config=agents_cfg["frontend_engineer"],
            llm=llm,
            tools=common_tools + [validate_json, extract_headings],
            verbose=True,
        ),
        "qa_engineer": Agent(
            config=agents_cfg["qa_engineer"],
            llm=llm,
            tools=common_tools + [check_markdown_links, count_lines, extract_headings],
            verbose=True,
        ),
        "architect_devops": Agent(
            config=agents_cfg["architect_devops"],
            llm=llm,
            tools=common_tools
            + [validate_yaml, validate_json, check_markdown_links, count_lines, extract_headings],
            verbose=True,
        ),
    }


def build_delivery_crew(
    user_request: str | None,
    approved_plan: str,
    feedback: str = "",
    tech_stack: Optional[TechStack] = None,
    directory_layout: Optional[DirectoryLayout] = None,
) -> Crew:
    """Return a Crew that produces implementation plans from an approved specification.

    Args:
        user_request: The original project request text.
        approved_plan: The approved specification content.
        feedback: Optional feedback/fixes to incorporate into the implementation.
                  When provided, agents will adjust their output to address these
                  improvements instead of generating from scratch.
        tech_stack: Parsed technology stack from the spec (injected into prompts).
        directory_layout: Parsed directory layout from the spec (injected into prompts).
    """
    agents = _build_agents()
    tasks_cfg = _load_yaml(CONFIG_DIR / "tasks.yaml")

    common_context = (
        f"\n\nApproved specification location:\n{ARTIFACTS.approved_spec.as_posix()}"
        f"\n\nApproved specification content:\n{approved_plan}"
    )
    if tech_stack:
        common_context += f"\n\n{tech_stack.to_context_string()}"
    if directory_layout:
        common_context += (
            f"\n\nProject Structure from spec:"
            f"\n- Project Type: {directory_layout.project_type}"
            f"\n- Source Root: {directory_layout.source_root}"
            f"\n- Backend Dir: {directory_layout.backend_dir}"
            f"\n- Frontend Dir: {directory_layout.frontend_dir}"
            f"\n- Test Dir: {directory_layout.test_dir}"
        )
    if user_request:
        common_context = f"\n\nOriginal project request:\n{user_request}" + common_context

    if feedback.strip():
        common_context += (
            f"\n\n⚠️ IMPORTANT — FIXES REQUIRED:"
            f"\nThe previous implementation was reviewed and the following changes are needed."
            f"\nPlease update the implementation plans to address ALL of these points:\n\n"
            f"{feedback}"
        )

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


def build_coding_crew(
    approved_spec: str,
    backend_plan: str = "",
    frontend_plan: str = "",
    user_request: str | None = None,
    feedback: str = "",
    tech_stack: Optional[TechStack] = None,
    directory_layout: Optional[DirectoryLayout] = None,
) -> Crew:
    """Return a Crew that writes actual source code from approved plans.

    Uses the SAME agents as build_delivery_crew but in CODING mode:
    - Agents get write tools (write_app_file, create_app_directory)
    - Tasks come from tasks_code.yaml instead of tasks.yaml
    - Output is real source files under apps/, not docs/

    Args:
        approved_spec: The approved specification text.
        backend_plan: Backend implementation plan text (from planning phase).
        frontend_plan: Frontend implementation plan text (from planning phase).
        user_request: Original project request (optional extra context).
        feedback: Optional fixes/improvements to incorporate into the code.
        tech_stack: Parsed technology stack from the spec (injected into prompts).
        directory_layout: Parsed directory layout from the spec (injected into prompts).
    """
    agents = _build_agents(coding_mode=True)
    tasks_cfg = _load_yaml(CONFIG_DIR / "tasks_code.yaml")

    common_context = f"\n\nApproved specification:\n{approved_spec}"
    if tech_stack:
        common_context += f"\n\n{tech_stack.to_context_string()}"
    if directory_layout:
        common_context += (
            f"\n\nProject Structure from spec:"
            f"\n- Project Type: {directory_layout.project_type}"
            f"\n- Source Root: {directory_layout.source_root}"
            f"\n- Backend Dir: {directory_layout.backend_dir}"
            f"\n- Frontend Dir: {directory_layout.frontend_dir}"
            f"\n- Test Dir: {directory_layout.test_dir}"
        )
    if backend_plan:
        common_context += f"\n\nBackend implementation plan:\n{backend_plan}"
    if frontend_plan:
        common_context += f"\n\nFrontend implementation plan:\n{frontend_plan}"
    if user_request:
        common_context = f"\n\nOriginal project request:\n{user_request}" + common_context

    if feedback.strip():
        common_context += (
            f"\n\n⚠️ IMPORTANT — FIXES REQUIRED:"
            f"\nThe previous code generation was reviewed and the following changes are needed."
            f"\nPlease update the source code to address ALL of these points:\n\n"
            f"{feedback}"
        )

    backend_task = Task(
        description=tasks_cfg["backend_code_task"]["description"] + common_context,
        expected_output=tasks_cfg["backend_code_task"]["expected_output"],
        agent=agents["backend_engineer"],
        markdown=True,
    )

    frontend_task = Task(
        description=tasks_cfg["frontend_code_task"]["description"] + common_context,
        expected_output=tasks_cfg["frontend_code_task"]["expected_output"],
        agent=agents["frontend_engineer"],
        context=[backend_task],
        markdown=True,
    )

    qa_task = Task(
        description=tasks_cfg["qa_code_task"]["description"] + common_context,
        expected_output=tasks_cfg["qa_code_task"]["expected_output"],
        agent=agents["qa_engineer"],
        context=[backend_task, frontend_task],
        markdown=True,
    )

    devops_task = Task(
        description=tasks_cfg["devops_code_task"]["description"] + common_context,
        expected_output=tasks_cfg["devops_code_task"]["expected_output"],
        agent=agents["architect_devops"],
        context=[backend_task, frontend_task, qa_task],
        markdown=True,
    )

    return Crew(
        agents=list(agents.values()),
        tasks=[backend_task, frontend_task, qa_task, devops_task],
        process=Process.sequential,
        verbose=True,
    )


def _make_context(
    approved_spec: str,
    backend_plan: str = "",
    frontend_plan: str = "",
    user_request: str | None = None,
    feedback: str = "",
    tech_stack: Optional[TechStack] = None,
    directory_layout: Optional[DirectoryLayout] = None,
) -> str:
    """Build common context string for coding sub-phase crews."""
    ctx = f"\n\nApproved specification:\n{approved_spec}"
    if tech_stack:
        ctx += f"\n\n{tech_stack.to_context_string()}"
    if directory_layout:
        ctx += (
            f"\n\nProject Structure from spec:"
            f"\n- Project Type: {directory_layout.project_type}"
            f"\n- Source Root: {directory_layout.source_root}"
            f"\n- Backend Dir: {directory_layout.backend_dir}"
            f"\n- Frontend Dir: {directory_layout.frontend_dir}"
            f"\n- Test Dir: {directory_layout.test_dir}"
        )
    if backend_plan:
        ctx += f"\n\nBackend implementation plan:\n{backend_plan}"
    if frontend_plan:
        ctx += f"\n\nFrontend implementation plan:\n{frontend_plan}"
    if user_request:
        ctx = f"\n\nOriginal project request:\n{user_request}" + ctx

    if feedback.strip():
        ctx += (
            f"\n\n⚠️ IMPORTANT — FIXES REQUIRED:"
            f"\nThe previous code generation was reviewed and the following changes are needed."
            f"\nPlease update the source code to address ALL of these points:\n\n"
            f"{feedback}"
        )
    return ctx


def build_coding_backend_crew(
    approved_spec: str,
    backend_plan: str = "",
    user_request: str | None = None,
    feedback: str = "",
    tech_stack: Optional[TechStack] = None,
    directory_layout: Optional[DirectoryLayout] = None,
) -> Crew:
    """Crew for CODING_BACKEND sub-phase — writes backend source code only."""
    agents = _build_agents(coding_mode=True)
    tasks_cfg = _load_yaml(CONFIG_DIR / "tasks_code.yaml")
    ctx = _make_context(
        approved_spec,
        backend_plan=backend_plan,
        user_request=user_request,
        feedback=feedback,
        tech_stack=tech_stack,
        directory_layout=directory_layout,
    )

    task = Task(
        description=tasks_cfg["backend_code_task"]["description"] + ctx,
        expected_output=tasks_cfg["backend_code_task"]["expected_output"],
        agent=agents["backend_engineer"],
        markdown=True,
    )
    return Crew(
        agents=[agents["backend_engineer"]],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )


def build_coding_frontend_crew(
    approved_spec: str,
    frontend_plan: str = "",
    user_request: str | None = None,
    feedback: str = "",
    tech_stack: Optional[TechStack] = None,
    directory_layout: Optional[DirectoryLayout] = None,
) -> Crew:
    """Crew for CODING_FRONTEND sub-phase — writes frontend source code only."""
    agents = _build_agents(coding_mode=True)
    tasks_cfg = _load_yaml(CONFIG_DIR / "tasks_code.yaml")
    ctx = _make_context(
        approved_spec,
        frontend_plan=frontend_plan,
        user_request=user_request,
        feedback=feedback,
        tech_stack=tech_stack,
        directory_layout=directory_layout,
    )

    task = Task(
        description=tasks_cfg["frontend_code_task"]["description"] + ctx,
        expected_output=tasks_cfg["frontend_code_task"]["expected_output"],
        agent=agents["frontend_engineer"],
        markdown=True,
    )
    return Crew(
        agents=[agents["frontend_engineer"]],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )


def build_coding_tests_crew(
    approved_spec: str,
    user_request: str | None = None,
    feedback: str = "",
    tech_stack: Optional[TechStack] = None,
    directory_layout: Optional[DirectoryLayout] = None,
) -> Crew:
    """Crew for CODING_TESTS sub-phase — writes tests and QA artifacts only."""
    agents = _build_agents(coding_mode=True)
    tasks_cfg = _load_yaml(CONFIG_DIR / "tasks_code.yaml")
    ctx = _make_context(
        approved_spec,
        user_request=user_request,
        feedback=feedback,
        tech_stack=tech_stack,
        directory_layout=directory_layout,
    )

    task = Task(
        description=tasks_cfg["qa_code_task"]["description"] + ctx,
        expected_output=tasks_cfg["qa_code_task"]["expected_output"],
        agent=agents["qa_engineer"],
        markdown=True,
    )
    return Crew(
        agents=[agents["qa_engineer"]],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )


def build_coding_devops_crew(
    approved_spec: str,
    user_request: str | None = None,
    feedback: str = "",
    tech_stack: Optional[TechStack] = None,
    directory_layout: Optional[DirectoryLayout] = None,
) -> Crew:
    """Crew for CODING_DEVOPS sub-phase — writes Docker, compose, env, README."""
    agents = _build_agents(coding_mode=True)
    tasks_cfg = _load_yaml(CONFIG_DIR / "tasks_code.yaml")
    ctx = _make_context(
        approved_spec,
        user_request=user_request,
        feedback=feedback,
        tech_stack=tech_stack,
        directory_layout=directory_layout,
    )

    task = Task(
        description=tasks_cfg["devops_code_task"]["description"] + ctx,
        expected_output=tasks_cfg["devops_code_task"]["expected_output"],
        agent=agents["architect_devops"],
        markdown=True,
    )
    return Crew(
        agents=[agents["architect_devops"]],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )
