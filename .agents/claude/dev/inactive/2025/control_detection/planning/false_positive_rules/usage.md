# FP Rule Aggregator: Usage Guide

## Quick Reference

```bash
# Full run (~47 LLM calls, ~15-20 minutes)
uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006

# Pilot mode (~14 LLM calls, ~5 minutes) - recommended for first run
uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006 \
    --pilot

# Skip Phase 3 synthesis (stops after consolidation)
uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006 \
    --skip-synthesis

# Custom parallelism (increase for faster runs, decrease to avoid rate limits)
uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006 \
    --parallelism 10

# Custom output timestamp (for reproducible output paths)
uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006 \
    --output-timestamp 20251230_120000
```

---

## CLI Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--fp-validation-timestamp` | Yes | - | Timestamp of FP validation run (e.g., `20251229_221006`) |
| `--output-timestamp` | No | Current time | Output directory timestamp |
| `--pilot` | No | False | Process only 1 batch per root cause |
| `--skip-synthesis` | No | False | Skip Phase 3 cross-root-cause synthesis |
| `-n, --parallelism` | No | 5 | Max concurrent LLM calls |

---

## Example Logs

### 1. Full Run (All Phases)

```
$ uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006

2025-12-30 10:00:00 - fp_rule_aggregator.run - INFO - Starting FP Rule Aggregation
    fp_validation_dir: files/llm_outputs/fp_validation/20251229_221006
    output_dir: files/llm_outputs/fp_rule_aggregator/20251230_100000
    pilot_mode: False
    skip_synthesis: False

2025-12-30 10:00:01 - fp_rule_aggregator.run - INFO - Loaded FP judge outputs
    root_cause_count: 14
    total_fps: 1868

2025-12-30 10:00:01 - fp_rule_aggregator.aggregator - INFO - Starting full aggregation
    root_cause_count: 14
    total_fps: 1868

# Phase 1: Batch Summarization (parallel)
2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch SEMANTIC_STRETCH_batch_00
    batch_id: SEMANTIC_STRETCH_batch_00
    root_cause: SEMANTIC_STRETCH
    fp_count: 60

2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch SEMANTIC_STRETCH_batch_01
    batch_id: SEMANTIC_STRETCH_batch_01
    root_cause: SEMANTIC_STRETCH
    fp_count: 60

2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch KEYWORD_TRIGGER_batch_00
    batch_id: KEYWORD_TRIGGER_batch_00
    root_cause: KEYWORD_TRIGGER
    fp_count: 60

2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch RELATED_BUT_DIFFERENT_batch_00
    batch_id: RELATED_BUT_DIFFERENT_batch_00
    root_cause: RELATED_BUT_DIFFERENT
    fp_count: 60

2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch PARTIAL_OVERLAP_batch_00
    batch_id: PARTIAL_OVERLAP_batch_00
    root_cause: PARTIAL_OVERLAP
    fp_count: 60

# ... (batches continue, 5 at a time due to semaphore)

2025-12-30 10:00:45 - fp_rule_aggregator.aggregator - INFO - Completed batch SEMANTIC_STRETCH_batch_00
    batch_id: SEMANTIC_STRETCH_batch_00
    rule_count: 4

2025-12-30 10:00:47 - fp_rule_aggregator.aggregator - INFO - Completed batch KEYWORD_TRIGGER_batch_00
    batch_id: KEYWORD_TRIGGER_batch_00
    rule_count: 3

# ... (completions continue)

2025-12-30 10:08:30 - fp_rule_aggregator.aggregator - INFO - Phase 1 complete
    batch_count: 40
    total_rules: 142

# Phase 2: Per-Root-Cause Consolidation
2025-12-30 10:08:31 - fp_rule_aggregator.aggregator - INFO - Consolidating SEMANTIC_STRETCH
    root_cause: SEMANTIC_STRETCH
    batch_count: 8

2025-12-30 10:08:31 - fp_rule_aggregator.aggregator - INFO - Consolidating KEYWORD_TRIGGER
    root_cause: KEYWORD_TRIGGER
    batch_count: 5

# ... (consolidation continues for multi-batch root causes)

2025-12-30 10:09:45 - fp_rule_aggregator.aggregator - INFO - Consolidated SEMANTIC_STRETCH
    root_cause: SEMANTIC_STRETCH
    universal_count: 6
    rare_count: 4

2025-12-30 10:09:52 - fp_rule_aggregator.aggregator - INFO - Consolidated KEYWORD_TRIGGER
    root_cause: KEYWORD_TRIGGER
    universal_count: 4
    rare_count: 2

2025-12-30 10:10:30 - fp_rule_aggregator.aggregator - INFO - Phase 2 complete
    root_cause_count: 14

# Phase 3: Cross-Root-Cause Synthesis
2025-12-30 10:10:31 - fp_rule_aggregator.aggregator - INFO - Starting Phase 3 synthesis
    root_cause_count: 14

2025-12-30 10:12:15 - fp_rule_aggregator.aggregator - INFO - Phase 3 complete

2025-12-30 10:12:15 - fp_rule_aggregator.aggregator - INFO - Aggregation complete
    universal_rules: 18
    rare_rules: 32

# Post-processing
2025-12-30 10:12:16 - fp_rule_aggregator.run - WARNING - Lint errors found
    error_count: 3

2025-12-30 10:12:16 - fp_rule_aggregator.run - INFO - Coverage computed
    coverage_pct: 87.4
    covered_fps: 1633
    total_fps: 1868

2025-12-30 10:12:17 - fp_rule_aggregator.run - INFO - Aggregation complete
    universal_rules: 18
    rare_rules: 32
    output_dir: files/llm_outputs/fp_rule_aggregator/20251230_100000
```

