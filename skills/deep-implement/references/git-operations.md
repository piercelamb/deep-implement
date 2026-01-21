# Git Operations

Git handling for /deep-implement.

## Safety Principles

1. **Never run destructive commands** unless explicitly requested
   - No `git reset --hard`
   - No `git push --force`
   - No `git clean -fd`

2. **Never skip hooks** unless user explicitly chooses to

3. **Never modify git config**

4. **Validate paths** before any file operation

## Git Detection

```python
check_git_repo(target_dir) -> {"available": bool, "root": str | None}
```

Run at setup. If not available, skip all git operations.

## Branch Check

At setup, check current branch:

```bash
git branch --show-current
```

If on `main` or `master`:
```
AskUserQuestion:
  question: "You're on the {branch} branch. Committing here may not be ideal."
  options:
    - label: "Continue on {branch}"
      description: "Proceed with implementation on this branch"
    - label: "Exit to create feature branch"
      description: "Stop to create a dedicated branch first"
```

## Working Tree Check

At setup, check if working tree is clean:

```bash
git status --porcelain
```

If dirty, warn user:
```
Working tree has uncommitted changes (N files).
This may cause issues mixing your work with implementation.

Options:
  1. Continue anyway
  2. Exit to commit/stash first
```

## Staging Changes

**Important:** `git add -u` does NOT stage new (untracked) files.

Correct approach:
```bash
# 1. Stage new files explicitly
git add path/to/new/file1.py path/to/new/file2.py

# 2. Stage modified tracked files
git add -u
```

## Generating Diffs

For code review:
```bash
git diff --staged
```

## Commit Style Detection

Read recent commits and detect style:

```bash
git log --oneline -20 --format=%s
```

**Conventional:** `feat:`, `fix:`, `docs:`, `chore:`, etc.
**Simple:** Regular sentences

Match the detected style in commit messages.

## Commit Creation

Use HEREDOC for message formatting:

```bash
git commit -m "$(cat <<'EOF'
Implement section 01: Foundation

- Created core data models
- Set up project structure
- Added initial test suite

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

## Storing Commit Hash

After successful commit:

```bash
git rev-parse HEAD
```

Store in session config for resume verification.

## Resume Verification

To check if a commit hash is valid:

```bash
git cat-file -t <hash>
```

Returns "commit" if valid, error otherwise.

## Path Safety

Before any file write, validate path is under allowed root:

```python
def validate_path_safety(path: Path, allowed_root: Path) -> bool:
    resolved_path = path.resolve()
    resolved_root = allowed_root.resolve()
    return str(resolved_path).startswith(str(resolved_root))
```

Reject:
- Absolute paths outside root
- Paths with `..` that escape root
- Symlinks pointing outside root
