# Implementation Splits: LLM_WRONG MapReduce

This document breaks the research plan into sequential, isolated units of work. Each split is independently implementable and verifiable before moving to the next.

## Overview

| Split | Name | Dependencies | Verification |
|-------|------|--------------|--------------|
| 1 | FalseNegativeLoader | None | Unit tests pass |
| 2 | Config Extension | Split 1 | Unit tests pass |
| 3 | Aggregator Mode Branching | Splits 1, 2 | Unit tests pass |
| 4 | CLI Mode Flag | Splits 1, 2, 3 | Unit tests + dry-run works |
| 5 | Round 1 Prompts | None (parallel) | Prompt tests pass |
| 6 | Consolidation Prompts | Split 5 | Prompt tests pass |
| 7 | Integration Testing | All above | Full pipeline runs |

---

## Split 1: FalseNegativeLoader

**Goal:** Create a standalone loader that reads LLM_WRONG entries from `detailed_results.json` and returns `PolicyReasons` objects compatible with the existing aggregator.

**Isolation:** This split has NO dependencies on existing code changes. It only imports the existing `PolicyReasons` dataclass.

### Files to Create

| File | Type | Description |
|------|------|-------------|
| `tests/scripts/experiments/control_detection/reason_aggregator/test_false_negative_loader.py` | Test | ~150 lines |
| `ai_services/scripts/experiments/control_detection/reason_aggregator/false_negative_loader.py` | Impl | ~80 lines |

### Scope

- Load JSON from `detailed_results.json`
- Filter to `verdict == "LLM_WRONG"` AND `dispute_reason in ("NO_MATCH", "PARTIAL")`
- Group entries by `policy_name`
- Format each entry as text (dispute, control, reasoning, evidence)
- Return `list[PolicyReasons]` for compatibility
- Provide `get_statistics()` method for dry-run info
- Support shuffle with seed for reproducibility

### Verification

```bash
uv run pytest tests/scripts/experiments/control_detection/reason_aggregator/test_false_negative_loader.py -v
```

**Success Criteria:**
- All 9 test cases pass
- Loader can be imported independently
- Returns correct data types

---

## Split 2: Config Extension

**Goal:** Add mode selection and false-negative-specific paths to `AggregatorConfig`.

**Isolation:** Only modifies `config.py`. Tests don't require aggregator changes yet.

### Files to Modify/Create

| File | Type | Description |
|------|------|-------------|
| `tests/scripts/experiments/control_detection/reason_aggregator/test_config.py` | Test | Add ~20 lines |
| `ai_services/scripts/experiments/control_detection/reason_aggregator/config.py` | Impl | Add ~15 lines |

### Scope

- Add `mode: Literal["mapping-reasons", "false-negatives"]` field
- Add `false_negative_results_file` path
- Add `false_negative_prompts_dir` path
- Add `false_negative_consolidation_prompts_dir` path
- Add `false_negative_output_dir` path
- Ensure type safety (invalid mode should fail)

### Verification

```bash
uv run pytest tests/scripts/experiments/control_detection/reason_aggregator/test_config.py -v -k "FalseNegative or mode"
```

**Success Criteria:**
- Config accepts both modes
- Invalid mode raises error
- All new paths are accessible on config object

---

## Split 3: Aggregator Mode Branching

**Goal:** Add mode-aware methods to `ReasonAggregator` that select the appropriate loader, prompts, and output directory based on config mode.

**Isolation:** Adds new methods to aggregator. Existing functionality unchanged (default mode is `mapping-reasons`).

### Files to Modify/Create

| File | Type | Description |
|------|------|-------------|
| `tests/scripts/experiments/control_detection/reason_aggregator/test_aggregator_mode.py` | Test | ~50 lines |
| `ai_services/scripts/experiments/control_detection/reason_aggregator/aggregator.py` | Impl | Add ~30 lines |

### Scope

- Add `_get_input_loader()` method (returns FalseNegativeLoader or ReasonFileLoader)
- Add `_get_round1_prompts_dir()` method
- Add `_get_consolidation_prompts_dir()` method
- Add `_get_output_dir()` method
- Wire these methods into the aggregation flow

### Verification

```bash
uv run pytest tests/scripts/experiments/control_detection/reason_aggregator/test_aggregator_mode.py -v
```

**Success Criteria:**
- Mode selection returns correct loader type
- Mode selection returns correct prompt directories
- Default mode (mapping-reasons) behavior unchanged

---

## Split 4: CLI Mode Flag

**Goal:** Add `--mode` / `-m` flag to CLI and wire it through to config.

**Isolation:** Modifies `run.py` only. Requires Splits 1-3 for the config and aggregator to work.

### Files to Modify/Create

| File | Type | Description |
|------|------|-------------|
| `tests/scripts/experiments/control_detection/reason_aggregator/test_cli.py` | Test | Add ~30 lines |
| `ai_services/scripts/experiments/control_detection/reason_aggregator/run.py` | Impl | Add ~15 lines |

### Scope

- Add `--mode` option with choices `mapping-reasons`, `false-negatives`
- Add `-m` short form
- Validate mode value
- Pass mode to `AggregatorConfig`
- Update dry-run output to show mode info

### Verification

```bash
# Unit tests
uv run pytest tests/scripts/experiments/control_detection/reason_aggregator/test_cli.py -v -k "mode"

# Manual verification
uv run python -m ai_services.scripts.experiments.control_detection.reason_aggregator.run --help
uv run python -m ai_services.scripts.experiments.control_detection.reason_aggregator.run --mode false-negatives --dry-run
```

**Success Criteria:**
- `--help` shows mode option
- `--mode false-negatives --dry-run` runs without error
- Invalid mode shows helpful error

---

