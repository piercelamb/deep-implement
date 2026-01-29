import pytest
import json
import subprocess
from pathlib import Path

from scripts.lib.sections import (
    parse_manifest_block,
    parse_project_config_block,
    validate_section_file,
    get_completed_sections,
    extract_file_paths_from_section,
)


class TestParseProjectConfigBlock:
    """Tests for parse_project_config_block function."""

    def test_valid_config(self):
        """Should parse valid project config block."""
        content = """<!-- PROJECT_CONFIG
runtime: python-uv
test_command: uv run pytest
END_PROJECT_CONFIG -->

# Index content here
"""
        result = parse_project_config_block(content)

        assert result["runtime"] == "python-uv"
        assert result["test_command"] == "uv run pytest"

    def test_config_with_spaces_in_values(self):
        """Should handle values with spaces."""
        content = """<!-- PROJECT_CONFIG
runtime: typescript-pnpm
test_command: pnpm test --coverage
END_PROJECT_CONFIG -->"""

        result = parse_project_config_block(content)

        assert result["runtime"] == "typescript-pnpm"
        assert result["test_command"] == "pnpm test --coverage"

    def test_missing_config(self):
        """Should return empty dict for missing config."""
        content = "# Just a regular markdown file"

        result = parse_project_config_block(content)

        assert result == {}

    def test_config_with_comments(self):
        """Should skip comment lines in config."""
        content = """<!-- PROJECT_CONFIG
# This is a comment
runtime: python-uv
# Another comment
test_command: pytest
END_PROJECT_CONFIG -->"""

        result = parse_project_config_block(content)

        assert len(result) == 2
        assert result["runtime"] == "python-uv"

    def test_config_with_extra_whitespace(self):
        """Should handle whitespace around keys and values."""
        content = """<!-- PROJECT_CONFIG
runtime: python-uv
  test_command: uv run pytest -v

END_PROJECT_CONFIG -->"""

        result = parse_project_config_block(content)

        assert result["runtime"] == "python-uv"
        assert result["test_command"] == "uv run pytest -v"


class TestParseManifestBlock:
    """Tests for parse_manifest_block function."""

    def test_valid_manifest(self):
        """Should parse valid manifest block."""
        content = """<!-- SECTION_MANIFEST
section-01-foundation
section-02-models
section-03-api
END_MANIFEST -->

# Index content here
"""
        result = parse_manifest_block(content)

        assert result == ["section-01-foundation", "section-02-models", "section-03-api"]

    def test_manifest_with_whitespace(self):
        """Should handle whitespace in manifest."""
        content = """<!-- SECTION_MANIFEST
  section-01-foundation
section-02-models

END_MANIFEST -->"""

        result = parse_manifest_block(content)

        assert result == ["section-01-foundation", "section-02-models"]

    def test_missing_manifest(self):
        """Should return empty list for missing manifest."""
        content = "# Just a regular markdown file"

        result = parse_manifest_block(content)

        assert result == []

    def test_empty_manifest(self):
        """Should handle empty manifest block."""
        content = """<!-- SECTION_MANIFEST
END_MANIFEST -->"""

        result = parse_manifest_block(content)

        assert result == []

    def test_malformed_manifest_no_end(self):
        """Should return empty list if END_MANIFEST missing."""
        content = """<!-- SECTION_MANIFEST
section-01-foundation
section-02-models
"""
        result = parse_manifest_block(content)

        assert result == []

    def test_manifest_with_comments(self):
        """Should ignore comment lines in manifest."""
        content = """<!-- SECTION_MANIFEST
section-01-foundation
# This is a comment
section-02-models
END_MANIFEST -->"""

        result = parse_manifest_block(content)

        # Should skip lines starting with #
        assert "section-01-foundation" in result
        assert "section-02-models" in result
        assert len(result) == 2


