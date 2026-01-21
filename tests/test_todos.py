import pytest

from scripts.lib.todos import generate_implementation_todos


class TestGenerateImplementationTodos:
    """Tests for generate_implementation_todos function."""

    def test_generate_todos_new_session(self):
        """Should generate todos for all sections in new session."""
        sections = ["section-01-foundation", "section-02-models"]
        completed = []
        context = {
            "sections_dir": "/path/to/sections",
            "git_available": True,
            "implementation_dir": "/path/to/implementation"
        }

        result = generate_implementation_todos(sections, completed, context)

        # Should have context items + section todos
        context_items = [t for t in result if t["status"] == "completed"]
        section_items = [t for t in result if t["status"] == "pending" and "section-" in t["content"]]

        assert any("sections_dir" in t["content"] for t in context_items)
        assert any("git_available" in t["content"] for t in context_items)
        assert len(section_items) == 2

    def test_generate_todos_partial_completion(self):
        """Should mark completed sections appropriately."""
        sections = ["section-01-foundation", "section-02-models"]
        completed = ["section-01-foundation"]
        context = {"sections_dir": "/path/to/sections"}

        result = generate_implementation_todos(sections, completed, context)

        section_todos = [t for t in result if "section-" in t["content"]]
        section_01 = next(t for t in section_todos if "section-01" in t["content"])
        section_02 = next(t for t in section_todos if "section-02" in t["content"])

        assert section_01["status"] == "completed"
        assert section_02["status"] == "pending"

    def test_todo_format(self):
        """Should generate todos with required fields."""
        sections = ["section-01-foundation"]
        completed = []
        context = {}

        result = generate_implementation_todos(sections, completed, context)

        for todo in result:
            assert "content" in todo
            assert "status" in todo
            assert "activeForm" in todo
            assert todo["status"] in ["pending", "in_progress", "completed"]

    def test_context_items_come_first(self):
        """Context items should be at the beginning of the list."""
        sections = ["section-01-foundation"]
        completed = []
        context = {
            "sections_dir": "/path/to/sections",
            "git_available": True
        }

        result = generate_implementation_todos(sections, completed, context)

        # First items should be context
        assert "sections_dir" in result[0]["content"]

    def test_active_form_present_tense(self):
        """activeForm should be in present tense."""
        sections = ["section-01-foundation"]
        completed = []
        context = {}

        result = generate_implementation_todos(sections, completed, context)

        for todo in result:
            if "section-" in todo["content"]:
                # Section todos should have "Implementing" form
                assert "Implementing" in todo["activeForm"]

    def test_all_sections_completed(self):
        """Should mark all sections complete when all are done."""
        sections = ["section-01-foundation", "section-02-models"]
        completed = ["section-01-foundation", "section-02-models"]
        context = {}

        result = generate_implementation_todos(sections, completed, context)

        section_todos = [t for t in result if "section-" in t["content"]]
        for todo in section_todos:
            assert todo["status"] == "completed"

    def test_pre_commit_context(self):
        """Should include pre-commit info in context if present."""
        sections = ["section-01-foundation"]
        completed = []
        context = {
            "pre_commit_present": True,
            "pre_commit_formatters": ["black", "isort"]
        }

        result = generate_implementation_todos(sections, completed, context)

        context_items = [t for t in result if t["status"] == "completed"]
        pre_commit_items = [t for t in context_items if "pre_commit" in t["content"]]
        assert len(pre_commit_items) > 0

    def test_finalization_todo_at_end(self):
        """Should include finalization todo after all sections."""
        sections = ["section-01-foundation", "section-02-models"]
        completed = []
        context = {}

        result = generate_implementation_todos(sections, completed, context)

        # Last todo should be finalization
        last_todo = result[-1]
        assert "final" in last_todo["content"].lower() or "usage" in last_todo["content"].lower()

    def test_empty_sections_list(self):
        """Should handle empty sections list."""
        sections = []
        completed = []
        context = {"sections_dir": "/path/to/sections"}

        result = generate_implementation_todos(sections, completed, context)

        # Should still have context items but no section todos
        assert any("sections_dir" in t["content"] for t in result)
        section_todos = [t for t in result if "Implement section" in t["content"]]
        assert len(section_todos) == 0
