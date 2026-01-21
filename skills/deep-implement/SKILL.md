# Deep Implementation Skill

Implements code from /deep-plan section files with integrated review and git workflow.

## CRITICAL: First Actions

**BEFORE using any other tools**, do these in order:

### 1. Print Intro Banner

```
═══════════════════════════════════════════════════════════════
DEEP-IMPLEMENT: Section-by-Section Implementation
═══════════════════════════════════════════════════════════════
Implements /deep-plan sections with:
  - TDD methodology
  - Code review at each step
  - Git commits with review trails

Usage: /deep-implement @path/to/sections/.
═══════════════════════════════════════════════════════════════
```

### 2. Validate Input

Check if user provided @directory argument ending with a path to a `sections/.` directory.

If NO argument or invalid:
```
═══════════════════════════════════════════════════════════════
DEEP-IMPLEMENT: Sections Directory Required
═══════════════════════════════════════════════════════════════

This skill requires a path to a sections directory from /deep-plan.

Example: /deep-implement @path/to/planning/sections/.

The sections directory must contain:
  - index.md with SECTION_MANIFEST block
  - section-NN-<name>.md files for each section
═══════════════════════════════════════════════════════════════
```
**Stop and wait for user to re-invoke with correct path.**

### 3. Run Setup Script

Find and run the setup script:
```bash
uv run {plugin_root}/scripts/checks/setup_implementation_session.py \
  --sections-dir "{sections_dir}" \
  --plugin-root "{plugin_root}"
```

Parse the JSON output.

**If `success == false`:** Display error and stop.

### 4. Handle Git Status

If `git_available == false`:
```
AskUserQuestion:
  question: "No git repository detected. Git operations will be skipped. Continue?"
  options:
    - label: "Continue without git"
      description: "Code review will use file contents instead of diffs"
    - label: "Exit to initialize git"
      description: "Stop to run git init first"
```

If user chooses "Exit", stop the workflow.

### 5. Handle Branch Check

