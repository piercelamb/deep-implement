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


VALID_CONCERNS = ["scaffold", "functional", "observability", "configuration", "resilience", "integration"]
CONCERN_ORDER = {c: i for i, c in enumerate(VALID_CONCERNS)}


def parse_manifest_block(index_content: str) -> list[str]:
    """
    Extract section names from SECTION_MANIFEST block.

    Handles optional concern tags after section names (e.g., "section-01-foundation scaffold").
    Tags are ignored here — use parse_section_concerns() to extract them.

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
        # Support optional concern tag: "section-01-foundation scaffold"
        parts = line.split()
        sections.append(parts[0])

    return sections


def parse_section_concerns(index_content: str) -> dict[str, str]:
    """
    Extract concern tags from SECTION_MANIFEST lines.

    Each manifest line can optionally include a concern tag:
        section-01-foundation scaffold
        section-02-models functional

    Args:
        index_content: Content of index.md file

    Returns:
        Dict mapping section name to concern type for sections that have valid tags.
        Sections without tags or with invalid tags are omitted.
    """
    pattern = r'<!--\s*SECTION_MANIFEST\s*\n(.*?)\nEND_MANIFEST\s*-->'
    match = re.search(pattern, index_content, re.DOTALL)

    if not match:
        return {}

    manifest_content = match.group(1)
    concerns = {}

    for line in manifest_content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] in VALID_CONCERNS:
            concerns[parts[0]] = parts[1]

    return concerns


def sort_sections_by_concern(sections: list[str], concerns: dict[str, str]) -> list[str]:
    """
    Reorder sections by concern type, preserving number order within same concern.

    Concern execution order: scaffold → functional → observability →
    configuration → resilience → integration.

    Untagged sections go after all tagged sections, in their original order.

    Args:
        sections: List of section names in manifest order
        concerns: Dict mapping section name to concern type

    Returns:
        Reordered list of section names.
    """
    if not concerns:
        return sections

    tagged = [(s, CONCERN_ORDER[concerns[s]]) for s in sections if s in concerns]
    untagged = [s for s in sections if s not in concerns]

    # Sort tagged by concern order, then by original position (stable sort preserves manifest order)
    tagged.sort(key=lambda x: x[1])

    return [s for s, _ in tagged] + untagged


def parse_section_meta(section_content: str) -> dict[str, str]:
    """
    Extract SECTION_META block from section file content.

    Expected format within a section .md file:
        <!-- SECTION_META
        concern: scaffold
        target_files: internal/ports/repository.go, internal/domain/entity.go
        estimated_lines: 150
        END_SECTION_META -->

    Args:
        section_content: Content of a section markdown file

    Returns:
        Dict with keys: concern, target_files, estimated_lines (all optional).
        Returns empty dict when no SECTION_META block found.
    """
    pattern = r'<!--\s*SECTION_META\s*\n(.*?)\nEND_SECTION_META\s*-->'
    match = re.search(pattern, section_content, re.DOTALL)

    if not match:
        return {}

    meta_content = match.group(1)
    meta = {}

    for line in meta_content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' in line:
            key, value = line.split(':', 1)
            meta[key.strip()] = value.strip()

    return meta


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
