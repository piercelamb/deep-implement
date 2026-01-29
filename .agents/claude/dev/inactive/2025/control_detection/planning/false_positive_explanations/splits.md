# Implementation Splits: False Positive Analysis

This document breaks the [plan.md](./plan.md) into sequential, isolated units of work. Each split can be implemented and verified independently before moving to the next.

**Approach: Test-Driven Development (TDD)**

Each split follows the TDD cycle:
1. **RED**: Write failing tests first
2. **GREEN**: Write minimal code to make tests pass
3. **REFACTOR**: Clean up while keeping tests green

---

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Split 1: Foundation (Models + Config + Collector)        ✅     │
│  → Verified: Collected 4,104 FPs from experiment 5 data         │
├─────────────────────────────────────────────────────────────────┤
│  Split 2: Distribution Analysis (Phase 0)                 ✅     │
│  → Verified: IR-3 accounts for 32.8% of FPs                     │
├─────────────────────────────────────────────────────────────────┤
│  Split 3: Pattern Deduplication (Phase 1)                 ✅     │
│  → Verified: 4,104 → 1,878 patterns (2.2x reduction)            │
├─────────────────────────────────────────────────────────────────┤
│  Split 4: Sampling (Phase 2)                              SKIP   │
│  → Not needed: 1,878 patterns at ~$10-20 is affordable          │
├─────────────────────────────────────────────────────────────────┤
│  Split 5: Judge Infrastructure (Prompts + Decider)        ✅     │
│  → Verified: 29 tests, FPJudgeDecider w/ original prompt cache  │
├─────────────────────────────────────────────────────────────────┤
│  Split 6: Output & Integration (Generator + CLI)          ✅     │
│  → Verified: 36 tests, CLI ready for end-to-end run             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Split 1: Foundation

**Goal**: Establish module structure, data models, and FP collection from experiment outputs.

### Files to Create

| File | Purpose |
|------|---------|
| `false_positive_validation/__init__.py` | Module exports |
| `false_positive_validation/fp_models.py` | FalsePositive, FPPattern, FPJudgeResult, enums |
| `false_positive_validation/fp_config.py` | Configuration settings |
| `false_positive_validation/fp_collector.py` | Collect MAPPED controls not in GT |

### Test Files (write FIRST)

| Test File | What to Test |
|-----------|--------------|
| `test_fp_models.py` | Dataclass creation, immutability, enum values |
| `test_fp_collector.py` | Collection logic, multi-batch handling |

### Key Deliverables

1. **Models**:
   - `FalsePositive` dataclass (input)
   - `FPPattern` dataclass (for deduplication)
   - `FPJudgeResult` dataclass (output)
   - `FPVerdict` enum (CONFIRMED_FP, UNCERTAIN)
   - `RootCause` enum (13 categories)

2. **Collector**:
   ```python
   def collect_false_positives(
       experiment_timestamp: str,
       llm_output_dir: Path,
       ground_truth_dir: Path,
   ) -> list[FalsePositive]
   ```

### Verification

```bash
# Run tests
uv run pytest tests/.../test_fp_models.py tests/.../test_fp_collector.py -v

# Manual verification
uv run python -c "
from false_positive_validation.fp_collector import collect_false_positives
fps = collect_false_positives('20251228_172545', ...)
print(f'Collected {len(fps)} false positives')
# Actual result: 4,104 FPs
"
```

### Exit Criteria

- [x] All model tests pass (17 tests)
- [x] All collector tests pass (12 tests)
- [x] Collector outputs 4,104 FPs from experiment 5 data
- [x] Each FalsePositive has all required fields populated

### Dependencies

None (this is the foundation).

---

## Split 2: Distribution Analysis (Phase 0)

**Goal**: Zero-cost analysis to understand FP landscape before any LLM calls.

### Files to Create

| File | Purpose |
|------|---------|
| `false_positive_validation/analyze_fp_distribution.py` | Generate distribution CSVs |

### Test Files (write FIRST)

| Test File | What to Test |
|-----------|--------------|
| `test_analyze_fp_distribution.py` | CSV generation, IR rule extraction |

### Key Deliverables

