"""
TODO generation for deep-implement sessions.

Generates TodoWrite-compatible items for tracking implementation progress,
including context items for state persistence and per-section tasks.
"""

# Per-section steps in the implementation loop
SECTION_STEPS = [
    ("implement", "Implement {section}", "Implementing {display_name}"),
    ("review_subagent", "Run code review subagent for {section}", "Running code review for {display_name}"),
    ("review_interview", "Perform code review interview for {section}", "Performing code review interview for {display_name}"),
    ("commit", "Commit {section}", "Committing {display_name}"),
    ("update_docs", "Update {section} documentation", "Updating {display_name} documentation"),
]


def generate_implementation_todos(
    sections: list[str],
    completed: list[str],
    context: dict
) -> list[dict]:
    """
    Generate TODO items for TodoWrite.

    Context items are stored as completed TODOs at the start for persistence.
    Section implementation tasks follow as pending/completed based on progress.

    Args:
        sections: List of section names from manifest
        completed: List of already completed section names
        context: Dict of context values to persist (paths, settings)

    Returns:
        List of TODO dicts with content, status, and activeForm
    """
    todos = []

    # Add context items first (stored as completed for persistence)
    context_items = [
        ("sections_dir", "Context: sections_dir"),
        ("implementation_dir", "Context: implementation_dir"),
        ("git_available", "Context: git_available"),
        ("git_root", "Context: git_root"),
        ("commit_style", "Context: commit_style"),
        ("test_command", "Context: test_command"),
        ("pre_commit_present", "Context: pre_commit_present"),
        ("pre_commit_formatters", "Context: pre_commit_formatters"),
    ]

    for key, active_form in context_items:
        if key in context:
            value = context[key]
            # Format lists nicely
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value) if value else "none"
            todos.append({
                "content": f"{key}={value}",
                "status": "completed",
                "activeForm": active_form
            })

    # Add section implementation todos with expanded steps
    for section in sections:
        # Extract section number and name for display
        # section-01-foundation -> "01: foundation"
        parts = section.replace("section-", "").split("-", 1)
        if len(parts) == 2:
            num, name = parts
            display_name = f"section {num}: {name.replace('-', ' ')}"
        else:
            display_name = section

        # All steps for completed sections are completed
        section_complete = section in completed

        for step_id, content_template, active_template in SECTION_STEPS:
            todos.append({
                "content": content_template.format(section=section, display_name=display_name),
                "status": "completed" if section_complete else "pending",
                "activeForm": active_template.format(section=section, display_name=display_name)
            })

    # Add finalization todo
    all_complete = all(s in completed for s in sections) if sections else False
    todos.append({
        "content": "Generate usage.md and output summary",
        "status": "completed" if all_complete else "pending",
        "activeForm": "Generating usage documentation"
    })

    return todos
