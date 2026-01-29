"""Tests for task storage module."""

import json
import pytest
from pathlib import Path

from scripts.lib.task_storage import (
    TaskToWrite,
    TaskWriteResult,
    TaskStatus,
    write_tasks,
    get_tasks_dir,
    build_dependency_graph,
)


class TestTaskToWrite:
    """Tests for TaskToWrite dataclass."""

    def test_to_file_dict_basic(self):
        """Should convert to dict with required fields."""
        task = TaskToWrite(
            position=1,
            subject="Test task",
            status=TaskStatus.PENDING,
            description="Test description",
            active_form="Testing",
        )

        result = task.to_file_dict()

        assert result["id"] == "1"
        assert result["subject"] == "Test task"
        assert result["status"] == "pending"
        assert result["description"] == "Test description"
        assert result["activeForm"] == "Testing"
        assert result["blocks"] == []
        assert result["blockedBy"] == []

    def test_to_file_dict_with_dependencies(self):
        """Should include blocks and blockedBy."""
        task = TaskToWrite(
            position=5,
            subject="Dependent task",
            status=TaskStatus.PENDING,
            description="",
            blocks=("6", "7"),
            blocked_by=("4",),
        )

        result = task.to_file_dict()

        assert result["blocks"] == ["6", "7"]
        assert result["blockedBy"] == ["4"]


class TestTaskWriteResult:
    """Tests for TaskWriteResult dataclass."""

    def test_ok_factory(self, tmp_path):
        """Should create success result."""
        result = TaskWriteResult.ok(
            task_list_id="test-id",
            tasks_written=5,
            tasks_dir=tmp_path,
        )

        assert result.success is True
        assert result.task_list_id == "test-id"
        assert result.tasks_written == 5
        assert result.tasks_dir == tmp_path
        assert result.error is None

    def test_err_factory(self):
        """Should create error result."""
        result = TaskWriteResult.err(
            task_list_id="test-id",
            error="Something went wrong",
        )

        assert result.success is False
        assert result.task_list_id == "test-id"
        assert result.tasks_written == 0
        assert result.error == "Something went wrong"


