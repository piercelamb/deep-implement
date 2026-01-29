"""Task reconciliation for deep-implement workflow.

This module handles getting the task list context from environment variables.
The session ID is captured by the SessionStart hook and written to CLAUDE_ENV_FILE.

Key concepts:
- CLAUDE_CODE_TASK_LIST_ID: User-specified task list for sharing across sessions
- CLAUDE_SESSION_ID: Auto-captured session ID from SessionStart hook
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Self


class TaskListSource(StrEnum):
    """Source of the task list ID."""

    CONTEXT = "context"  # From hook additionalContext -> CLI arg
    USER_ENV = "user_env"  # From CLAUDE_CODE_TASK_LIST_ID
    SESSION = "session"  # From CLAUDE_SESSION_ID
    NONE = "none"  # No task list ID available


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskListContext:
    """Context about the task list being used."""

    task_list_id: str | None
    source: TaskListSource
    is_user_specified: bool  # True if CLAUDE_CODE_TASK_LIST_ID was set

    @classmethod
    def from_env(cls) -> Self:
        """Get task list context from environment variables.

        Priority: CLAUDE_CODE_TASK_LIST_ID > CLAUDE_SESSION_ID

        Returns:
            TaskListContext with task_list_id, source, and is_user_specified
        """
        user_specified = os.environ.get("CLAUDE_CODE_TASK_LIST_ID")
        if user_specified:
            return cls(
                task_list_id=user_specified,
                source=TaskListSource.USER_ENV,
                is_user_specified=True,
            )

        session_id = os.environ.get("CLAUDE_SESSION_ID")
        if session_id:
            return cls(
                task_list_id=session_id,
                source=TaskListSource.SESSION,
                is_user_specified=False,
            )

        return cls(
            task_list_id=None,
            source=TaskListSource.NONE,
            is_user_specified=False,
        )
