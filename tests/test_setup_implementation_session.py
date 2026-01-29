import pytest
import json
import subprocess
import sys
from pathlib import Path

from scripts.checks.setup_implementation_session import (
    validate_sections_dir,
    check_git_repo,
    check_current_branch,
    check_working_tree_status,
    detect_commit_style,
    detect_section_review_state,
    infer_session_state,
)

SETUP_SCRIPT = Path(__file__).parent.parent / "scripts" / "checks" / "setup_implementation_session.py"


class TestValidateSectionsDir:
    """Tests for validate_sections_dir function."""

    def test_valid_sections_dir(self, mock_sections_dir):
        """Valid sections directory should return success."""
        result = validate_sections_dir(mock_sections_dir)

        assert result["valid"] is True
        assert result["error"] is None
        assert "section-01-foundation" in result["sections"]
        assert "section-02-models" in result["sections"]
        assert result["project_config"]["runtime"] == "python-uv"
        assert result["project_config"]["test_command"] == "uv run pytest"

    def test_nonexistent_dir(self, temp_dir):
        """Non-existent directory should return error."""
        result = validate_sections_dir(temp_dir / "nonexistent")

        assert result["valid"] is False
        assert "does not exist" in result["error"].lower()

    def test_file_instead_of_dir(self, temp_dir):
        """File path instead of directory should return error."""
        file_path = temp_dir / "not_a_dir.txt"
        file_path.write_text("content")

        result = validate_sections_dir(file_path)

        assert result["valid"] is False
        assert "not a directory" in result["error"].lower()

    def test_missing_index_md(self, temp_dir):
        """Directory without index.md should return error."""
        sections_dir = temp_dir / "sections"
        sections_dir.mkdir()

        result = validate_sections_dir(sections_dir)

        assert result["valid"] is False
        assert "index.md" in result["error"].lower()

    def test_missing_project_config_block(self, temp_dir):
        """index.md without PROJECT_CONFIG should return error."""
        sections_dir = temp_dir / "sections"
        sections_dir.mkdir()
        (sections_dir / "index.md").write_text("# Just a header\nNo config here.")

        result = validate_sections_dir(sections_dir)

        assert result["valid"] is False
        assert "project_config" in result["error"].lower()

    def test_missing_manifest_block(self, temp_dir):
        """index.md without SECTION_MANIFEST should return error."""
        sections_dir = temp_dir / "sections"
        sections_dir.mkdir()
        (sections_dir / "index.md").write_text(
            "<!-- PROJECT_CONFIG\nruntime: python-uv\ntest_command: uv run pytest\nEND_PROJECT_CONFIG -->\n# No manifest here."
        )

        result = validate_sections_dir(sections_dir)

        assert result["valid"] is False
        assert "manifest" in result["error"].lower()

    def test_missing_section_file(self, temp_dir):
        """Manifest referencing non-existent section file should return error."""
        sections_dir = temp_dir / "sections"
        sections_dir.mkdir()
        (sections_dir / "index.md").write_text(
            "<!-- PROJECT_CONFIG\nruntime: python-uv\ntest_command: uv run pytest\nEND_PROJECT_CONFIG -->\n<!-- SECTION_MANIFEST\nsection-01-missing\nEND_MANIFEST -->"
        )

        result = validate_sections_dir(sections_dir)

        assert result["valid"] is False
        assert "section-01-missing" in result["error"]

    def test_empty_section_file(self, temp_dir):
        """Section file with no content should return error."""
        sections_dir = temp_dir / "sections"
        sections_dir.mkdir()
        (sections_dir / "index.md").write_text(
            "<!-- PROJECT_CONFIG\nruntime: python-uv\ntest_command: uv run pytest\nEND_PROJECT_CONFIG -->\n<!-- SECTION_MANIFEST\nsection-01-empty\nEND_MANIFEST -->"
        )
        (sections_dir / "section-01-empty.md").write_text("")

        result = validate_sections_dir(sections_dir)

        assert result["valid"] is False
        assert "empty" in result["error"].lower()


