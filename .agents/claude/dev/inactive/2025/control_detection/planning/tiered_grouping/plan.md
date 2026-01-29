# Tiered Control Batching: Page-Aware Strategy

## Context for New Engineers

**What we're building**: An automated compliance checker that determines which regulatory controls (e.g., "Passwords must be 12+ characters") are addressed by a company's policy documents (e.g., a 50-page "Information Security Policy" PDF).

**The pipeline**:
1. **ColModernVBERT scoring**: An embedding model scores each control against each page of the document (0-1 relevance score)
2. **Candidate filtering**: Controls scoring above threshold (0.48) become "candidates" for LLM verification
3. **LLM verification**: Gemini reads the full document and confirms which candidates are actually addressed
4. **This plan**: Optimizes step 3 by intelligently batching controls for LLM calls

**Key constraints**:
- MAX_CALLS = 50 LLM requests per document (cost control)
- MAX_BATCH_SIZE = 10 controls per request (quality control, hard limit)
- Fewer controls per request = better LLM attention = higher quality

**Why pages matter**: ColModernVBERT already tells us which page each control is most relevant to. Controls that score highest on the same page likely relate to the same document section—grouping them helps the LLM focus.

---

## Problem Statement

We need to batch candidate controls for LLM evaluation with two competing goals:
1. **Quality**: Fewer controls per request → better LLM attention per control
2. **Cost**: Fewer total requests → cheaper and faster

Current approach uses pure K-means clustering on control embeddings, hoping similar descriptions align with similar document pages. This is **indirect**.

**Better approach**: Use ColModernVBERT's page-level scores directly—they already tell us which pages each control cares about.

---

## Key Insight: Minimum Necessary Batch Size

When consolidation is needed, we should use the **minimum batch size** to fit under MAX_CALLS:

```
target_batch_size = ceil(total_candidates / MAX_CALLS)
```

**NOT** MAX_BATCH_SIZE.

### Example

- 200 candidates, MAX_CALLS=50, MAX_BATCH_SIZE=10
- After page grouping: 80 batches
- **Wrong**: Consolidate to 20 batches of 10 (wastes quality)
- **Right**: Consolidate to 50 batches of 4 (minimum necessary)

---

