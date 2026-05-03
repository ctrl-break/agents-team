"""
Common utility tools available to all agents.
Validation, search, and inspection helpers.
"""

import json
import re

from crewai.tools import tool

from agents.tools.path_utils import resolve_repo_path, get_repo_root


@tool("Validate YAML syntax")
def validate_yaml(relative_path: str) -> str:
    """
    Check whether a YAML file inside the repository is syntactically valid.
    Returns a summary of top-level keys and any parse errors.
    Example: 'docs/specs/config.yaml'
    """
    import yaml

    path = resolve_repo_path(relative_path)
    if not path.exists():
        return f"Error: file does not exist: {path}"
    if not path.is_file():
        return f"Error: path is not a file: {path}"

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return f"YAML parse error in {path}:\n{str(e)}"

    if data is None:
        return f"File {path} is empty (no YAML content)."

    if isinstance(data, dict):
        keys = list(data.keys())
        return (
            f"Valid YAML in: {path}\n"
            f"Top-level keys ({len(keys)}): {', '.join(str(k) for k in keys)}"
        )
    elif isinstance(data, list):
        return f"Valid YAML in: {path}\nTop-level list with {len(data)} items."
    else:
        return f"Valid YAML in: {path}\nTop-level scalar value: {type(data).__name__}"


@tool("Validate JSON syntax")
def validate_json(relative_path: str) -> str:
    """
    Check whether a JSON file inside the repository is syntactically valid.
    Returns structure summary and any parse errors.
    Example: 'apps/my-app/package.json'
    """
    path = resolve_repo_path(relative_path)
    if not path.exists():
        return f"Error: file does not exist: {path}"
    if not path.is_file():
        return f"Error: path is not a file: {path}"

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return f"JSON parse error in {path}:\n{str(e)}"

    if isinstance(data, dict):
        keys = list(data.keys())
        return (
            f"Valid JSON in: {path}\n"
            f"Top-level keys ({len(keys)}): {', '.join(str(k) for k in keys)}"
        )
    elif isinstance(data, list):
        return f"Valid JSON in: {path}\nTop-level array with {len(data)} items."
    else:
        return f"Valid JSON in: {path}\nTop-level scalar: {type(data).__name__}"


@tool("Check markdown links")
def check_markdown_links(relative_path: str) -> str:
    """
    Extract and validate all internal links in a markdown file.
    Reports broken links to files that do not exist in the repository.
    Example: 'docs/specs/latest-plan.md'
    """
    path = resolve_repo_path(relative_path)
    if not path.exists():
        return f"Error: file does not exist: {path}"
    if not path.is_file():
        return f"Error: path is not a file: {path}"

    content = path.read_text(encoding="utf-8")
    link_pattern = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
    links = link_pattern.findall(content)

    if not links:
        return f"No markdown links found in: {path}"

    broken = []
    valid = []
    external = []

    for text, url in links:
        if url.startswith(("http://", "https://", "mailto:", "#")):
            external.append(url)
            continue

        target = (path.parent / url).resolve()
        try:
            target.relative_to(get_repo_root())
        except ValueError:
            external.append(url)
            continue

        if target.exists():
            kind = "DIR" if target.is_dir() else "FILE"
            valid.append(f"  [{kind}] {url}")
        else:
            broken.append(f"  [BROKEN] {url} -> {target}")

    lines = [f"Link check for: {path}"]
    if valid:
        lines.append(f"\nValid internal links ({len(valid)}):")
        lines.extend(valid)
    if external:
        lines.append(f"\nExternal/skipped links ({len(external)}):")
        for u in external:
            lines.append(f"  [EXT] {u}")
    if broken:
        lines.append(f"\nBroken links ({len(broken)}):")
        lines.extend(broken)
    else:
        lines.append("\nNo broken internal links found.")

    return "\n".join(lines)


@tool("Search inside text files")
def search_code(
    relative_path: str = ".",
    pattern: str = "",
    file_glob: str = "*.md",
    max_results: int = 30,
) -> str:
    """
    Search for a regex pattern inside text files under a repository path.
    Returns matching file paths with line numbers and snippets.
    Example:
    - relative_path: 'docs'
    - pattern: 'API|REST|endpoint'
    - file_glob: '*.md'
    """
    path = resolve_repo_path(relative_path)
    if not path.exists():
        return f"Error: path does not exist: {path}"

    if not pattern:
        return "Error: pattern is required."

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Error: invalid regex pattern: {e}"

    results = []
    files_scanned = 0

    target = path if path.is_dir() else path.parent
    for file_path in target.rglob(file_glob):
        if file_path.is_file():
            files_scanned += 1
            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue

            for i, line in enumerate(content.splitlines(), start=1):
                if regex.search(line):
                    results.append(
                        f"  {file_path.relative_to(target)}:{i}: {line.strip()[:200]}"
                    )
                    if len(results) >= max_results:
                        break
            if len(results) >= max_results:
                break

    if not results:
        return (
            f"No matches for '{pattern}' in {target} "
            f"(scanned {files_scanned} files matching '{file_glob}')."
        )

    header = (
        f"Found {len(results)} matches for '{pattern}' in {target} "
        f"(scanned {files_scanned} files matching '{file_glob}'):\n"
    )
    return header + "\n".join(results)


@tool("Count lines of text")
def count_lines(relative_path: str = ".", file_glob: str = "*.md") -> str:
    """
    Count total lines across text files matching a glob under a repository path.
    Useful for estimating document size and completeness.
    Example:
    - relative_path: 'docs'
    - file_glob: '*.md'
    """
    path = resolve_repo_path(relative_path)
    if not path.exists():
        return f"Error: path does not exist: {path}"

    target = path if path.is_dir() else path.parent
    total_lines = 0
    file_counts: dict[str, int] = {}

    for file_path in target.rglob(file_glob):
        if file_path.is_file():
            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            lines_count = len(content.splitlines())
            total_lines += lines_count
            file_counts[str(file_path.relative_to(target))] = lines_count

    if not file_counts:
        return f"No files matching '{file_glob}' found in: {target}"

    items = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
    lines = [
        f"Line counts for '{file_glob}' in {target}:",
        f"Total lines: {total_lines} across {len(items)} files\n",
    ]
    for fname, count in items[:20]:
        lines.append(f"  {count:6d}  {fname}")
    if len(items) > 20:
        lines.append(f"  ... and {len(items) - 20} more files.")

    return "\n".join(lines)


@tool("Extract headings from markdown")
def extract_headings(relative_path: str) -> str:
    """
    Extract a table-of-contents style list of all headings from a markdown file.
    Returns heading level, text, and line number.
    Example: 'docs/specs/latest-plan.md'
    """
    path = resolve_repo_path(relative_path)
    if not path.exists():
        return f"Error: file does not exist: {path}"
    if not path.is_file():
        return f"Error: path is not a file: {path}"

    content = path.read_text(encoding="utf-8")
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

    headings = []
    for i, line in enumerate(content.splitlines(), start=1):
        match = heading_pattern.match(line)
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            indent = "  " * (level - 1)
            headings.append(f"  {indent}L{i:4d}  H{level} {text}")

    if not headings:
        return f"No markdown headings found in: {path}"

    return f"Headings in {path} ({len(headings)} total):\n" + "\n".join(headings)