import pytest
import json
from pathlib import Path

from scripts.checks.setup_implementation_session import (
    validate_sections_dir,
    check_git_repo,
    check_current_branch,
    check_working_tree_status,
    detect_commit_style,
    infer_session_state,
)


class TestValidateSectionsDir:
    """Tests for validate_sections_dir function."""

    def test_valid_sections_dir(self, mock_sections_dir):
        """Valid sections directory should return success."""
        result = validate_sections_dir(mock_sections_dir)

        assert result["valid"] is True
        assert result["error"] is None
        assert "section-01-foundation" in result["sections"]
        assert "section-02-models" in result["sections"]

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

    def test_missing_manifest_block(self, temp_dir):
        """index.md without SECTION_MANIFEST should return error."""
        sections_dir = temp_dir / "sections"
        sections_dir.mkdir()
        (sections_dir / "index.md").write_text("# Just a header\nNo manifest here.")

        result = validate_sections_dir(sections_dir)

        assert result["valid"] is False
        assert "manifest" in result["error"].lower()

    def test_missing_section_file(self, temp_dir):
        """Manifest referencing non-existent section file should return error."""
        sections_dir = temp_dir / "sections"
        sections_dir.mkdir()
        (sections_dir / "index.md").write_text(
            "<!-- SECTION_MANIFEST\nsection-01-missing\nEND_MANIFEST -->"
        )

        result = validate_sections_dir(sections_dir)

        assert result["valid"] is False
        assert "section-01-missing" in result["error"]

    def test_empty_section_file(self, temp_dir):
        """Section file with no content should return error."""
        sections_dir = temp_dir / "sections"
        sections_dir.mkdir()
        (sections_dir / "index.md").write_text(
            "<!-- SECTION_MANIFEST\nsection-01-empty\nEND_MANIFEST -->"
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

    def test_new_session(self, mock_sections_dir, temp_dir):
        """No existing implementation dir should return mode='new'."""
        result = infer_session_state(mock_sections_dir, temp_dir / "implementation", None)

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

    def test_all_complete(self, mock_sections_dir, mock_implementation_dir):
        """All sections complete should return mode='complete'."""
        config = {
            "sections": ["section-01-foundation", "section-02-models"],
            "sections_state": {
                "section-01-foundation": {"status": "complete", "commit_hash": "abc123"},
                "section-02-models": {"status": "complete", "commit_hash": "def456"}
            }
        }
        (mock_implementation_dir / "deep_implement_config.json").write_text(json.dumps(config))

        result = infer_session_state(mock_sections_dir, mock_implementation_dir, None)

        assert result["mode"] == "complete"
