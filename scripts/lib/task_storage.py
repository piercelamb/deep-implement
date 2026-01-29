"""Direct task file storage for Claude Code Tasks.

Writes task files directly to ~/.claude/tasks/<task_list_id>/
instead of returning operations for Claude to execute.

COUPLING WARNING: This module depends on Claude Code's internal
task storage format. If Anthropic changes the format, this code
will need to be updated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self


class TaskStatus(StrEnum):
    """Status values for tasks."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskWriteError(Exception):
    """Raised when task files cannot be written."""

    pass


def get_tasks_dir(task_list_id: str) -> Path:
    """Get the tasks directory for a task list ID."""
    return Path.home() / ".claude" / "tasks" / task_list_id


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskToWrite:
    """A task to write to disk."""

    position: int
    subject: str
    status: TaskStatus
    description: str = ""
    active_form: str = ""
    blocks: tuple[str, ...] = ()  # Task IDs this task blocks
    blocked_by: tuple[str, ...] = ()  # Task IDs blocking this task

    def to_file_dict(self) -> dict:
        """Convert to dict matching Claude Code task file format."""
        return {
            "id": str(self.position),
            "subject": self.subject,
            "description": self.description,
            "activeForm": self.active_form,
            "status": str(self.status),
            "blocks": list(self.blocks),
            "blockedBy": list(self.blocked_by),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskWriteResult:
    """Result of writing tasks to disk."""

    success: bool
    task_list_id: str
    tasks_written: int
    tasks_dir: Path
    error: str | None = None

    @classmethod
    def ok(cls, task_list_id: str, tasks_written: int, tasks_dir: Path) -> Self:
        return cls(
            success=True,
            task_list_id=task_list_id,
            tasks_written=tasks_written,
            tasks_dir=tasks_dir,
        )

    @classmethod
    def err(cls, task_list_id: str, error: str) -> Self:
        return cls(
            success=False,
            task_list_id=task_list_id,
            tasks_written=0,
            tasks_dir=Path(),
            error=error,
        )


def write_tasks(
    task_list_id: str,
    tasks: list[TaskToWrite],
    dependency_graph: dict[int, tuple[list[str], list[str]]] | None = None,
    *,
    mark_extra_obsolete: bool = True,
) -> TaskWriteResult:
    """Write tasks directly to Claude Code task storage.

    Args:
        task_list_id: Session ID or user-specified task list ID
        tasks: List of tasks to write (in position order)
        dependency_graph: Optional dict of position -> (blocks, blockedBy).
            If provided, overrides blocks/blocked_by on TaskToWrite.
        mark_extra_obsolete: If True, marks existing tasks beyond
            the last written position as [obsolete] + completed

    Returns:
        TaskWriteResult with success status and details

    Note: This overwrites existing task files at the same positions.
    """
    if not task_list_id:
        return TaskWriteResult.err("", "No task_list_id provided")

    tasks_dir = get_tasks_dir(task_list_id)

    try:
        # Create directory if needed
        tasks_dir.mkdir(parents=True, exist_ok=True)

        # Track highest position we write to
        max_written_position = 0

        # Write each task
        for task in tasks:
            task_data = task.to_file_dict()

            # Apply dependency graph if provided
            if dependency_graph and task.position in dependency_graph:
                blocks, blocked_by = dependency_graph[task.position]
                task_data["blocks"] = blocks
                task_data["blockedBy"] = blocked_by

            task_file = tasks_dir / f"{task.position}.json"
            task_file.write_text(json.dumps(task_data, indent=2))
            max_written_position = max(max_written_position, task.position)

        # Mark extra existing tasks as obsolete
        if mark_extra_obsolete:
            _mark_extra_obsolete(tasks_dir, max_written_position)

        return TaskWriteResult.ok(
            task_list_id=task_list_id,
            tasks_written=len(tasks),
            tasks_dir=tasks_dir,
        )

    except PermissionError as e:
        return TaskWriteResult.err(task_list_id, f"Permission denied: {e}")
    except OSError as e:
        return TaskWriteResult.err(task_list_id, f"File system error: {e}")


def _mark_extra_obsolete(tasks_dir: Path, max_written_position: int) -> None:
    """Mark existing task files beyond max_written_position as obsolete.

    Preserves existing blocks/blockedBy fields when marking obsolete.
    """
    for task_file in tasks_dir.glob("*.json"):
        try:
            position = int(task_file.stem)
            if position > max_written_position:
                # Read existing, check if already obsolete
                data = json.loads(task_file.read_text())
                if (
                    data.get("subject") == "[obsolete]"
                    and data.get("status") == "completed"
                ):
                    continue  # Already obsolete
                # Mark as obsolete (preserve other fields like blocks/blockedBy)
                data["subject"] = "[obsolete]"
                data["status"] = "completed"
                # Ensure required fields exist
                data.setdefault("blocks", [])
                data.setdefault("blockedBy", [])
                task_file.write_text(json.dumps(data, indent=2))
        except (ValueError, json.JSONDecodeError):
            continue  # Skip non-numeric or invalid files


def build_dependency_graph(
    tasks: list[TaskToWrite],
    semantic_dependencies: dict[str, list[str]],
    semantic_to_position: dict[str, int],
) -> dict[int, tuple[list[str], list[str]]]:
    """Build blocks and blockedBy arrays for each task position.

    Args:
        tasks: List of tasks with positions
        semantic_dependencies: Dict of semantic_id -> list of semantic_ids it's blocked by
        semantic_to_position: Dict of semantic_id -> position number

    Returns:
        Dict of position -> (blocks, blockedBy) where each is a list of position strings
    """
    # Initialize empty lists for each position
    blocks: dict[int, list[str]] = {t.position: [] for t in tasks}
    blocked_by: dict[int, list[str]] = {t.position: [] for t in tasks}

    # Build blockedBy from semantic dependencies
    for semantic_id, deps in semantic_dependencies.items():
        if semantic_id not in semantic_to_position:
            continue
        position = semantic_to_position[semantic_id]
        if position not in blocked_by:
            continue
        for dep_id in deps:
            if dep_id in semantic_to_position:
                dep_position = semantic_to_position[dep_id]
                blocked_by[position].append(str(dep_position))

    # Build blocks (inverse of blockedBy)
    for position, deps in blocked_by.items():
        for dep_pos_str in deps:
            dep_pos = int(dep_pos_str)
            if dep_pos in blocks:
                blocks[dep_pos].append(str(position))

    return {pos: (blocks[pos], blocked_by[pos]) for pos in blocks}
