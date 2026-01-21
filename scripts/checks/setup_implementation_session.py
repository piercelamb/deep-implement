#!/usr/bin/env python3
"""
Setup script for deep-implement sessions.

Validates sections directory, detects git configuration, checks pre-commit hooks,
infers resume state, and generates TODOs for the skill.

Usage:
    uv run scripts/checks/setup-implementation-session.py \
        --sections-dir <path> \
        --plugin-root <path>
"""

import argparse
import json
import subprocess
import sys
import re
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.lib.config import load_session_config, save_session_config, create_session_config
from scripts.lib.sections import parse_manifest_block, validate_section_file, get_completed_sections
from scripts.lib.todos import generate_implementation_todos


# Known formatters that modify files
KNOWN_FORMATTERS = {
    # Python
    "black", "isort", "autopep8", "yapf", "blue",
    # Python with specific IDs
    "ruff-format",
    # JavaScript/TypeScript
    "prettier", "eslint-fix",
    # Rust
    "fmt", "rustfmt",
    # Go
    "gofmt", "goimports",
    # General
    "end-of-file-fixer", "trailing-whitespace",
}

# Partial matches for formatters (repo URLs or IDs containing these)
FORMATTER_PATTERNS = [
    "black", "isort", "autopep8", "yapf", "prettier",
    "rustfmt", "gofmt", "goimports", "ruff",
]


def validate_sections_dir(sections_dir: Path) -> dict:
    """
    Validate sections directory structure.

    Checks:
    1. Path exists and is a directory
    2. index.md exists
    3. index.md has valid SECTION_MANIFEST block
    4. All manifest sections have corresponding files
    5. All section files have content

    Args:
        sections_dir: Path to sections directory

    Returns:
        {"valid": bool, "error": str | None, "sections": list[str]}
    """
    sections_dir = Path(sections_dir)

    if not sections_dir.exists():
        return {"valid": False, "error": f"Sections directory does not exist: {sections_dir}", "sections": []}

    if not sections_dir.is_dir():
        return {"valid": False, "error": f"Path is not a directory: {sections_dir}", "sections": []}

    index_path = sections_dir / "index.md"
    if not index_path.exists():
        return {"valid": False, "error": f"index.md not found in {sections_dir}", "sections": []}

    # Parse manifest
    index_content = index_path.read_text()
    sections = parse_manifest_block(index_content)

    if not sections:
        return {"valid": False, "error": "No valid SECTION_MANIFEST block found in index.md", "sections": []}

    # Validate each section file
    for section in sections:
        section_path = sections_dir / f"{section}.md"
        result = validate_section_file(section_path)
        if not result["valid"]:
            return {"valid": False, "error": result["error"], "sections": sections}

    return {"valid": True, "error": None, "sections": sections}


def check_git_repo(target_dir: Path) -> dict:
    """
    Check if target is in a git repository.

    Args:
        target_dir: Directory to check

    Returns:
        {"available": bool, "root": str | None}
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=target_dir,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return {"available": True, "root": result.stdout.strip()}
    except Exception:
        pass

    return {"available": False, "root": None}


# Protected branch patterns
PROTECTED_BRANCHES = {"main", "master"}
PROTECTED_BRANCH_PREFIXES = ("release/", "release-", "hotfix/", "hotfix-")


def check_current_branch(git_root: Path) -> dict:
    """
    Check current git branch and if it's a protected branch.

    Args:
        git_root: Git repository root

    Returns:
        {"branch": str | None, "is_protected": bool}
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=git_root,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            is_protected = (
                branch in PROTECTED_BRANCHES or
                branch.startswith(PROTECTED_BRANCH_PREFIXES)
            )
            return {"branch": branch, "is_protected": is_protected}
    except Exception:
        pass

    return {"branch": None, "is_protected": False}


