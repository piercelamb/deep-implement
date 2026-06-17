# GitHub Workflow

GitHub integration for deep-implement: one PR per section with optional tracking issue.

## Prerequisites

The setup script checks three conditions:
1. **GitHub remote** — `git remote get-url origin` points to `github.com`
2. **`gh` CLI installed** — `gh --version` succeeds
3. **`gh` authenticated** — `gh auth status` succeeds

All three must pass for `github.available = true` in setup output. If any fail, GitHub workflow is not offered.

## Opt-In

At Step F (Branch Check), if `github.available`, ask the user. If they opt in:
- Store `base_branch` = current branch
- Create tracking issue with section checklist
- Store issue number in config via `update_github_state.py`

## Per-Section Flow

When GitHub is enabled, the workflow wraps each section:

### Before implementation (Step 5)
```bash
git checkout -b implement/{section-name}
```

### After commit (Step 10.5)
```bash
git push -u origin implement/{section-name}
gh pr create --title "section-NN: {name}" \
    --body "## Summary\n{description}\n\nCloses #{issue}" \
    --base {base_branch}
```

Store PR info, update issue checkbox, print URL, return to base branch.

### Between sections
```bash
git checkout {base_branch}
```

## Tracking Issue

Created at start with section checklist:
```markdown
## Implementation Tracking

Sections:
- [ ] section-01-foundation
- [ ] section-02-models
...
```

Checkboxes updated after each section PR. The last PR's `Closes #N` auto-closes the issue on merge.

## Idempotency on Resume

- **Issue**: Check for existing issue by title prefix before creating a new one
- **Branch**: If `implement/{section-name}` exists, check it out instead of creating
- **PR**: Check for existing PR on the branch before creating (`gh pr list --head implement/{section-name}`)
- **Config**: `github.section_prs` tracks which sections already have PRs

## Error Handling

GitHub operations are **best-effort**. Network failures, permission errors, or API rate limits print a warning and continue. Implementation progress is never blocked by GitHub.

If push fails: warn user, continue to next section (commit is saved locally).
If PR creation fails: warn user, print manual command they can run later.
If issue update fails: silently continue.

## Finalization

When all sections complete, print summary table:
```
Pull Requests:
  PR #1: section-01-foundation — https://github.com/owner/repo/pull/1
  PR #2: section-02-models — https://github.com/owner/repo/pull/2
Tracking Issue: #42
```

No push or PR at finalization — everything was handled per-section.
