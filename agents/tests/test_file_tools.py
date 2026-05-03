"""Tests for agents.tools.file_tools — core file operations used by agents."""

import tempfile
import os
from pathlib import Path

import pytest

from agents.tools.file_tools import (
    IGNORED_NAMES,
    DEFAULT_MAX_LIST_ITEMS,
    _ensure_allowed_path,
    _should_skip_path,
    list_files,
    read_text_file,
    write_text_file,
    write_docs_file,
    write_app_file,
    create_directory,
    create_app_directory,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def temp_work_dir(monkeypatch):
    """Create a temp dir that mimics the repo root with docs/ and apps/ subdirs."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "docs").mkdir()
        (root / "apps").mkdir()
        (root / "agents").mkdir(parents=True, exist_ok=True)

        # Patch get_repo_root to return our temp dir
        monkeypatch.setattr(
            "agents.tools.path_utils.Path",
            lambda p: Path(tmp) / p if not Path(p).is_absolute() else Path(p),
        )
        # Override resolve_repo_path to resolve inside our temp dir
        import agents.tools.file_tools as ft

        original_resolve = ft.resolve_repo_path

        def _fake_resolve(relative_path: str) -> Path:
            target = (Path(tmp) / relative_path).resolve()
            try:
                target.relative_to(Path(tmp).resolve())
            except ValueError:
                raise ValueError(
                    f"Path '{relative_path}' points outside of the repository root."
                )
            return target

        monkeypatch.setattr(ft, "resolve_repo_path", _fake_resolve)
        yield Path(tmp)


# ── _ensure_allowed_path ────────────────────────────────────────────────────


class TestEnsureAllowedPath:
    def test_allows_docs(self):
        _ensure_allowed_path("docs/spec.md", ("docs",))

    def test_allows_apps(self):
        _ensure_allowed_path("apps/myapp/main.py", ("apps",))

    def test_allows_exact_match(self):
        _ensure_allowed_path("docs", ("docs",))

    def test_rejects_other_root(self):
        with pytest.raises(ValueError, match="outside allowed roots"):
            _ensure_allowed_path("other/file.txt", ("docs", "apps"))

    def test_rejects_traversal(self):
        with pytest.raises(ValueError, match="outside allowed roots"):
            _ensure_allowed_path("../etc/passwd", ("docs",))


# ── _should_skip_path ───────────────────────────────────────────────────────


class TestShouldSkipPath:
    def test_skips_git(self, temp_work_dir):
        git_dir = temp_work_dir / ".git"
        git_dir.mkdir()
        assert _should_skip_path(git_dir, temp_work_dir) is True

    def test_skips_node_modules(self, temp_work_dir):
        nm = temp_work_dir / "node_modules"
        nm.mkdir()
        assert _should_skip_path(nm, temp_work_dir) is True

    def test_skips_venv(self, temp_work_dir):
        venv = temp_work_dir / ".venv"
        venv.mkdir()
        assert _should_skip_path(venv, temp_work_dir) is True

    def test_does_not_skip_regular_dir(self, temp_work_dir):
        regular = temp_work_dir / "docs"
        assert _should_skip_path(regular, temp_work_dir) is False

    def test_skips_nested_ignored(self, temp_work_dir):
        nested = temp_work_dir / "apps" / "myapp" / "node_modules"
        nested.mkdir(parents=True)
        assert _should_skip_path(nested, temp_work_dir) is True


# ── read_text_file ──────────────────────────────────────────────────────────


class TestReadTextFile:
    def test_reads_existing_file(self, temp_work_dir):
        (temp_work_dir / "docs" / "test.md").write_text("Hello world", encoding="utf-8")
        result = read_text_file.func("docs/test.md")
        assert "Hello world" in result

    def test_error_on_missing_file(self):
        result = read_text_file.func("docs/nonexistent.md")
        assert result.startswith("Error: file does not exist")

    def test_error_on_directory(self, temp_work_dir):
        result = read_text_file.func("docs")
        assert "Error" in result


# ── write_text_file ─────────────────────────────────────────────────────────


class TestWriteTextFile:
    def test_writes_new_file(self, temp_work_dir):
        result = write_text_file.func("docs/new.md", "# Test")
        assert "File written" in result
        assert (temp_work_dir / "docs" / "new.md").read_text() == "# Test"

    def test_overwrites_existing(self, temp_work_dir):
        (temp_work_dir / "docs" / "existing.md").write_text("old")
        result = write_text_file.func("docs/existing.md", "new")
        assert "File written" in result
        assert (temp_work_dir / "docs" / "existing.md").read_text() == "new"


# ── write_docs_file ─────────────────────────────────────────────────────────


class TestWriteDocsFile:
    def test_writes_under_docs(self, temp_work_dir):
        result = write_docs_file.func("docs/plan.md", "content")
        assert "File written" in result

    def test_does_not_overwrite_by_default(self, temp_work_dir):
        (temp_work_dir / "docs" / "plan.md").write_text("original")
        result = write_docs_file.func("docs/plan.md", "new")
        assert "Error: file already exists" in result

    def test_rejects_non_docs_path(self):
        with pytest.raises(ValueError):
            write_docs_file.func("apps/something.md", "x")


# ── write_app_file ──────────────────────────────────────────────────────────


class TestWriteAppFile:
    def test_writes_under_apps(self, temp_work_dir):
        result = write_app_file.func("apps/main.py", "print('hi')")
        assert "File written" in result

    def test_rejects_non_apps_path(self):
        with pytest.raises(ValueError):
            write_app_file.func("docs/something.md", "x")


# ── create_directory ────────────────────────────────────────────────────────


class TestCreateDirectory:
    def test_creates_dir(self, temp_work_dir):
        result = create_directory.func("apps/myapp/src")
        assert "Directory created" in result
        assert (temp_work_dir / "apps" / "myapp" / "src").is_dir()

    def test_existing_dir_is_ok(self, temp_work_dir):
        (temp_work_dir / "apps" / "existing").mkdir()
        result = create_directory.func("apps/existing")
        assert "Directory created" in result


# ── create_app_directory ────────────────────────────────────────────────────


class TestCreateAppDirectory:
    def test_creates_app_dir(self, temp_work_dir):
        result = create_app_directory.func("apps/myapp")
        assert "Directory created" in result
        assert (temp_work_dir / "apps" / "myapp").is_dir()

    def test_rejects_non_apps(self):
        with pytest.raises(ValueError):
            create_app_directory.func("docs/something")


# ── list_files ──────────────────────────────────────────────────────────────


class TestListFiles:
    def test_lists_files(self, temp_work_dir):
        (temp_work_dir / "docs" / "a.md").write_text("a")
        (temp_work_dir / "docs" / "b.md").write_text("b")
        result = list_files.func("docs", recursive=False)
        assert "[FILE] a.md" in result
        assert "[FILE] b.md" in result

    def test_truncates_long_lists(self, temp_work_dir):
        for i in range(10):
            (temp_work_dir / f"file_{i}.txt").write_text("x")
        result = list_files.func(".", recursive=False, max_items=5)
        assert "truncated" in result.lower()

    def test_error_on_missing_path(self):
        result = list_files.func("nonexistent")
        assert "Error" in result

    def test_skips_ignored_dirs(self, temp_work_dir):
        (temp_work_dir / ".git").mkdir()
        (temp_work_dir / "docs" / "real.md").write_text("real")
        result = list_files.func(".", recursive=False)
        assert ".git" not in result
        assert "docs" in result or "real.md" in result