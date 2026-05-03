"""Tests for agents.tools.common_tools."""

import json
from pathlib import Path

import pytest

from agents.tools.common_tools import (
    validate_yaml,
    validate_json,
    check_markdown_links,
    search_code,
    count_lines,
    extract_headings,
)


@pytest.fixture
def tmp_repo(monkeypatch, tmp_path):
    """Create a temporary directory structure mimicking the repo root."""
    docs = tmp_path / "docs"
    docs.mkdir()
    apps = tmp_path / "apps"
    apps.mkdir()

    import agents.tools.common_tools as ct

    orig = ct.resolve_repo_path

    def fake_resolve(relative_path: str) -> Path:
        target = (tmp_path / relative_path).resolve()
        try:
            target.relative_to(tmp_path.resolve())
        except ValueError:
            raise ValueError(f"Path '{relative_path}' points outside of the repository root.")
        return target

    monkeypatch.setattr(ct, "resolve_repo_path", fake_resolve)
    monkeypatch.setattr(ct, "get_repo_root", lambda: tmp_path.resolve())
    return tmp_path


# ── validate_yaml ───────────────────────────────────────────────────────────


class TestValidateYaml:
    def test_valid_yaml_dict(self, tmp_repo):
        (tmp_repo / "docs" / "config.yaml").write_text("key1: val1\nkey2: val2\n")
        result = validate_yaml.func("docs/config.yaml")
        assert "Valid YAML" in result
        assert "key1" in result

    def test_valid_yaml_list(self, tmp_repo):
        (tmp_repo / "docs" / "list.yaml").write_text("- item1\n- item2\n")
        result = validate_yaml.func("docs/list.yaml")
        assert "Valid YAML" in result
        assert "list with 2 items" in result

    def test_parse_error(self, tmp_repo):
        (tmp_repo / "docs" / "bad.yaml").write_text(": bad syntax\n")
        result = validate_yaml.func("docs/bad.yaml")
        assert "YAML parse error" in result

    def test_missing_file(self):
        result = validate_yaml.func("docs/nonexistent.yaml")
        assert "Error: file does not exist" in result

    def test_empty_file(self, tmp_repo):
        (tmp_repo / "docs" / "empty.yaml").write_text("")
        result = validate_yaml.func("docs/empty.yaml")
        assert "empty" in result.lower()


# ── validate_json ───────────────────────────────────────────────────────────


class TestValidateJson:
    def test_valid_json_dict(self, tmp_repo):
        (tmp_repo / "docs" / "config.json").write_text('{"key": "val"}')
        result = validate_json.func("docs/config.json")
        assert "Valid JSON" in result
        assert "key" in result

    def test_valid_json_list(self, tmp_repo):
        (tmp_repo / "docs" / "list.json").write_text('[1, 2, 3]')
        result = validate_json.func("docs/list.json")
        assert "Valid JSON" in result

    def test_parse_error(self, tmp_repo):
        (tmp_repo / "docs" / "bad.json").write_text("{invalid")
        result = validate_json.func("docs/bad.json")
        assert "JSON parse error" in result

    def test_missing_file(self):
        result = validate_json.func("docs/nonexistent.json")
        assert "Error: file does not exist" in result


# ── check_markdown_links ───────────────────────────────────────────────────


class TestCheckMarkdownLinks:
    def test_no_links(self, tmp_repo):
        (tmp_repo / "docs" / "nolinks.md").write_text("# No links here")
        result = check_markdown_links.func("docs/nolinks.md")
        assert "No markdown links found" in result

    def test_valid_internal_link(self, tmp_repo):
        (tmp_repo / "docs" / "source.md").write_text("[target](target.md)")
        (tmp_repo / "docs" / "target.md").write_text("Hello")
        result = check_markdown_links.func("docs/source.md")
        assert "Valid internal links" in result

    def test_broken_link(self, tmp_repo):
        (tmp_repo / "docs" / "source.md").write_text("[missing](missing.md)")
        result = check_markdown_links.func("docs/source.md")
        assert "Broken links" in result

    def test_external_link_skipped(self, tmp_repo):
        (tmp_repo / "docs" / "source.md").write_text("[ext](https://example.com)")
        result = check_markdown_links.func("docs/source.md")
        assert "External/skipped links" in result

    def test_mixed_links(self, tmp_repo):
        (tmp_repo / "docs" / "source.md").write_text(
            "[good](good.md)\n[ext](https://x.com)\n[bad](bad.md)"
        )
        (tmp_repo / "docs" / "good.md").write_text("ok")
        result = check_markdown_links.func("docs/source.md")
        assert "Valid internal links" in result
        assert "External/skipped links" in result
        assert "Broken links" in result


# ── search_code ─────────────────────────────────────────────────────────────


class TestSearchCode:
    def test_finds_pattern(self, tmp_repo):
        (tmp_repo / "docs" / "a.md").write_text("API endpoint\nREST\nGraphQL")
        result = search_code.func("docs", pattern="API|REST", file_glob="*.md")
        assert "Found" in result
        assert "API endpoint" in result

    def test_no_matches(self, tmp_repo):
        (tmp_repo / "docs" / "a.md").write_text("nothing here")
        result = search_code.func("docs", pattern="ZZZ_NOT_FOUND", file_glob="*.md")
        assert "No matches" in result

    def test_requires_pattern(self):
        result = search_code.func(".", pattern="")
        assert "Error" in result

    def test_invalid_regex(self):
        result = search_code.func(".", pattern="[invalid")
        assert "Error" in result

    def test_case_insensitive(self, tmp_repo):
        (tmp_repo / "docs" / "a.md").write_text("ENDPOINT")
        result = search_code.func("docs", pattern="endpoint", file_glob="*.md")
        assert "ENDPOINT" in result

    def test_truncates_to_max_results(self, tmp_repo):
        for i in range(40):
            (tmp_repo / f"file_{i}.md").write_text(f"match_{i}")
        result = search_code.func(".", pattern="match_", file_glob="*.md", max_results=5)
        assert "Found 5" in result


# ── count_lines ─────────────────────────────────────────────────────────────


class TestCountLines:
    def test_counts_lines(self, tmp_repo):
        (tmp_repo / "docs" / "a.md").write_text("line1\nline2\nline3")
        (tmp_repo / "docs" / "b.md").write_text("one")
        result = count_lines.func("docs", file_glob="*.md")
        assert "Total lines: 4" in result
        assert "2 files" in result

    def test_no_matching_files(self, tmp_repo):
        result = count_lines.func("docs", file_glob="*.py")
        assert "No files matching" in result


# ── extract_headings ────────────────────────────────────────────────────────


class TestExtractHeadings:
    def test_extracts_headings(self, tmp_repo):
        content = "# H1\n## H2\n### H3\nplain text\n## H2b\n"
        (tmp_repo / "docs" / "doc.md").write_text(content)
        result = extract_headings.func("docs/doc.md")
        assert "H1" in result
        assert "H2" in result
        assert "H3" in result
        assert "H2b" in result
        assert "4 total" in result

    def test_no_headings(self, tmp_repo):
        (tmp_repo / "docs" / "doc.md").write_text("Just text, no headings")
        result = extract_headings.func("docs/doc.md")
        assert "No markdown headings found" in result