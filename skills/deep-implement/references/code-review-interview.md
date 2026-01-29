# Code Review Interview Protocol

Process for triaging code review findings and interviewing the user on important items.

## Overview

After the code-reviewer subagent writes its review to `section-NN-review.md`, triage the findings and interview the user only on items that genuinely need their input.

**Key principles:**
- Not everything needs to be an interview question
- Use judgment to fix obvious things and let go of nitpicks
- Only ask about decisions with real tradeoffs
- Write everything to the transcript (both interview decisions AND auto-fixes)

## Two-Phase Process

```
Phase 1: TRIAGE + INTERVIEW      Phase 2: APPLY FIXES
┌─────────────────────────┐     ┌─────────────────────┐
│ 1. Read review          │     │ 1. Read transcript  │
│ 2. Triage findings      │     │ 2. Apply all FIX    │
│ 3. Ask about important  │     │ 3. Run tests        │
│ 4. Write transcript     │     │ 4. Re-stage files   │
└─────────────────────────┘     └─────────────────────┘
         │                               │
         ▼                               ▼
   interview.md                   → COMMIT ←
   (checkpoint)                  (definitive checkpoint)
```

**This file covers Phase 1.** For Phase 2, see [apply-interview-fixes.md](apply-interview-fixes.md).

**Recovery:**
- Interview file doesn't exist → Restart Phase 1 from beginning
- Interview file exists but no commit → Restart Phase 2 from beginning
- Commit exists → Section complete

---

## Phase 1: Triage and Interview

### 1. Read and Triage the Review

Read the review file at `{code_review_dir}/section-NN-review.md`.

Not everything in a code review needs to become an interview question. Use your judgment:

**Ask the user about:**
- Decisions with real tradeoffs
- Security or correctness concerns
- Things where you're genuinely unsure what they'd prefer

**Just fix (don't ask):**
- Obvious improvements you're confident about
- Things any reasonable developer would want fixed
- Low-risk changes with clear benefit

**Let go:**
- Stylistic nitpicks that don't matter
- "Could be slightly better" observations
- Anything pedantic

The goal is a useful conversation, not a comprehensive audit. When in doubt, lean toward fixing or letting go rather than asking.

### 2. Conduct Interview (if needed)

Only ask about items that genuinely need user input. Remember that the user hasn't been staring at the code - they need to understand what you're asking about. You should contextualize the information from the review with information from the associated `{sections_dir}/section-NN-<name>.md` file so they can fully understand the question.

For each item worth discussing:

```
───────────────────────────────────────────────────────────────
Issue: {brief title}
───────────────────────────────────────────────────────────────

{contextualized explanation of the issue and tradeoffs}

{options for resolution}
```

Use AskUserQuestion for each. Record their decision.

If nothing needs discussion, that's fine - just mention you reviewed the findings and are proceeding with auto-fixes (if any).

### 3. Write Transcript

Write to `{code_review_dir}/section-NN-interview.md` **BEFORE applying any fixes**.

The transcript includes BOTH:
- Items discussed with user (with their decisions)
- Items you're auto-fixing (with note that you're fixing without asking)

---

## Directory Structure

```
planning/
└── implementation/               # state_dir
    └── code_review/
        ├── section-01-diff.md       # Input to subagent
        ├── section-01-review.md     # Subagent review (freeform)
        ├── section-01-interview.md  # Transcript (interview + auto-fixes)
        └── ...
```

---

## Edge Cases

### Nothing Actionable

If the review has nothing worth fixing or discussing:

```
═══════════════════════════════════════════════════════════════
CODE REVIEW: Section NN - Name
═══════════════════════════════════════════════════════════════
Reviewed the code review findings. Nothing requires changes.
Proceeding to commit.
═══════════════════════════════════════════════════════════════
```

Write a minimal transcript:
```markdown
# Code Review: Section NN - Name

**Date:** {ISO timestamp}

No actionable issues. Review noted minor observations but nothing worth changing.
```

Then proceed to documentation update and commit.

### Only Auto-Fixes

If everything can be auto-fixed (nothing needs discussion):

```
═══════════════════════════════════════════════════════════════
CODE REVIEW: Section NN - Name
═══════════════════════════════════════════════════════════════
Reviewed the findings. A few trivial improvements to make,
nothing that needs discussion. Applying fixes and proceeding.
═══════════════════════════════════════════════════════════════
```

Write transcript with auto-fixes section, then proceed to apply them.