class TestCheckGitRepo:
    """Tests for check_git_repo function."""

    def test_valid_git_repo(self, mock_git_repo):
        """Directory in git repo should return available=True."""
        result = check_git_repo(mock_git_repo)

        assert result["available"] is True
        # Resolve both to handle macOS /var -> /private/var symlink
        assert Path(result["root"]).resolve() == mock_git_repo.resolve()

    def test_subdirectory_of_git_repo(self, mock_git_repo):
        """Subdirectory of git repo should find repo root."""
        subdir = mock_git_repo / "subdir"
        subdir.mkdir()

        result = check_git_repo(subdir)

        assert result["available"] is True
        # Resolve both to handle macOS /var -> /private/var symlink
        assert Path(result["root"]).resolve() == mock_git_repo.resolve()

    def test_non_git_directory(self, temp_dir):
        """Directory outside git repo should return available=False."""
        result = check_git_repo(temp_dir)

        assert result["available"] is False
        assert result["root"] is None


class TestCheckCurrentBranch:
    """Tests for check_current_branch function."""

    def test_returns_branch_name(self, mock_git_repo):
        """Should return current branch name."""
        result = check_current_branch(mock_git_repo)

        # mock_git_repo starts on master or main
        assert result["branch"] in ["master", "main"]

    def test_detects_protected_branch_main(self, mock_git_repo):
        """Should flag main as protected."""
        import subprocess
        # Ensure we're on main
        subprocess.run(["git", "checkout", "-b", "main"], cwd=mock_git_repo, capture_output=True)

        result = check_current_branch(mock_git_repo)

        assert result["branch"] == "main"
        assert result["is_protected"] is True

    def test_detects_protected_branch_master(self, mock_git_repo):
        """Should flag master as protected."""
        result = check_current_branch(mock_git_repo)

        # mock_git_repo defaults to master
        if result["branch"] == "master":
            assert result["is_protected"] is True

    def test_detects_protected_branch_release(self, mock_git_repo):
        """Should flag release branches as protected."""
        import subprocess
        subprocess.run(["git", "checkout", "-b", "release/1.0"], cwd=mock_git_repo, capture_output=True)

        result = check_current_branch(mock_git_repo)

        assert result["branch"] == "release/1.0"
        assert result["is_protected"] is True

    def test_feature_branch_not_protected(self, mock_git_repo):
        """Feature branch should not be flagged as protected."""
        import subprocess
        subprocess.run(["git", "checkout", "-b", "feature/my-feature"], cwd=mock_git_repo, capture_output=True)

        result = check_current_branch(mock_git_repo)

        assert result["branch"] == "feature/my-feature"
        assert result["is_protected"] is False

    def test_non_git_dir_returns_none(self, temp_dir):
        """Non-git directory should return None branch."""
        result = check_current_branch(temp_dir)

        assert result["branch"] is None
        assert result["is_protected"] is False


class TestCheckWorkingTreeStatus:
    """Tests for check_working_tree_status function."""

    def test_clean_working_tree(self, mock_git_repo):
        """Clean working tree should return clean=True."""
        result = check_working_tree_status(mock_git_repo)

        assert result["clean"] is True
        assert result["dirty_files"] == []

    def test_dirty_working_tree(self, mock_git_repo):
        """Modified files should return clean=False with file list."""
        (mock_git_repo / "new_file.txt").write_text("new content")

        result = check_working_tree_status(mock_git_repo)

        assert result["clean"] is False
        assert "new_file.txt" in result["dirty_files"]

    def test_modified_tracked_file(self, mock_git_repo):
        """Modified tracked file should appear in dirty_files."""
        (mock_git_repo / "README.md").write_text("modified content")

        result = check_working_tree_status(mock_git_repo)

        assert result["clean"] is False
        assert "README.md" in result["dirty_files"]


