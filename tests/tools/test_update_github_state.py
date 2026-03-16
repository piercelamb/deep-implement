"""Tests for update_github_state CLI tool."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "tools" / "update_github_state.py"


class TestUpdateGitHubStateCLI:
    """Tests for update_github_state.py CLI script."""

    def test_stores_issue_number(self, mock_implementation_dir, sample_config):
        """Should store tracking issue number and enable GitHub."""
        config_path = mock_implementation_dir / "deep_implement_config.json"
        config_path.write_text(json.dumps(sample_config))

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--state-dir", str(mock_implementation_dir),
                "--issue-number", "42",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "issue_number=42" in result.stdout

        config = json.loads(config_path.read_text())
        assert config["github"]["issue_number"] == 42
        assert config["github"]["enabled"] is True

    def test_stores_section_pr(self, mock_implementation_dir, sample_config):
        """Should store PR number and URL for a section."""
        config_path = mock_implementation_dir / "deep_implement_config.json"
        config_path.write_text(json.dumps(sample_config))

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--state-dir", str(mock_implementation_dir),
                "--section", "section-01-foundation",
                "--pr-number", "43",
                "--pr-url", "https://github.com/owner/repo/pull/43",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "pr_number=43" in result.stdout

        config = json.loads(config_path.read_text())
        pr_info = config["github"]["section_prs"]["section-01-foundation"]
        assert pr_info["number"] == 43
        assert pr_info["url"] == "https://github.com/owner/repo/pull/43"

    def test_pr_requires_section(self, mock_implementation_dir, sample_config):
        """Should error if --pr-number given without --section."""
        config_path = mock_implementation_dir / "deep_implement_config.json"
        config_path.write_text(json.dumps(sample_config))

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--state-dir", str(mock_implementation_dir),
                "--pr-number", "43",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "--section is required" in result.stdout

    def test_handles_missing_config(self, mock_implementation_dir):
        """Should return error for missing config file."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--state-dir", str(mock_implementation_dir),
                "--issue-number", "42",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "No config found" in result.stdout

    def test_requires_issue_or_pr(self, mock_implementation_dir, sample_config):
        """Should error if neither --issue-number nor --pr-number provided."""
        config_path = mock_implementation_dir / "deep_implement_config.json"
        config_path.write_text(json.dumps(sample_config))

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--state-dir", str(mock_implementation_dir),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "Must provide" in result.stdout

    def test_preserves_existing_prs(self, mock_implementation_dir, sample_config):
        """Should not overwrite other sections' PR info."""
        sample_config["github"]["section_prs"] = {
            "section-01-foundation": {"number": 10, "url": "https://example.com/10"}
        }
        config_path = mock_implementation_dir / "deep_implement_config.json"
        config_path.write_text(json.dumps(sample_config))

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--state-dir", str(mock_implementation_dir),
                "--section", "section-02-models",
                "--pr-number", "11",
                "--pr-url", "https://example.com/11",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        config = json.loads(config_path.read_text())
        assert config["github"]["section_prs"]["section-01-foundation"]["number"] == 10
        assert config["github"]["section_prs"]["section-02-models"]["number"] == 11

    def test_creates_github_key_if_missing(self, mock_implementation_dir, sample_config):
        """Should create github dict if config has no github key."""
        del sample_config["github"]
        config_path = mock_implementation_dir / "deep_implement_config.json"
        config_path.write_text(json.dumps(sample_config))

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--state-dir", str(mock_implementation_dir),
                "--issue-number", "99",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        config = json.loads(config_path.read_text())
        assert config["github"]["issue_number"] == 99
