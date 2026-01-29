# Control-Centric Implementation: Work Splits

This document breaks the implementation plan into sequential, isolated units of work.
Each split can be implemented and verified independently before moving to the next.

---

## Splitting Principles

1. **Isolation**: Each split has clear boundaries and minimal dependencies
2. **Testability**: Each split can be verified with unit tests before proceeding
3. **Sequential**: Later splits build on earlier ones
4. **Single Responsibility**: Each split does one thing well

---

## Overview: 6 Work Splits

```
Split 1: Test Infrastructure + Clustering
    ↓
Split 2: Batching & Budget (Pure Functions)
    ↓
Split 3: Retrieval Anchors + XML (Pure Functions)
    ↓
Split 4: Prompts (Static Files)
    ↓
Split 5: Decider Core (Orchestration + LLM)
    ↓
Split 6: CLI Integration + E2E Testing
```

---

## Split 1: Test Infrastructure + Control Clustering

**Goal**: Set up test infrastructure and implement control clustering module.

**Dependencies**: None (standalone)

**Files to Create**:
```
tests/scripts/experiments/control_detection/
├── __init__.py
├── conftest.py                    # Shared fixtures
└── test_control_clustering.py     # Clustering tests

ai_services/scripts/experiments/control_detection/
└── control_clustering.py          # Clustering implementation
```

**Deliverables**:
1. Test fixtures: `sample_controls`, `sample_cluster_map`, `mock_embeddings`
2. `ControlClusterCache` class with:
   - `compute()` - K-means on mean-pooled embeddings
   - `save()` / `load()` - JSON serialization
   - `is_valid_for_hash()` - Cache invalidation
   - `get_cluster_id()` - Lookup
3. Helper functions: `mean_pool_embedding()`, `compute_clusters()`

**Verification**:
```bash
uv run pytest tests/scripts/experiments/control_detection/test_control_clustering.py -v
```

**Success Criteria**:
- [ ] All 8 clustering tests pass
- [ ] Cache file written to `files/control_clusters.json`
- [ ] Deterministic: same seed → same clusters

---

## Split 2: Batching & Budget (Pure Functions)

**Goal**: Implement batching algorithms and budget enforcement as pure functions.

**Dependencies**: Split 1 (for `sample_cluster_map` fixture)

**Files to Create/Modify**:
```
tests/scripts/experiments/control_detection/
└── test_batching.py               # Batching tests

ai_services/scripts/experiments/control_detection/
└── batching.py                    # NEW: Pure batching functions
```

**Note**: We create `batching.py` as a separate module to keep functions pure and testable.
Later, `control_centric_decider.py` will import from this module.

**Deliverables**:
1. `BatchingStrategy` enum (COHERENT, DIVERSE)
2. `ControlBatch` dataclass
3. `create_batches()` function:
   - COHERENT: Group by cluster
   - DIVERSE: Spread across clusters
   - Respects `max_calls` limit
4. `apply_budget()` function:
   - Truncates to `max_controls`
   - Maintains cluster diversity

**Verification**:
```bash
uv run pytest tests/scripts/experiments/control_detection/test_batching.py -v
```

**Success Criteria**:
- [ ] All 7 batching tests pass (3 coherent, 2 diverse, 4 budget)
- [ ] Every candidate assigned exactly once
- [ ] `n_batches <= max_calls`

---

## Split 3: Retrieval Anchors + XML Formatting (Pure Functions)

**Goal**: Implement retrieval anchor computation and XML formatting.

**Dependencies**: Split 1 (for `sample_document_prediction` fixture)

**Files to Create/Modify**:
```
tests/scripts/experiments/control_detection/
└── test_retrieval_anchors.py      # Anchor tests

ai_services/scripts/experiments/control_detection/
└── retrieval_anchors.py           # NEW: Pure anchor functions
```

**Deliverables**:
1. `RetrievalAnchors` dataclass (top_pages, best_score, page_scores)
2. `compute_retrieval_anchors()` function:
   - Finds top 3 pages per control
   - Sorted by score descending
3. `format_control_xml()` function:
   - Formats control with retrieval hints
   - Properly escapes XML special characters

**Verification**:
```bash
uv run pytest tests/scripts/experiments/control_detection/test_retrieval_anchors.py -v
```

**Success Criteria**:
- [ ] All 6 retrieval anchor tests pass
- [ ] XML is valid and properly escaped
- [ ] Handles missing controls gracefully

---

## Split 4: Control-Centric Prompts (Static Files)

**Goal**: Create prompt files for control-centric mode.

**Dependencies**: None (standalone)

**Files to Create**:
```
ai_services/scripts/experiments/control_detection/prompts/control_centric/
├── system                         # System prompt with binding language definition
├── user                           # User prompt template with {controls_xml}
└── response.json                  # JSON schema for batch results
```

**Deliverables**:
1. **System prompt** with:
   - Binary decision instructions
   - Binding language definition (broadened + constrained)
   - Evidence quote requirement