1. **IR Rule Extraction**:
   ```python
   def extract_primary_ir_rule(reasoning: str) -> str | None
   ```

2. **Distribution Analysis**:
   ```python
   def analyze_distribution(all_fps: list[FalsePositive], output_dir: Path) -> dict
   ```

3. **Output CSVs**:
   - `fps_by_control.csv` - control_id, fp_count, policies_list
   - `fps_by_policy.csv` - policy_name, fp_count, controls_list
   - `fps_by_confidence.csv` - confidence, fp_count
   - `fps_by_ir_rule.csv` - ir_rule_cited, fp_count

### Verification

```bash
# Run tests
uv run pytest tests/.../test_analyze_fp_distribution.py -v

# Manual verification
uv run python -c "
from false_positive_validation.fp_collector import collect_false_positives
from false_positive_validation.analyze_fp_distribution import analyze_distribution
from pathlib import Path

fps = collect_false_positives(...)
stats = analyze_distribution(fps, Path('files/llm_outputs/fp_distribution'))
print(stats)
# Actual result: IR-3 at 32.8%, IR-1 at 16.3%, IR-2 at 15.6%
"
```

### Exit Criteria

- [x] All distribution tests pass (19 tests)
- [x] All 4 CSVs are generated
- [x] Can identify top 20 controls by FP count
- [x] Can identify which IR rules are most cited (IR-3 dominates at 32.8%)
- [x] Stats show Pareto distribution

### Dependencies

- Split 1 (models, collector)

---

## Split 3: Pattern Deduplication (Phase 1)

**Goal**: Reduce 4,104 FP instances to unique patterns using `(control_id, IR_rule)` signature.

> **Key Finding**: Original plan expected 10-17x reduction with `(control_id, IR_rule, evidence_hash)`.
> Testing revealed evidence quotes are unique per policy, so that yields only 1.0x.
> Changed to `(control_id, IR_rule)` which achieves **2.2x reduction** (4,104 → 1,878).
> See [deduplication_analysis.md](./deduplication_analysis.md) for details.

### Files to Create

| File | Purpose |
|------|---------|
| `false_positive_validation/deduplicate_fps.py` | Pattern signature + deduplication |

### Test Files (write FIRST)

| Test File | What to Test |
|-----------|--------------|
| `test_deduplicate_fps.py` | Signature computation, grouping, frequency sorting |

### Key Deliverables

1. **Pattern Signature**:
   ```python
   def compute_pattern_signature(fp: FalsePositive, include_evidence: bool = False) -> str
   def normalize_evidence_hash(evidence: str) -> str
   ```

2. **Deduplication**:
   ```python
   def deduplicate_fps(all_fps: list[FalsePositive], include_evidence: bool = False) -> list[FPPattern]
   ```

### Verification

```bash
# Run tests
uv run pytest tests/.../test_deduplicate_fps.py -v

# Manual verification
uv run python -c "
from false_positive_validation.fp_collector import collect_false_positives
from false_positive_validation.deduplicate_fps import deduplicate_fps

fps = collect_false_positives(...)
patterns = deduplicate_fps(fps)  # Default: (control_id, IR_rule)
print(f'Reduced {len(fps)} FPs to {len(patterns)} patterns')
print(f'Reduction ratio: {len(fps) / len(patterns):.1f}x')
# Actual result: 4,104 → 1,878 patterns (2.2x reduction)
"
```

### Exit Criteria

- [x] All deduplication tests pass (29 tests)
- [x] Reduction ratio is 2.2x (4,104 → 1,878 patterns)
- [x] Each pattern has frequency, policies, and 2-3 representatives
- [x] Patterns sorted by frequency descending
- [x] Same control + IR → single pattern (evidence excluded by default)

### Dependencies

- Split 1 (models)
- Split 2 (IR rule extraction)

---

## Split 4: Sampling (Phase 2) — SKIPPED

**Status**: ⏭️ **SKIPPED** — Not needed given actual pattern count.

**Reason**: With 1,878 patterns at ~$10-20 total cost (Flash-tier models), we recommend analyzing ALL patterns rather than sampling. The marginal cost savings (~$15 vs ~$5) don't justify the potential information loss.

