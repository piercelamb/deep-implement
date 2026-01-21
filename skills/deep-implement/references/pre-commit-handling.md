# Pre-Commit Hook Handling

Handling pre-commit hooks during /deep-implement commits.

## Detection

At setup, detect pre-commit configuration:

1. **Framework:** `.pre-commit-config.yaml`
2. **Native:** `.git/hooks/pre-commit` (executable)

### Known Formatters

These hooks modify files and may require re-staging:

**Python:**
- black, isort, autopep8, yapf, ruff-format

**JavaScript/TypeScript:**
- prettier, eslint (with --fix)

**Rust:**
- rustfmt, fmt

**Go:**
- gofmt, goimports

## Commit Workflow

```
┌─────────────────────────────────────┐
│         Attempt git commit          │
└─────────────────┬───────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
    SUCCESS              FAILED
        │                   │
   Record hash        ┌─────┴─────┐
   Continue           │           │
                   Modified   Lint Error
                   Files      (no mods)
                      │           │
                  Re-stage    Present to
                  Retry       User
                  (max 2)        │
                      │      ┌───┴───┐
                      │      │   │   │
                      └──────│───│───┘
                             │   │
                           Fix Skip Stop
```

## Handling Modified Files

When commit fails and `git status` shows modified files:

1. Log which files were modified:
   ```
   Pre-commit modified files:
     - src/models.py (formatter)
     - src/utils.py (formatter)
   ```

2. Re-stage modified files:
   ```bash
   git add src/models.py src/utils.py
   ```

3. Retry commit (fresh commit, NOT amend)

4. Max 2 retries to prevent infinite loops

5. If still failing after retries, escalate to user

## Handling Lint Errors

When commit fails with lint/check errors (no file modifications):

Present to user:
```
AskUserQuestion:
  question: "Pre-commit hook failed. How would you like to proceed?"
  options:
    - label: "Review errors and fix"
      description: "I'll analyze the errors and attempt fixes"
    - label: "Skip hooks (--no-verify)"
      description: "Commit without running hooks (will be logged)"
    - label: "Stop implementation"
      description: "Pause to manually resolve"
```

### "Review errors and fix"

1. Parse pre-commit output for specific errors
2. Attempt to fix issues (lint errors, type errors, etc.)
3. Run tests to verify fixes don't break functionality
4. Re-stage all changes
5. Retry commit

### "Skip hooks (--no-verify)"

1. Execute: `git commit --no-verify -m "..."`
2. Log in review file: "Note: Pre-commit hooks skipped by user request"
3. Continue with workflow

### "Stop implementation"

1. Leave staged changes in place
2. Print diagnostic info
3. Exit gracefully

## State Tracking

Store pre-commit info per section in session config:

```json
{
  "sections_state": {
    "section-01-foundation": {
      "status": "complete",
      "commit_hash": "abc123",
      "pre_commit": {
        "hooks_ran": true,
        "modification_retries": 1,
        "skipped": false
      }
    }
  }
}
```

## Native Hook Limitations

For native hooks (`.git/hooks/pre-commit`):

- Cannot introspect behavior
- Warn user: "Native hook detected, behavior unknown"
- Apply same retry logic for modifications
- Cannot identify specific formatters
