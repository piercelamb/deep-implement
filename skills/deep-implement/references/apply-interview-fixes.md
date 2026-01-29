# Apply Interview Fixes

Apply all fixes recorded in the interview transcript.

## Overview

Read the transcript and implement:
1. Fixes the user approved during the interview
2. Auto-fixes you decided to make without asking

Both are recorded in `section-NN-interview.md` - this is your source of truth.

**Recovery:** If compaction happens, the interview file is the checkpoint. Restart applying fixes from the beginning - you'll notice already-applied changes as you work.

---

## Steps

### 1. Read Transcript

Read `{code_review_dir}/section-NN-interview.md` to find:
- Items in "Discussed with User" marked for fixing
- Items in "Auto-Fixes" section

### 2. Apply Fixes

For each fix (both user-approved and auto-fixes):

1. Check if already applied (code already changed) → skip
2. If not applied, implement the fix
3. Note what was changed

**Why check first?** If compaction happened mid-way, some fixes may already be applied. You'll notice as you read the code.

### 3. Run Tests

After all fixes applied:
```bash
{test_command}
```

If tests fail, fix them.

### 4. Re-Stage Changes

```bash
git add -u
git add <any_new_files>
```

Then proceed to update section documentation and commit.

---

## Edge Cases

### No Fixes

If the transcript has no fixes (user skipped everything, no auto-fixes), this step is a no-op. Proceed directly to documentation update and commit.