def check_working_tree_status(git_root: Path) -> dict:
    """
    Check if working tree is clean.

    Args:
        git_root: Git repository root

    Returns:
        {"clean": bool, "dirty_files": list[str]}
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=git_root,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.strip().split('\n') if l]
            dirty_files = []
            for line in lines:
                # Format: XY filename (XY are 2 status chars, then space, then filename)
                # Use split to handle various formats robustly
                parts = line.split(maxsplit=1)
                if len(parts) >= 2:
                    dirty_files.append(parts[1].strip())
                elif len(parts) == 1 and len(line) > 2:
                    # Fallback: just strip the status chars
                    dirty_files.append(line[3:].strip())
            return {"clean": len(dirty_files) == 0, "dirty_files": dirty_files}
    except Exception:
        pass

    return {"clean": True, "dirty_files": []}


def detect_commit_style(git_root: Path) -> str:
    """
    Detect commit message style from git history.

    Args:
        git_root: Git repository root

    Returns:
        "conventional" | "simple" | "unknown"
    """
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-20", "--format=%s"],
            cwd=git_root,
            capture_output=True,
            text=True
        )
        if result.returncode != 0 or not result.stdout.strip():
            return "unknown"

        messages = result.stdout.strip().split('\n')

        # Check for conventional commit patterns
        conventional_pattern = re.compile(r'^(feat|fix|docs|style|refactor|test|chore|build|ci|perf|revert)(\(.+\))?!?:')
        conventional_count = sum(1 for msg in messages if conventional_pattern.match(msg))

        if conventional_count >= len(messages) * 0.5:  # 50% threshold
            return "conventional"
        elif messages:
            return "simple"
        else:
            return "unknown"

    except Exception:
        return "unknown"


def validate_path_safety(path: Path, allowed_root: Path) -> bool:
    """
    Ensure path is under allowed_root after normalization.

    Rejects absolute paths outside root and '..' traversal.

    Args:
        path: Path to validate
        allowed_root: Root directory that paths must be under

    Returns:
        True if path is safe, False otherwise
    """
    try:
        # Resolve both paths to handle symlinks and ..
        resolved_path = Path(path).resolve()
        resolved_root = Path(allowed_root).resolve()

        # Check if path is under root
        return str(resolved_path).startswith(str(resolved_root))
    except Exception:
        return False


def check_pre_commit_hooks(git_root: Path) -> dict:
    """
    Detect pre-commit hook configuration.

    Checks:
    1. .pre-commit-config.yaml (pre-commit framework)
    2. .git/hooks/pre-commit (native hook)
    3. Parses YAML for known formatters

    Args:
        git_root: Git repository root

    Returns:
        {
            "present": bool,
            "type": "pre-commit-framework" | "native-hook" | "both" | "none",
            "config_file": str | None,
            "native_hook": str | None,
            "may_modify_files": bool,
            "detected_formatters": list[str]
        }
    """
    git_root = Path(git_root)

    pre_commit_config = git_root / ".pre-commit-config.yaml"
    native_hook = git_root / ".git" / "hooks" / "pre-commit"

    has_framework = pre_commit_config.exists()
    has_native = native_hook.exists() and bool(native_hook.stat().st_mode & 0o111)  # executable

    detected_formatters = []
    may_modify_files = False

    # Parse pre-commit config for formatters
    if has_framework:
        try:
            content = pre_commit_config.read_text()
            # Simple YAML parsing for hook IDs
            # Look for "- id: <hook_id>" patterns
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('- id:'):
                    hook_id = line.replace('- id:', '').strip()
                    # Check if this is a known formatter
                    if hook_id in KNOWN_FORMATTERS:
                        detected_formatters.append(hook_id)
                        may_modify_files = True
                    else:
                        # Check partial matches
                        for pattern in FORMATTER_PATTERNS:
                            if pattern in hook_id.lower():
                                detected_formatters.append(hook_id)
                                may_modify_files = True
                                break

                # Also check repo URLs for formatter patterns
                if line.startswith('- repo:'):
                    repo_url = line.replace('- repo:', '').strip()
                    for pattern in FORMATTER_PATTERNS:
                        if pattern in repo_url.lower():
                            # This repo likely has formatters
                            pass  # Will be caught by hook ID check
        except Exception:
            pass

    # Determine type
    if has_framework and has_native:
        hook_type = "both"
    elif has_framework:
        hook_type = "pre-commit-framework"
    elif has_native:
        hook_type = "native-hook"
        may_modify_files = True  # Unknown, assume it might
    else:
        hook_type = "none"

    return {
        "present": has_framework or has_native,
        "type": hook_type,
        "config_file": str(pre_commit_config) if has_framework else None,
        "native_hook": str(native_hook) if has_native else None,
        "may_modify_files": may_modify_files,
        "detected_formatters": detected_formatters
    }


def infer_session_state(
    sections_dir: Path,
    implementation_dir: Path,
    git_root: Path | None
) -> dict:
    """
    Determine if this is a new or resume session.

    Args:
        sections_dir: Path to sections directory
        implementation_dir: Path to implementation directory
        git_root: Git root (None if no git)

    Returns:
        {
            "mode": "new" | "resume" | "complete",
            "completed_sections": list[str],
            "resume_from": str | None
        }
    """
    implementation_dir = Path(implementation_dir)

    # Check for existing config
    config = load_session_config(implementation_dir)
    if config is None:
        return {
            "mode": "new",
            "completed_sections": [],
            "resume_from": None
        }

    # Get completed sections
    completed = get_completed_sections(implementation_dir, git_root)
    all_sections = config.get("sections", [])

    if len(completed) >= len(all_sections) and all_sections:
        return {
            "mode": "complete",
            "completed_sections": completed,
            "resume_from": None
        }

    # Find first incomplete section
    resume_from = None
    for section in all_sections:
        if section not in completed:
            resume_from = section
            break

    return {
        "mode": "resume" if completed else "new",
        "completed_sections": completed,
        "resume_from": resume_from
    }


def main():
    parser = argparse.ArgumentParser(description="Setup deep-implement session")
    parser.add_argument("--sections-dir", required=True, help="Path to sections directory")
    parser.add_argument("--plugin-root", required=True, help="Path to plugin root")
    args = parser.parse_args()

    sections_dir = Path(args.sections_dir).resolve()
    plugin_root = Path(args.plugin_root).resolve()

    # Validate sections directory
    validation = validate_sections_dir(sections_dir)
    if not validation["valid"]:
        print(json.dumps({
            "success": False,
            "error": validation["error"]
        }))
        return

    sections = validation["sections"]

    # Determine implementation directory (sibling to sections)
    implementation_dir = sections_dir.parent / "implementation"

    # Check git
    git_info = check_git_repo(sections_dir)
    git_root = Path(git_info["root"]) if git_info["available"] else None

    # Check current branch
    branch_info = {"branch": None, "is_protected": False}
    if git_root:
        branch_info = check_current_branch(git_root)

    # Check working tree
    working_tree = {"clean": True, "dirty_files": []}
    if git_root:
        working_tree = check_working_tree_status(git_root)

    # Detect commit style
    commit_style = "unknown"
    if git_root:
        commit_style = detect_commit_style(git_root)

    # Check pre-commit hooks
    pre_commit = {"present": False, "type": "none", "may_modify_files": False, "detected_formatters": []}
    if git_root:
        pre_commit = check_pre_commit_hooks(git_root)

    # Infer session state
    state = infer_session_state(sections_dir, implementation_dir, git_root)

    # Create or update session config
    if state["mode"] == "new":
        config = create_session_config(
            plugin_root=plugin_root,
            sections_dir=sections_dir,
            implementation_dir=implementation_dir,
            git_available=git_info["available"],
            git_root=git_root,
            commit_style=commit_style,
            sections=sections,
            pre_commit=pre_commit
        )
        save_session_config(implementation_dir, config)

    # Generate TODOs
    context = {
        "sections_dir": str(sections_dir),
        "implementation_dir": str(implementation_dir),
        "git_available": git_info["available"],
        "git_root": str(git_root) if git_root else None,
        "commit_style": commit_style,
        "test_command": "uv run pytest",
        "pre_commit_present": pre_commit["present"],
        "pre_commit_formatters": pre_commit["detected_formatters"]
    }
    todos = generate_implementation_todos(sections, state["completed_sections"], context)

    # Output result
    result = {
        "success": True,
        "mode": state["mode"],
        "sections_dir": str(sections_dir),
        "implementation_dir": str(implementation_dir),
        "git_available": git_info["available"],
        "git_root": str(git_root) if git_root else None,
        "current_branch": branch_info["branch"],
        "is_protected_branch": branch_info["is_protected"],
        "working_tree_clean": working_tree["clean"],
        "dirty_files": working_tree["dirty_files"],
        "commit_style": commit_style,
        "pre_commit": pre_commit,
        "sections": sections,
        "completed_sections": state["completed_sections"],
        "resume_from": state["resume_from"],
        "todos": todos
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
