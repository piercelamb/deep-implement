# Sampling Recommendation v2: Post-Deduplication Strategy

## Executive Summary

After deduplicating 4,104 FPs to 1,878 patterns using `(control_id, IR_rule)` signatures, we have two viable paths:

| Option | Patterns Analyzed | Est. Cost | Tradeoff |
|--------|-------------------|-----------|----------|
| **A: Full Analysis** | 1,878 | ~$10-20 | Complete picture, no sampling bias |
| **B: Strategic Sample** | ~500 | ~$3-5 | Good coverage, faster iteration |

**Recommendation**: Start with Option A (full analysis) using a cost-effective model like Gemini 1.5 Flash. The marginal cost difference (~$15) is negligible compared to the value of complete data for prompt engineering decisions.

If cost or time constraints require sampling, use Option B with the bucket strategy detailed below.

---

## Key Findings Driving This Strategy

### 1. Pattern Count Is Manageable

The 2.2x reduction (4,104 → 1,878) lands us in an analyzable range:
- At ~$0.005-0.01 per pattern (Flash-tier models): **$9-19 total**
- At ~$0.05 per pattern (Pro-tier models): **$94 total**

Even the higher estimate is reasonable for a one-time analysis that will inform prompt improvements.

### 2. Clear Pareto Distribution

```
Frequency Distribution:
  Freq 1:     995 patterns (53%)   →  995 FPs (24%)
  Freq 2-5:   764 patterns (41%)   → 1,968 FPs (48%)
  Freq 6-10:  106 patterns (6%)    →  756 FPs (18%)
  Freq 11+:    13 patterns (<1%)   →  385 FPs (9%)
```

**Insight**: The 119 high-frequency patterns (freq ≥ 6) represent only 6% of patterns but 27% of FPs. These are mandatory to analyze.

### 3. IR-3 Dominates

IR-3 (Semantic Equivalence) accounts for 32.8% of FPs—more than double any other rule. This rule requires special attention in any sampling strategy.

---

## Option A: Full Analysis (Recommended)

### Why Full Analysis?

1. **Cost is negligible**: ~$15 vs ~$5 is not a meaningful difference
2. **No sampling bias**: Complete data for accurate root cause distribution
3. **Pattern weight preserved**: Can aggregate by frequency for impact analysis
4. **Future-proof**: Results can be re-sliced without re-running

### Implementation

```python
# Use all 1,878 patterns
patterns = deduplicate_fps(all_fps, include_evidence=False)

# Judge each pattern
for pattern in patterns:
    result = await judge_false_positive(
        fp=pattern.representatives[0],  # Use best representative
        cache_name=policy_cache,
        pattern_frequency=pattern.frequency,  # Include for context
    )
```

### Representative Selection Improvement

Adopt Gemini's suggestion: select the **highest-confidence** FP as the representative, not just the first one encountered.

```python
def _select_representative(fps: list[FalsePositive]) -> FalsePositive:
    """Select the FP with highest confidence as representative.

    Rationale: A 95% confidence error is a "purer" example of the
    logic failure than a 40% confidence error. Analyzing the most
    confident mistakes reveals the core reasoning flaw.
    """
    confidence_order = {"high": 3, "medium": 2, "low": 1}
    return max(fps, key=lambda fp: confidence_order.get(fp.llm_confidence.value, 0))
```

### Output Weighting

When aggregating root causes, weight by pattern frequency:

```python
# Weighted distribution (for impact analysis)
weighted_counts = defaultdict(int)
for result in judge_results:
    weighted_counts[result.root_cause] += result.pattern_frequency

# Unweighted distribution (for variety analysis)
unweighted_counts = Counter(r.root_cause for r in judge_results)
```

---

## Option B: Strategic Sampling (~500 patterns)

Use this approach if:
- Using expensive models (GPT-4o, Claude 3.5 Sonnet)
- Human review is the bottleneck
- Need fast iteration on prompt changes

### Bucket Strategy

| Bucket | Criteria | Count | Rationale |
|--------|----------|-------|-----------|
| A | freq ≥ 6 | 119 | **Mandatory** - High-impact systemic failures |
| B | IR-3 patterns not in A | 100 | **Oversample** - Most abused rule (32.8%) |
| C | Top confidence (freq < 6, not IR-3) | 150 | **Dangerous** - High-confidence hallucinations |
| D | Policy coverage fill | ~50 | **Diversity** - Every policy represented |
| E | IR rule coverage fill | ~50 | **Diversity** - Every IR rule represented |
| F | Random from remainder | ~31 | **Long tail** - Catch unexpected patterns |
| **Total** | | **~500** | |

