---
name: deep-implement
description: Implements code from /deep-plan section files with TDD methodology, code review, and git workflow. Use when implementing plans created by /deep-plan.
license: MIT
compatibility: Requires uv (Python 3.11+), git repository recommended
---

# Deep Implementation Skill

Implements code from /deep-plan section files with integrated review and git workflow.

## CRITICAL: First Actions

**BEFORE using any other tools**, do these in order:

### A. Print Intro Banner

```
⚠️  CONTEXT WARNING: This workflow is token-intensive. Consider compacting first.

═══════════════════════════════════════════════════════════════
DEEP-IMPLEMENT: Section-by-Section Implementation
═══════════════════════════════════════════════════════════════
Implements /deep-plan sections with:
  - TDD methodology
  - Code review at each step
  - Git commits with review trails

Usage: /deep-implement @path/to/sections/.

Note: deep-implement creates a large TODO list. Expand your window to avoid flickering
═══════════════════════════════════════════════════════════════
```

### B. Validate Input

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

### C. Discover Plugin Root

Find the setup script to discover the plugin root:
```bash
find "$(pwd)" -path "*/deep_implement/scripts/checks/setup_implementation_session.py" -type f 2>/dev/null | head -1
```

If not found in current directory, search from home:
```bash
find ~ -path "*/deep_implement/scripts/checks/setup_implementation_session.py" -type f 2>/dev/null | head -1
```

**Store the script path.** The plugin_root is the directory two levels up from `scripts/checks/`.

### D. Determine Target Directory

The target directory is where implementation code will be written. Check if a previous session exists with a saved target:

```bash
# Check for existing config
cat "{sections_dir}/../implementation/deep_implement_config.json" 2>/dev/null | grep -o '"target_dir": "[^"]*"'
```

**If config exists with target_dir:** Use that value (skip the prompt).

**If no config or no target_dir:** Get current working directory and ask user:

```bash
pwd
```

```
AskUserQuestion:
  question: "Where should implementation code be written?"
  options:
    - label: "{cwd}"
      description: "Current working directory (Recommended)"
    - label: "Specify path"
      description: "Enter a different absolute path"
```

If user selects "Specify path", they will type the absolute path.

**Store target_dir** for use in setup script.

### E. Run Setup Script

**First, check for session_id in your context.** Look for `DEEP_IMPLEMENT_SESSION_ID=xxx`
which was set by the SessionStart hook. This appears in your context as additional context.

Run the setup script with discovered paths:
```bash
uv run {script_path} \
  --sections-dir "{sections_dir}" \
  --target-dir "{target_dir}" \
  --plugin-root "{plugin_root}" \
  --session-id "{DEEP_IMPLEMENT_SESSION_ID}"
```

If `DEEP_IMPLEMENT_SESSION_ID` is not in your context, omit `--session-id`
(setup will fall back to `CLAUDE_SESSION_ID` env var).

Parse the JSON output.

**If `success == false`:** Display error and stop.

**Session ID diagnostics in output:**
- `session_id`: The session ID being used for tasks
- `session_id_source`: Where it came from ("context", "env", or "none")
- `session_id_matched`: If both context and env were present, whether they matched (useful for debugging)

### F. Handle Branch Check

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

### G. Handle Working Tree Status

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

### H. Print Preflight Report

```
═══════════════════════════════════════════════════════════════
PREFLIGHT REPORT
═══════════════════════════════════════════════════════════════
Target dir:     {target_dir}
Repo root:      {git_root}
Branch:         {current_branch}
Working tree:   {Clean | Dirty (N files)}
Pre-commit:     {Detected (type) | None}
                {May modify files: Yes (formatters) | No | Unknown}
Test command:   {test_command}
Sections:       {N} detected
Completed:      {M} already done
State storage:  {state_dir}
═══════════════════════════════════════════════════════════════
```

### I. Verify Task List

Check the setup output for task status:

1. If `tasks_written > 0`: Tasks have been written. Call `TaskList` to see them.
2. If `task_write_error` is present: Task write failed - log the error and continue with manual tracking.
3. If no `task_list_id`: Session ID not available - the SessionStart hook may not have run.

**After setup succeeds:** Call `TaskList` to see the implementation tasks.

**Understanding the task list:**

The task list contains **6 high-level reminders per section**:
1. Implement section-NN
2. Run code review subagent for section-NN
3. Perform code review interview for section-NN
4. Update section-NN documentation
5. Commit section-NN
6. Record section-NN completion

Plus a **compaction prompt every 2nd section** (after 02, 04, 06, etc.).

Context items appear as pending tasks at the start (e.g., `plugin_root=/path/...`, `sections_dir=/path/...`).

These are **milestones to track progress**, not detailed instructions. For the actual workflow steps, always refer to:
- This file (SKILL.md) for the overall orchestration
- The reference documents in `references/` for detailed protocols

Mark each task as `in_progress` when starting: `TaskUpdate(taskId=X, status="in_progress")`
Mark each task as `completed` when done: `TaskUpdate(taskId=X, status="completed")`

---

## Implementation Loop

For each incomplete section (in manifest order):

**Task milestone mapping:**
| Task Subject | Workflow Steps |
|-----------|----------------|
| Implement section-NN | Steps 1-5 (read, TDD, stage) |
| Run code review subagent | Step 6 (launch subagent, write review) |
| Perform code review interview | Steps 7-8 (triage, interview, apply fixes) |
| Update section-NN documentation | Step 9 (update section file with what was actually built) |
| Commit section-NN | Step 10 (commit implementation + doc update together) |
| Record section-NN completion | Step 11 (run update_section_state.py to save commit hash) |
| Context check (every 2nd section only) | Step 13 (context management options) |

