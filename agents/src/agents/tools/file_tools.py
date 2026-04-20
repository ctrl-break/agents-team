from crewai.tools import tool

from agents.tools.path_utils import resolve_repo_path


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
def list_files(relative_path: str = ".", recursive: bool = True) -> str:
    """
    List files and directories inside a repository path.
    Example input:
    - relative_path: 'apps'
    - recursive: True
    """
    path = resolve_repo_path(relative_path)

    if not path.exists():
        return f"Error: path does not exist: {path}"

    if path.is_file():
        return str(path)

    if recursive:
        items = sorted(path.rglob("*"))
    else:
        items = sorted(path.iterdir())

    if not items:
        return f"No files found in: {path}"

    result = []
    for item in items:
        kind = "DIR " if item.is_dir() else "FILE"
        result.append(f"[{kind}] {item.relative_to(path)}")

    return "\n".join(result)
