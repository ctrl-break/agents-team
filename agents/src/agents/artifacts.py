from dataclasses import dataclass
from pathlib import Path

from agents.tools.path_utils import get_repo_root


@dataclass(frozen=True)
class ArtifactPaths:
    pending_spec: Path
    approved_spec: Path
    backend_plan: Path
    frontend_plan: Path
    qa_report: Path
    architecture_report: Path


def build_artifact_paths() -> ArtifactPaths:
    repo_root = get_repo_root()

    return ArtifactPaths(
        pending_spec=repo_root / "docs" / "specs" / "pending-plan.md",
        approved_spec=repo_root / "docs" / "specs" / "latest-plan.md",
        backend_plan=repo_root / "docs" / "implementation" / "backend-plan.md",
        frontend_plan=repo_root / "docs" / "implementation" / "frontend-plan.md",
        qa_report=repo_root / "docs" / "qa" / "qa-report.md",
        architecture_report=repo_root
        / "docs"
        / "architecture"
        / "architecture-review.md",
    )
