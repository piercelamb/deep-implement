# Finalization

After all sections are implemented and committed, generate documentation and output a summary.

## Generate usage.md

Introspect the implemented code to create a usage guide:

1. List all files created during implementation
2. Identify main entry points (CLI commands, API endpoints, main functions)
3. Generate example usage based on the implementation
4. Write to `{state_dir}/usage.md`

```markdown
# Usage Guide

## Quick Start

[Generated from implemented code - show how to run/use what was built]

## Example Output

[Hypothetical output - actual results may vary]

## API Reference

[Generated from implemented code - document public interfaces]
```

The usage guide should be practical and help someone actually use what was built.

---

## Output Summary

Print a completion summary:

```
═══════════════════════════════════════════════════════════════
DEEP-IMPLEMENT COMPLETE
═══════════════════════════════════════════════════════════════

Sections implemented: {N}/{N}
Commits created: {N}
Reviews written: {N}

Generated files:
  {implementation_dir}/
  ├── code_review/
  │   ├── section-01-diff.md
  │   ├── section-01-review.md
  │   └── ...
  └── usage.md

Git commits:
  {hash1} Implement section 01: Name
  {hash2} Implement section 02: Name
  ...

Next steps:
  - Review {implementation_dir}/usage.md
  - Run full test suite: {test_command}
  - Create PR if ready
═══════════════════════════════════════════════════════════════
```