If `is_protected_branch == true` (setup script detects main, master, release/* branches):
```
AskUserQuestion:
  question: "You're on the {current_branch} branch. Committing here may not be ideal."
  options:
    - label: "Continue on {current_branch}"
      description: "Proceed with implementation on this branch"
    - label: "Exit to create feature branch"
      description: "Stop to create a dedicated branch first"
```

If user chooses "Exit", stop the workflow.

### 6. Handle Working Tree Status

If `working_tree_clean == false`:
```
AskUserQuestion:
  question: "Working tree has {N} uncommitted changes. This may cause issues."
  options:
    - label: "Continue anyway"
      description: "Proceed with implementation (changes may get mixed)"
    - label: "Exit to commit/stash first"
      description: "Stop to handle uncommitted changes"
```

### 7. Print Preflight Report

```
═══════════════════════════════════════════════════════════════
PREFLIGHT REPORT
═══════════════════════════════════════════════════════════════
Repo root:      {git_root or "No git"}
Branch:         {current_branch or "N/A"}
Working tree:   {Clean | Dirty (N files)}
Pre-commit:     {Detected (type) | None}
                {May modify files: Yes (formatters) | No | Unknown}
Test command:   {test_command}
Sections:       {N} detected
Completed:      {M} already done
State storage:  {implementation_dir}
═══════════════════════════════════════════════════════════════
```

### 8. Create TODO List

Pass the `todos` array from setup output to TodoWrite.

**Understanding the TODO list:**

The TODO list contains **5 high-level reminders per section**:
1. Implement section-NN
2. Run code review subagent for section-NN
3. Perform code review interview for section-NN
4. Commit section-NN
5. Update section-NN documentation

These are **milestones to track progress**, not detailed instructions. For the actual workflow steps, always refer to:
- This file (SKILL.md) for the overall orchestration
- The reference documents in `references/` for detailed protocols

Mark each TODO as `in_progress` when starting that phase, and `completed` when done.

---

## Implementation Loop

For each incomplete section (in manifest order):

**TODO milestone mapping:**
| TODO Item | Workflow Steps |
|-----------|----------------|
| Implement section-NN | Steps 1-5 (read, TDD, stage) |
| Run code review subagent | Step 6, parts 1-4 |
| Perform code review interview | Step 6, parts 5-7 |
| Commit section-NN | Step 7 |
| Update section-NN documentation | Step 8 |

### Step 1: Mark In Progress

Update TODO: `status: "in_progress"`

### Step 2: Read Section File

```
Read {sections_dir}/section-NN-<name>.md
```

### Step 3: Implement Section

See [implementation-loop.md](references/implementation-loop.md)

Follow TDD workflow:
1. Create skeleton files for imports
2. Write tests from section spec
3. Run tests (expect failures)
4. Write implementation
5. Run tests (expect pass)
6. Handle failures with retry (max 3)

### Step 4: Track Created Files

Maintain list of all files created during implementation.

### Step 5: Stage Changes

```bash
# Stage new files
git add {created_files...}

# Stage modified files
git add -u
```

### Step 6: Code Review

See [code-review-protocol.md](references/code-review-protocol.md)

1. Create `{implementation_dir}/code_review/` directory if it doesn't exist
2. Write staged diff to `{code_review_dir}/section-NN-diff.md`
3. Launch `code-reviewer` subagent to analyze the diff
4. Write subagent's findings to `{code_review_dir}/section-NN-review.md`
5. Read review and present findings via AskUserQuestion (multiSelect)
6. Apply selected fixes
7. Re-stage if needed

### Step 7: Commit

See [git-operations.md](references/git-operations.md) and [pre-commit-handling.md](references/pre-commit-handling.md)

1. Create commit message matching detected style
2. Attempt commit
3. Handle pre-commit hooks:
   - If files modified: re-stage and retry (max 2)
   - If lint error: present options to user
4. On success: store commit hash in session config

```bash
git commit -m "$(cat <<'EOF'
Implement section NN: Name

- Summary of changes
- Key features added

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### Step 8: Update Section Documentation

See [section-doc-update.md](references/section-doc-update.md)

After successful commit, update the original section file to reflect what was actually implemented:

1. Read `{sections_dir}/section-NN-<name>.md`
2. Compare planned implementation vs actual:
   - Code review fixes that changed the approach
   - File paths that differed from plan
   - Tests that were added/modified
3. Update the section file with:
   - Actual file paths created/modified
   - Any deviations from original plan (with rationale)
   - Final test count and coverage notes
4. Commit the section doc update:
   ```bash
   git add {sections_dir}/section-NN-<name>.md
   git commit -m "docs: update section-NN docs to match implementation"
   ```

This keeps section files as accurate documentation of what was built, not just what was planned.

### Step 9: Update State

```python
update_section_state(
    implementation_dir,
    section_name,
    status="complete",
    commit_hash="{hash}",
    review_file="review-section-NN.md",
    pre_commit={hooks_ran, modification_retries, skipped}
)
```

### Step 10: Mark Complete

Update TODO: `status: "completed"`

### Step 11: Prompt Compaction

```
═══════════════════════════════════════════════════════════════
Section NN complete and committed.
═══════════════════════════════════════════════════════════════

Completed: {M}/{N} sections
Next: section-{NN+1}-{name}

Consider compacting context before continuing.
Type "continue" when ready.

Note: After compaction, context reloads from {implementation_dir}/deep_implement_config.json
```

Wait for user to say "continue".

### Step 12: Loop

Repeat from Step 1 for next section.

---

## Finalization

After all sections complete:

### Generate usage.md

Introspect implemented code:
- List created files
- Identify main entry points
- Generate example usage
- Write to `{implementation_dir}/usage.md`

```markdown
# Usage Guide

## Quick Start

[Generated from implemented code]

## Example Output

[Hypothetical output - actual results may vary]

## API Reference

[Generated from implemented code]
```

### Output Summary

```
═══════════════════════════════════════════════════════════════
DEEP-IMPLEMENT COMPLETE
═══════════════════════════════════════════════════════════════

Sections implemented: {N}/{N}
Commits created: {N}
Reviews written: {N}

Generated files:
  {implementation_dir}/
  ├── code_review/
  │   ├── section-01-diff.md
  │   ├── section-01-review.md
  │   └── ...
  └── usage.md

Git commits:
  {hash1} Implement section 01: Name
  {hash2} Implement section 02: Name
  ...

Next steps:
  - Review {implementation_dir}/usage.md
  - Run full test suite: {test_command}
  - Create PR if ready
═══════════════════════════════════════════════════════════════
```

---

## Error Handling

### Test Failures

After 3 failed fix attempts:
```
AskUserQuestion:
  question: "Tests still failing after 3 attempts. How to proceed?"
  options:
    - label: "Review and debug"
      description: "I'll show you the test and implementation for inspection"
    - label: "Skip section"
      description: "Mark section as skipped and continue to next"
    - label: "Stop implementation"
      description: "Pause to manually investigate"
```

### Pre-Commit Failures

See [pre-commit-handling.md](references/pre-commit-handling.md)

### Git Commit Failures

If commit fails (non-pre-commit):
```
Git commit failed: {error}

The staged changes are preserved.
You can manually commit with: git commit -m "message"

Continue to next section? [y/n]
```

### Path Safety Violations

```
═══════════════════════════════════════════════════════════════
SECURITY ERROR
═══════════════════════════════════════════════════════════════

Attempted to write file outside allowed directory:
  Path: {attempted_path}
  Allowed root: {git_root}

This section file may contain invalid paths.
Please review the section file.
═══════════════════════════════════════════════════════════════
```

---

## Context After Compaction

After user compacts and says "continue":

1. Re-read `{implementation_dir}/deep_implement_config.json`
2. Determine current state from `sections_state`
3. Resume from next incomplete section
4. TodoWrite with regenerated todos from config

---

## Reference Documents

- [implementation-loop.md](references/implementation-loop.md) - TDD workflow details
- [code-review-protocol.md](references/code-review-protocol.md) - Review and fix process
- [git-operations.md](references/git-operations.md) - Git handling
- [pre-commit-handling.md](references/pre-commit-handling.md) - Hook handling