See [sampling_recommendation_v2.md](./sampling_recommendation_v2.md) for a sampling strategy if cost becomes a concern in the future.

### Exit Criteria

- [x] Decision made: Skip sampling, analyze all 1,878 patterns
- [ ] (Future) If sampling needed, implement bucket strategy from sampling_recommendation_v2.md

### Dependencies

- Split 1 (models)
- Split 3 (deduplication)

---

## Split 5: Judge Infrastructure

**Goal**: Create prompts and judge decider to analyze FPs with LLM.

### Files to Create

| File | Purpose |
|------|---------|
| `prompts/fp_judge/system` | FP judge system prompt |
| `prompts/fp_judge/user` | User template with FP details |
| `prompts/fp_judge/response.json` | Structured output schema |
| `false_positive_validation/fp_judge_decider.py` | Judge with context caching |

### Test Files (write FIRST)

| Test File | What to Test |
|-----------|--------------|
| `test_fp_judge_decider.py` | Prompt rendering, response parsing, cache setup |

### Key Deliverables

1. **Prompts**:
   - System: Role as Security Compliance Auditor, reference IR rules
   - User: Control details + original LLM evaluation
   - Response: verdict, confidence, misapplied_rules, root_cause, etc.

2. **Judge Decider** (key difference from gt_validation):
   ```python
   class FPJudgeDecider:
       async def _upload_document_cache(
           self,
           pdf_bytes: bytes,
           policy_name: str,
           original_mapping_prompt: str,  # Include original prompt!
       ) -> str

       async def judge_false_positive(
           self,
           fp: FalsePositive,
           cache_name: str,
       ) -> FPJudgeResult
   ```

### Verification

```bash
# Run tests (mocked LLM)
uv run pytest tests/.../test_fp_judge_decider.py -v

# Manual verification (real LLM, ~5-10 patterns)
uv run python -c "
from false_positive_validation.fp_judge_decider import FPJudgeDecider

decider = FPJudgeDecider(...)
# Pick diverse test cases from different root cause categories
for fp in test_fps[:5]:
    result = await decider.judge_false_positive(fp, cache_name)
    print(f'{fp.control_id}: {result.verdict} - {result.root_cause}')
    print(f'  Misapplied rules: {result.misapplied_rules}')
"
```

### Exit Criteria

- [x] All judge tests pass (29 tests)
- [x] Prompts render correctly with FP data
- [x] Judge returns valid FPJudgeResult objects
- [x] root_cause is from controlled vocabulary (RootCause enum)
- [x] misapplied_rules contains valid IR rule names
- [x] Context cache includes original mapping prompt

### Dependencies

- Split 1 (models)

---

## Split 6: Output & Integration

**Goal**: Complete the pipeline with output generation and CLI orchestration.

### Files to Create

| File | Purpose |
|------|---------|
| `false_positive_validation/fp_output_generator.py` | Generate CSVs, JSONs, summaries |
| `false_positive_validation/run_fp_validation.py` | CLI orchestrator |

### Test Files (write FIRST)

| Test File | What to Test |
|-----------|--------------|
| `test_fp_output_generator.py` | Output file format, aggregation |
| `test_run_fp_validation.py` | CLI args, pipeline orchestration |

### Key Deliverables

1. **Output Generator**:
   ```python
   def generate_outputs(
       results: list[FPJudgeResult],
       patterns: list[FPPattern],
       output_dir: Path,
   ) -> None
   ```

   Outputs:
   - `detailed_results.json` - All results
   - `fp_analysis_summary.json` - Aggregate stats
   - `fp_confirmed.csv` - Confirmed FPs
   - `fp_uncertain.csv` - Needs human review

2. **CLI Orchestrator**:
   ```bash
   uv run python -m ai_services.scripts.experiments.control_detection.false_positive_validation.run_fp_validation \
       --experiment-timestamp 20251228_112332 \
       --original-prompts-dir control_centric_false_negatives \
       --gcp-project ai-team-gemini-dev \
       --sampling-strategy all \
       --seed 42
   ```

### Verification