class TestDetectCommitStyle:
    """Tests for detect_commit_style function."""

    def test_conventional_commits(self, mock_git_repo):
        """Repo with conventional commits should return 'conventional'."""
        import subprocess
        (mock_git_repo / "file.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "feat: add new feature"], cwd=mock_git_repo, capture_output=True)
        (mock_git_repo / "file2.txt").write_text("content2")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "fix: resolve bug"], cwd=mock_git_repo, capture_output=True)

        result = detect_commit_style(mock_git_repo)

        assert result == "conventional"

    def test_simple_commits(self, mock_git_repo):
        """Repo with simple commits should return 'simple'."""
        import subprocess
        (mock_git_repo / "file.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add new feature"], cwd=mock_git_repo, capture_output=True)
        (mock_git_repo / "file2.txt").write_text("content2")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Fix the bug"], cwd=mock_git_repo, capture_output=True)

        result = detect_commit_style(mock_git_repo)

        assert result in ["simple", "unknown"]

    def test_empty_git_log(self, temp_dir):
        """New repo with only initial commit should return style."""
        import subprocess
        repo = temp_dir / "new_repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True)

        result = detect_commit_style(repo)

        # No commits yet, should return unknown
        assert result == "unknown"


class TestInferSessionState:
    """Tests for session state detection."""

    def test_new_session(self, mock_sections_dir, temp_dir, mock_git_repo):
        """No existing implementation dir should return mode='new'."""
        result = infer_session_state(mock_sections_dir, temp_dir / "implementation", mock_git_repo)

        assert result["mode"] == "new"
        assert result["completed_sections"] == []

    def test_resume_partial_completion(self, mock_sections_dir, mock_implementation_dir, mock_git_repo):
        """Partial completion should return mode='resume' with correct resume point."""
        import subprocess

        # Create a commit to reference
        (mock_git_repo / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "test"], cwd=mock_git_repo, capture_output=True)
        hash_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=mock_git_repo, capture_output=True, text=True)
        commit_hash = hash_result.stdout.strip()

        # Create config with one completed section
        config = {
            "sections": ["section-01-foundation", "section-02-models"],
            "sections_state": {
                "section-01-foundation": {
                    "status": "complete",
                    "commit_hash": commit_hash
                }
            }
        }
        (mock_implementation_dir / "deep_implement_config.json").write_text(json.dumps(config))

        result = infer_session_state(
            mock_sections_dir,
            mock_implementation_dir,
            mock_git_repo
        )

        assert result["mode"] == "resume"
        assert result["resume_from"] == "section-02-models"
        assert "section-01-foundation" in result["completed_sections"]

    def test_all_complete(self, mock_sections_dir, mock_implementation_dir, mock_git_repo):
        """All sections complete should return mode='complete'."""
        import subprocess

        # Create actual commits to use as valid hashes
        (mock_git_repo / "section1.py").write_text("# section 1")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "section 1"], cwd=mock_git_repo, capture_output=True)
        hash1_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=mock_git_repo, capture_output=True, text=True)
        hash1 = hash1_result.stdout.strip()

        (mock_git_repo / "section2.py").write_text("# section 2")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "section 2"], cwd=mock_git_repo, capture_output=True)
        hash2_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=mock_git_repo, capture_output=True, text=True)
        hash2 = hash2_result.stdout.strip()

        config = {
            "sections": ["section-01-foundation", "section-02-models"],
            "sections_state": {
                "section-01-foundation": {"status": "complete", "commit_hash": hash1},
                "section-02-models": {"status": "complete", "commit_hash": hash2}
            }
        }
        (mock_implementation_dir / "deep_implement_config.json").write_text(json.dumps(config))

        result = infer_session_state(mock_sections_dir, mock_implementation_dir, mock_git_repo)

        assert result["mode"] == "complete"


