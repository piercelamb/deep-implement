# Pre-Push Aggregate Review

Optional quality gate before pushing each section branch and creating a PR.

## When

Runs in Step 10.5, after commit but before `git push`. Only when GitHub workflow is enabled.

## Process

1. Generate the full section diff against base branch:
   ```bash
   git diff {base_branch}...HEAD
   ```

2. Write diff to `{code_review_dir}/section-NN-prepush-diff.md`

3. Launch `code-reviewer` subagent with the aggregate diff and section plan

4. Parse review findings

## Handling Findings

**No findings or LOW/MEDIUM only:** Proceed with push.

**CRITICAL findings:**
```
AskUserQuestion:
  question: "Pre-push review found critical issues. How to proceed?"
  options:
    - label: "Fix issues"
      description: "Address critical findings before pushing"
    - label: "Push anyway"
      description: "Accept the risk and create PR"
    - label: "Stop"
      description: "Pause to investigate manually"
```

If user chooses "Fix issues": apply fixes, re-run tests, amend commit, re-review (max 1 retry).

## Skipping

The pre-push review is a quality signal, not a gate. If it adds too much latency or the user wants to skip, they can always choose "Push anyway". The per-section code review (Step 6-8) already catches most issues.
