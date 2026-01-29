# Tiered Batching: Implementation Splits

This document breaks `plan.md` into sequential, isolated units of work. Each split can be implemented and verified independently before moving to the next.

---

## Split Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         IMPLEMENTATION SPLITS                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Split 1: Data Structures                                               │
│  ├── UniqueControl dataclass                                            │
│  └── ControlBatch dataclass                                             │
│                          │                                              │
│                          ▼                                              │
│  Split 2: Page Grouping (Algorithm Step 1)                              │
│  └── group_by_max_page()                                                │
│                          │                                              │
│                          ▼                                              │
│  Split 3: Oversized Splitting (Algorithm Step 2)                        │
│  └── split_oversized_groups()                                           │
│                          │                                              │
│                          ▼                                              │
│  Split 4: Batch Consolidation (Algorithm Step 3)                        │
│  ├── merge_priority()                                                   │
│  ├── find_best_mergeable_pair()                                         │
│  └── consolidate_batches()                                              │
│                          │                                              │
│                          ▼                                              │
│  Split 5: Truncation (Algorithm Steps 0 + Phase B)                      │
│  ├── truncate_candidates() (primary)                                    │
│  └── truncate_batches() (secondary)                                     │
│                          │                                              │
│                          ▼                                              │
│  Split 6: Main Function + Integration                                   │
│  ├── create_page_aware_batches()                                        │
│  └── Update control_centric_decider.py                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Split 1: Data Structures

**Goal**: Define the foundational data structures used throughout the batching pipeline.

**Scope**:
- `UniqueControl` dataclass (frozen, slots, kw_only)
- `ControlBatch` dataclass with `primary_page`, `can_merge_with()`, `__len__()`

**Dependencies**: None (foundational)

**Input/Output**:
- N/A (data containers)

**Key Behaviors to Test**:
1. `UniqueControl.to_retrieval_anchors()` converts correctly
2. `UniqueControl.top_pages` limited to 3 entries
3. `ControlBatch.primary_page` returns most common page
4. `ControlBatch.primary_page` breaks ties with lowest page number
5. `ControlBatch.can_merge_with()` validates combined size
6. `ControlBatch.__len__()` returns control count

**Verification**: All data structure tests pass.

---

## Split 2: Page Grouping (Algorithm Step 1)

**Goal**: Group controls by the page where they scored highest.

**Scope**:
- `group_by_max_page(candidates: list[UniqueControl]) -> dict[int, list[UniqueControl]]`

**Dependencies**: Split 1 (UniqueControl)

**Input**: List of `UniqueControl` (already deduped)

**Output**: Dict mapping page number → list of controls with that max_page

**Key Behaviors to Test**:
1. Controls with same `max_page` grouped together
2. Controls with different `max_page` in separate groups
3. Empty input returns empty dict
4. Single control returns single group

**Verification**: Page grouping tests pass.

---

## Split 3: Oversized Splitting (Algorithm Step 2)

**Goal**: Split page groups that exceed `MAX_BATCH_SIZE` using cluster assignments.

**Scope**:
- `split_oversized_groups(page_groups: dict[int, list[UniqueControl]], cluster_map: dict[str, int], max_batch_size: int) -> list[ControlBatch]`

**Dependencies**: Split 1 (UniqueControl, ControlBatch), Split 2 (page groups)

**Input**: Page groups from Split 2, cluster_map (pre-existing)

**Output**: List of `ControlBatch`, each ≤ `MAX_BATCH_SIZE`

**Algorithm**:
```
For each page_group:
  if len(group) <= MAX_BATCH_SIZE:
    batches.append(ControlBatch(group))
  else:
    cluster_groups = group_by(group, key=cluster_map[ctrl.control_id])
    for cluster_group in cluster_groups:
      if len(cluster_group) <= MAX_BATCH_SIZE:
        batches.append(ControlBatch(cluster_group))
      else:
        # Still too big: chunk sequentially
        batches.extend(chunk(cluster_group, MAX_BATCH_SIZE))
```

**Key Behaviors to Test**:
1. Groups ≤ MAX_BATCH_SIZE remain intact
2. Groups > MAX_BATCH_SIZE split by cluster
3. Cluster groups > MAX_BATCH_SIZE chunked sequentially
4. All output batches ≤ MAX_BATCH_SIZE (invariant)
5. Deterministic output ordering (sorted by control_id within chunks)

**Verification**: Oversized splitting tests pass, all batches ≤ MAX_BATCH_SIZE.

---

## Split 4: Batch Consolidation (Algorithm Step 3)

**Goal**: Merge small batches to reduce count to ≤ `MAX_CALLS` while minimizing batch sizes.

**Scope**:
- `merge_priority(batch_a: ControlBatch, batch_b: ControlBatch, max_batch_size: int) -> tuple[int, int] | None`
- `find_best_mergeable_pair(batches: list[ControlBatch], max_batch_size: int) -> tuple[int, int] | None`
- `consolidate_batches(batches: list[ControlBatch], max_calls: int, max_batch_size: int) -> list[ControlBatch]`

**Dependencies**: Split 1 (ControlBatch)

**Input**: List of `ControlBatch` (may exceed `MAX_CALLS`)

**Output**: List of `ControlBatch` (≤ `MAX_CALLS`, each ≤ `MAX_BATCH_SIZE`)

