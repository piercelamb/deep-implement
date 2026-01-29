# Section Documentation Update

**Before committing**, update the section file to reflect actual implementation.

## Purpose

Section files start as implementation plans. After implementation, they should become accurate documentation of what was built. This keeps the section files useful as reference documentation, not stale plans.

## When to Update

Update the section file:
1. After implementation + code review + interview fixes are complete
2. **Before** the commit

## What to Update

### 1. File Paths

If actual file paths differ from planned:

```markdown
## Files Created

~~Planned: `src/models/user.py`~~
Actual: `src/models/users.py` (plural for consistency with existing codebase)
```

Or simply update the paths inline if the change is minor.

### 2. Implementation Deviations

Document significant deviations from the plan:

```markdown
## Implementation Notes

**Deviation from plan:** Originally planned to use `dataclass`, but switched to `Pydantic`
for validation. This aligns with existing patterns in `src/models/`.
```

### 3. Code Review Fixes

If code review resulted in significant changes:

```markdown
## Code Review Changes

- Added input validation for `user_id` parameter (review finding #2)
- Switched from `print()` to structured logging (review finding #4)
```

### 4. Test Coverage

Update test information if it differs:

```markdown
## Tests

- `tests/test_user.py`: 8 tests (planned: 6, added 2 edge case tests from review)
```

## Update Process

1. **Read the section file** you just implemented
2. **Compare** planned vs actual implementation
3. **Update in place** - modify the existing content, don't append
4. **Keep it concise** - this is documentation, not a changelog
5. **Stage if in repo** (see below)

### Staging the Doc Update

The sections directory may or may not be inside the target git repo:

**If `sections_dir` is inside `git_root`:**
```bash
git add {sections_dir}/section-NN-<name>.md
```
The doc update will be included in the section commit.

**If `sections_dir` is outside `git_root`:**
- Just update the file (no staging needed)
- The doc update lives with the planning files, separate from the implementation commit
- This is fine - the section file still serves as documentation

To check: compare `sections_dir` path against `git_root` path.

## What NOT to Update

- Don't change the section number or name
- Don't remove the SECTION_MANIFEST reference
- Don't add implementation details that belong in code comments
- Don't duplicate the full code - reference file paths instead

## Example Update

Before (plan):
```markdown
### File: `scripts/lib/config.py`

Create config management module with:
- `load_config()` - Load from JSON
- `save_config()` - Save to JSON
```

After (documentation):
```markdown
### File: `scripts/lib/config.py`

Config management module:
- `load_session_config()` - Load from JSON (renamed for clarity)
- `save_session_config()` - Save to JSON
- `create_session_config()` - Create new config with defaults (added)
- `update_section_state()` - Update per-section state (added)

**Note:** Added `create_session_config` and `update_section_state` based on
code review feedback about separation of concerns.
```

## Skip Conditions

Skip the documentation update if:
- No significant deviations from plan
- Only minor formatting/style changes were made
- The section file already accurately reflects implementation