## The Algorithm

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TIERED BATCHING ALGORITHM                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Input: DocumentPrediction with per-page ScoredControls                 │
│  Config: MAX_CALLS=50, MAX_BATCH_SIZE=10                                │
│  Capacity: MAX_CALLS × MAX_BATCH_SIZE = 500                             │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ STEP -1: Dedupe to Unique Controls (with Top Pages)               │  │
│  │                                                                   │  │
│  │   # A control can appear in top_controls for multiple pages!     │  │
│  │   # Track ALL page scores, then extract top 3 for LLM hints      │  │
│  │   control_page_scores: dict[control_id] -> list[(page, score)]    │  │
│  │   for page_pred in document_prediction.page_predictions:          │  │
│  │     for scored_ctrl in page_pred.top_controls:                    │  │
│  │       control_page_scores[ctrl_id].append((page_num, score))      │  │
│  │                                                                   │  │
│  │   # Convert to UniqueControl with top_pages                       │  │
│  │   for ctrl_id, page_scores in control_page_scores.items():        │  │
│  │     sorted_pages = sorted(page_scores, key=score, reverse=True)   │  │
│  │     max_score = sorted_pages[0].score                             │  │
│  │     max_page = sorted_pages[0].page  # For Step 1 grouping        │  │
│  │     top_pages = sorted_pages[:3]     # For LLM retrieval hints    │  │
│  │                                                                   │  │
│  │   candidates = list of UniqueControl(id, max_score, max_page,     │  │
│  │                                       top_pages, control)         │  │
│  │   N = len(candidates)  # Now guaranteed unique by control_id      │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ STEP 0: Truncate if Over Capacity                                 │  │
│  │                                                                   │  │
│  │   capacity = MAX_CALLS × MAX_BATCH_SIZE                           │  │
│  │   if N > capacity:                                                │  │
│  │     LOG WARNING: "Truncating {N} candidates to {capacity}"        │  │
│  │     sort by (-max_score, control_id)  # Deterministic             │  │
│  │     candidates = candidates[:capacity]                            │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ STEP 1: Group by Max-Score Page                                   │  │
│  │                                                                   │  │
│  │   For each control in candidates:                                 │  │
│  │     page_groups[control.max_page].append(control)                 │  │
│  │                                                                   │  │
│  │   Result: P page-groups (natural clustering by document section)  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ STEP 2: Split Oversized Page Groups                               │  │
│  │                                                                   │  │
│  │   For each page_group where len(group) > MAX_BATCH_SIZE:          │  │
│  │     # Group controls by their pre-computed cluster_id             │  │
│  │     cluster_groups = group_by(group, key=cluster_map[ctrl.id])    │  │
│  │     for cluster_group in cluster_groups:                          │  │
│  │       if len(cluster_group) <= MAX_BATCH_SIZE:                    │  │
│  │         batches.append(cluster_group)                             │  │
│  │       else:                                                       │  │
│  │         # Still too big: chunk sequentially (sorted by control_id)│  │
│  │         batches.extend(chunk(cluster_group, MAX_BATCH_SIZE))      │  │
│  │   Else:                                                           │  │
│  │     batches.append(page_group)                                    │  │
│  │                                                                   │  │
│  │   Result: B batches (where B ≥ P, each ≤ MAX_BATCH_SIZE)          │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ STEP 3: Smart Consolidation (only if B > MAX_CALLS)               │  │
│  │                                                                   │  │
│  │   if len(batches) <= MAX_CALLS:                                   │  │
│  │     return batches  # No consolidation needed!                    │  │
│  │                                                                   │  │
│  │   # Phase A: Merge batches until under MAX_CALLS                  │  │
│  │   while len(batches) > MAX_CALLS:                                 │  │
│  │     best_pair = find_best_mergeable_pair(batches)                 │  │
│  │       # MUST check: len(a) + len(b) <= MAX_BATCH_SIZE             │  │
│  │       # Priority: (combined_size, page_distance, min_page)        │  │
│  │     if best_pair is None:                                         │  │
│  │       break  # Cannot merge further                               │  │
│  │     merge(best_pair)                                              │  │
│  │                                                                   │  │
│  │   # Phase B: Secondary truncation if still over MAX_CALLS         │  │
│  │   if len(batches) > MAX_CALLS:                                    │  │
│  │     LOG WARNING: "Cannot merge to {MAX_CALLS}, dropping controls" │  │
│  │     # Drop lowest-scoring controls from largest batches           │  │
│  │     while len(batches) > MAX_CALLS:                               │  │
│  │       largest_batch = max(batches, key=len)                       │  │
│  │       drop lowest-scoring control from largest_batch              │  │
│  │       if len(largest_batch) == 0: remove batch                    │  │
│  │                                                                   │  │
│  │   Result: ≤ MAX_CALLS batches, each ≤ MAX_BATCH_SIZE (guaranteed) │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Output: List of batches optimized for both quality and cost            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Behavior by Scenario

### Scenario A: Few Candidates (N ≤ MAX_CALLS)

Example: 30 candidates, MAX_CALLS=50

```
Step 1: 30 controls → ~15-25 page groups (depends on document)
Step 2: No splitting needed (all groups small)
Step 3: 25 batches ≤ 50 MAX_CALLS → NO consolidation

Result: ~25 batches of 1-2 controls each
Quality: Excellent (small batches)
Cost: 25 API calls
```

### Scenario B: Moderate Candidates (MAX_CALLS < N ≤ capacity)

Example: 200 candidates, MAX_CALLS=50, MAX_BATCH_SIZE=10

```
Step 1: 200 controls → ~40-60 page groups
Step 2: Split any groups > 10 → ~70 batches
Step 3: 70 > 50 → MUST consolidate
        target_size = ceil(200/50) = 4
        Merge until ≤ 50 batches

Result: ~50 batches of ~4 controls each
Quality: Good (4 per batch, not 10)
Cost: 50 API calls (at limit)
```

### Scenario C: Many Candidates (N ≈ capacity)

Example: 450 candidates, MAX_CALLS=50, MAX_BATCH_SIZE=10

```
Step 1: 450 controls → many page groups
Step 2: Split large groups → ~100+ batches
Step 3: target_size = ceil(450/50) = 9
        Merge until ≤ 50 batches

Result: ~50 batches of ~9 controls each
Quality: Acceptable (near max, but necessary)
Cost: 50 API calls (at limit)
```

### Scenario D: Over Capacity (N > MAX_CALLS × MAX_BATCH_SIZE)

Example: 600 candidates, MAX_CALLS=50, MAX_BATCH_SIZE=10, capacity=500

```
Step 0: 600 > 500 (capacity)
        LOG WARNING: "Truncating 600 candidates to 500"
        Keep top 500 by score, drop lowest 100

Result: 50 batches of 10 controls each
        100 lowest-scoring candidates dropped
```

---

## Consolidation Strategy: Merge Preferences

When merging batches, we must:

