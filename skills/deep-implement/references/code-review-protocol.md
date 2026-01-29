# Code Review Protocol

Code review workflow using a dedicated subagent for /deep-implement.

## Overview

This protocol covers running the code-reviewer subagent.

After implementing a section, before committing:

1. Track files created during implementation
2. Stage all changes (new and modified)
3. Generate diff and write to `{state_dir}/code_review/section-NN-diff.md`
4. Launch code-reviewer subagent
5. Write review to file

Then proceed to the Code Review Interview (Step 7 in SKILL.md).

## Directory Structure

Create `code_review/` inside the state directory:

```
planning/
├── sections/
│   ├── index.md
│   └── section-NN-*.md
└── implementation/               # state_dir
    ├── deep_implement_config.json
    └── code_review/              # Created by this workflow
        ├── section-01-diff.md       # Diff input for subagent
        ├── section-01-review.md     # Review output from subagent
        ├── section-01-interview.md  # Interview transcript (written by interview step)
        ├── section-02-diff.md
        ├── section-02-review.md
        ├── section-02-interview.md
        └── ...
```

## Step Details

### 1. Track Created Files

During implementation, maintain a list of files created.

This is needed because `git add -u` only stages **modified tracked files**, not new files.

### 2. Stage Changes

```bash
# Stage NEW files explicitly
git add path/to/new/file1.py path/to/new/file2.py ...

# Stage MODIFIED tracked files
git add -u
```

### 3. Generate Diff and Write to File

```bash
git diff --staged > {code_review_dir}/section-NN-diff.md
```

If the diff is empty, skip review and proceed to commit.

### 4. Launch Code Reviewer Subagent

Launch the `code-reviewer` subagent with both the section plan and the diff:

```
Task:
  subagent_type: "code-reviewer"
  description: "Review section NN code"
  prompt: |
    Review this implementation:
    - Section plan: {sections_dir}/section-NN-<name>.md
    - Code changes: {code_review_dir}/section-NN-diff.md
```

The subagent:
- Has tools: `Read, Grep, Glob` (NO Write)
- Reads the section plan to understand requirements
- Reads the diff to see what was implemented
- Compares implementation against the plan
- Returns JSON with section name and freeform review

**Subagent returns:**
```json
{
  "section": "section-NN-name",
  "review": "Freeform review text with findings, suggestions, etc."
}
```

The review is freeform prose - the subagent has flexibility in how it structures its feedback.

### 5. Write Review to File

Write the subagent's review to `{code_review_dir}/section-NN-review.md`:

```markdown
# Code Review: Section NN - Name

{review text from subagent}
```

After writing the review file, proceed to [code-review-interview.md](code-review-interview.md) for the interactive interview process.

See `agents/code-reviewer.md` for the custom subagent definition.