2. **User prompt** with:
   - `{controls_xml}` placeholder
   - Retrieval hints instructions
3. **Response schema** for:
   - `batch_results[]` with control_id, addresses_control, evidence_quote, etc.

**Verification**:
- Manual review of prompts
- Validate JSON schema is valid

**Success Criteria**:
- [ ] System prompt includes binding language definition
- [ ] User prompt has {controls_xml} placeholder
- [ ] Response schema matches expected structure

---

## Split 5: Control-Centric Decider (Core Orchestration)

**Goal**: Implement the main decider class with LLM integration.

**Dependencies**: Splits 1, 2, 3, 4

**Files to Create/Modify**:
```
tests/scripts/experiments/control_detection/
└── test_control_centric_decider.py  # Integration tests

ai_services/scripts/experiments/control_detection/
├── control_centric_decider.py       # Main decider class
└── experiment_config.py             # Add new constants
```

**Deliverables**:
1. **Dataclasses**:
   - `ControlCentricConfig`
   - `BatchDecision`
   - `DocumentControlCentricDecision`
2. **ControlCentricDecider class**:
   - `decide_document()` - Main entry point
   - `_filter_candidates()` - Threshold + budget
   - `_process_batch()` - Single LLM call
   - `_aggregate_results()` - Combine batches
3. **LLM Integration**:
   - Gemini cache management (upload, delete)
   - Retry logic with tenacity
   - Semaphore-based concurrency
4. **Config constants**:
   - `MAX_CALLS_PER_DOCUMENT = 50`
   - `TARGET_BATCH_SIZE = 8`
   - `CONTROL_CLUSTER_FILE`

**Verification**:
```bash
uv run pytest tests/scripts/experiments/control_detection/test_control_centric_decider.py -v
```

**Success Criteria**:
- [ ] All 6 decider tests pass (with mocked LLM)
- [ ] Cache deleted on success and error
- [ ] Respects max_calls limit
- [ ] Results properly aggregated

---

## Split 6: CLI Integration + End-to-End Testing

**Goal**: Integrate with run_experiment.py and validate end-to-end.

**Dependencies**: Split 5

**Files to Modify**:
```
ai_services/scripts/experiments/control_detection/
└── run_experiment.py              # Add --mode, --batch-strategy, --max-calls

tests/scripts/experiments/control_detection/
└── test_run_experiment_integration.py  # CLI tests
```

**Deliverables**:
1. **CLI Arguments**:
   - `--mode`: `page_centric` (default) | `control_centric`
   - `--batch-strategy`: `coherent` (default) | `diverse`
   - `--max-calls`: Max LLM calls per document (default: 50)
2. **Mode Routing**:
   - Branch to `ControlCentricDecider` when mode is control_centric
   - Pass config through correctly
3. **End-to-End Validation**:
   - Single document smoke test
   - Compare metrics with page-centric baseline

**Verification**:
```bash
# Unit tests
uv run pytest tests/scripts/experiments/control_detection/test_run_experiment_integration.py -v

# E2E smoke test
python -m ai_services.scripts.experiments.control_detection.run_experiment \
    --mode control_centric \
    --row 0 \
    --experiment template_policies
```

**Success Criteria**:
- [ ] CLI args parse correctly
- [ ] Mode routing works
- [ ] Single document completes without error
- [ ] Output includes evidence quotes
- [ ] Cache cleaned up

---

## Implementation Order Summary

| Split | Name | Est. Time | Key Output |
|-------|------|-----------|------------|
| 1 | Test Infrastructure + Clustering | 2 hours | `control_clustering.py`, `conftest.py` |
| 2 | Batching & Budget | 1.5 hours | `batching.py` |
| 3 | Retrieval Anchors + XML | 1 hour | `retrieval_anchors.py` |
| 4 | Prompts | 30 min | `prompts/control_centric/` |
| 5 | Decider Core | 3.5 hours | `control_centric_decider.py` |
| 6 | CLI Integration + E2E | 2 hours | Modified `run_experiment.py` |
| **Total** | | **~10.5 hours** | |

---

## Checkpoint Verification

After each split, verify:

1. **All tests pass**: `uv run pytest tests/scripts/experiments/control_detection/ -v`
2. **No regressions**: Existing tests still pass
3. **Type checking**: `uv run mypy ai_services/scripts/experiments/control_detection/`
4. **Linting**: `uv run ruff check ai_services/scripts/experiments/control_detection/`

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Clustering takes too long | Use cached embeddings from predictor.py |
| LLM rate limits | Retry logic with jitter + semaphore |
| Cache not deleted | asyncio.shield() + signal handlers |
| XML escaping bugs | Use xml.etree for proper escaping |
| Test flakiness | Mock all external calls |

---

## Next Steps

After completing all splits:

1. Run full experiment on template_policies dataset
2. Compare P/R/F1 with page-centric baseline
3. Analyze evidence quotes for quality
4. Iterate on prompts if needed
