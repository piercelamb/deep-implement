"""Implementation task definitions for deep-implement.

This module defines the task templates and configuration for the
implementation workflow. Tasks are generated based on these definitions
and written directly to the task storage.
"""

from dataclasses import dataclass
from enum import StrEnum


class TaskStatus(StrEnum):
    """Status values for tasks."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskDefinition:
    """Template for a task type."""

    subject: str
    description: str
    active_form: str


# Semantic IDs for section steps (in execution order)
# Order: implement -> review -> interview -> docs -> commit -> record
# Doc update happens BEFORE commit so everything goes in one commit
# Record completion happens AFTER commit to save hash for resume
SECTION_STEP_IDS = [
    "implement",
    "review_subagent",
    "review_interview",
    "update_docs",
    "commit",
    "record_completion",
]

# Template definitions for each step type
# {section} is replaced with section name (e.g., "section-01-foundation")
# {display_name} is replaced with human-readable name (e.g., "section 01: foundation")
SECTION_STEP_DEFINITIONS: dict[str, TaskDefinition] = {
    "implement": TaskDefinition(
        subject="Implement {section}",
        description="Implement the code changes described in {section}",
        active_form="Implementing {display_name}",
    ),
    "review_subagent": TaskDefinition(
        subject="Run code review subagent for {section}",
        description="Run the code review subagent on implemented changes",
        active_form="Running code review for {display_name}",
    ),
    "review_interview": TaskDefinition(
        subject="Perform code review interview for {section}",
        description="Triage review findings and discuss with user",
        active_form="Performing code review interview for {display_name}",
    ),
    "update_docs": TaskDefinition(
        subject="Update {section} documentation",
        description="Update relevant documentation for the section",
        active_form="Updating {display_name} documentation",
    ),
    "commit": TaskDefinition(
        subject="Commit {section}",
        description="Create git commit for the completed section",
        active_form="Committing {display_name}",
    ),
    "record_completion": TaskDefinition(
        subject="Record {section} completion",
        description="Run update_section_state.py to save commit hash to config for resume support",
        active_form="Recording {display_name} completion",
    ),
}

# Compaction prompt task - added only every 2nd section
COMPACTION_TASK = TaskDefinition(
    subject="Prompt user for compaction after {section}",
    description="Prompt user to compact the conversation",
    active_form="Prompting for compaction after {display_name}",
)

# Finalization task - at the end of all sections
FINALIZATION_TASK = TaskDefinition(
    subject="Read finalization.md, generate usage.md, and print completion summary",
    description="Complete the implementation workflow by reading finalization.md and generating usage documentation",
    active_form="Reading finalization.md and generating usage documentation",
)

# Maps resume_step from detect_section_review_state to which steps are complete
# Key: resume_step value
# Value: set of step_ids that are complete when resuming at this step
#
# Note: If commit hash exists in config, section is in completed_sections
# and all 6 tasks are complete. The "commit" state handles edge case where
# commit was made but record_completion wasn't run (crash between commit and record).
RESUME_STEP_COMPLETE_MAPPING: dict[str, set[str]] = {
    "implement": set(),  # Nothing complete yet
    "review": {"implement"},  # Implementation done, starting review
    "interview": {"implement", "review_subagent"},  # Review done, starting interview
    "apply_fixes": {"implement", "review_subagent"},  # Interview recorded, restart applying fixes
    "commit": {"implement", "review_subagent", "review_interview", "update_docs"},  # Commit done, need to record
}

# Context items stored at the start of the task list (as completed tasks)
# Order matters - plugin_root must be first for context recovery after compaction
CONTEXT_ITEM_KEYS = [
    "plugin_root",
    "sections_dir",
    "target_dir",
    "state_dir",
    "runtime",
    "test_command",
]


def format_display_name(section: str) -> str:
    """Convert section name to human-readable display name.

    Args:
        section: Section name like "section-01-foundation"

    Returns:
        Display name like "section 01: foundation"
    """
    # section-01-foundation -> "01: foundation"
    parts = section.replace("section-", "").split("-", 1)
    if len(parts) == 2:
        num, name = parts
        return f"section {num}: {name.replace('-', ' ')}"
    return section