class TestDetectSectionReviewState:
    """Tests for detect_section_review_state function."""

    def test_no_review_files(self, mock_implementation_dir):
        """Should return implement step when no review files exist."""
        result = detect_section_review_state(mock_implementation_dir, "section-01-foundation")

        assert result["has_diff"] is False
        assert result["has_review"] is False
        assert result["has_interview"] is False
        assert result["resume_step"] == "implement"

    def test_diff_only(self, mock_implementation_dir):
        """Should return review step when only diff exists."""
        code_review_dir = mock_implementation_dir / "code_review"
        code_review_dir.mkdir()
        (code_review_dir / "section-01-diff.md").write_text("# Diff content")

        result = detect_section_review_state(mock_implementation_dir, "section-01-foundation")

        assert result["has_diff"] is True
        assert result["has_review"] is False
        assert result["has_interview"] is False
        assert result["resume_step"] == "review"

    def test_diff_and_review(self, mock_implementation_dir):
        """Should return interview step when diff and review exist."""
        code_review_dir = mock_implementation_dir / "code_review"
        code_review_dir.mkdir()
        (code_review_dir / "section-01-diff.md").write_text("# Diff content")
        (code_review_dir / "section-01-review.md").write_text("# Review findings")

        result = detect_section_review_state(mock_implementation_dir, "section-01-foundation")

        assert result["has_diff"] is True
        assert result["has_review"] is True
        assert result["has_interview"] is False
        assert result["resume_step"] == "interview"

    def test_interview_exists(self, mock_implementation_dir):
        """Should return apply_fixes step when interview exists (regardless of content)."""
        code_review_dir = mock_implementation_dir / "code_review"
        code_review_dir.mkdir()
        (code_review_dir / "section-01-diff.md").write_text("# Diff")
        (code_review_dir / "section-01-review.md").write_text("# Review")
        # Content doesn't matter - file existence is the checkpoint
        (code_review_dir / "section-01-interview.md").write_text(
            "# Interview\n\n## Findings..."
        )

        result = detect_section_review_state(mock_implementation_dir, "section-01-foundation")

        assert result["has_interview"] is True
        assert result["resume_step"] == "apply_fixes"

    def test_section_02_files(self, mock_implementation_dir):
        """Should detect files for section-02 correctly."""
        code_review_dir = mock_implementation_dir / "code_review"
        code_review_dir.mkdir()
        (code_review_dir / "section-02-diff.md").write_text("# Diff")
        (code_review_dir / "section-02-review.md").write_text("# Review")

        result = detect_section_review_state(mock_implementation_dir, "section-02-models")

        assert result["has_diff"] is True
        assert result["has_review"] is True
        assert result["has_interview"] is False
        assert result["resume_step"] == "interview"

    def test_infer_state_includes_review_state(self, mock_sections_dir, mock_implementation_dir, mock_git_repo):
        """infer_session_state should include resume_section_state for incomplete section."""
        # Create config with no completed sections
        config = {
            "sections": ["section-01-foundation", "section-02-models"],
            "sections_state": {}
        }
        (mock_implementation_dir / "deep_implement_config.json").write_text(json.dumps(config))

        # Create review files for section-01 (interview exists = apply fixes from beginning)
        code_review_dir = mock_implementation_dir / "code_review"
        code_review_dir.mkdir()
        (code_review_dir / "section-01-diff.md").write_text("# Diff")
        (code_review_dir / "section-01-review.md").write_text("# Review")
        (code_review_dir / "section-01-interview.md").write_text("# Interview transcript")

        result = infer_session_state(mock_sections_dir, mock_implementation_dir, mock_git_repo)

        assert result["resume_from"] == "section-01-foundation"
        assert result["resume_section_state"] is not None
        assert result["resume_section_state"]["resume_step"] == "apply_fixes"
        assert result["resume_section_state"]["has_interview"] is True


