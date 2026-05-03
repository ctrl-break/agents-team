"""Tests for agents.tools.path_utils."""

from pathlib import Path

import pytest

from agents.tools.path_utils import get_repo_root, resolve_repo_path


class TestGetRepoRoot:
    """Tests for get_repo_root()."""

    def test_returns_path(self):
        root = get_repo_root()
        assert isinstance(root, Path)

    def test_is_absolute(self):
        root = get_repo_root()
        assert root.is_absolute() or root.resolve().is_absolute()

    def test_contains_agents_directory(self):
        root = get_repo_root()
        agents_dir = root / "agents"
        assert agents_dir.exists() or agents_dir.is_dir()


class TestResolveRepoPath:
    """Tests for resolve_repo_path()."""

    def test_simple_relative_path(self):
        result = resolve_repo_path("agents/pyproject.toml")
        assert result.name == "pyproject.toml"
        assert result.exists()

    def test_docs_directory(self):
        result = resolve_repo_path("docs")
        root = get_repo_root()
        assert result == root / "docs"

    def test_path_traversal_raises(self):
        with pytest.raises(ValueError, match="outside of the repository root"):
            resolve_repo_path("../etc/passwd")

    def test_multiple_level_traversal_raises(self):
        with pytest.raises(ValueError, match="outside of the repository root"):
            resolve_repo_path("../../Windows/System32")

    def test_absolute_path_inside_repo_outside_agent_dir(self):
        """Even an absolute path inside repo root should work."""
        root = get_repo_root()
        rel = str(root / "agents" / "pyproject.toml")
        result = resolve_repo_path(rel)
        assert result.exists()

    def test_empty_string(self):
        """Empty string resolves to repo root."""
        result = resolve_repo_path("")
        assert result == get_repo_root().resolve()