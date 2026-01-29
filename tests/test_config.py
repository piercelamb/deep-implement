import pytest
import json
from pathlib import Path

from scripts.lib.config import (
    load_session_config,
    save_session_config,
    create_session_config,
    update_section_state,
    CONFIG_FILE,
)


class TestLoadSessionConfig:
    """Tests for load_session_config function."""

    def test_load_existing_config(self, mock_implementation_dir, sample_config):
        """Should load config from existing file."""
        config_path = mock_implementation_dir / CONFIG_FILE
        config_path.write_text(json.dumps(sample_config))

        result = load_session_config(mock_implementation_dir)

        assert result["plugin_root"] == sample_config["plugin_root"]
        assert result["sections"] == sample_config["sections"]

    def test_load_nonexistent_config(self, mock_implementation_dir):
        """Should return None for nonexistent config."""
        result = load_session_config(mock_implementation_dir)

        assert result is None

    def test_load_from_nonexistent_directory(self, temp_dir):
        """Should return None for nonexistent directory."""
        result = load_session_config(temp_dir / "nonexistent")

        assert result is None


class TestSaveSessionConfig:
    """Tests for save_session_config function."""

    def test_save_config(self, mock_implementation_dir, sample_config):
        """Should write config to file."""
        save_session_config(mock_implementation_dir, sample_config)

        config_path = mock_implementation_dir / CONFIG_FILE
        assert config_path.exists()

        loaded = json.loads(config_path.read_text())
        assert loaded["plugin_root"] == sample_config["plugin_root"]

    def test_save_creates_directory(self, temp_dir, sample_config):
        """Should create implementation directory if needed."""
        impl_dir = temp_dir / "new_impl"

        save_session_config(impl_dir, sample_config)

        assert (impl_dir / CONFIG_FILE).exists()

    def test_save_overwrites_existing(self, mock_implementation_dir, sample_config):
        """Should overwrite existing config."""
        # Write initial config
        save_session_config(mock_implementation_dir, sample_config)

        # Modify and save again
        sample_config["test_command"] = "pytest -x"
        save_session_config(mock_implementation_dir, sample_config)

        loaded = load_session_config(mock_implementation_dir)
        assert loaded["test_command"] == "pytest -x"


class TestCreateSessionConfig:
    """Tests for create_session_config function."""

    def test_create_new_config(self, temp_dir):
        """Should create config with all required fields."""
        result = create_session_config(
            plugin_root=temp_dir / "plugin",
            sections_dir=temp_dir / "sections",
            target_dir=temp_dir / "target",
            state_dir=temp_dir / "state",
            git_root=temp_dir / "repo",
            commit_style="conventional",
            test_command="pytest"
        )

        assert result["plugin_root"] == str(temp_dir / "plugin")
        assert result["sections_dir"] == str(temp_dir / "sections")
        assert result["target_dir"] == str(temp_dir / "target")
        assert result["state_dir"] == str(temp_dir / "state")
        assert result["git_root"] == str(temp_dir / "repo")
        assert result["test_command"] == "pytest"
        assert "sections_state" in result
        assert result["sections_state"] == {}
        assert "created_at" in result

    def test_create_config_with_sections(self, temp_dir):
        """Should accept sections list."""
        result = create_session_config(
            plugin_root=temp_dir / "plugin",
            sections_dir=temp_dir / "sections",
            target_dir=temp_dir / "target",
            state_dir=temp_dir / "state",
            git_root=temp_dir / "repo",
            commit_style="simple",
            test_command="pytest",
            sections=["section-01-foundation", "section-02-models"]
        )

        assert result["sections"] == ["section-01-foundation", "section-02-models"]


class TestUpdateSectionState:
    """Tests for update_section_state function."""

    def test_update_section_complete(self, mock_implementation_dir, sample_config):
        """Should update section state to complete with hash."""
        save_session_config(mock_implementation_dir, sample_config)

        update_section_state(
            mock_implementation_dir,
            "section-01-foundation",
            status="complete",
            commit_hash="abc123def456",
            review_file="review-section-01.md"
        )

        config = load_session_config(mock_implementation_dir)
        state = config["sections_state"]["section-01-foundation"]
        assert state["status"] == "complete"
        assert state["commit_hash"] == "abc123def456"
        assert state["review_file"] == "review-section-01.md"
        assert "completed_at" in state

    def test_update_preserves_other_sections(self, mock_implementation_dir, sample_config):
        """Should not affect other sections when updating one."""
        sample_config["sections_state"] = {
            "section-01-foundation": {"status": "complete", "commit_hash": "old123"}
        }
        save_session_config(mock_implementation_dir, sample_config)

        update_section_state(
            mock_implementation_dir,
            "section-02-models",
            status="complete",
            commit_hash="new456"
        )

        config = load_session_config(mock_implementation_dir)
        assert config["sections_state"]["section-01-foundation"]["commit_hash"] == "old123"
        assert config["sections_state"]["section-02-models"]["commit_hash"] == "new456"

    def test_update_in_progress(self, mock_implementation_dir, sample_config):
        """Should allow setting in_progress status."""
        save_session_config(mock_implementation_dir, sample_config)

        update_section_state(
            mock_implementation_dir,
            "section-01-foundation",
            status="in_progress"
        )

        config = load_session_config(mock_implementation_dir)
        assert config["sections_state"]["section-01-foundation"]["status"] == "in_progress"

    def test_update_with_pre_commit_info(self, mock_implementation_dir, sample_config):
        """Should store pre-commit handling info."""
        save_session_config(mock_implementation_dir, sample_config)

        update_section_state(
            mock_implementation_dir,
            "section-01-foundation",
            status="complete",
            commit_hash="abc123",
            pre_commit={
                "hooks_ran": True,
                "modification_retries": 1,
                "skipped": False
            }
        )

        config = load_session_config(mock_implementation_dir)
        state = config["sections_state"]["section-01-foundation"]
        assert state["pre_commit"]["hooks_ran"] is True
        assert state["pre_commit"]["modification_retries"] == 1
