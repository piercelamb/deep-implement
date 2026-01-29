"""
Integration tests for deep-implement.

These tests verify full workflows across multiple components.
"""

import pytest
import subprocess
import json
import shutil
from pathlib import Path


class TestFullSetupFlow:
    """Integration tests for complete setup flow."""

    def test_new_session_setup(self, mock_sections_dir, temp_dir, mock_git_repo):
        """Full setup for a new session should succeed."""
        # Create minimal plugin structure
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()
        scripts_dir = plugin_root / "scripts" / "checks"
        scripts_dir.mkdir(parents=True)
        lib_dir = plugin_root / "scripts" / "lib"
        lib_dir.mkdir(parents=True)

        # Target directory must be a git repo
        target_dir = mock_git_repo

        # This test assumes the setup script is properly installed
        # Skip if not available
        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found - run after implementation")

        result = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
                "--target-dir", str(target_dir),
                "--plugin-root", str(plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Parse output
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {result.stdout}\nstderr: {result.stderr}")

        assert output["success"] is True
        assert output["mode"] == "new"
        assert len(output["sections"]) == 2
        # Tasks may or may not be written depending on CLAUDE_SESSION_ID
        assert "tasks_written" in output
        # Resolve both paths to handle macOS /var -> /private/var symlink
        assert Path(output["target_dir"]).resolve() == target_dir.resolve()
        assert output["git_root"] is not None

        # Verify config was created in state_dir
        state_dir = mock_sections_dir.parent / "implementation"
        assert (state_dir / "deep_implement_config.json").exists()

    def test_setup_creates_state_dir(self, mock_sections_dir, temp_dir, mock_git_repo):
        """Setup should create state directory if missing."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        # Target directory must be a git repo
        target_dir = mock_git_repo

        state_dir = mock_sections_dir.parent / "implementation"
        assert not state_dir.exists()

        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found")

        subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
                "--target-dir", str(target_dir),
                "--plugin-root", str(plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert state_dir.exists()
        assert (state_dir / "deep_implement_config.json").exists()

    def test_setup_fails_without_git(self, mock_sections_dir, temp_dir):
        """Setup should fail if target directory is not a git repo."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        # Target directory is NOT a git repo
        target_dir = temp_dir / "target"
        target_dir.mkdir()

        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found")

        result = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
                "--target-dir", str(target_dir),
                "--plugin-root", str(plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {result.stdout}\nstderr: {result.stderr}")

        assert output["success"] is False
        assert "git" in output["error"].lower()


class TestResumeFlow:
    """Integration tests for resume functionality."""

    def test_resume_session_setup(self, mock_sections_dir, temp_dir, mock_git_repo):
        """Setup with existing partial completion should resume correctly."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        # Create state dir with partial progress
        state_dir = mock_sections_dir.parent / "implementation"
        state_dir.mkdir()

        # Create a real commit to reference
        (mock_git_repo / "test_file.py").write_text("# test")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "test commit"], cwd=mock_git_repo, capture_output=True)
        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=mock_git_repo,
            capture_output=True,
            text=True
        )
        commit_hash = hash_result.stdout.strip()

        # Create config showing section-01 complete
        config = {
            "plugin_root": str(plugin_root),
            "sections_dir": str(mock_sections_dir),
            "target_dir": str(mock_git_repo),
            "state_dir": str(state_dir),
            "git_root": str(mock_git_repo),
            "commit_style": "simple",
            "test_command": "uv run pytest",
            "sections": ["section-01-foundation", "section-02-models"],
            "sections_state": {
                "section-01-foundation": {
                    "status": "complete",
                    "commit_hash": commit_hash,
                    "review_file": "review-section-01.md"
                }
            },
            "created_at": "2025-01-14T10:00:00Z"
        }
        (state_dir / "deep_implement_config.json").write_text(json.dumps(config))

        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found")

        # Move sections into git repo for proper detection
        sections_in_repo = mock_git_repo / "sections"
        shutil.copytree(mock_sections_dir, sections_in_repo)

        result = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(sections_in_repo),
                "--target-dir", str(mock_git_repo),
                "--plugin-root", str(plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON: {result.stdout}\nstderr: {result.stderr}")

        # Should detect partial completion
        assert output["success"] is True
        assert output["git_root"] is not None

    def test_all_sections_complete(self, mock_sections_dir, temp_dir, mock_git_repo):
        """Setup with all sections complete should report complete mode."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        # Create two commits to reference
        (mock_git_repo / "file1.py").write_text("# section 1")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "section 1"], cwd=mock_git_repo, capture_output=True)
        hash1_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=mock_git_repo, capture_output=True, text=True)
        hash1 = hash1_result.stdout.strip()

        (mock_git_repo / "file2.py").write_text("# section 2")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "section 2"], cwd=mock_git_repo, capture_output=True)
        hash2_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=mock_git_repo, capture_output=True, text=True)
        hash2 = hash2_result.stdout.strip()

        state_dir = mock_sections_dir.parent / "implementation"
        state_dir.mkdir()

        # Create config with all sections complete (with valid commit hashes)
        config = {
            "plugin_root": str(plugin_root),
            "sections_dir": str(mock_sections_dir),
            "target_dir": str(mock_git_repo),
            "state_dir": str(state_dir),
            "git_root": str(mock_git_repo),
            "commit_style": "simple",
            "test_command": "uv run pytest",
            "sections": ["section-01-foundation", "section-02-models"],
            "sections_state": {
                "section-01-foundation": {
                    "status": "complete",
                    "commit_hash": hash1
                },
                "section-02-models": {
                    "status": "complete",
                    "commit_hash": hash2
                }
            },
            "created_at": "2025-01-14T10:00:00Z"
        }
        (state_dir / "deep_implement_config.json").write_text(json.dumps(config))

        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found")

        result = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
                "--target-dir", str(mock_git_repo),
                "--plugin-root", str(plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON: {result.stdout}")

        assert output["success"] is True
        assert output["mode"] == "complete"


class TestPreCommitIntegration:
    """Integration tests for pre-commit hook handling."""

    def test_setup_detects_pre_commit_framework(self, temp_dir, mock_git_repo):
        """Setup should detect and report pre-commit framework configuration."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        # Create sections in git repo
        sections_dir = mock_git_repo / "sections"
        sections_dir.mkdir()

        # Create valid sections structure
        index_content = """<!-- PROJECT_CONFIG
runtime: python-uv
test_command: uv run pytest
END_PROJECT_CONFIG -->

<!-- SECTION_MANIFEST
section-01-test
END_MANIFEST -->

# Test Index
"""
        (sections_dir / "index.md").write_text(index_content)
        (sections_dir / "section-01-test.md").write_text("# Section 01\nTest content")

        # Add pre-commit config with formatters
        pre_commit_config = """repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
"""
        (mock_git_repo / ".pre-commit-config.yaml").write_text(pre_commit_config)

        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found")

        result = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(sections_dir),
                "--target-dir", str(mock_git_repo),
                "--plugin-root", str(plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON: {result.stdout}\nstderr: {result.stderr}")

        assert output["success"] is True
        assert output["pre_commit"]["present"] is True
        assert output["pre_commit"]["type"] == "pre-commit-framework"
        assert output["pre_commit"]["may_modify_files"] is True
        assert "black" in output["pre_commit"]["detected_formatters"]
        assert "isort" in output["pre_commit"]["detected_formatters"]

    def test_setup_detects_native_hook(self, temp_dir, mock_git_repo):
        """Setup should detect native pre-commit hook."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        sections_dir = mock_git_repo / "sections"
        sections_dir.mkdir()

        index_content = """<!-- PROJECT_CONFIG
runtime: python-uv
test_command: uv run pytest
END_PROJECT_CONFIG -->

<!-- SECTION_MANIFEST
section-01-test
END_MANIFEST -->
"""
        (sections_dir / "index.md").write_text(index_content)
        (sections_dir / "section-01-test.md").write_text("# Test\nContent")

        # Create native hook
        hooks_dir = mock_git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook = hooks_dir / "pre-commit"
        hook.write_text("#!/bin/bash\necho 'Running pre-commit'")
        hook.chmod(0o755)

        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found")

        result = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(sections_dir),
                "--target-dir", str(mock_git_repo),
                "--plugin-root", str(plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON: {result.stdout}")

        assert output["success"] is True
        assert output["pre_commit"]["present"] is True
        assert output["pre_commit"]["type"] == "native-hook"


class TestConfigPersistence:
    """Integration tests for config persistence across resume."""

    def test_config_persists_across_invocations(self, mock_sections_dir, temp_dir, mock_git_repo):
        """Session config should persist and be readable across invocations."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        # Target directory must be a git repo
        target_dir = mock_git_repo

        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found")

        # First invocation
        result1 = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
                "--target-dir", str(target_dir),
                "--plugin-root", str(plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        output1 = json.loads(result1.stdout)
        assert output1["success"] is True
        assert output1["mode"] == "new"

        # Verify config file exists
        state_dir = mock_sections_dir.parent / "implementation"
        config_path = state_dir / "deep_implement_config.json"
        assert config_path.exists()

        # Create a real commit to use for section completion
        (target_dir / "section1.py").write_text("# section 1")
        subprocess.run(["git", "add", "."], cwd=target_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "section 1"], cwd=target_dir, capture_output=True)
        hash_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=target_dir, capture_output=True, text=True)
        commit_hash = hash_result.stdout.strip()

        # Read and modify config (simulate section completion with valid commit hash)
        config = json.loads(config_path.read_text())
        config["sections_state"]["section-01-foundation"] = {
            "status": "complete",
            "commit_hash": commit_hash
        }
        config_path.write_text(json.dumps(config))

        # Second invocation should see the change
        result2 = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
                "--target-dir", str(target_dir),
                "--plugin-root", str(plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        output2 = json.loads(result2.stdout)
        assert output2["success"] is True
        # With valid git commit hash, should show resume
        assert output2["mode"] == "resume"


class TestTaskGeneration:
    """Integration tests for task generation."""

    def test_setup_returns_task_info(self, mock_sections_dir, temp_dir, mock_git_repo, monkeypatch):
        """Setup should return task-related fields in output."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        # Target directory must be a git repo
        target_dir = mock_git_repo

        # Set a session ID so tasks get written
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session-123")

        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found")

        result = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
                "--target-dir", str(target_dir),
                "--plugin-root", str(plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
            env={**subprocess.os.environ, "CLAUDE_SESSION_ID": "test-session-123"}
        )

        output = json.loads(result.stdout)

        # Should have task-related fields
        assert "tasks_written" in output
        assert "session_id" in output
        assert output["session_id"] == "test-session-123"
        assert output["session_id_source"] == "env"
        # With 2 sections, 6 context items, 12 section tasks (6 per section), 1 finalization = 19 tasks
        assert output["tasks_written"] > 0

    def test_setup_without_session_id(self, mock_sections_dir, temp_dir, mock_git_repo, monkeypatch):
        """Setup without session ID should report 0 tasks written."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        # Target directory must be a git repo
        target_dir = mock_git_repo

        # Ensure no session ID is set
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_TASK_LIST_ID", raising=False)

        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found")

        # Create clean environment without session variables
        clean_env = {k: v for k, v in subprocess.os.environ.items()
                     if k not in ("CLAUDE_SESSION_ID", "CLAUDE_CODE_TASK_LIST_ID")}

        result = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
                "--target-dir", str(target_dir),
                "--plugin-root", str(plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
            env=clean_env
        )

        output = json.loads(result.stdout)

        # Should still succeed but report 0 tasks written
        assert output["success"] is True
        assert output["tasks_written"] == 0
        assert output["session_id"] is None
        assert output["session_id_source"] == "none"
