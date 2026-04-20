from crewai.tools import tool

from agents.tools.path_utils import resolve_repo_path

IGNORED_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".idea",
    ".vscode",
    "site-packages",
    "dist",
    "build",
}

DEFAULT_MAX_LIST_ITEMS = 200


def _ensure_allowed_path(path: str, allowed_roots: tuple[str, ...]) -> None:
    normalized = path.replace("\\", "/").lstrip("./")

    if not any(
        normalized == root or normalized.startswith(f"{root}/")
        for root in allowed_roots
    ):
        allowed = ", ".join(allowed_roots)
        raise ValueError(
            f"Path '{path}' is outside allowed roots. Allowed roots: {allowed}"
        )


def _write_text(relative_path: str, content: str, *, overwrite: bool) -> str:
    path = resolve_repo_path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and not overwrite:
        return f"Error: file already exists: {path}"

    path.write_text(content, encoding="utf-8")
    return f"File written: {path}"


def _should_skip_path(item, base_path) -> bool:
    try:
        parts = item.relative_to(base_path).parts
    except ValueError:
        return True

    return any(part in IGNORED_NAMES for part in parts)


@tool("Create directory")
def create_directory(relative_path: str) -> str:
    """
    Create a directory inside the repository.
    Example input: 'apps/expense-bot/src'
    """
    path = resolve_repo_path(relative_path)
    path.mkdir(parents=True, exist_ok=True)
    return f"Directory created: {path}"


@tool("Write text file")
def write_text_file(relative_path: str, content: str) -> str:
    """
    Write UTF-8 text content to a file inside the repository.
    Creates parent directories if needed.
    Example input:
    - relative_path: 'docs/specs/expense-bot-plan.md'
    - content: '# Plan...'
    """
    return _write_text(relative_path, content, overwrite=True)


@tool("Write docs file")
def write_docs_file(relative_path: str, content: str) -> str:
    """
    Write a text file only under the docs/ directory.
    Existing files are preserved unless a task chooses a new file path.
    """
    _ensure_allowed_path(relative_path, ("docs",))
    return _write_text(relative_path, content, overwrite=False)


@tool("Write app file")
def write_app_file(relative_path: str, content: str) -> str:
    """
    Write a text file only under the apps/ directory.
    Existing files are preserved unless a task chooses a new file path.
    """
    _ensure_allowed_path(relative_path, ("apps",))
    return _write_text(relative_path, content, overwrite=False)


@tool("Create app directory")
def create_app_directory(relative_path: str) -> str:
    """
    Create a directory only under the apps/ directory.
    """
    _ensure_allowed_path(relative_path, ("apps",))
    path = resolve_repo_path(relative_path)
    path.mkdir(parents=True, exist_ok=True)
    return f"Directory created: {path}"


@tool("Read text file")
def read_text_file(relative_path: str) -> str:
    """
    Read UTF-8 text content from a file inside the repository.
    Example input: 'docs/specs/expense-bot-plan.md'
    """
    path = resolve_repo_path(relative_path)

    if not path.exists():
        return f"Error: file does not exist: {path}"

    if not path.is_file():
        return f"Error: path is not a file: {path}"

    return path.read_text(encoding="utf-8")


@tool("List files")
def list_files(
    relative_path: str = ".", recursive: bool = True, max_items: int = DEFAULT_MAX_LIST_ITEMS
) -> str:
    """
    List files and directories inside a repository path.
    Example input:
    - relative_path: 'apps'
    - recursive: True
    - max_items: 100
    """
    path = resolve_repo_path(relative_path)

    if not path.exists():
        return f"Error: path does not exist: {path}"

    if path.is_file():
        return str(path)

    if max_items <= 0:
        return "Error: max_items must be greater than 0."

    if recursive:
        items = [item for item in sorted(path.rglob("*")) if not _should_skip_path(item, path)]
    else:
        items = [item for item in sorted(path.iterdir()) if not _should_skip_path(item, path)]

    if not items:
        return f"No files found in: {path}"

    result = []
    for item in items[:max_items]:
        kind = "DIR " if item.is_dir() else "FILE"
        result.append(f"[{kind}] {item.relative_to(path)}")

    if len(items) > max_items:
        remaining = len(items) - max_items
        result.append(
            f"... truncated {remaining} more items. Narrow the path or increase max_items."
        )

    return "\n".join(result)
