import pytest
from pathlib import Path
import tempfile
import shutil
import json


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d)


@pytest.fixture
def mock_sections_dir(temp_dir):
    """Create a valid sections directory structure."""
    sections_dir = temp_dir / "sections"
    sections_dir.mkdir()

    # Create index.md with project config and manifest
    index_content = """<!-- PROJECT_CONFIG
runtime: python-uv
test_command: uv run pytest
END_PROJECT_CONFIG -->

<!-- SECTION_MANIFEST
section-01-foundation
section-02-models
END_MANIFEST -->

# Implementation Sections Index

## Section Overview
- section-01-foundation: Core setup
- section-02-models: Data models
"""
    (sections_dir / "index.md").write_text(index_content)

    # Create section files
    (sections_dir / "section-01-foundation.md").write_text(
        "# Section 01: Foundation\n\n## Implementation\nCreate the base structure."
    )
    (sections_dir / "section-02-models.md").write_text(
        "# Section 02: Models\n\n## Implementation\nCreate data models."
    )

    return sections_dir


@pytest.fixture
def mock_git_repo(temp_dir):
    """Create a mock git repository."""
    import subprocess
    repo_dir = temp_dir / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, capture_output=True)
    # Create initial commit
    (repo_dir / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True)
    return repo_dir


@pytest.fixture
def mock_implementation_dir(temp_dir):
    """Create a mock implementation directory with config."""
    impl_dir = temp_dir / "implementation"
    impl_dir.mkdir()
    return impl_dir


@pytest.fixture
def sample_config():
    """Return a sample session config."""
    return {
        "plugin_root": "/path/to/plugin",
        "sections_dir": "/path/to/sections",
        "target_dir": "/path/to/target",
        "state_dir": "/path/to/state",
        "git_root": "/path/to/repo",
        "commit_style": "conventional",
        "test_command": "uv run pytest",
        "pre_commit": {
            "present": False,
            "type": "none",
            "may_modify_files": False,
            "detected_formatters": []
        },
        "sections": ["section-01-foundation", "section-02-models"],
        "sections_state": {},
        "created_at": "2025-01-14T10:30:00Z"
    }