**Note:** Step 12 (Mark Complete) is internal task status update. Step 14 (Loop) continues to next section. Context checks only appear after sections 02, 04, 06, etc.

### Step 1: Mark In Progress

Update task: `TaskUpdate(taskId=X, status="in_progress")`

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

### Step 6: Code Review (Subagent)

See [code-review-protocol.md](references/code-review-protocol.md)

1. Create `{state_dir}/code_review/` directory if it doesn't exist
2. Write staged diff to `{code_review_dir}/section-NN-diff.md`
3. Launch `code-reviewer` subagent to analyze the diff
4. Write subagent's review to `{code_review_dir}/section-NN-review.md`

### Step 7: Code Review Triage and Interview

See [code-review-interview.md](references/code-review-interview.md)

Triage the review findings and interview the user only on important items:

1. Read the review and use judgment to categorize:
   - **Ask user:** Decisions with real tradeoffs, security concerns
   - **Auto-fix:** Obvious improvements, low-risk changes
   - **Let go:** Nitpicks, pedantic observations
2. Interview user only on items that need their input
3. Write transcript with both interview decisions AND auto-fixes to `{code_review_dir}/section-NN-interview.md`

The goal is a useful conversation, not a comprehensive audit.

### Step 8: Apply Fixes

See [apply-interview-fixes.md](references/apply-interview-fixes.md)

Apply all fixes recorded in the transcript:

1. Read `{code_review_dir}/section-NN-interview.md`
2. Apply user-approved fixes and auto-fixes (if already applied, skip)
3. Run tests to verify nothing broke
4. Re-stage modified files

**Recovery:** If compaction happens, the interview file is the checkpoint. Restart applying fixes from the beginning - you'll notice already-applied changes. The commit is the definitive checkpoint.

### Step 9: Update Section Documentation

See [section-doc-update.md](references/section-doc-update.md)

**Before committing**, update the original section file to reflect what was actually implemented:

1. Read `{sections_dir}/section-NN-<name>.md`
2. Compare planned implementation vs actual:
   - Code review fixes that changed the approach
   - File paths that differed from plan
   - Tests that were added/modified
3. Update the section file with:
   - Actual file paths created/modified
   - Any deviations from original plan (with rationale)
   - Final test count and coverage notes
4. **If sections_dir is inside git_root**, stage the section doc:
   ```bash
   git add {sections_dir}/section-NN-<name>.md
   ```
   (If sections_dir is outside git_root, skip staging - the doc update lives with the planning files)

This keeps section files as accurate documentation of what was built, not just what was planned.

### Step 10: Commit

See [git-operations.md](references/git-operations.md) and [pre-commit-handling.md](references/pre-commit-handling.md)

Commit implementation + doc update together (one commit per section):

1. Create commit message matching detected style
2. Attempt commit
3. Handle pre-commit hooks:
   - If files modified: re-stage and retry (max 2)
   - If lint error: present options to user
4. On success: store commit hash in session config

```bash
git commit -m "$(cat <<'EOF'
Implement section NN: Name

- Very concise summary of features/changes

Plan: section-NN-<name>.md
Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### Step 11: Update State

After successful commit, update the session config:

```bash
uv run {plugin_root}/scripts/tools/update_section_state.py \
    --state-dir "{state_dir}" \
    --section "{section_name}" \
    --commit-hash "{commit_hash}"
```

This records the commit hash so the section is recognized as complete on resume.

### Step 12: Mark Complete

Update task: `TaskUpdate(taskId=X, status="completed")`

### Step 13: Context Check (Every 2nd Section)

**Only prompt after sections 02, 04, 06, etc.** (every 2nd section).

If this is NOT a 2nd section, skip directly to Step 14.

If this IS a 2nd section (02, 04, 06, ...):

```
═══════════════════════════════════════════════════════════════
Section NN complete and committed.
═══════════════════════════════════════════════════════════════

Completed: {M}/{N} sections
Next: section-{NN+1}-{name}

Context Management Options:
  1. /clear + re-run /deep-implement (Recommended)
     - Fresh context with full instructions
     - Progress preserved via file-based recovery

  2. Continue in current session
     - Auto-compact triggers at ~95% if needed
     - May lose some instruction detail after compaction

Type "continue" or run /clear and re-invoke /deep-implement @{sections_dir}/.
```

Wait for user response. If they say "continue", proceed to Step 14.

### Step 14: Loop

Repeat from Step 1 for next section.

---

## Finalization

After all sections complete, see [finalization.md](references/finalization.md):

1. Generate `{state_dir}/usage.md` with usage guide for what was built
2. Print completion summary with commits, files, and next steps

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

## Context Recovery

**After `/clear` + re-run `/deep-implement`:**

The setup script detects completed sections via `deep_implement_config.json` and marks their tasks complete. You'll resume from the next pending section with fresh instructions.

**After compaction (if user chose "continue"):**

1. Call `TaskList` to see current state
2. Find context tasks to recover paths:
   - `plugin_root=...` - extract value after `=`
   - `sections_dir=...` - extract value after `=`
   - `state_dir=...` - extract value after `=`
3. Find next pending, unblocked task
4. Resume workflow from that task

---

## Reference Documents

- [implementation-loop.md](references/implementation-loop.md) - TDD workflow details
- [code-review-protocol.md](references/code-review-protocol.md) - Subagent review process
- [code-review-interview.md](references/code-review-interview.md) - Interactive interview with user
- [apply-interview-fixes.md](references/apply-interview-fixes.md) - Applying fixes from interview
- [section-doc-update.md](references/section-doc-update.md) - Updating section documentation
- [git-operations.md](references/git-operations.md) - Git handling
- [pre-commit-handling.md](references/pre-commit-handling.md) - Hook handling
- [finalization.md](references/finalization.md) - Usage guide and completion summary