**Duration:** ~12 minutes
**LLM Calls:** ~47 (40 batch + 5 consolidate + 2 synthesize)

---

### 2. Pilot Mode (Quick Validation)

```
$ uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006 \
    --pilot

2025-12-30 10:00:00 - fp_rule_aggregator.run - INFO - Starting FP Rule Aggregation
    fp_validation_dir: files/llm_outputs/fp_validation/20251229_221006
    output_dir: files/llm_outputs/fp_rule_aggregator/20251230_100000
    pilot_mode: True
    skip_synthesis: False

2025-12-30 10:00:01 - fp_rule_aggregator.run - INFO - Loaded FP judge outputs
    root_cause_count: 14
    total_fps: 1868

2025-12-30 10:00:01 - fp_rule_aggregator.aggregator - INFO - Starting full aggregation
    root_cause_count: 14
    total_fps: 1868

# Phase 1: Only 1 batch per root cause (14 batches total)
2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch SEMANTIC_STRETCH_batch_00
    batch_id: SEMANTIC_STRETCH_batch_00
    root_cause: SEMANTIC_STRETCH
    fp_count: 60

2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch KEYWORD_TRIGGER_batch_00
    batch_id: KEYWORD_TRIGGER_batch_00
    root_cause: KEYWORD_TRIGGER
    fp_count: 60

2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch RELATED_BUT_DIFFERENT_batch_00
    batch_id: RELATED_BUT_DIFFERENT_batch_00
    root_cause: RELATED_BUT_DIFFERENT
    fp_count: 60

2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch PARTIAL_OVERLAP_batch_00
    batch_id: PARTIAL_OVERLAP_batch_00
    root_cause: PARTIAL_OVERLAP
    fp_count: 60

2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch WRONG_CONTROL_TYPE_batch_00
    batch_id: WRONG_CONTROL_TYPE_batch_00
    root_cause: WRONG_CONTROL_TYPE
    fp_count: 45

# ... (14 batches total, 5 at a time)

2025-12-30 10:02:30 - fp_rule_aggregator.aggregator - INFO - Phase 1 complete
    batch_count: 14
    total_rules: 48

# Phase 2: No consolidation needed (only 1 batch per root cause)
2025-12-30 10:02:30 - fp_rule_aggregator.aggregator - INFO - Phase 2 complete
    root_cause_count: 14

# Phase 3: Synthesis
2025-12-30 10:02:31 - fp_rule_aggregator.aggregator - INFO - Starting Phase 3 synthesis
    root_cause_count: 14

2025-12-30 10:04:00 - fp_rule_aggregator.aggregator - INFO - Phase 3 complete

2025-12-30 10:04:00 - fp_rule_aggregator.aggregator - INFO - Aggregation complete
    universal_rules: 8
    rare_rules: 40

2025-12-30 10:04:01 - fp_rule_aggregator.run - INFO - Coverage computed
    coverage_pct: 32.1
    covered_fps: 600
    total_fps: 1868

2025-12-30 10:04:02 - fp_rule_aggregator.run - INFO - Aggregation complete
    universal_rules: 8
    rare_rules: 40
    output_dir: files/llm_outputs/fp_rule_aggregator/20251230_100000
```

