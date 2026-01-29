# Implementation Splits: Map-Reduce Reason Aggregator

This document breaks the main plan into sequential, isolated units of work. Each split is independently testable and builds on previous splits.

## Split Overview

| Split | Name | Dependencies | LLM Required | Files Created |
|-------|------|--------------|--------------|---------------|
| 1 | Foundation | None | No | config.py, models.py |
| 2 | Input Pipeline | Split 1 | No | input_loader.py |
| 3 | Output Pipeline | Split 1 | No | output_writer.py |
| 4 | Prompts | None | No | prompts/* |
| 5 | Single-Pair Aggregation | Splits 1-4 | Yes (mocked) | aggregator.py (partial) |
| 6 | Multi-Round Orchestration | Split 5 | Yes (mocked) | aggregator.py (complete) |
| 7 | CLI & Resume | Splits 1-6 | Yes | run.py |

---

## Split 1: Foundation (Pure Python, No I/O)

**Goal:** Create the core data structures and utility functions that everything else depends on.

**Files to Create:**
- `reason_aggregator/__init__.py`
- `reason_aggregator/config.py`
- `reason_aggregator/models.py` (extracted from aggregator.py in plan)

**Components:**
1. `AggregatorConfig` dataclass
2. `AggregatedPattern` dataclass
3. `RoundOutput` dataclass
4. `create_binary_pairs()` function

**Test File:** `tests/.../reason_aggregator/test_foundation.py`

**Verification Criteria:**
- [ ] Config defaults are correct (max_parallel_pairs=3, max_rounds=10, etc.)
- [ ] Config paths exist and are valid
- [ ] Dataclasses can be instantiated with all required fields
- [ ] `create_binary_pairs([A,B,C,D,E,F])` returns `[(A,B), (C,D), (E,F)]`
- [ ] `create_binary_pairs([A,B,C,D,E])` returns `[(A,B), (C,D), (E,None)]`
- [ ] Convergence test: 37 items converge to 1 in exactly 6 rounds

**No External Dependencies:** This split uses only Python stdlib.

---

## Split 2: Input Pipeline (File I/O, No LLM)

**Goal:** Load policy data from JSON files.

**Files to Create:**
- `reason_aggregator/input_loader.py`

**Components:**
1. `PolicyReasons` dataclass
2. `ReasonFileLoader` class
   - `load_all(shuffle, seed)`
   - `load_policy(policy_name)`

**Test File:** `tests/.../reason_aggregator/test_input_loader.py`

**Verification Criteria:**
- [ ] `load_all()` returns exactly 37 PolicyReasons objects
- [ ] Each PolicyReasons has non-empty `generalized_reasons`
- [ ] Shuffle with same seed produces identical order
- [ ] Shuffle with different seeds produces different order
- [ ] Handles missing `responses/` directory gracefully (skip)
- [ ] Handles `is_mapped: false` files gracefully (empty reasons list)

**Dependencies:** Split 1 (for config paths)

---

## Split 3: Output Pipeline (File I/O, No LLM)

**Goal:** Write aggregation results to disk with atomic writes.

**Files to Create:**
- `reason_aggregator/output_writer.py`

**Components:**
1. `AggregatorOutputWriter` class
   - `write_round_output(output: RoundOutput)`
   - `write_final_output(output: RoundOutput)`
   - `_atomic_write(path, content)`
   - `_format_as_markdown(output)`
2. Add `to_dict()` method to `RoundOutput` and `AggregatedPattern`

**Test File:** `tests/.../reason_aggregator/test_output_writer.py`

**Verification Criteria:**
- [ ] Round output writes to `round_{N}/{pair_id}.json`
- [ ] Final output writes both `.json` and `.md` files
- [ ] Atomic writes leave no `.tmp` files on success
- [ ] Atomic writes clean up `.tmp` on failure
- [ ] Markdown format matches expected structure
- [ ] JSON is valid and parseable

**Dependencies:** Split 1 (for dataclasses)

---

## Split 4: Prompts (Static Files)

**Goal:** Create the LLM prompts for aggregation.

**Files to Create:**
- `reason_aggregator/prompts/aggregate_reasons/system`
- `reason_aggregator/prompts/aggregate_reasons/user`
- `reason_aggregator/prompts/aggregate_reasons/response.json`

**Components:**
1. System prompt with safety rules
2. User prompt with Union+Consolidate logic and enum values
3. JSON schema for structured output

**Verification Criteria:**
- [ ] All three files exist
- [ ] `response.json` is valid JSON
- [ ] `response.json` schema validates with jsonschema library
- [ ] Enum values in user prompt match enum values in response.json
- [ ] Safety rules present in system prompt

**Dependencies:** None (static files)

---

## Split 5: Single-Pair Aggregation (LLM Integration)

**Goal:** Implement the core LLM call for aggregating two inputs.

**Files to Create/Modify:**
- `reason_aggregator/aggregator.py` (partial - single pair only)

**Components:**
1. `ReasonAggregator` class (constructor only)
2. `aggregate_pair(left, right, round_num)` method
3. `_get_pair_id()` helper
4. `_passthrough_solo()` helper
5. `AggregationError` exception
6. Reuse `PromptBundle` from `control_mapping_reasons`

**Test File:** `tests/.../reason_aggregator/test_aggregator.py`

**Verification Criteria:**
- [ ] Mock test: `aggregate_pair()` calls Gemini client with correct prompts
- [ ] Mock test: Returns `RoundOutput` with patterns
- [ ] Mock test: `pair_id` is stable (`Policy_A__Policy_B` format)
- [ ] Mock test: Failure raises `AggregationError`, not silent drop
- [ ] Mock test: `_passthrough_solo()` wraps input as RoundOutput
- [ ] Integration test (optional, skipped in CI): Single real Gemini call works

**Dependencies:** Splits 1-4

---

## Split 6: Multi-Round Orchestration

**Goal:** Implement parallel execution and multi-round convergence loop.

**Files to Modify:**
- `reason_aggregator/aggregator.py` (complete)

**Components:**
1. `_run_round(items, round_num)` method
   - Semaphore for parallelism
   - asyncio.gather without return_exceptions
2. `run_full_aggregation()` method
   - Load inputs with shuffle
   - Loop until convergence or max_rounds
   - Write outputs after each round

**Test File:** `tests/.../reason_aggregator/test_orchestration.py`

**Verification Criteria:**
- [ ] Mock test: 37 inputs converge to 1 output in 6 rounds
- [ ] Mock test: Semaphore limits concurrent calls to `max_parallel_pairs`
- [ ] Mock test: Single failure in round causes entire round to fail
- [ ] Mock test: Solo items pass through without LLM call
- [ ] Mock test: Output writer called after each round

**Dependencies:** Split 5

---

## Split 7: CLI & Resume

**Goal:** Create command-line interface and resume support.

**Files to Create:**
- `reason_aggregator/run.py`

**Components:**
1. Typer CLI app
2. `--all` flag for full aggregation
3. `--round N` flag for single round
4. `-n` flag for parallelism
5. `--max-rounds` flag
6. `--resume` flag
7. Resume logic: check existing files, skip completed pairs

**Test File:** `tests/.../reason_aggregator/test_cli.py`

**Verification Criteria:**
- [ ] `--help` shows all options
- [ ] `--all` triggers `run_full_aggregation()`
- [ ] `--round 1` runs only round 1
- [ ] `-n 2` sets `max_parallel_pairs=2`
- [ ] `--resume` skips pairs with existing output files
- [ ] Exit code 0 on success, non-zero on failure

**Integration Test (manual):**
```bash
uv run python -m ai_services.scripts.experiments.control_detection.reason_aggregator.run --round 1 -n 1
```

**Dependencies:** Splits 1-6

---

## Implementation Order & Checkpoints

```
Split 1 ──┬── Split 2 ──┐
          │             │
          └── Split 3 ──┼── Split 5 ── Split 6 ── Split 7
                        │
Split 4 ────────────────┘
```

### Checkpoint 1: After Splits 1-3
- All data structures defined
- Can load 37 policies
- Can write outputs to disk
- **No LLM calls yet**
- Run: `uv run pytest tests/.../reason_aggregator/ -k "not aggregator and not cli"`

### Checkpoint 2: After Split 4
- Prompts created and validated
- Ready for LLM integration
- Run: Manual review of prompt files

### Checkpoint 3: After Split 5
- Single LLM call works
- Can aggregate one pair
- Run: `uv run pytest tests/.../reason_aggregator/test_aggregator.py`

### Checkpoint 4: After Split 6
- Full aggregation works (mocked)
- Convergence verified
- Run: `uv run pytest tests/.../reason_aggregator/test_orchestration.py`

### Checkpoint 5: After Split 7 (Complete)
- CLI works
- Resume works
- Full integration test possible
- Run: `uv run python -m ai_services.scripts.experiments.control_detection.reason_aggregator.run --all -n 1`

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM output doesn't match schema | Split 5 includes schema validation + retry logic |
| Rate limiting from Gemini | Low default parallelism (3), can reduce with `-n 1` |
| Resume state corruption | Atomic writes (Split 3) + stable pair IDs (Split 5) |
| Context window overflow | Union logic may produce large outputs - add max_patterns limit if needed |

---

## Estimated Effort

| Split | Estimated Effort | Notes |
|-------|------------------|-------|
| 1 | Small | Mostly dataclass definitions |
| 2 | Small | File I/O, straightforward |
| 3 | Small | File I/O + markdown formatting |
| 4 | Small | Static files, copy from plan |
| 5 | Medium | LLM integration, error handling |
| 6 | Medium | Async orchestration, parallelism |
| 7 | Small | CLI wiring, resume logic |

**Total: 7 splits, ~3-4 hours of implementation**