**CONSTRAINT**: Only merge if `len(a) + len(b) <= MAX_BATCH_SIZE`. Skip invalid pairs.

**PRIORITY ORDER** (lower = better to merge):

1. **Smallest combined size first**: Prefer merging small batches to keep them small
   - Rationale: Smaller batches = better LLM quality

2. **Adjacent pages second**: Among equal-size merges, prefer adjacent pages
   - Rationale: Adjacent pages likely cover related content

3. **If no valid merges exist**: Proceed to Phase B (secondary truncation)

---

## Determinism Rules

All tie-breaks must be deterministic for reproducible results:

| Situation | Tie-break Rule |
|-----------|---------------|
| Equal max_score on multiple pages | Use **lowest page number** |
| Truncation ordering | Sort by `(-max_score, control_id)` |
| `primary_page` ties in Counter | Use **lowest page** among tied modes |
| Merge pair ties (same priority score) | Use `(min_primary_page_a, min_primary_page_b)` |
| Controls within a batch | Sort by `(-max_score, control_id)` |
| Batches in output | Sort by `(primary_page, min_control_id)`|

```python
def merge_priority(batch_a, batch_b, max_batch_size: int) -> tuple[int, int] | None:
    """Score for merging two batches (lower = better to merge). Returns None if invalid."""
    combined_size = len(batch_a) + len(batch_b)

    # CRITICAL: Cannot merge if it would exceed max batch size
    if combined_size > max_batch_size:
        return None  # Invalid merge

    page_distance = abs(batch_a.primary_page - batch_b.primary_page)

    # Prefer SMALL combined size first, THEN adjacent pages
    # This keeps batches as small as possible for LLM quality
    return (combined_size, page_distance)
```

---

## Implementation Plan (TDD Approach)

> **Test-Driven Development**: We write tests FIRST, then implement code to make them pass. This ensures:
> - Clear specification of expected behavior before coding
> - Confidence that edge cases are handled
> - Refactoring safety with comprehensive test coverage

### Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `tests/scripts/experiments/control_detection/test_page_aware_batching.py` | **Create** | Tests FIRST (TDD) |
| `batching.py` | **Modify** | Add `create_page_aware_batches()` to pass tests |
| `control_clustering.py` | **Keep** | Still needed for Step 2 (splitting oversized page groups) |
| `control_centric_decider.py` | **Modify** | Use new batching function |

---

### Phase 1: Write Tests (RED)

Create `test_page_aware_batching.py` with failing tests for each behavior:

```python
# tests/scripts/experiments/control_detection/test_page_aware_batching.py

class TestUniqueControl:
    """Test UniqueControl data structure."""

    def test_to_retrieval_anchors_converts_correctly(self): ...
    def test_top_pages_limited_to_three(self): ...

class TestControlBatch:
    """Test ControlBatch data structure."""

    def test_primary_page_returns_most_common(self): ...
    def test_primary_page_breaks_ties_with_lowest_page(self): ...
    def test_can_merge_with_validates_size(self): ...
    def test_len_returns_control_count(self): ...

class TestCreatePageAwareBatches:
    """Test the main batching function."""

    # Step 1: Page grouping
    def test_groups_controls_by_max_score_page(self): ...
    def test_page_grouping_uses_lowest_page_on_score_tie(self): ...

    # Step 2: Oversized splitting
    def test_splits_oversized_groups_by_cluster(self): ...
    def test_chunks_large_cluster_groups_sequentially(self): ...

    # Step 3: Consolidation
    def test_no_consolidation_when_under_max_calls(self): ...
    def test_merges_to_minimum_batch_size(self): ...
    def test_merge_prefers_smallest_combined_size(self): ...
    def test_merge_prefers_adjacent_pages_on_size_tie(self): ...
    def test_never_merges_beyond_max_batch_size(self): ...

    # Truncation
    def test_truncates_when_over_capacity(self): ...
    def test_truncation_keeps_highest_scoring(self): ...
    def test_secondary_truncation_when_merge_impossible(self): ...

    # Determinism
    def test_deterministic_output_ordering(self): ...

    # Edge cases
    def test_zero_candidates_returns_empty(self): ...
    def test_one_candidate_returns_single_batch(self): ...
    def test_exactly_max_calls_candidates(self): ...
```

**Run tests**: All should FAIL (no implementation yet).

---

### Phase 2: Implement Data Structures (GREEN)

Implement `UniqueControl` and `ControlBatch` to pass their tests:

### New Function: `create_page_aware_batches()`

