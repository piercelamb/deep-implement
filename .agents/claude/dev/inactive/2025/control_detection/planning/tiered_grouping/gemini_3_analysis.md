This is a strong, well-reasoned plan that correctly identifies the tension between cost (API calls) and quality (attention per control). The "Minimum Necessary Batch Size" insight is particularly valuable—it prevents the system from defaulting to 10 controls per call when 4 would suffice, thereby maximizing LLM performance.

However, there are three specific "footguns" (risks) in the algorithm logic and one compliance risk that need addressing before implementation.

### 1. The "Merge Violation" Footgun
**The Issue:** In `STEP 3`, the plan says "Merge smallest adjacent batches."
**The Risk:** If you have two adjacent batches that are both moderate in size (e.g., Page 4 has 6 controls, Page 5 has 5 controls), merging them creates a batch of 11. This violates `MAX_BATCH_SIZE` (10).
**The Fix:** The merge logic must strictly validate that `len(batch_a) + len(batch_b) <= MAX_BATCH_SIZE`. If adjacent batches cannot be merged, you must look for non-adjacent merges or stop merging (if possible).

**Modification to Step 3:**
```python
while len(batches) > MAX_CALLS:
    # Find best VALID pair to merge
    best_pair = None
    min_score = infinity
    
    for i, batch_a in enumerate(batches):
        for j, batch_b in enumerate(batches[i+1:]):
            if len(batch_a) + len(batch_b) > MAX_BATCH_SIZE:
                continue # Skip invalid merges
            
            score = calculate_merge_score(batch_a, batch_b)
            if score < min_score:
                min_score = score
                best_pair = (batch_a, batch_b)
    
    if best_pair:
        merge(best_pair)
    else:
        break # Cannot reduce further without violating batch size
```

### 2. The "Global Cluster" Footgun (Step 2)
**The Issue:** Step 2 suggests using `split_by_clustering` for oversized page groups.
**The Risk:** The `cluster_map` likely contains *global* cluster IDs. If Page 12 has 15 controls, and they all belong to Global Cluster 5 (e.g., "Access Control"), K-means won't distinguish them. You'll pass a list of identical cluster IDs to the splitter, which won't know how to divide them.
**The Fix:** For splitting oversized page groups, simpler is better.
1.  **Try Sub-Clustering:** Run a *local* K-means on just those 15 controls (k=2).
2.  **Fallback:** If local clustering fails (or data is too uniform), use **semantic sorting**. Sort the controls by their text length or alphabetically (to keep duplicates near each other) and perform a hard split (slice the list).

### 3. The "Silent Data Loss" Risk (Scenario D)
**The Issue:** For Over-Capacity (Scenario D), the plan chooses "Truncate to top N by score."
**The Risk:** In a compliance context, silently dropping the 501st candidate (which might be a critical control that scored 0.49 vs 0.50) is dangerous. It creates "false negatives" where the system says "Not Addressed" simply because it ran out of budget.
**The Fix:** 
1.  **Prioritize:** Truncation is the last resort.
2.  **Elastic Batch Size:** If `Total Candidates` is 520 (just over limit), calculate the `required_batch_size`. `ceil(520 / 50) = 11`. If this is within a tolerance (e.g., +20% of Max Batch Size), **allow the batch size to flex** to 11 or 12 rather than dropping data.
3.  **Hard Truncation:** Only drop data if the required batch size exceeds the "Elastic Limit" (e.g., 15).

### 4. Merge Priority Normalization
**The Issue:** The priority function compares `page_distance` (range ~1-100) and `combined_size` (range 2-10).
```python
return (page_distance, combined_size)
```
**The Risk:** `page_distance` will dominate. Merging Page 1 (size 2) and Page 5 (size 2) has distance 4. Merging Page 10 (size 2) and Page 11 (size 9) has distance 1. The algorithm will prefer creating a massive batch of 11 (bad for quality) over a batch of 4 (good for quality) just because the pages are adjacent.
**The Fix:** Prioritize **Size Balance** over Page Adjacency. We want to fill buckets evenly first.
```python
def merge_priority(batch_a, batch_b):
    # Primary: Resulting size (lower is better, keep batches small)
    # Secondary: Page distance (lower is better, keep context local)
    size_score = len(batch_a) + len(batch_b)
    page_dist = abs(batch_a.primary_page - batch_b.primary_page)
    
    # Weight size much higher than distance
    return (size_score * 100) + page_dist 
```

---

## refined_plan.md additions

Add these specific implementation details to your plan:

### 1. Updated `ControlBatch` class
Add a `can_merge_with` method to encapsulate the constraint logic.

```python
@dataclass
class ControlBatch:
    controls: list[ScoredControl]
    source_pages: list[int] # Changed from set to list to track distribution if needed

    def can_merge_with(self, other: 'ControlBatch', max_size: int) -> bool:
        return (len(self.controls) + len(other.controls)) <= max_size
```

### 2. Revised `create_page_aware_batches` Logic
Include the "Elastic Limit" logic.

```python
ELASTIC_BATCH_LIMIT = 12  # Allow slightly larger batches to avoid dropping data

total_candidates = len(candidates)
min_required_batch = ceil(total_candidates / MAX_CALLS)

effective_max_batch = MAX_BATCH_SIZE
if min_required_batch > MAX_BATCH_SIZE:
    if min_required_batch <= ELASTIC_BATCH_LIMIT:
        print(f"WARN: flexing max batch size to {min_required_batch} to fit capacity")
        effective_max_batch = min_required_batch
    else:
        print(f"WARN: Truncating {total_candidates} to capacity")
        # Logic to truncate candidates here
```

### 3. Handling "Page 0" or "Page None"
Ensure the code handles cases where `page_num` might be missing or 0 (e.g., metadata sections).
*   **Action:** Default to `page_num=1` or `999` if `None`, or group all `None` pages together.

### 4. Deterministic Sorting
Before Step 1, sort `candidates` by `(page_num, score DESC)`. This ensures that when you split groups or process lists, the order is always deterministic for testing.

---

### Summary of Changes to Plan
1.  **Logic:** Add `effective_max_batch` calculation (Elastic Limit).
2.  **Logic:** Modify Step 3 loop to check `can_merge_with`.
3.  **Logic:** Change `merge_priority` to weight `size` higher than `page_distance`.
4.  **Logic:** Step 2 splitting should default to list slicing/local sort, not global clustering.

With these additions, the plan is robust. Proceed with `batching.py`.