class TestValidateSectionFile:
    """Tests for validate_section_file function."""

    def test_valid_section_file(self, temp_dir):
        """Should validate section file with content."""
        section = temp_dir / "section-01-test.md"
        section.write_text("# Section 01\n\n## Implementation\nDo the thing.")

        result = validate_section_file(section)

        assert result["valid"] is True
        assert result["error"] is None

    def test_empty_section_file(self, temp_dir):
        """Should reject empty section file."""
        section = temp_dir / "section-01-empty.md"
        section.write_text("")

        result = validate_section_file(section)

        assert result["valid"] is False
        assert "empty" in result["error"].lower()

    def test_whitespace_only_section(self, temp_dir):
        """Should reject section with only whitespace."""
        section = temp_dir / "section-01-whitespace.md"
        section.write_text("   \n\n   \t  ")

        result = validate_section_file(section)

        assert result["valid"] is False
        assert "empty" in result["error"].lower()

    def test_nonexistent_section_file(self, temp_dir):
        """Should reject nonexistent file."""
        section = temp_dir / "section-01-missing.md"

        result = validate_section_file(section)

        assert result["valid"] is False
        assert "not found" in result["error"].lower() or "not exist" in result["error"].lower()


class TestGetCompletedSections:
    """Tests for get_completed_sections function."""

    def test_no_completed_sections(self, mock_implementation_dir, mock_git_repo):
        """Should return empty list when no sections complete."""
        config = {"sections_state": {}}
        (mock_implementation_dir / "deep_implement_config.json").write_text(json.dumps(config))

        result = get_completed_sections(mock_implementation_dir, git_root=mock_git_repo)

        assert result == []

    def test_with_completed_sections_valid_hash(self, mock_implementation_dir, mock_git_repo):
        """Should return list of completed section names with valid commit hash."""
        # Create a commit to reference
        (mock_git_repo / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "test"], cwd=mock_git_repo, capture_output=True)
        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=mock_git_repo,
            capture_output=True,
            text=True
        )
        commit_hash = hash_result.stdout.strip()

        config = {
            "sections_state": {
                "section-01-foundation": {"status": "complete", "commit_hash": commit_hash}
            }
        }
        (mock_implementation_dir / "deep_implement_config.json").write_text(json.dumps(config))

        result = get_completed_sections(mock_implementation_dir, mock_git_repo)

        assert "section-01-foundation" in result

    def test_invalid_commit_hash(self, mock_implementation_dir, mock_git_repo):
        """Should not include section with invalid commit hash."""
        config = {
            "sections_state": {
                "section-01-foundation": {"status": "complete", "commit_hash": "invalidhash123"}
            }
        }
        (mock_implementation_dir / "deep_implement_config.json").write_text(json.dumps(config))

        result = get_completed_sections(mock_implementation_dir, mock_git_repo)

        assert "section-01-foundation" not in result

    def test_no_config_file(self, mock_implementation_dir, mock_git_repo):
        """Should return empty list if no config file."""
        result = get_completed_sections(mock_implementation_dir, git_root=mock_git_repo)

        assert result == []


class TestExtractFilePathsFromSection:
    """Tests for extract_file_paths_from_section function."""

    def test_extract_paths_from_files_table(self):
        """Should extract paths from Files to create table."""
        content = """# Section 01

## Files to Create

| File | Purpose |
|------|---------|
| src/models.py | Data models |
| tests/test_models.py | Model tests |
"""
        result = extract_file_paths_from_section(content)

        assert "src/models.py" in result
        assert "tests/test_models.py" in result

    def test_extract_paths_from_code_blocks(self):
        """Should extract paths from File: annotations."""
        content = """# Section 01

### File: `src/utils.py`

```python
def helper():
    pass
```
"""
        result = extract_file_paths_from_section(content)

        assert "src/utils.py" in result

    def test_extract_paths_from_file_header(self):
        """Should extract paths from **File:** headers."""
        content = """# Section 01

**File: `scripts/lib/config.py`**

```python
# code here
```
"""
        result = extract_file_paths_from_section(content)

        assert "scripts/lib/config.py" in result

    def test_no_paths_found(self):
        """Should return empty list if no paths detected."""
        content = "# Section with no file paths mentioned"

        result = extract_file_paths_from_section(content)

        assert result == []

    def test_deduplicates_paths(self):
        """Should not return duplicate paths."""
        content = """# Section

### File: `src/models.py`

```python
pass
```

### File: `src/models.py`

More content about models.py
"""
        result = extract_file_paths_from_section(content)

        assert result.count("src/models.py") == 1
