# LLM Control Detection: Implementation Splits

This document breaks `llm_control_detection.md` into sequential, isolated units of work. Each split is independently testable and delivers a meaningful milestone.

## Overview

```
Split 1: Data Foundation (Cycles 1-3)
    ↓
Split 2: Helper Functions (Cycles 4-6)
    ↓
Split 3: Aggregation Logic (Cycle 7)
    ↓
Split 4: LLM Decider Class (Cycle 8)
    ↓
Split 5: CLI Integration & Prompts (Cycle 9)
```

---

## Split 1: Data Foundation

**Cycles:** 1, 2, 3
**Prerequisites:** None
**Estimated complexity:** Low-Medium

### Purpose

Establish all data structures and utilities needed by subsequent splits. This is the foundation layer with no external dependencies.

### Deliverables

1. **DCFControl domain field** (Cycle 1)
   - Modify `DCFControl` dataclass to add `domain: str | None`
   - Update `load_controls()` to parse "Control Domain" column from CSV
   - Files: `dcf_controls.py` (modify), `test_dcf_controls.py` (create)

2. **Prompt Loader** (Cycle 2)
   - Create `PromptBundle` class for loading prompts from disk
   - Implement `load_response_schema()` with dynamic enum replacement
   - Files: `prompt_loader.py` (create), `test_prompt_loader.py` (create)

3. **Configuration Dataclasses** (Cycle 3)
   - Create all dataclasses in `llm_decider.py`:
     - `NeighborInclusionConfig`
     - `LLMDeciderConfig`
     - `PageLLMInput`
     - `ControlSelection`
     - `PageLLMDecision`
     - `DocumentLLMDecision`
   - Files: `llm_decider.py` (create), `test_llm_decider_config.py` (create)

### Verification

```bash
uv run pytest tests/scripts/experiments/control_detection/test_dcf_controls.py -v
uv run pytest tests/scripts/experiments/control_detection/test_prompt_loader.py -v
uv run pytest tests/scripts/experiments/control_detection/test_llm_decider_config.py -v
```

### Exit Criteria

- [ ] DCFControl has domain field, load_controls parses it
- [ ] PromptBundle.load() works with placeholder substitution
- [ ] All dataclasses are frozen, slotted, kw_only
- [ ] All Split 1 tests pass

---

## Split 2: Helper Functions

**Cycles:** 4, 5, 6
**Prerequisites:** Split 1 (dataclasses)
**Estimated complexity:** Medium

### Purpose

Implement pure functions for determining which pages to include, which controls to consider, and which pages trigger LLM calls. These are stateless helper functions with no I/O.

### Deliverables

1. **Neighbor Inclusion Logic** (Cycle 4)
   - Implement `should_include_neighbor()` function
   - Two-level hierarchy: same control ID (lenient threshold), same domain (full threshold)
   - Files: `llm_decider.py` (add function), `test_neighbor_inclusion.py` (create)

2. **Candidate List Building** (Cycle 5)
   - Implement `build_candidate_list()` function
   - Merges primary + neighbor controls, deduplicates, sorts by score
   - Files: `llm_decider.py` (add function), `test_candidate_building.py` (create)

3. **Page Triggering Logic** (Cycle 6)
   - Implement `get_triggered_pages()` function
   - Dual threshold strategy: trigger vs candidate thresholds
   - Files: `llm_decider.py` (add function), `test_triggered_pages.py` (create)

### Verification

```bash
uv run pytest tests/scripts/experiments/control_detection/test_neighbor_inclusion.py -v
uv run pytest tests/scripts/experiments/control_detection/test_candidate_building.py -v
uv run pytest tests/scripts/experiments/control_detection/test_triggered_pages.py -v
```

### Exit Criteria

- [ ] `should_include_neighbor()` correctly applies two-level threshold hierarchy
- [ ] `build_candidate_list()` deduplicates and sorts by score
- [ ] `get_triggered_pages()` applies dual threshold strategy
- [ ] All Split 2 tests pass

---

## Split 3: Aggregation Logic

**Cycles:** 7
**Prerequisites:** Split 1 (dataclasses only)
**Estimated complexity:** Low

### Purpose

Implement the multi-select aggregation strategy. This is a pure function that takes page decisions and produces a document decision.

### Deliverables

1. **Decision Aggregation** (Cycle 7)
   - Define `CONFIDENCE_WEIGHTS = {"high": 3, "medium": 2, "low": 1}`
   - Implement `aggregate_decisions()` function
   - Union strategy: collect all controls, take max confidence per control
   - Files: `llm_decider.py` (add function), `test_aggregation.py` (create)

### Verification

```bash
uv run pytest tests/scripts/experiments/control_detection/test_aggregation.py -v
```

### Exit Criteria

- [ ] Aggregation produces union of all selected controls
- [ ] Max confidence is taken when same control appears on multiple pages
- [ ] Controls sorted by confidence, then page count
- [ ] Empty input returns empty DocumentLLMDecision
- [ ] All Split 3 tests pass

