To intelligently reduce the 5,287 false positives to a manageable but representative sample (e.g., ~150-200), you should use a **"Pareto + Diversity" Hybrid Strategy**.

In data processing like this, errors are rarely normally distributed. They usually follow a Power Law: a small number of "bad" controls or "vague" policies are likely responsible for a huge chunk of your FPs.

Here is the recommended sampling algorithm to implement in `fp_collector.py`:

### The Strategy: "Pareto + Diversity" (Target: ~200 items)

We will build the sample set from three distinct buckets:

#### Bucket A: The "Frequent Flyers" (Top Offending Controls)
*   **Goal:** Fix the specific controls that confuse the model the most.
*   **Logic:** Group all FPs by `control_id`.
*   **Action:** Take the **Top 20** controls with the highest FP count.
*   **Sample:** Select **3 random instances** for each of these 20 controls.
*   **Yield:** ~60 items.
*   **Why:** Fixing the logic for "Synchronize Clocks" or "Encrypt Data" will likely wipe out hundreds of FPs at once.

#### Bucket B: The "Problem Policies" (Top Offending Documents)
*   **Goal:** Understand why specific documents trigger hallucinations (e.g., is the document too vague? formatting issues?).
*   **Logic:** Group all remaining FPs by `policy_name`.
*   **Action:** Take the **Top 5** policies with the highest FP count.
*   **Sample:** Select **10 random instances** from each of these 5 policies (excluding ones already picked in Bucket A).
*   **Yield:** ~50 items.
*   **Why:** These policies act as "stress tests" for your Interpretive Rules.

#### Bucket C: The "Long Tail" (Diversity Coverage)
*   **Goal:** Ensure we don't overfit to the worst offenders and miss subtle logic errors in standard policies.
*   **Logic:** Look at the remaining `policy_name` list (policies not in Bucket B).
*   **Action:** Select **2 random instances** from *every single remaining policy*.
*   **Yield:** (37 total - 5 top) * 2 ≈ 64 items.
*   **Why:** This ensures every policy is represented at least slightly.

---

### Implementation Logic for `fp_collector.py`

Here is how to implement this logic programmatically:

```python
import random
from collections import Counter

def sample_false_positives(all_fps: list[FalsePositive], target_size: int = 200) -> list[FalsePositive]:
    """
    Intelligent sampling to maximize insight while minimizing cost.
    Strategy: Top Controls + Top Policies + Diversity Tail
    """
    selected_indices = set()
    sample_set = []
    
    # Helper to add to sample
    def add_fp(fp_index):
        if fp_index not in selected_indices:
            selected_indices.add(fp_index)
            sample_set.append(all_fps[fp_index])

    # ---------------------------------------------------------
    # Bucket A: Top 20 Offending Controls (3 examples each)
    # ---------------------------------------------------------
    control_counts = Counter(fp.control_id for fp in all_fps)
    top_20_controls = [c for c, _ in control_counts.most_common(20)]
    
    for ctrl_id in top_20_controls:
        # Find all FPs for this control
        candidates = [i for i, fp in enumerate(all_fps) if fp.control_id == ctrl_id]
        # Pick 3 random
        for i in random.sample(candidates, min(len(candidates), 3)):
            add_fp(i)

    # ---------------------------------------------------------
    # Bucket B: Top 5 Offending Policies (10 examples each)
    # ---------------------------------------------------------
    # Re-calculate counts excluding what we already picked (optional, but cleaner to look at raw)
    policy_counts = Counter(fp.policy_name for fp in all_fps)
    top_5_policies = [p for p, _ in policy_counts.most_common(5)]
    
    for pol_name in top_5_policies:
        candidates = [i for i, fp in enumerate(all_fps) 
                     if fp.policy_name == pol_name and i not in selected_indices]
        for i in random.sample(candidates, min(len(candidates), 10)):
            add_fp(i)

    # ---------------------------------------------------------
    # Bucket C: Diversity Tail (Ensure every policy is seen)
    # ---------------------------------------------------------
    all_policies = set(fp.policy_name for fp in all_fps)
    remaining_policies = all_policies - set(top_5_policies)
    
    for pol_name in remaining_policies:
        candidates = [i for i, fp in enumerate(all_fps) 
                     if fp.policy_name == pol_name and i not in selected_indices]
        # Pick 2 from each remaining policy
        for i in random.sample(candidates, min(len(candidates), 2)):
            add_fp(i)
            
    # ---------------------------------------------------------
    # Bucket D: Random Fill (if we are under target)
    # ---------------------------------------------------------
    remaining_indices = [i for i in range(len(all_fps)) if i not in selected_indices]
    slots_left = target_size - len(sample_set)
    
    if slots_left > 0 and remaining_indices:
        for i in random.sample(remaining_indices, min(len(remaining_indices), slots_left)):
            add_fp(i)

    print(f"Sampled {len(sample_set)} FPs from population of {len(all_fps)}")
    return sample_set
```

### Why this is better than random sampling
1.  **Noise Reduction:** If "Control X" accounts for 1,000 FPs, random sampling would give you ~20 instances of it. You only need ~3 to realize the rule is broken. This saves ~17 API calls.
2.  **Breadth:** Random sampling might miss a unique policy that has subtle errors because it only has a few FPs. Bucket C guarantees coverage.
3.  **Actionable Data:** You will immediately get a list of "The 20 Broken Controls" and "The 5 Unreadable Policies," which are clear targets for your prompt engineering efforts.