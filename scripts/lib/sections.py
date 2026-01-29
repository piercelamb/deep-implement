"""
Section file handling for deep-implement.

Handles parsing SECTION_MANIFEST blocks, validating section files,
tracking completed sections via commit hashes, and extracting file paths.
"""

import re
import subprocess
from pathlib import Path

from scripts.lib.config import load_session_config


def parse_project_config_block(index_content: str) -> dict[str, str]:
    """
    Extract project configuration from PROJECT_CONFIG block.

    Args:
        index_content: Content of index.md file

    Returns:
        Dict with keys: target_dir, runtime, test_command
        Returns empty dict if no valid config found.
    """
    pattern = r'<!--\s*PROJECT_CONFIG\s*\n(.*?)\nEND_PROJECT_CONFIG\s*-->'
    match = re.search(pattern, index_content, re.DOTALL)

    if not match:
        return {}

    config_content = match.group(1)
    config = {}

    for line in config_content.split('\n'):
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith('#'):
            continue
        # Parse key: value pairs
        if ':' in line:
            key, value = line.split(':', 1)
            config[key.strip()] = value.strip()

    return config


def parse_manifest_block(index_content: str) -> list[str]:
    """
    Extract section names from SECTION_MANIFEST block.

    Args:
        index_content: Content of index.md file

    Returns:
        List of section names, e.g., ["section-01-foundation", "section-02-models"]
        Returns empty list if no valid manifest found.
    """
    # Match the manifest block
    pattern = r'<!--\s*SECTION_MANIFEST\s*\n(.*?)\nEND_MANIFEST\s*-->'
    match = re.search(pattern, index_content, re.DOTALL)

    if not match:
        return []

    manifest_content = match.group(1)
    sections = []

    for line in manifest_content.split('\n'):
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith('#'):
            continue
        sections.append(line)

    return sections


def validate_section_file(section_path: Path) -> dict:
    """
    Check section file exists and has content.

    Args:
        section_path: Path to section markdown file

    Returns:
        {"valid": bool, "error": str | None}
    """
    section_path = Path(section_path)

    if not section_path.exists():
        return {"valid": False, "error": f"Section file not found: {section_path}"}

    content = section_path.read_text()

    if not content.strip():
        return {"valid": False, "error": f"Section file is empty: {section_path}"}

    return {"valid": True, "error": None}


def _is_commit_reachable(commit_hash: str, git_root: Path) -> bool:
    """Check if a commit hash is reachable in the git repo."""
    try:
        result = subprocess.run(
            ["git", "cat-file", "-t", commit_hash],
            cwd=git_root,
            capture_output=True,
            text=True
        )
        return result.returncode == 0 and result.stdout.strip() == "commit"
    except Exception:
        return False


def get_completed_sections(
    implementation_dir: Path,
    git_root: Path
) -> list[str]:
    """
    List sections with valid commit hashes (reachable in git log).

    Args:
        implementation_dir: Path to implementation directory
        git_root: Git repository root

    Returns:
        List of completed section names
    """
    config = load_session_config(implementation_dir)
    if config is None:
        return []

    sections_state = config.get("sections_state", {})
    completed = []

    for section_name, state in sections_state.items():
        if state.get("status") != "complete":
            continue

        commit_hash = state.get("commit_hash")

        if commit_hash and _is_commit_reachable(commit_hash, git_root):
            completed.append(section_name)

    return completed


def extract_file_paths_from_section(section_content: str) -> list[str]:
    """
    Parse section content for file paths to create/modify.

    Looks for:
    - Tables with file paths: | src/models.py | ...
    - File headers: ### File: `path/to/file.py`
    - Bold file headers: **File: `path/to/file.py`**

    Args:
        section_content: Content of section markdown file

    Returns:
        List of unique file paths found
    """
    paths = set()

    # Pattern 1: Table rows with file paths (| path/to/file.py | ...)
    # Look for markdown table cells containing paths with extensions
    table_pattern = r'\|\s*([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)\s*\|'
    for match in re.finditer(table_pattern, section_content):
        path = match.group(1)
        # Filter out obvious non-paths
        if '/' in path or path.endswith(('.py', '.md', '.json', '.toml', '.yaml', '.yml', '.js', '.ts')):
            paths.add(path)

    # Pattern 2: File headers with backticks
    # ### File: `path/to/file.py` or **File: `path/to/file.py`**
    header_pattern = r'(?:###\s*)?(?:\*\*)?File:\s*`([^`]+)`'
    for match in re.finditer(header_pattern, section_content):
        paths.add(match.group(1))

    # Pattern 3: Standalone file paths in backticks that look like paths
    # `scripts/lib/config.py`
    backtick_pattern = r'`([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)`'
    for match in re.finditer(backtick_pattern, section_content):
        path = match.group(1)
        if '/' in path:  # Must have directory separator to be a path
            paths.add(path)

    return list(paths)