class TestSessionIdHandling:
    """Tests for --session-id argument and diagnostic output."""

    def _run_setup_script(
        self,
        sections_dir: Path,
        target_dir: Path,
        plugin_root: Path,
        session_id: str | None = None,
        env_session_id: str | None = None,
    ) -> dict:
        """Run setup script and return parsed JSON output."""
        import os

        cmd = [
            sys.executable,
            str(SETUP_SCRIPT),
            "--sections-dir", str(sections_dir),
            "--target-dir", str(target_dir),
            "--plugin-root", str(plugin_root),
        ]
        if session_id:
            cmd.extend(["--session-id", session_id])

        env = os.environ.copy()
        # Clear any existing session vars
        env.pop("CLAUDE_SESSION_ID", None)
        env.pop("CLAUDE_CODE_TASK_LIST_ID", None)
        if env_session_id:
            env["CLAUDE_SESSION_ID"] = env_session_id

        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return json.loads(result.stdout)

    def test_session_id_from_arg_takes_precedence(
        self, mock_sections_dir, mock_git_repo
    ):
        """--session-id should take precedence over env var."""
        plugin_root = Path(__file__).parent.parent

        output = self._run_setup_script(
            sections_dir=mock_sections_dir,
            target_dir=mock_git_repo,
            plugin_root=plugin_root,
            session_id="context-session-123",
            env_session_id="env-session-456",
        )

        assert output["success"] is True
        assert output["session_id"] == "context-session-123"
        assert output["session_id_source"] == "context"
        assert output["session_id_matched"] is False

    def test_session_id_from_env_when_no_arg(
        self, mock_sections_dir, mock_git_repo
    ):
        """Should use env var when --session-id not provided."""
        plugin_root = Path(__file__).parent.parent

        output = self._run_setup_script(
            sections_dir=mock_sections_dir,
            target_dir=mock_git_repo,
            plugin_root=plugin_root,
            session_id=None,
            env_session_id="env-session-789",
        )

        assert output["success"] is True
        assert output["session_id"] == "env-session-789"
        assert output["session_id_source"] == "env"
        assert output["session_id_matched"] is None  # Only one source

    def test_session_id_matched_true_when_same(
        self, mock_sections_dir, mock_git_repo
    ):
        """session_id_matched should be True when both sources have same value."""
        plugin_root = Path(__file__).parent.parent

        output = self._run_setup_script(
            sections_dir=mock_sections_dir,
            target_dir=mock_git_repo,
            plugin_root=plugin_root,
            session_id="same-session-id",
            env_session_id="same-session-id",
        )

        assert output["success"] is True
        assert output["session_id"] == "same-session-id"
        assert output["session_id_source"] == "context"
        assert output["session_id_matched"] is True

    def test_session_id_none_when_neither_provided(
        self, mock_sections_dir, mock_git_repo
    ):
        """Should report source='none' when no session ID available."""
        plugin_root = Path(__file__).parent.parent

        output = self._run_setup_script(
            sections_dir=mock_sections_dir,
            target_dir=mock_git_repo,
            plugin_root=plugin_root,
            session_id=None,
            env_session_id=None,
        )

        assert output["success"] is True
        assert output["session_id"] is None
        assert output["session_id_source"] == "none"
        assert output["session_id_matched"] is None
        assert output["task_write_error"] is not None  # Should report error

    def test_tasks_written_with_context_session_id(
        self, mock_sections_dir, mock_git_repo, tmp_path
    ):
        """Tasks should be written when --session-id provided."""
        plugin_root = Path(__file__).parent.parent

        output = self._run_setup_script(
            sections_dir=mock_sections_dir,
            target_dir=mock_git_repo,
            plugin_root=plugin_root,
            session_id="task-test-session",
            env_session_id=None,
        )

        assert output["success"] is True
        assert output["tasks_written"] > 0
        assert output["task_write_error"] is None