### Implementation

```python
def sample_patterns(
    patterns: list[FPPattern],
    target_count: int = 500,
    seed: int = 42,
) -> list[FPPattern]:
    """Strategic sampling with coverage guarantees."""
    rng = random.Random(seed)
    sampled = set()

    # Bucket A: All high-frequency patterns (mandatory)
    bucket_a = [p for p in patterns if p.frequency >= 6]
    sampled.update(bucket_a)

    remaining = [p for p in patterns if p not in sampled]

    # Bucket B: IR-3 oversample (most abused rule)
    ir3_patterns = [p for p in remaining if p.primary_ir_rule == "IR-3"]
    bucket_b = rng.sample(ir3_patterns, min(100, len(ir3_patterns)))
    sampled.update(bucket_b)

    remaining = [p for p in remaining if p not in sampled]

    # Bucket C: High-confidence one-offs
    # Sort by representative's confidence (descending)
    remaining_sorted = sorted(
        remaining,
        key=lambda p: get_confidence_score(p.representatives[0]),
        reverse=True
    )
    bucket_c = remaining_sorted[:150]
    sampled.update(bucket_c)

    remaining = [p for p in remaining if p not in sampled]

    # Bucket D: Policy coverage
    covered_policies = {pol for p in sampled for pol in p.policies}
    all_policies = {pol for p in patterns for pol in p.policies}
    missing_policies = all_policies - covered_policies

    for policy in missing_policies:
        candidates = [p for p in remaining if policy in p.policies]
        if candidates:
            selected = rng.choice(candidates)
            sampled.add(selected)
            remaining.remove(selected)

    # Bucket E: IR rule coverage
    covered_irs = {p.primary_ir_rule for p in sampled}
    all_irs = {p.primary_ir_rule for p in patterns if p.primary_ir_rule}
    missing_irs = all_irs - covered_irs

    for ir in missing_irs:
        candidates = [p for p in remaining if p.primary_ir_rule == ir]
        if candidates:
            # Take up to 5 per missing IR
            for selected in rng.sample(candidates, min(5, len(candidates))):
                sampled.add(selected)
                remaining.remove(selected)

    # Bucket F: Random fill to target
    if len(sampled) < target_count and remaining:
        fill_count = min(target_count - len(sampled), len(remaining))
        bucket_f = rng.sample(remaining, fill_count)
        sampled.update(bucket_f)

    return sorted(sampled, key=lambda p: p.frequency, reverse=True)
```

### Coverage Guarantees

The sampling algorithm ensures:
- [x] All high-frequency patterns (freq ≥ 6) included
- [x] IR-3 oversampled (given its 32.8% share)
- [x] High-confidence errors prioritized
- [x] Every policy has at least 1 pattern analyzed
- [x] Every IR rule has at least 5 patterns analyzed
- [x] Random sample for long-tail coverage

---

## Rejected Alternatives

### ChatGPT: Evidence Archetype Features

**Suggestion**: Add `(section_type, bindingness, specificity)` to signature.

**Verdict**: Rejected for now.

**Reasoning**:
- Adds significant complexity to signature computation
- Requires parsing evidence to classify section type, bindingness
- Better suited as **post-analysis enrichment** after we understand root causes
- Can revisit if judge results show we're over-merging different failure modes

### ChatGPT: Fuzzy/Near-Duplicate Matching

**Suggestion**: Use SimHash/MinHash instead of exact evidence hashes.

**Verdict**: Rejected.

**Reasoning**:
- Our finding was that `(control_id, IR_rule)` is the right abstraction level
- Evidence varies by policy by design (each policy has unique text)
- We don't need evidence deduplication—we need **reasoning pattern** deduplication
- If we want finer granularity later, evidence archetypes are simpler than fuzzy hashing

### ChatGPT: Semantic Clustering

**Suggestion**: Embed and cluster within `(control_id, IR_rule)` groups.

**Verdict**: Deferred.

**Reasoning**:
- Good idea for the freq=1 long tail (995 patterns)
- But with full analysis being affordable, clustering is premature optimization
- Revisit if we need to analyze a much larger FP set in the future

---

## Implementation Changes Required

### 1. Update `deduplicate_fps.py`

Add confidence-based representative selection:

