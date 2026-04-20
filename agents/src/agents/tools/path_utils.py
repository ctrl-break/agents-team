from pathlib import Path


def get_repo_root() -> Path:
    """
    Returns the repository root directory.

    Current structure assumption:
    repo/
      agents/
        src/
          agents/
            tools/
    """
    return Path(__file__).resolve().parents[4]


def resolve_repo_path(relative_path: str) -> Path:
    """
    Resolves a relative path inside the repository root and prevents escaping outside it.
    """
    repo_root = get_repo_root().resolve()
    target_path = (repo_root / relative_path).resolve()

    try:
        target_path.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(
            f"Path '{relative_path}' points outside of the repository root."
        ) from exc

    return target_path