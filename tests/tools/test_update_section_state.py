"""Tests for update_section_state CLI tool."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Get the plugin root for running the script
PLUGIN_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "tools" / "update_section_state.py"


class TestUpdateSectionStateCLI:
    """Tests for update_section_state.py CLI script."""

    def test_updates_config_correctly(self, mock_implementation_dir, sample_config):
        """Should update section state with commit hash."""
        # Write initial config
        config_path = mock_implementation_dir / "deep_implement_config.json"
        config_path.write_text(json.dumps(sample_config))

        # Run the script
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--state-dir", str(mock_implementation_dir),
                "--section", "section-01-foundation",
                "--commit-hash", "abc1234",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Updated section-01-foundation" in result.stdout

        # Verify config was updated
        config = json.loads(config_path.read_text())
        assert config["sections_state"]["section-01-foundation"]["status"] == "complete"
        assert config["sections_state"]["section-01-foundation"]["commit_hash"] == "abc1234"

    def test_creates_sections_state_if_missing(self, mock_implementation_dir, sample_config):
        """Should create sections_state dict if it doesn't exist."""
        # Remove sections_state from config
        del sample_config["sections_state"]
        config_path = mock_implementation_dir / "deep_implement_config.json"
        config_path.write_text(json.dumps(sample_config))

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--state-dir", str(mock_implementation_dir),
                "--section", "section-01-foundation",
                "--commit-hash", "def5678",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        config = json.loads(config_path.read_text())
        assert "sections_state" in config
        assert config["sections_state"]["section-01-foundation"]["commit_hash"] == "def5678"

    def test_preserves_other_sections(self, mock_implementation_dir, sample_config):
        """Should not affect other sections when updating one."""
        # Add existing section state
        sample_config["sections_state"] = {
            "section-01-foundation": {
                "status": "complete",
                "commit_hash": "old123",
            }
        }
        config_path = mock_implementation_dir / "deep_implement_config.json"
        config_path.write_text(json.dumps(sample_config))

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--state-dir", str(mock_implementation_dir),
                "--section", "section-02-models",
                "--commit-hash", "new456",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        config = json.loads(config_path.read_text())
        # Old section preserved
        assert config["sections_state"]["section-01-foundation"]["commit_hash"] == "old123"
        # New section added
        assert config["sections_state"]["section-02-models"]["commit_hash"] == "new456"

    def test_handles_missing_config_file(self, mock_implementation_dir):
        """Should return error for missing config file."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--state-dir", str(mock_implementation_dir),
                "--section", "section-01-foundation",
                "--commit-hash", "abc1234",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "Error: No config found" in result.stdout

    def test_with_review_file(self, mock_implementation_dir, sample_config):
        """Should include review_file when provided."""
        config_path = mock_implementation_dir / "deep_implement_config.json"
        config_path.write_text(json.dumps(sample_config))

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--state-dir", str(mock_implementation_dir),
                "--section", "section-01-foundation",
                "--commit-hash", "abc1234",
                "--review-file", "section-01-review.md",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        config = json.loads(config_path.read_text())
        assert config["sections_state"]["section-01-foundation"]["review_file"] == "section-01-review.md"

    def test_requires_state_dir(self):
        """Should error if --state-dir not provided."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--section", "section-01-foundation",
                "--commit-hash", "abc1234",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "required" in result.stderr.lower()

    def test_requires_section(self, mock_implementation_dir):
        """Should error if --section not provided."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--state-dir", str(mock_implementation_dir),
                "--commit-hash", "abc1234",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "required" in result.stderr.lower()

    def test_requires_commit_hash(self, mock_implementation_dir):
        """Should error if --commit-hash not provided."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--state-dir", str(mock_implementation_dir),
                "--section", "section-01-foundation",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "required" in result.stderr.lower()