```python
def create_page_aware_batches(
    candidates: list[UniqueControl],  # Already deduped with top_pages!
    cluster_map: dict[str, int],
    max_calls: int = 50,
    max_batch_size: int = 10,
) -> list[ControlBatch]:
    """
    Create batches using tiered page-aware strategy.

    Tiers:
    1. Group by max-score page (from UniqueControl.max_page)
    2. Split oversized groups by cluster_id, then chunk
    3. Consolidate small batches to fit MAX_CALLS (minimize batch sizes)

    Args:
        candidates: Deduped controls with precomputed max_page and top_pages.
        cluster_map: Pre-computed K-means cluster assignments.
        max_calls: Maximum LLM calls allowed.
        max_batch_size: Maximum controls per batch.

    Returns:
        List of ControlBatch containing UniqueControl objects.
        Call control.to_retrieval_anchors() when formatting for LLM.
    """
```

### Data Structures

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class UniqueControl:
    """A deduped control with precomputed page info for batching and LLM hints."""

    control_id: str
    control: DCFControl  # Original control object
    max_score: float     # Highest score across all pages
    max_page: int        # Page with highest score (for Step 1 grouping)
    top_pages: tuple[tuple[int, float], ...]  # Up to 3 (page, score) pairs for LLM

    def to_retrieval_anchors(self) -> RetrievalAnchors:
        """Convert to RetrievalAnchors for LLM formatting (no recomputation!)."""
        return RetrievalAnchors(
            top_pages=tuple(p[0] for p in self.top_pages),
            best_score=self.max_score,
            page_scores=tuple(p[1] for p in self.top_pages),
        )


@dataclass
class ControlBatch:
    controls: list[UniqueControl]  # Changed from ScoredControl!
    source_pages: list[int]  # Pages these controls came from

    def __len__(self) -> int:
        return len(self.controls)

    @property
    def primary_page(self) -> int:
        """Most common source page in this batch."""
        # Determinism: use lowest page among tied modes
        counts = Counter(self.source_pages)
        max_count = max(counts.values())
        tied_pages = [p for p, c in counts.items() if c == max_count]
        return min(tied_pages)

    def can_merge_with(self, other: "ControlBatch", max_size: int) -> bool:
        """Check if merging with another batch would exceed max size."""
        return len(self.controls) + len(other.controls) <= max_size
```

**Why `UniqueControl`?**
- Avoids recomputing `top_pages` at LLM call time (currently done via `compute_retrieval_anchors()`)
- Carries all needed data through the batching pipeline
- `to_retrieval_anchors()` provides zero-cost conversion for LLM formatting

### Source Data: ScoredControl → UniqueControl

**Input** (`ScoredControl` from `predictor.py`):
```python
@dataclass(slots=True)
class ScoredControl:
    control: DCFControl
    score: float
    page_num: int  # Which page had this score
```

**Transformation in Step -1** (dedupe with top_pages):
```python
# Collect all page scores per control
control_page_scores: dict[str, list[tuple[int, float]]] = defaultdict(list)
for page_pred in document_prediction.page_predictions:
    for scored_ctrl in page_pred.top_controls:
        ctrl_id = scored_ctrl.control.control_id
        control_page_scores[ctrl_id].append((page_pred.page_num, scored_ctrl.score))

# Convert to UniqueControl with top 3 pages
candidates = []
for ctrl_id, page_scores in control_page_scores.items():
    sorted_pages = sorted(page_scores, key=lambda x: (-x[1], x[0]))  # score desc, page asc
    candidates.append(UniqueControl(
        control_id=ctrl_id,
        control=...,  # From first ScoredControl with this ID
        max_score=sorted_pages[0][1],
        max_page=sorted_pages[0][0],
        top_pages=tuple(sorted_pages[:3]),  # Up to 3 for LLM hints
    ))