class TestWriteTasks:
    """Tests for write_tasks function."""

    def test_writes_tasks_to_disk(self, tmp_path, monkeypatch):
        """Should write task files to ~/.claude/tasks/<id>/."""
        # Mock Path.home() to use tmp_path
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        tasks = [
            TaskToWrite(
                position=1,
                subject="First task",
                status=TaskStatus.COMPLETED,
                description="Context",
                active_form="Context",
            ),
            TaskToWrite(
                position=2,
                subject="Second task",
                status=TaskStatus.PENDING,
                description="Do something",
                active_form="Doing something",
            ),
        ]

        result = write_tasks("test-session-123", tasks)

        assert result.success is True
        assert result.tasks_written == 2

        # Check files exist
        tasks_dir = tmp_path / ".claude" / "tasks" / "test-session-123"
        assert (tasks_dir / "1.json").exists()
        assert (tasks_dir / "2.json").exists()

        # Check file content
        task1 = json.loads((tasks_dir / "1.json").read_text())
        assert task1["subject"] == "First task"
        assert task1["status"] == "completed"

    def test_applies_dependency_graph(self, tmp_path, monkeypatch):
        """Should apply dependency graph when provided."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        tasks = [
            TaskToWrite(position=1, subject="Task 1", status=TaskStatus.PENDING),
            TaskToWrite(position=2, subject="Task 2", status=TaskStatus.PENDING),
        ]

        dependency_graph = {
            1: (["2"], []),  # Task 1 blocks Task 2
            2: ([], ["1"]),  # Task 2 blocked by Task 1
        }

        result = write_tasks("test-id", tasks, dependency_graph=dependency_graph)

        assert result.success is True

        tasks_dir = tmp_path / ".claude" / "tasks" / "test-id"
        task1 = json.loads((tasks_dir / "1.json").read_text())
        task2 = json.loads((tasks_dir / "2.json").read_text())

        assert task1["blocks"] == ["2"]
        assert task1["blockedBy"] == []
        assert task2["blocks"] == []
        assert task2["blockedBy"] == ["1"]

    def test_marks_extra_tasks_obsolete(self, tmp_path, monkeypatch):
        """Should mark existing tasks beyond max position as obsolete."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create existing tasks directory with more tasks
        tasks_dir = tmp_path / ".claude" / "tasks" / "test-id"
        tasks_dir.mkdir(parents=True)
        (tasks_dir / "1.json").write_text(json.dumps({"id": "1", "subject": "Old task 1", "status": "pending"}))
        (tasks_dir / "2.json").write_text(json.dumps({"id": "2", "subject": "Old task 2", "status": "pending"}))
        (tasks_dir / "3.json").write_text(json.dumps({"id": "3", "subject": "Old task 3", "status": "pending"}))

        # Write only 2 new tasks
        tasks = [
            TaskToWrite(position=1, subject="New task 1", status=TaskStatus.PENDING),
            TaskToWrite(position=2, subject="New task 2", status=TaskStatus.PENDING),
        ]

        result = write_tasks("test-id", tasks)

        assert result.success is True

        # Task 3 should be marked obsolete
        task3 = json.loads((tasks_dir / "3.json").read_text())
        assert task3["subject"] == "[obsolete]"
        assert task3["status"] == "completed"

    def test_returns_error_for_empty_task_list_id(self):
        """Should return error when task_list_id is empty."""
        result = write_tasks("", [])

        assert result.success is False
        assert "No task_list_id" in result.error

    def test_creates_directory_if_missing(self, tmp_path, monkeypatch):
        """Should create tasks directory if it doesn't exist."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        tasks = [TaskToWrite(position=1, subject="Task", status=TaskStatus.PENDING)]

        result = write_tasks("new-session", tasks)

        assert result.success is True
        assert (tmp_path / ".claude" / "tasks" / "new-session").is_dir()


class TestBuildDependencyGraph:
    """Tests for build_dependency_graph function."""

    def test_builds_sequential_dependencies(self):
        """Should build blocks/blockedBy from semantic dependencies."""
        tasks = [
            TaskToWrite(position=1, subject="Task 1", status=TaskStatus.PENDING),
            TaskToWrite(position=2, subject="Task 2", status=TaskStatus.PENDING),
            TaskToWrite(position=3, subject="Task 3", status=TaskStatus.PENDING),
        ]

        semantic_deps = {
            "task-2": ["task-1"],  # Task 2 blocked by Task 1
            "task-3": ["task-2"],  # Task 3 blocked by Task 2
        }

        semantic_to_position = {
            "task-1": 1,
            "task-2": 2,
            "task-3": 3,
        }

        result = build_dependency_graph(tasks, semantic_deps, semantic_to_position)

        # Task 1: blocks [2], blockedBy []
        assert result[1] == (["2"], [])
        # Task 2: blocks [3], blockedBy [1]
        assert result[2] == (["3"], ["1"])
        # Task 3: blocks [], blockedBy [2]
        assert result[3] == ([], ["2"])

    def test_handles_missing_semantic_ids(self):
        """Should ignore dependencies with missing semantic IDs."""
        tasks = [
            TaskToWrite(position=1, subject="Task 1", status=TaskStatus.PENDING),
        ]

        semantic_deps = {
            "nonexistent": ["also-nonexistent"],
        }

        semantic_to_position = {
            "task-1": 1,
        }

        result = build_dependency_graph(tasks, semantic_deps, semantic_to_position)

        assert result[1] == ([], [])


class TestGetTasksDir:
    """Tests for get_tasks_dir function."""

    def test_returns_correct_path(self, monkeypatch):
        """Should return ~/.claude/tasks/<task_list_id>/."""
        monkeypatch.setattr(Path, "home", lambda: Path("/Users/test"))

        result = get_tasks_dir("my-session-id")

        assert result == Path("/Users/test/.claude/tasks/my-session-id")
