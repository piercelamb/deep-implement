# Code Review Protocol

Code review workflow using a dedicated subagent for /deep-implement.

## Overview

After implementing a section, before committing:

1. Track files created during implementation
2. Stage all changes (new and modified)
3. Generate diff and write to review directory
4. Launch code-reviewer subagent
5. Write review findings to file
6. Present findings to user
7. Apply selected fixes
8. Re-stage if needed

## Directory Structure

Create `code_review/` inside the implementation directory:

```
planning/
├── sections/
│   ├── index.md
│   └── section-NN-*.md
└── implementation/
    ├── deep_implement_config.json
    └── code_review/                # Created by this workflow
        ├── section-01-diff.md      # Diff input for subagent
        ├── section-01-review.md    # Review output from subagent
        ├── section-02-diff.md
        ├── section-02-review.md
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

For no-git fallback, write file contents instead:
```markdown
# Section NN: Name - Code Changes

## Files Created/Modified

### path/to/file1.py
\`\`\`python
<full file content>
\`\`\`

### path/to/file2.py
\`\`\`python
<full file content>
\`\`\`
```

### 4. Launch Code Reviewer Subagent

Launch the `code-reviewer` subagent:

```
Task:
  subagent_type: "code-reviewer"
  description: "Review section NN code"
  prompt: "Review the code changes in {code_review_dir}/section-NN-diff.md"
```

The subagent:
- Has tools: `Read, Grep, Glob` (NO Write)
- Reads the diff file
- Returns JSON with findings

**Subagent returns:**
```json
{
  "section": "section-NN-name",
  "findings": [
    {
      "id": 1,
      "title": "Missing null check",
      "severity": "medium",
      "explanation": "The function doesn't handle null input...",
      "suggestion": "Add: if value is None: raise ValueError(...)"
    },
    ...
  ],
  "summary": {
    "files_reviewed": 3,
    "total_findings": 5,
    "by_severity": {"high": 1, "medium": 2, "low": 2}
  }
}
```

### 5. Write Review to File

Parse the subagent's JSON response and write to `{code_review_dir}/section-NN-review.md`:

```markdown
# Code Review: Section NN - Name

## Summary

Files reviewed: 3
Total findings: 5 (1 high, 2 medium, 2 low)

## Findings

### 1. [MEDIUM] Missing null check

The function doesn't handle null input...

**Suggestion:** Add: if value is None: raise ValueError(...)

---

### 2. [HIGH] SQL injection vulnerability

...
```

### 6. Present Findings to User

Read the review file and use AskUserQuestion with multiSelect:

```
AskUserQuestion:
  question: "Which review findings should be addressed?"
  header: "Code Review"
  multiSelect: true
  options:
    - label: "1. [MEDIUM] Missing null check"
      description: "The function doesn't handle null input..."
    - label: "2. [HIGH] SQL injection vulnerability"
      description: "..."
    ...
    - label: "None - proceed with commit"
      description: "Accept implementation as-is"
```

### 7. Apply Selected Fixes

For each finding the user selected:
1. Implement the fix
2. Run tests to verify fix doesn't break anything
3. Track any new files created

### 8. Re-Stage Changes

If fixes were applied:
```bash
git add <new_fix_files>
git add -u
```

Update the review file with fix status:
```markdown
## Applied Fixes

- Finding 1: Added null check in validate_input()
- Finding 3: Parameterized SQL query
```

See `agents/code-reviewer.md` for the custom subagent definition.
