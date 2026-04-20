from pathlib import Path
from agents.tools.file_tools import create_directory, list_files, read_text_file, write_text_file
import yaml

from crewai import Agent, Task, Crew, Process


BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"


def load_yaml(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_configs():
    agents_config = load_yaml(CONFIG_DIR / "agents.yaml")
    tasks_config = load_yaml(CONFIG_DIR / "tasks.yaml")
    return agents_config, tasks_config


def build_agents():
    agents_config, _ = load_configs()

    product_manager = Agent(
        config=agents_config["product_manager"],
        tools=[write_text_file, read_text_file, list_files],
        verbose=True,
    )

    backend_engineer = Agent(
        config=agents_config["backend_engineer"],
        tools=[create_directory, write_text_file, read_text_file, list_files],
        verbose=True,
    )

    frontend_engineer = Agent(
        config=agents_config["frontend_engineer"],
        tools=[create_directory, write_text_file, read_text_file, list_files],
        verbose=True,
    )

    qa_engineer = Agent(
        config=agents_config["qa_engineer"],
        tools=[read_text_file, list_files, write_text_file],
        verbose=True,
    )

    architect_devops = Agent(
        config=agents_config["architect_devops"],
        tools=[read_text_file, list_files, write_text_file],
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
    agents, tasks_config = build_agents(), load_configs()[1]

    pm_task = Task(
        description=(
            tasks_config["pm_spec_task"]["description"]
            + f"\n\nProject request:\n{user_request}"
        ),
        expected_output=tasks_config["pm_spec_task"]["expected_output"],
        agent=agents["product_manager"],
    )

    crew = Crew(
        agents=[agents["product_manager"]],
        tasks=[pm_task],
        process=Process.sequential,
        verbose=True,
    )

    return crew


def build_delivery_crew(user_request: str, approved_plan: str) -> Crew:
    agents, tasks_config = build_agents(), load_configs()[1]

    common_context = (
        f"\n\nOriginal project request:\n{user_request}"
        f"\n\nApproved specification:\n{approved_plan}"
    )

    backend_task = Task(
        description=tasks_config["backend_task"]["description"] + common_context,
        expected_output=tasks_config["backend_task"]["expected_output"],
        agent=agents["backend_engineer"],
    )

    frontend_task = Task(
        description=tasks_config["frontend_task"]["description"] + common_context,
        expected_output=tasks_config["frontend_task"]["expected_output"],
        agent=agents["frontend_engineer"],
    )

    qa_task = Task(
        description=tasks_config["qa_task"]["description"] + common_context,
        expected_output=tasks_config["qa_task"]["expected_output"],
        agent=agents["qa_engineer"],
    )

    architecture_task = Task(
        description=tasks_config["architecture_task"]["description"] + common_context,
        expected_output=tasks_config["architecture_task"]["expected_output"],
        agent=agents["architect_devops"],
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