```bash
# Run tests
uv run pytest tests/.../test_fp_output_generator.py tests/.../test_run_fp_validation.py -v

# End-to-end test on small sample
uv run python -m ... --max-patterns 10

# Check outputs
ls files/llm_outputs/fp_validation/{timestamp}/
# Should see:
#   detailed_results.json
#   fp_analysis_summary.json
#   fp_confirmed.csv
#   fp_uncertain.csv
#   run_metadata.json
```

### Exit Criteria

- [x] All output generator tests pass (18 tests)
- [x] All CLI tests pass (18 tests)
- [ ] End-to-end run completes successfully (requires LLM costs)
- [x] Summary stats aggregate correctly by root_cause
- [x] Summary stats aggregate correctly by misapplied_rule
- [x] run_metadata.json captures CLI args and timing

### Dependencies

- Split 1 (models)
- Split 3 (deduplication)
- Split 5 (judge)

---

## Dependency Graph

```
Split 1 (Foundation)              ✅ COMPLETE
    │
    ├──► Split 2 (Distribution)   ✅ COMPLETE (IR-3 at 32.8%)
    │
    ├──► Split 3 (Deduplication)  ✅ COMPLETE (2.2x reduction)
    │        │
    │        └──► Split 4 (Sampling) ⏭️ SKIPPED (1,878 patterns affordable)
    │
    └──► Split 5 (Judge)          ✅ COMPLETE (29 tests)
              │
              └──► Split 6 (Output & Integration)  ✅ COMPLETE (36 tests)
```

---

## Recommended Execution Order

| Order | Split | Status | Notes |
|-------|-------|--------|-------|
| 1 | Split 1: Foundation | ✅ Done | 29 tests, 4,104 FPs collected |
| 2 | Split 2: Distribution | ✅ Done | 19 tests, IR-3 at 32.8% |
| 3 | Split 3: Deduplication | ✅ Done | 29 tests, 2.2x reduction |
| 4 | Split 4: Sampling | ⏭️ Skipped | Not needed (1,878 patterns affordable) |
| 5 | Split 5: Judge | ✅ Done | 29 tests, FPJudgeDecider w/ original prompt cache |
| 6 | Split 6: Integration | ✅ Done | 36 tests, Output generator + CLI orchestrator |

---

## Estimated Effort

| Split | Complexity | Est. Effort | LLM Cost | Status |
|-------|------------|-------------|----------|--------|
| 1: Foundation | Medium | 3-4 hours | $0 | ✅ Done |
| 2: Distribution | Low | 1-2 hours | $0 | ✅ Done |
| 3: Deduplication | Medium | 2-3 hours | $0 | ✅ Done |
| 4: Sampling | Medium | 2-3 hours | $0 | ⏭️ Skipped |
| 5: Judge | High | 4-6 hours | ~$5-10 (test calls) | ✅ Done |
| 6: Integration | Medium | 3-4 hours | ~$10-20 (1,878 patterns) | ✅ Done |

**Pipeline Complete**: Ready to run end-to-end (~$10-20 LLM cost for 1,878 patterns)

---

## Quick Reference: Test Commands

```bash
# Split 1 ✅
uv run pytest tests/.../test_fp_models.py tests/.../test_fp_collector.py -v

# Split 2 ✅
uv run pytest tests/.../test_analyze_fp_distribution.py -v

# Split 3 ✅
uv run pytest tests/.../test_deduplicate_fps.py -v

# Split 4 ⏭️ SKIPPED (no tests needed)

# Split 5 ✅
uv run pytest tests/.../test_fp_judge_decider.py -v

# Split 6 ✅
uv run pytest tests/.../test_fp_output_generator.py tests/.../test_run_fp_validation.py -v

# All tests (142 passing)
uv run pytest tests/scripts/experiments/control_detection/false_positive_validation/ -v --cov

# Run the full pipeline (requires GCP project with Vertex AI access)
uv run python -m ai_services.scripts.experiments.control_detection.false_positive_validation.run_fp_validation \
    --experiment-timestamp 20251228_172545 \
    --gcp-project <YOUR_GCP_PROJECT> \
    --max-patterns 10  # Start small for testing
```