**Algorithm**:
```
if len(batches) <= MAX_CALLS:
  return batches  # No consolidation needed

while len(batches) > MAX_CALLS:
  best_pair = find_best_mergeable_pair(batches, MAX_BATCH_SIZE)
  if best_pair is None:
    break  # Cannot merge further
  merge(best_pair)

return batches
```

**Merge Priority**: `(combined_size, page_distance)` - smaller combined size first, then adjacent pages

**Key Behaviors to Test**:
1. No consolidation when batches ≤ MAX_CALLS
2. Merges to minimum necessary batch size (not MAX_BATCH_SIZE)
3. Prefers smallest combined size
4. Prefers adjacent pages on size tie
5. Never merges if combined size > MAX_BATCH_SIZE
6. Deterministic merge order (tie-break by min_primary_page)
7. Returns partial result if no valid merges remain

**Verification**: Consolidation tests pass, output ≤ MAX_CALLS batches.

---

## Split 5: Truncation (Algorithm Steps 0 + Phase B)

**Goal**: Handle over-capacity scenarios by dropping lowest-scoring controls.

**Scope**:
- `truncate_candidates(candidates: list[UniqueControl], capacity: int) -> list[UniqueControl]` (Step 0)
- `truncate_batches(batches: list[ControlBatch], max_calls: int) -> list[ControlBatch]` (Phase B)

**Dependencies**: Split 1 (UniqueControl, ControlBatch)

**Primary Truncation (Step 0)**:
- Input: Candidates where `N > capacity`
- Output: Top N candidates by score
- Ordering: `(-max_score, control_id)` for determinism

**Secondary Truncation (Phase B)**:
- Input: Batches where merging couldn't reach MAX_CALLS
- Output: Batches ≤ MAX_CALLS by dropping lowest-scoring controls
- Algorithm: Drop from largest batches first

**Key Behaviors to Test**:
1. Primary: Keeps highest-scoring candidates
2. Primary: Deterministic ordering on score ties
3. Primary: Logs warning with original count
4. Secondary: Drops from largest batches
5. Secondary: Removes empty batches
6. Secondary: Logs warning when invoked
7. No truncation when under capacity

**Verification**: Truncation tests pass, outputs respect capacity limits.

---

## Split 6: Main Function + Integration

**Goal**: Wire all components into `create_page_aware_batches()` and integrate with `control_centric_decider.py`.

**Scope**:
- `create_page_aware_batches()` orchestrates Splits 2-5
- `dedupe_to_unique_controls()` (Step -1) in decider
- Update `control_centric_decider.py` to use new batching

**Dependencies**: All previous splits

**Main Function Flow**:
```python
def create_page_aware_batches(
    candidates: list[UniqueControl],
    cluster_map: dict[str, int],
    max_calls: int = 50,
    max_batch_size: int = 10,
) -> list[ControlBatch]:
    # Step 0: Truncate if over capacity
    capacity = max_calls * max_batch_size
    if len(candidates) > capacity:
        candidates = truncate_candidates(candidates, capacity)

    # Step 1: Group by max-score page
    page_groups = group_by_max_page(candidates)

    # Step 2: Split oversized groups
    batches = split_oversized_groups(page_groups, cluster_map, max_batch_size)

    # Step 3: Consolidate if needed
    if len(batches) > max_calls:
        batches = consolidate_batches(batches, max_calls, max_batch_size)

        # Phase B: Secondary truncation if still over
        if len(batches) > max_calls:
            batches = truncate_batches(batches, max_calls)

    return batches
```

**Integration in `control_centric_decider.py`**:
```python
# Step -1: Dedupe to UniqueControl
unique_controls = dedupe_to_unique_controls(document_prediction)

# Create batches
batches = create_page_aware_batches(
    candidates=unique_controls,
    cluster_map=cluster_cache.get_cluster_map(),
    max_calls=self.config.max_calls,
    max_batch_size=self.config.max_batch_size,
)
```

**Key Behaviors to Test**:
1. End-to-end: Few candidates → small batches, no consolidation
2. End-to-end: Moderate candidates → consolidation to minimum size
3. End-to-end: Over capacity → truncation + max packing
4. Determinism: Same input → same output
5. Integration: Replaces existing batching without regression

**Verification**: All tests pass, experiment runs successfully.

---

## Split Dependencies Graph

```
Split 1 (Data Structures)
    │
    ├──────────┬──────────┬──────────┐
    ▼          ▼          ▼          ▼
Split 2    Split 3    Split 4    Split 5
(Grouping) (Splitting) (Merging) (Truncation)
    │          │          │          │
    └──────────┴──────────┴──────────┘
                    │
                    ▼
              Split 6 (Integration)
```

---

## Execution Order

| Order | Split | Est. Complexity | Blocking? |
|-------|-------|-----------------|-----------|
| 1 | Split 1: Data Structures | Low | Yes (foundation) |
| 2 | Split 2: Page Grouping | Low | No |
| 3 | Split 3: Oversized Splitting | Medium | No |
| 4 | Split 4: Batch Consolidation | High | No |
| 5 | Split 5: Truncation | Medium | No |
| 6 | Split 6: Integration | Medium | Yes (final) |

**Note**: Splits 2-5 can be developed in parallel after Split 1 is complete, but testing the full flow requires all to be done.

---

## Verification Strategy

After each split:
1. Run split-specific tests → all pass
2. Run all existing tests → no regressions
3. Manual spot-check with real data (optional)

After all splits:
1. Run full test suite
2. Run experiment on test document
3. Compare batch distribution to expected behavior