## Split 5: Round 1 Prompts (false_negative_analysis)

**Goal:** Create the prompts for Round 1 extraction of failure patterns from LLM_WRONG data.

**Isolation:** Can be done in parallel with Splits 2-4. Only creates files, no code changes.

### Files to Create

| File | Type | Description |
|------|------|-------------|
| `tests/scripts/experiments/control_detection/reason_aggregator/test_prompts_false_negative.py` | Test | ~30 lines (partial) |
| `reason_aggregator/prompts/false_negative_analysis/system` | Prompt | System instructions |
| `reason_aggregator/prompts/false_negative_analysis/user` | Prompt | User template with placeholders |
| `reason_aggregator/prompts/false_negative_analysis/response.json` | Schema | JSON schema for output |

### Scope

**System Prompt:**
- Role: GRC Auditor analyzing LLM false negatives
- Task: Extract failure avoidance rules
- Focus: Generalizable patterns, not specific policy/control pairs
- Output: Structured rules with failure patterns and recovery heuristics

**User Prompt Placeholders:**
- `{SOURCE_1_NAME}` - First policy name
- `{SOURCE_1_REASONS}` - First policy's failure analyses
- `{SOURCE_2_NAME}` - Second policy name
- `{SOURCE_2_REASONS}` - Second policy's failure analyses

**Response Schema:**
- `decision_rules` array (reuse existing schema structure for compatibility)
- Each rule: `rule_name`, `failure_pattern`, `recovery_heuristic`, `evidence_types`, etc.

### Verification

```bash
uv run pytest tests/scripts/experiments/control_detection/reason_aggregator/test_prompts_false_negative.py -v -k "round1"
```

**Success Criteria:**
- All 3 prompt files exist
- System prompt mentions "failure" or "false negative"
- User prompt has all 4 placeholders
- Response schema is valid JSON with required structure

---

## Split 6: Consolidation Prompts (consolidate_failure_patterns)

**Goal:** Create the prompts for Round 2+ consolidation of failure patterns.

**Isolation:** Depends on Split 5's schema decisions. Creates files only.

### Files to Create

| File | Type | Description |
|------|------|-------------|
| `reason_aggregator/prompts/consolidate_failure_patterns/system` | Prompt | Consolidation instructions |
| `reason_aggregator/prompts/consolidate_failure_patterns/user` | Prompt | User template with indexed patterns |
| `reason_aggregator/prompts/consolidate_failure_patterns/response.json` | Schema | JSON schema for merged output |

### Scope

**System Prompt:**
- Role: Pattern consolidation expert
- Task: Merge similar failure patterns, preserve specificity
- Rules: Same merge criteria as existing consolidation prompts

**User Prompt:**
- Reference indexed patterns (U1_0, R1_0, etc.)
- Instructions for merging vs. passing through

**Response Schema:**
- `merged_rules` array with `derived_from` tracking
- `unchanged_universal` array for pass-through

### Verification

```bash
uv run pytest tests/scripts/experiments/control_detection/reason_aggregator/test_prompts_false_negative.py -v -k "consolidation"
```

**Success Criteria:**
- All 3 consolidation prompt files exist
- User prompt references indexed patterns
- Response schema is valid JSON

---

## Split 7: Integration Testing

**Goal:** Verify the complete pipeline works end-to-end with real data.

**Isolation:** Requires all previous splits. Tests against actual `detailed_results.json`.

### Scope

1. **Dry Run Test:**
   ```bash
   uv run python -m ai_services.scripts.experiments.control_detection.reason_aggregator.run \
     --mode false-negatives \
     --dry-run
   ```
   - Should show: 69 entries, ~20 unique policies

2. **Single Round Test:**
   ```bash
   uv run python -m ai_services.scripts.experiments.control_detection.reason_aggregator.run \
     --mode false-negatives \
     --max-rounds 1 \
     -n 1
   ```
   - Should produce round 1 output files

3. **Full Aggregation:**
   ```bash
   uv run python -m ai_services.scripts.experiments.control_detection.reason_aggregator.run \
     --mode false-negatives \
     -n 3
   ```
   - Should converge to final output
   - Check `failure_patterns/` directory for results

### Verification

**Success Criteria:**
- Dry run shows correct statistics
- Round 1 produces valid JSON output
- Full run converges without errors
- Final output contains meaningful failure avoidance rules

---

## Dependency Graph

```
Split 1 (Loader) ──────┐
                       ├──► Split 3 (Aggregator) ──► Split 4 (CLI) ──┐
Split 2 (Config) ──────┘                                             │
                                                                     ├──► Split 7 (Integration)
Split 5 (Round 1 Prompts) ──► Split 6 (Consolidation Prompts) ──────┘
```

**Parallel Tracks:**
- Track A: Splits 1 → 2 → 3 → 4 (code changes)
- Track B: Splits 5 → 6 (prompt files)
- Merge: Split 7 (integration)

---

## Estimated Effort

| Split | Lines (Test) | Lines (Impl) | Time Est. |
|-------|-------------|--------------|-----------|
| 1 | ~150 | ~80 | 30 min |
| 2 | ~20 | ~15 | 15 min |
| 3 | ~50 | ~30 | 20 min |
| 4 | ~30 | ~15 | 15 min |
| 5 | ~15 | ~3 files | 30 min |
| 6 | ~15 | ~3 files | 20 min |
| 7 | - | - | 30 min |
| **Total** | ~280 | ~140 + 6 files | ~2.5 hrs |

---

## Notes

- Each split should be committed separately for clean git history
- Tests are written FIRST in each split (TDD)
- Prompts (Splits 5-6) can be drafted and iterated without code changes
- Integration testing (Split 7) may reveal prompt tuning needs
