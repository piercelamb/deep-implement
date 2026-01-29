import pytest
import os
from pathlib import Path

from scripts.checks.setup_implementation_session import validate_path_safety


class TestValidatePathSafety:
    """Tests for validate_path_safety function."""

    def test_valid_path_under_root(self, temp_dir):
        """Path under allowed root should be valid."""
        allowed_root = temp_dir
        path = temp_dir / "subdir" / "file.py"

        result = validate_path_safety(path, allowed_root)

        assert result is True

    def test_path_traversal_rejected(self, temp_dir):
        """Path with .. traversal outside root should be rejected."""
        allowed_root = temp_dir / "project"
        allowed_root.mkdir()
        path = allowed_root / ".." / "outside" / "file.py"

        result = validate_path_safety(path, allowed_root)

        assert result is False

    def test_absolute_path_outside_root(self, temp_dir):
        """Absolute path outside root should be rejected."""
        allowed_root = temp_dir / "project"
        allowed_root.mkdir()
        path = Path("/etc/passwd")

        result = validate_path_safety(path, allowed_root)

        assert result is False

    def test_path_within_root_absolute(self, temp_dir):
        """Absolute path within root should be accepted."""
        allowed_root = temp_dir / "project"
        allowed_root.mkdir()
        path = allowed_root / "src" / "file.py"

        result = validate_path_safety(path.resolve(), allowed_root)

        assert result is True

    def test_symlink_escape_rejected(self, temp_dir):
        """Symlink pointing outside root should be rejected."""
        allowed_root = temp_dir / "project"
        allowed_root.mkdir()

        # Create symlink pointing outside
        outside = temp_dir / "outside"
        outside.mkdir()
        symlink = allowed_root / "escape"
        os.symlink(outside, symlink)

        path = symlink / "file.py"

        result = validate_path_safety(path, allowed_root)

        assert result is False
