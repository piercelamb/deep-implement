# Implementation Loop

Per-section implementation workflow for /deep-implement.

## Loop Overview

For each section in the manifest:

```
1. Mark section in progress (TodoWrite)
2. Read section file
3. Create skeleton files
4. Write tests (TDD red phase)
5. Run tests (expect failures)
6. Write implementation code
7. Run tests (expect pass)
8. Handle failures with retry
```

## Step Details

### 1. Mark In Progress

Update the section TODO to `in_progress`:
```
TodoWrite: Update section TODO status to "in_progress"
```

### 2. Read Section File

```
Read sections/section-NN-<name>.md
```

Extract:
- Test code (look for code blocks in "Tests First" section)
- Implementation requirements
- File paths to create/modify
- Success criteria

### 3. Create Skeleton Files

**CRITICAL:** Before writing tests, create empty skeleton files for modules that will be imported.

This prevents `ImportError` during the TDD red phase.

Example:
```python
# For a test that does: from scripts.lib.config import load_session_config
# Create: scripts/lib/config.py with:
def load_session_config(*args, **kwargs):
    raise NotImplementedError("Skeleton - implement me")
```

### 4. Write Tests (Red Phase)

Create test files from the section's test specifications.

Place tests in appropriate locations (typically `tests/test_*.py`).

### 5. Run Tests (Expect Failures)

```bash
{test_command} tests/test_<module>.py -v
```

Expected result: **Assertion failures** (NOT import errors).

If you see `ImportError` or `ModuleNotFoundError`:
- Check that skeleton files exist
- Check import paths are correct

### 6. Write Implementation

Replace skeleton code with real implementation.

Follow the section's implementation specifications exactly.

### 7. Run Tests (Expect Pass)

```bash
{test_command} tests/test_<module>.py -v
```

All tests should pass.

### 8. Handle Failures

If tests fail after implementation:

**Attempt 1-3:** Diagnose and fix
- Read error messages
- Check implementation against spec
- Fix and re-run

**After 3 attempts:** Escalate to user
```
Tests still failing after 3 attempts.

Failures:
  - test_name: Error message

Would you like to:
  1. Review the test and implementation
  2. Skip this section and continue
  3. Stop implementation
```

## Next Steps

After the implementation loop completes for a section:
1. Stage changes (see git-operations.md)
2. Review code (see code-review-protocol.md)
3. Commit (see git-operations.md)
4. Prompt compaction
5. Continue to next section
