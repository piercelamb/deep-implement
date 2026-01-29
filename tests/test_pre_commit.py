import pytest
from pathlib import Path

from scripts.checks.setup_implementation_session import check_pre_commit_hooks


class TestCheckPreCommitHooks:
    """Tests for check_pre_commit_hooks function."""

    def test_no_hooks(self, mock_git_repo):
        """Repo without pre-commit should return present=False."""
        result = check_pre_commit_hooks(mock_git_repo)

        assert result["present"] is False
        assert result["type"] == "none"

    def test_pre_commit_framework(self, mock_git_repo):
        """Should detect pre-commit framework config."""
        config_content = """repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
"""
        (mock_git_repo / ".pre-commit-config.yaml").write_text(config_content)

        result = check_pre_commit_hooks(mock_git_repo)

        assert result["present"] is True
        assert result["type"] == "pre-commit-framework"
        assert result["may_modify_files"] is True
        assert "black" in result["detected_formatters"]
        assert "isort" in result["detected_formatters"]

    def test_native_hook_only(self, mock_git_repo):
        """Should detect native pre-commit hook."""
        hooks_dir = mock_git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook = hooks_dir / "pre-commit"
        hook.write_text("#!/bin/bash\necho 'hook running'")
        hook.chmod(0o755)

        result = check_pre_commit_hooks(mock_git_repo)

        assert result["present"] is True
        assert result["type"] == "native-hook"
        assert result["native_hook"] is not None

    def test_both_hooks(self, mock_git_repo):
        """Should detect both framework and native hook."""
        # Add pre-commit config
        (mock_git_repo / ".pre-commit-config.yaml").write_text("repos: []")

        # Add native hook
        hooks_dir = mock_git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook = hooks_dir / "pre-commit"
        hook.write_text("#!/bin/bash\necho 'hook'")
        hook.chmod(0o755)

        result = check_pre_commit_hooks(mock_git_repo)

        assert result["present"] is True
        assert result["type"] == "both"

    def test_detect_python_formatters(self, mock_git_repo):
        """Should detect known Python formatters."""
        config = """repos:
  - repo: https://github.com/psf/black
    hooks:
      - id: black
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff-format
"""
        (mock_git_repo / ".pre-commit-config.yaml").write_text(config)

        result = check_pre_commit_hooks(mock_git_repo)

        assert "black" in result["detected_formatters"]
        assert any("ruff" in f for f in result["detected_formatters"])

    def test_detect_prettier(self, mock_git_repo):
        """Should detect Prettier formatter."""
        config = """repos:
  - repo: https://github.com/pre-commit/mirrors-prettier
    hooks:
      - id: prettier
"""
        (mock_git_repo / ".pre-commit-config.yaml").write_text(config)

        result = check_pre_commit_hooks(mock_git_repo)

        assert result["may_modify_files"] is True
        assert "prettier" in result["detected_formatters"]

    def test_linters_not_marked_as_formatters(self, mock_git_repo):
        """Linter-only hooks should not be marked as formatters."""
        config = """repos:
  - repo: https://github.com/pycqa/flake8
    hooks:
      - id: flake8
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: check-yaml
"""
        (mock_git_repo / ".pre-commit-config.yaml").write_text(config)

        result = check_pre_commit_hooks(mock_git_repo)

        # flake8 and check-yaml don't modify files
        assert result["may_modify_files"] is False
        assert result["detected_formatters"] == []

    def test_rustfmt_detection(self, mock_git_repo):
        """Should detect rustfmt."""
        config = """repos:
  - repo: https://github.com/doublify/pre-commit-rust
    hooks:
      - id: fmt
"""
        (mock_git_repo / ".pre-commit-config.yaml").write_text(config)

        result = check_pre_commit_hooks(mock_git_repo)

        assert result["may_modify_files"] is True

    def test_gofmt_detection(self, mock_git_repo):
        """Should detect gofmt/goimports."""
        config = """repos:
  - repo: https://github.com/dnephin/pre-commit-golang
    hooks:
      - id: gofmt
      - id: goimports
"""
        (mock_git_repo / ".pre-commit-config.yaml").write_text(config)

        result = check_pre_commit_hooks(mock_git_repo)

        assert result["may_modify_files"] is True
        assert any("go" in f for f in result["detected_formatters"])
