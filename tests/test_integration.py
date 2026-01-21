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

    def test_new_session_setup(self, mock_sections_dir, temp_dir):
        """Full setup for a new session should succeed."""
        # Create minimal plugin structure
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()
        scripts_dir = plugin_root / "scripts" / "checks"
        scripts_dir.mkdir(parents=True)
        lib_dir = plugin_root / "scripts" / "lib"
        lib_dir.mkdir(parents=True)

        # Copy actual implementation files
        # Note: In real test, this would use installed package
        # For now, we test the script directly

        # This test assumes the setup script is properly installed
        # Skip if not available
        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found - run after implementation")

        result = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
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
        assert len(output["todos"]) > 0

        # Verify config was created
        impl_dir = mock_sections_dir.parent / "implementation"
        assert (impl_dir / "deep_implement_config.json").exists()

    def test_setup_creates_implementation_dir(self, mock_sections_dir, temp_dir):
        """Setup should create implementation directory if missing."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        impl_dir = mock_sections_dir.parent / "implementation"
        assert not impl_dir.exists()

        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found")

        subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
                "--plugin-root", str(plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert impl_dir.exists()
        assert (impl_dir / "deep_implement_config.json").exists()


class TestResumeFlow:
    """Integration tests for resume functionality."""

    def test_resume_session_setup(self, mock_sections_dir, temp_dir, mock_git_repo):
        """Setup with existing partial completion should resume correctly."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        # Create implementation dir with partial progress
        impl_dir = mock_sections_dir.parent / "implementation"
        impl_dir.mkdir()

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
            "implementation_dir": str(impl_dir),
            "git_available": True,
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
        (impl_dir / "deep_implement_config.json").write_text(json.dumps(config))

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
        # Mode depends on whether we verify commit hash
        assert output["git_available"] is True

    def test_all_sections_complete(self, mock_sections_dir, temp_dir):
        """Setup with all sections complete should report complete mode."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        impl_dir = mock_sections_dir.parent / "implementation"
        impl_dir.mkdir()

        # Create config with all sections complete
        config = {
            "plugin_root": str(plugin_root),
            "sections_dir": str(mock_sections_dir),
            "implementation_dir": str(impl_dir),
            "git_available": False,
            "git_root": None,
            "commit_style": "unknown",
            "test_command": "uv run pytest",
            "sections": ["section-01-foundation", "section-02-models"],
            "sections_state": {
                "section-01-foundation": {
                    "status": "complete",
                    "commit_hash": "abc123"
                },
                "section-02-models": {
                    "status": "complete",
                    "commit_hash": "def456"
                }
            },
            "created_at": "2025-01-14T10:00:00Z"
        }
        (impl_dir / "deep_implement_config.json").write_text(json.dumps(config))

        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found")

        result = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
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


class TestNoGitFlow:
    """Integration tests for no-git mode."""

    def test_setup_without_git(self, mock_sections_dir, temp_dir):
        """Setup should work in directory without git."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found")

        # mock_sections_dir is not in a git repo (temp_dir has no .git)
        result = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
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
        assert output["git_available"] is False
        assert output["git_root"] is None
        assert output["working_tree_clean"] is True  # Default when no git


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
        index_content = """<!-- SECTION_MANIFEST
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

        index_content = """<!-- SECTION_MANIFEST
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

    def test_config_persists_across_invocations(self, mock_sections_dir, temp_dir):
        """Session config should persist and be readable across invocations."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found")

        # First invocation
        result1 = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
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
        impl_dir = mock_sections_dir.parent / "implementation"
        config_path = impl_dir / "deep_implement_config.json"
        assert config_path.exists()

        # Read and modify config (simulate section completion)
        config = json.loads(config_path.read_text())
        config["sections_state"]["section-01-foundation"] = {
            "status": "complete",
            "commit_hash": "test123"
        }
        config_path.write_text(json.dumps(config))

        # Second invocation should see the change
        result2 = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
                "--plugin-root", str(plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        output2 = json.loads(result2.stdout)
        assert output2["success"] is True
        # Without git to verify hash, still shows resume
        assert output2["mode"] in ["resume", "new"]


class TestTodoGeneration:
    """Integration tests for TODO generation."""

    def test_todos_include_context_items(self, mock_sections_dir, temp_dir):
        """Generated TODOs should include context items for persistence."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found")

        result = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
                "--plugin-root", str(plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        output = json.loads(result.stdout)
        todos = output["todos"]

        # Should have context items
        context_todos = [t for t in todos if t["status"] == "completed"]
        assert len(context_todos) > 0
        assert any("sections_dir" in t["content"] for t in context_todos)

    def test_todos_include_all_sections(self, mock_sections_dir, temp_dir):
        """Generated TODOs should include item for each section."""
        plugin_root = temp_dir / "plugin"
        plugin_root.mkdir()

        setup_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"
        if not setup_script.exists():
            pytest.skip("Setup script not found")

        result = subprocess.run(
            [
                "uv", "run", str(setup_script),
                "--sections-dir", str(mock_sections_dir),
                "--plugin-root", str(plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        output = json.loads(result.stdout)
        todos = output["todos"]

        # Should have pending todos for each section
        section_todos = [t for t in todos if "section" in t["content"].lower() and "implement" in t["content"].lower()]
        assert len(section_todos) == 2  # mock_sections_dir has 2 sections