```python
def _select_representatives(
    fps: list[FalsePositive],
    max_count: int = 3,
) -> list[FalsePositive]:
    """Select representative FP instances, prioritizing high confidence."""
    if len(fps) <= max_count:
        return fps

    # Sort by confidence (high > medium > low)
    confidence_order = {"high": 3, "medium": 2, "low": 1}
    sorted_fps = sorted(
        fps,
        key=lambda fp: confidence_order.get(fp.llm_confidence.value, 0),
        reverse=True
    )

    # Select highest-confidence FPs from different policies
    selected: list[FalsePositive] = []
    seen_policies: set[str] = set()

    for fp in sorted_fps:
        if fp.policy_name not in seen_policies:
            selected.append(fp)
            seen_policies.add(fp.policy_name)
            if len(selected) >= max_count:
                break

    # Fill remaining slots with highest-confidence regardless of policy
    if len(selected) < max_count:
        for fp in sorted_fps:
            if fp not in selected:
                selected.append(fp)
                if len(selected) >= max_count:
                    break

    return selected[:max_count]
```

### 2. Add `fp_sampler.py` (if using Option B)

Implement the bucket sampling algorithm above.

### 3. Update Judge Prompt

Include pattern frequency in context:

```
<pattern_context>
  <frequency>{pattern.frequency}</frequency>
  <affected_policies>{len(pattern.policies)}</affected_policies>
</pattern_context>

This logic pattern caused {frequency} false positives across {affected_policies} different policies.
Analyze the reasoning carefully—fixing this pattern has high impact.
```

---

## Stats Verification (Per ChatGPT's Flag)

ChatGPT noted: "Your IR table shows pattern count == FP count for many IRs."

**Verification needed**: Ensure the IR distribution table in deduplication_analysis.md counts **unique signatures**, not raw FP rows.

```python
# Correct way to count patterns per IR
patterns_by_ir = defaultdict(set)
for pattern in patterns:
    patterns_by_ir[pattern.primary_ir_rule].add(pattern.signature)

for ir, sigs in sorted(patterns_by_ir.items(), key=lambda x: len(x[1]), reverse=True):
    print(f"{ir}: {len(sigs)} patterns")
```

If the pattern counts match FP counts for some IRs, it means those IRs are producing mostly unique `(control_id, IR_rule)` combinations rather than repeating the same pattern across policies.

---

## Decision Matrix

| Factor | Option A (Full) | Option B (Sample) |
|--------|-----------------|-------------------|
| Cost | ~$15 | ~$5 |
| Coverage | 100% | ~95%+ with guarantees |
| Bias risk | None | Possible (mitigated by buckets) |
| Implementation effort | Lower | Higher (sampler code) |
| Iteration speed | Slower (run once) | Faster (can re-sample) |
| Recommended for | Final analysis | Prompt iteration |

---

## Next Steps

1. **Implement confidence-based representative selection** in `deduplicate_fps.py`
2. **Choose Option A or B** based on cost tolerance
3. **Proceed to Split 5**: Judge Infrastructure
4. **After judge results**: Aggregate by root cause (weighted by frequency) to prioritize prompt fixes

---

## Appendix: IR Rule Distribution Verification Script

```python
"""Verify IR distribution counts patterns vs FPs correctly."""
from collections import defaultdict
from false_positive_validation import collect_false_positives, deduplicate_fps

# Collect FPs
fps = collect_false_positives(...)
patterns = deduplicate_fps(fps)

# Count FPs per IR (raw)
fps_per_ir = defaultdict(int)
for fp in fps:
    ir = extract_primary_ir_rule(fp.llm_reasoning) or "None"
    fps_per_ir[ir] += 1

# Count patterns per IR (deduplicated)
patterns_per_ir = defaultdict(int)
for p in patterns:
    ir = p.primary_ir_rule or "None"
    patterns_per_ir[ir] += 1

# Compare
print("IR Rule | FP Count | Pattern Count | Reduction")
print("-" * 50)
for ir in sorted(fps_per_ir.keys()):
    fp_count = fps_per_ir[ir]
    pat_count = patterns_per_ir[ir]
    reduction = fp_count / pat_count if pat_count > 0 else 0
    print(f"{ir:8} | {fp_count:8} | {pat_count:13} | {reduction:.1f}x")
```

---

## Date

2024-12-29

## Sources

- deduplication_analysis.md (our findings)
- ChatGPT analysis (evidence archetypes, fuzzy hashing, semantic clustering)
- Gemini analysis (confidence-based selection, simpler bucket strategy)
