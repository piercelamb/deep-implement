"""
Configuration management for deep-implement sessions.

Handles loading, saving, and updating session configuration including
per-section completion state with commit hashes for reliable resume.
"""

from pathlib import Path
import json
from datetime import datetime, timezone
from typing import Any

CONFIG_FILE = "deep_implement_config.json"


def load_session_config(implementation_dir: Path) -> dict | None:
    """
    Load existing session config from implementation directory.

    Args:
        implementation_dir: Path to implementation directory

    Returns:
        Config dict if found, None otherwise
    """
    config_path = Path(implementation_dir) / CONFIG_FILE
    if not config_path.exists():
        return None

    with open(config_path) as f:
        return json.load(f)


def save_session_config(implementation_dir: Path, config: dict) -> None:
    """
    Save session config to implementation directory.

    Creates the directory if it doesn't exist.

    Args:
        implementation_dir: Path to implementation directory
        config: Config dict to save
    """
    impl_dir = Path(implementation_dir)
    impl_dir.mkdir(parents=True, exist_ok=True)

    config_path = impl_dir / CONFIG_FILE
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def create_session_config(
    plugin_root: Path,
    sections_dir: Path,
    implementation_dir: Path,
    git_available: bool,
    git_root: Path | None,
    commit_style: str,
    test_command: str = "uv run pytest",
    sections: list[str] | None = None,
    pre_commit: dict | None = None,
) -> dict:
    """
    Create a new session config with all required fields.

    Args:
        plugin_root: Path to the deep-implement plugin
        sections_dir: Path to sections directory
        implementation_dir: Path to implementation directory
        git_available: Whether git is available
        git_root: Git repository root path (None if no git)
        commit_style: Detected commit style ("conventional", "simple", "unknown")
        test_command: Command to run tests
        sections: List of section names from manifest
        pre_commit: Pre-commit hook configuration dict

    Returns:
        New config dict
    """
    return {
        "plugin_root": str(plugin_root),
        "sections_dir": str(sections_dir),
        "implementation_dir": str(implementation_dir),
        "git_available": git_available,
        "git_root": str(git_root) if git_root else None,
        "commit_style": commit_style,
        "test_command": test_command,
        "sections": sections or [],
        "sections_state": {},
        "pre_commit": pre_commit or {
            "present": False,
            "type": "none",
            "may_modify_files": False,
            "detected_formatters": []
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def update_section_state(
    implementation_dir: Path,
    section_name: str,
    status: str,
    commit_hash: str | None = None,
    review_file: str | None = None,
    pre_commit: dict | None = None,
) -> None:
    """
    Update per-section completion state in session config.

    Args:
        implementation_dir: Path to implementation directory
        section_name: Name of section to update
        status: New status ("in_progress", "complete")
        commit_hash: Git commit hash if committed
        review_file: Review file name if review written
        pre_commit: Pre-commit handling info for this section
    """
    config = load_session_config(implementation_dir)
    if config is None:
        raise ValueError(f"No config found in {implementation_dir}")

    if "sections_state" not in config:
        config["sections_state"] = {}

    state: dict[str, Any] = {"status": status}

    if commit_hash is not None:
        state["commit_hash"] = commit_hash

    if review_file is not None:
        state["review_file"] = review_file

    if pre_commit is not None:
        state["pre_commit"] = pre_commit

    if status == "complete":
        state["completed_at"] = datetime.now(timezone.utc).isoformat()

    config["sections_state"][section_name] = state
    save_session_config(implementation_dir, config)