**Duration:** ~4 minutes
**LLM Calls:** ~16 (14 batch + 0 consolidate + 2 synthesize)

**Note:** Pilot mode has lower coverage (~32%) because only 1 batch per root cause is processed. Use for validating prompts before full run.

---

### 3. Skip Synthesis Mode

```
$ uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006 \
    --skip-synthesis

2025-12-30 10:00:00 - fp_rule_aggregator.run - INFO - Starting FP Rule Aggregation
    fp_validation_dir: files/llm_outputs/fp_validation/20251229_221006
    output_dir: files/llm_outputs/fp_rule_aggregator/20251230_100000
    pilot_mode: False
    skip_synthesis: True

# ... Phase 1 and 2 proceed normally ...

2025-12-30 10:10:30 - fp_rule_aggregator.aggregator - INFO - Phase 2 complete
    root_cause_count: 14

2025-12-30 10:10:30 - fp_rule_aggregator.aggregator - INFO - Skipping Phase 3 synthesis

2025-12-30 10:10:30 - fp_rule_aggregator.aggregator - INFO - Aggregation complete
    universal_rules: 24
    rare_rules: 118

2025-12-30 10:10:31 - fp_rule_aggregator.run - INFO - Aggregation complete
    universal_rules: 24
    rare_rules: 118
    output_dir: files/llm_outputs/fp_rule_aggregator/20251230_100000
```

**Duration:** ~10 minutes
**LLM Calls:** ~45 (40 batch + 5 consolidate + 0 synthesize)

**Note:** Skip synthesis results in more rules (no cross-root-cause deduplication) but faster completion. Useful for examining per-root-cause patterns.

---

### 4. High Parallelism Run

```
$ uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006 \
    --parallelism 10

2025-12-30 10:00:00 - fp_rule_aggregator.run - INFO - Starting FP Rule Aggregation
    fp_validation_dir: files/llm_outputs/fp_validation/20251229_221006
    output_dir: files/llm_outputs/fp_rule_aggregator/20251230_100000
    pilot_mode: False
    skip_synthesis: False

# Phase 1: 10 batches processed concurrently
2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch SEMANTIC_STRETCH_batch_00
2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch SEMANTIC_STRETCH_batch_01
2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch SEMANTIC_STRETCH_batch_02
2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch KEYWORD_TRIGGER_batch_00
2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch KEYWORD_TRIGGER_batch_01
2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch RELATED_BUT_DIFFERENT_batch_00
2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch RELATED_BUT_DIFFERENT_batch_01
2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch PARTIAL_OVERLAP_batch_00
2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch PARTIAL_OVERLAP_batch_01
2025-12-30 10:00:02 - fp_rule_aggregator.aggregator - INFO - Processing batch WRONG_CONTROL_TYPE_batch_00

# ... faster completion due to higher parallelism ...
```

**Duration:** ~8 minutes (vs ~12 minutes at parallelism=5)
**Risk:** May hit rate limits with very high parallelism

---

### 5. Error: Missing FP Validation Directory

```
$ uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 99999999_999999

Traceback (most recent call last):
  File "run.py", line 245, in main
    config = build_config(args)
  File "run.py", line 125, in build_config
    raise FileNotFoundError(
FileNotFoundError: FP validation directory not found: files/llm_outputs/fp_validation/99999999_999999
```

---

### 6. Error: LLM Rate Limit (Retryable)

```
2025-12-30 10:05:30 - fp_rule_aggregator.aggregator - WARNING - Rate limit hit, retrying
    batch_id: SEMANTIC_STRETCH_batch_03
    retry_count: 1
    wait_seconds: 30

2025-12-30 10:06:00 - fp_rule_aggregator.aggregator - INFO - Retry successful
    batch_id: SEMANTIC_STRETCH_batch_03
```

---

## Output Files

After a successful run, the output directory contains:

```
files/llm_outputs/fp_rule_aggregator/{timestamp}/
├── failure_avoidance_rules.json    # Final rules (JSON)
├── universal_rules.md              # High-confidence rules (Markdown)
├── rare_rules.md                   # Low-confidence rules (Markdown)
├── run_metadata.json               # Config, stats, git SHA, prompt hashes
├── lint_report.json                # Rule quality issues
├── coverage_report.json            # FP coverage statistics
└── batches/                        # Per-batch outputs (debugging)
    ├── SEMANTIC_STRETCH_batch_00.json
    ├── SEMANTIC_STRETCH_batch_01.json
    ├── KEYWORD_TRIGGER_batch_00.json
    └── ...
```

### Inspecting Outputs

```bash
# View run summary
cat files/llm_outputs/fp_rule_aggregator/*/run_metadata.json | jq .output_stats

# View coverage
cat files/llm_outputs/fp_rule_aggregator/*/coverage_report.json | jq .

# View lint errors
cat files/llm_outputs/fp_rule_aggregator/*/lint_report.json | jq .errors

# Count rules
cat files/llm_outputs/fp_rule_aggregator/*/failure_avoidance_rules.json | jq '.universal_rules | length'
cat files/llm_outputs/fp_rule_aggregator/*/failure_avoidance_rules.json | jq '.rare_rules | length'

# View a specific batch
cat files/llm_outputs/fp_rule_aggregator/*/batches/SEMANTIC_STRETCH_batch_00.json | jq .
```

---

## Common Workflows

### 1. Initial Validation (Recommended First Run)

```bash
# Start with pilot mode to validate prompts
uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006 \
    --pilot \
    --output-timestamp pilot_run

# Review outputs
cat files/llm_outputs/fp_rule_aggregator/pilot_run/lint_report.json | jq .
cat files/llm_outputs/fp_rule_aggregator/pilot_run/universal_rules.md
```

### 2. Full Production Run

```bash
# Full run after validating pilot
uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006 \
    --output-timestamp production_run
```

### 3. Debugging Specific Root Causes

```bash
# Run without synthesis to see per-root-cause rules
uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006 \
    --skip-synthesis \
    --output-timestamp debug_run

# Examine specific root cause batches
ls files/llm_outputs/fp_rule_aggregator/debug_run/batches/SEMANTIC_STRETCH_*.json
```

### 4. Re-running with Modified Prompts

```bash
# After modifying prompts, run pilot to validate
uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006 \
    --pilot \
    --output-timestamp prompt_v2_pilot

# Compare prompt hashes between runs
diff <(cat files/llm_outputs/fp_rule_aggregator/pilot_run/run_metadata.json | jq .reproducibility.prompt_hashes) \
     <(cat files/llm_outputs/fp_rule_aggregator/prompt_v2_pilot/run_metadata.json | jq .reproducibility.prompt_hashes)
```

---

## Troubleshooting

### "Empty response for batch X"

The LLM returned no content. Usually a transient issue.

```bash
# Re-run with lower parallelism
uv run python -m ... --parallelism 3
```

### High Lint Error Count

Review the lint report to identify common issues:

```bash
cat files/llm_outputs/fp_rule_aggregator/*/lint_report.json | jq '.errors | group_by(.error) | map({error: .[0].error, count: length})'
```

Common issues:
- Vague boundary conditions ("unless relevant")
- Missing allow conditions
- Empty supporting_fp_indices

### Low Coverage

Coverage below 80% indicates rules aren't addressing enough FPs.

```bash
# Check which FPs are uncovered
cat files/llm_outputs/fp_rule_aggregator/*/coverage_report.json | jq .
```

Consider:
- Running full mode instead of pilot
- Reviewing prompts to encourage broader rules

### Rate Limiting

If seeing frequent rate limit errors:

```bash
# Reduce parallelism
uv run python -m ... --parallelism 2
```

---

## Performance Reference

| Mode | LLM Calls | Duration | Coverage |
|------|-----------|----------|----------|
| Pilot | ~16 | ~4 min | ~30% |
| Full | ~47 | ~12 min | ~85% |
| Skip Synthesis | ~45 | ~10 min | ~85% |
| High Parallelism (n=10) | ~47 | ~8 min | ~85% |

*Durations are approximate and depend on LLM response times.*