---

## Split 4: LLM Decider Class

**Cycles:** 8
**Prerequisites:** Splits 1, 2, 3
**Estimated complexity:** High

### Purpose

Implement the `LLMDecider` class that orchestrates the full decision pipeline. This split uses mocked LLM calls to test the orchestration logic.

### Deliverables

1. **LLMDecider Class** (Cycle 8)
   - Factory method `LLMDecider.create()` with Vertex AI authentication
   - `build_page_inputs()` - builds PageLLMInput with neighbor context
   - `decide_page()` - makes single page decision (async, uses google-genai SDK)
   - `decide_document()` - orchestrates all pages with concurrency control
   - Files: `llm_decider.py` (add class), `test_llm_decider.py` (create)

### Key Implementation Notes

- Use `google.genai.Client` for Vertex AI
- Async methods for LLM calls
- `asyncio.Semaphore` for concurrency limiting
- All LLM calls mocked in tests

### Verification

```bash
uv run pytest tests/scripts/experiments/control_detection/test_llm_decider.py -v
```

### Exit Criteria

- [ ] LLMDecider.create() initializes Vertex AI client
- [ ] build_page_inputs() correctly includes neighbor pages
- [ ] decide_page() parses multi-select response correctly
- [ ] decide_document() handles concurrency and aggregation
- [ ] All Split 4 tests pass (with mocked LLM)

---

## Split 5: CLI Integration & Prompts

**Cycles:** 9
**Prerequisites:** Split 4
**Estimated complexity:** Medium

### Purpose

Wire everything together with CLI arguments and create the actual prompt files. This enables end-to-end execution.

### Deliverables

1. **CLI Arguments** (Cycle 9.2)
   - Add LLM-related arguments to `run_experiment.py`:
     - `--use-llm` flag
     - `--gcp-project`, `--gcp-region`
     - `--llm-model`, `--trigger-threshold`, `--candidate-threshold`
     - `--max-candidates`, `--no-neighbor-inclusion`
     - `--neighbor-threshold-ratio`, `--max-pages-per-call`, `--max-concurrent`
   - Files: `run_experiment.py` (modify)

2. **Prompt Files** (Cycle 9.3)
   - Create `prompts/select_control/system` (load distilled mapping instructions)
   - Create `prompts/select_control/user` (page analysis template)
   - Create `prompts/select_control/response.json` (multi-select schema)
   - Files: `prompts/select_control/*` (create)

3. **Integration Tests** (Cycle 9.1)
   - Test CLI argument parsing
   - Test LLM flow when enabled vs disabled
   - Files: `test_llm_decider_integration.py` (create)

### Verification

```bash
# Unit/integration tests
uv run pytest tests/scripts/experiments/control_detection/test_llm_decider_integration.py -v

# Full test suite
uv run pytest tests/scripts/experiments/control_detection/ -v

# Manual test (requires GCP credentials)
uv run --group gcp --group ai python ai_services/scripts/experiments/control_detection/run_experiment.py \
    --use-llm \
    --gcp-project your-project-id \
    --row 4
```

### Exit Criteria

- [ ] CLI arguments parsed correctly
- [ ] Prompt files created and loading correctly
- [ ] Integration tests pass
- [ ] Manual end-to-end test works with real LLM
- [ ] All tests pass

---

## Summary Table

| Split | Cycles | Files Created | Files Modified | Complexity |
|-------|--------|---------------|----------------|------------|
| 1. Data Foundation | 1, 2, 3 | prompt_loader.py, llm_decider.py (partial), 3 test files | dcf_controls.py | Low-Med |
| 2. Helper Functions | 4, 5, 6 | 3 test files | llm_decider.py | Medium |
| 3. Aggregation | 7 | 1 test file | llm_decider.py | Low |
| 4. LLM Decider | 8 | 1 test file | llm_decider.py | High |
| 5. CLI Integration | 9 | prompts/*, 1 test file | run_experiment.py | Medium |

## Dependencies Graph

```
Split 1 (Foundation)
   │
   ├──────────────┬──────────────┐
   │              │              │
   ▼              ▼              │
Split 2       Split 3            │
(Helpers)     (Aggregation)      │
   │              │              │
   └──────────────┴──────────────┘
                  │
                  ▼
              Split 4
           (LLM Decider)
                  │
                  ▼
              Split 5
           (Integration)
```

Note: Splits 2 and 3 can be done in parallel since they both only depend on Split 1's dataclasses.

---

## Task Template

When implementing each split, use this template for each cycle:

### Cycle N: [Name]

**Status:** [ ] Not Started / [ ] In Progress / [ ] Complete

#### Tasks
- [ ] Write failing tests (RED)
- [ ] Implement to pass (GREEN)
- [ ] Refactor if needed
- [ ] Run verification command
- [ ] Commit with message: `feat: [cycle description]`

#### Notes
(Add any implementation notes, blockers, or decisions here)