```

**Output**: `UniqueControl` carries `top_pages` through batching → no need to call `compute_retrieval_anchors()` at LLM time.

---

### Phase 3: Implement Main Function (GREEN)

Implement `create_page_aware_batches()` incrementally, running tests after each step:

1. **Implement Step 1 (page grouping)** → Run tests → Some pass
2. **Implement Step 2 (oversized splitting)** → Run tests → More pass
3. **Implement Step 3 (consolidation)** → Run tests → More pass
4. **Implement truncation** → Run tests → All pass

---

### Phase 4: Refactor (REFACTOR)

With all tests passing:
1. Extract helper functions if logic is complex
2. Improve naming for clarity
3. Add logging for observability
4. Ensure all tests still pass

---

### Phase 5: Integration

Update `control_centric_decider.py` to use the new batching:
1. Write integration test for full flow
2. Replace existing batching call with `create_page_aware_batches()`
3. Verify integration test passes

---

## TDD Cycle Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                     TDD IMPLEMENTATION ORDER                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Write test_page_aware_batching.py (all tests fail)    RED   │
│                          │                                      │
│                          ▼                                      │
│  2. Implement UniqueControl + ControlBatch                GREEN │
│     → Run tests → data structure tests pass                     │
│                          │                                      │
│                          ▼                                      │
│  3. Implement create_page_aware_batches() step by step    GREEN │
│     → Run tests after each step → more pass                     │
│                          │                                      │
│                          ▼                                      │
│  4. All tests pass → Refactor for clarity              REFACTOR │
│                          │                                      │
│                          ▼                                      │
│  5. Update control_centric_decider.py                  INTEGRATE│
│     → Integration test passes                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Questions Before Implementation

1. ~~**Does `ScoredControl` have per-page scores?**~~ ✅ **RESOLVED**: Yes, each `ScoredControl` has `page_num`. We iterate through `PagePrediction` lists to find max-score page per control.

2. **What happens when a control scores equally on multiple pages?**
   - **Recommendation**: Use lowest page number (deterministic, preserves document order)

3. ~~**Should we expose `target_batch_size` as a config option?**~~ ✅ **RESOLVED**: No. Always compute dynamically: `target_size = ceil(N / MAX_CALLS)`. This ensures minimum necessary batch size.

4. **For over-capacity scenarios (N > MAX_CALLS × MAX_BATCH_SIZE), which option?**
   - a) Dynamically increase MAX_BATCH_SIZE for this document
   - b) Truncate to top N by score (discard lowest-scoring candidates)
   - c) Raise ColModernVBERT threshold dynamically
   - d) Return error to caller
   - **Recommendation**: Option (b) - truncate to top N by score. It's simple, deterministic, and prioritizes the most confident matches.

---

## Success Criteria

1. **Page-aware grouping**: Controls grouped by where they scored, not just embedding similarity
2. **Minimum batch sizes**: Never use larger batches than necessary to fit MAX_CALLS
3. **Hard batch limit**: Never exceed MAX_BATCH_SIZE (user has full control)
4. **Preserved locality**: Merged batches prefer adjacent pages
5. **K-means as fallback only**: Used for splitting oversized page groups, not primary grouping
6. **Deterministic**: Same input → same batches
7. **Truncation logged**: Over-capacity triggers warning with candidate count

---

## Refinements Applied

Based on external reviews, the following fixes were incorporated:

**From `gemini_3_analysis.md`:**

| Issue | Fix Applied |
|-------|-------------|
| Merge could exceed MAX_BATCH_SIZE | Added `can_merge_with()` validation, returns None for invalid merges |
| Global cluster IDs don't help split page groups | Group by cluster, then chunk if still too large |
| Priority order was backwards | Changed to `(combined_size, page_distance)` - size first |

**From `chatgpt_analysis.md`:**

| Issue | Fix Applied |
|-------|-------------|
| Duplicate controls across pages | Added Step -1: Dedupe to unique controls |
| Input data model unclear | Clarified: takes DocumentPrediction, computes max_page per control |
| MAX_CALLS could be exceeded | Added Phase B: secondary truncation if merging fails |
| Determinism gaps | Added explicit tie-break rules table |
| split_by_clustering under-specified | Clarified: group by cluster_id, then chunk each group |

---

## Production Considerations (Out of Scope for Experiment)

> **Note**: This section documents tradeoffs to consider for production. For the experiment, we always use `MAX_CALLS` and spread controls as thinly as possible to maximize LLM attention per control.

In production, there's a meaningful tradeoff between `MAX_BATCH_SIZE` and `MAX_CALLS`:

| Strategy | Approach | Pros | Cons |
|----------|----------|------|------|
| **Maximize quality** | Use all MAX_CALLS, pack minimally | Best LLM attention per control | Higher cost/latency |
| **Minimize cost** | Pack to MAX_BATCH_SIZE, use fewer calls | Cheaper, faster | LLM may miss nuance |
| **Adaptive** | Choose based on document/candidate count | Balanced | More complexity |

**Questions for production**:
1. When candidate count is low (e.g., 30), should we still use all 50 calls (1-2 per batch) or consolidate to fewer, larger batches to save cost?
2. For documents where quality is critical (e.g., high-value customers), should we dynamically increase MAX_CALLS?
3. Should we expose a "quality vs cost" knob to callers?

**Experiment approach**: Always spread controls as thinly as possible within `MAX_CALLS`. This gives us a quality baseline. We can later experiment with tighter packing to measure quality degradation vs cost savings.
