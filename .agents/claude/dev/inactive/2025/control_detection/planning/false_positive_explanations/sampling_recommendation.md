# Sampling Recommendation: Reducing 5,287 FPs to Analyzable Set

*Synthesized from Claude, Gemini, and ChatGPT recommendations*

## The Problem

We have **5,287 false positives** across **37 policy documents**. Analyzing all of them is:
- **Expensive**: ~5,287 Gemini calls
- **Redundant**: Many FPs are the SAME failure pattern repeated
- **Time-consuming**: Even at 5 concurrent calls, this takes hours

**Goal**: Identify the failure patterns causing FPs so we can tighten the prompts.

## Critical Insight: Analyze Patterns, Not Instances

Most of those 5,287 FPs are **repeats of the same failure mode**. If Control X incorrectly maps to 30 policies using IR-2 with similar evidence, we don't need to judge all 30 — analyzing 2-3 representatives tells us the pattern.

**The key innovation**: Switch the unit of analysis from "FP instance" to "FP pattern."

## The Approach

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Phase 0: Distribution Analysis (Zero Cost)                              │
│  → Understand the FP landscape before any decisions                      │
├─────────────────────────────────────────────────────────────────────────┤
│  Phase 1: Pattern Deduplication (Critical)                               │
│  → 5,287 instances → ~300-500 unique patterns                            │
├─────────────────────────────────────────────────────────────────────────┤
│  Phase 2: Analyze Patterns                                               │
│  → If ≤500 patterns: Analyze ALL directly                                │
│  → If >500 patterns: Apply Pareto + Diversity sampling (see below)       │
└─────────────────────────────────────────────────────────────────────────┘
```

**Expected case**: Pattern deduplication reduces 5,287 → ~300-500 patterns, which is manageable to analyze directly.

**Fallback**: If deduplication still leaves 1000+ patterns, use the optional sampling strategy below.

---

## Phase 0: Distribution Analysis (Zero LLM Cost)

Before ANY sampling decisions, run a script to understand the FP landscape:

**Outputs:**
```
fps_by_control.csv      # control_id, fp_count, policies_list
fps_by_policy.csv       # policy_name, fp_count, controls_list
fps_by_confidence.csv   # confidence, fp_count
fps_by_ir_rule.csv      # ir_rule_cited, fp_count (parse from reasoning)
```

**What we'll learn:**
- Are 20 controls responsible for 80% of FPs? (Pareto distribution)
- Are 5 policies responsible for 50% of FPs? (permissive policies)
- Is IR-2 cited in 60% of FP reasonings? (over-applied rule)

This takes ~30 seconds and informs all subsequent decisions.

---

## Phase 1: Pattern Deduplication (The Big Win)

**Create a signature for each FP instance:**

```python
def compute_pattern_signature(fp: FalsePositive) -> str:
    """Group FPs by their failure pattern, not individual instance."""
    return hash((
        fp.control_id,                    # Same control
        extract_primary_ir_rule(fp.reasoning),  # Same IR rule cited
        normalize_evidence_hash(fp.evidence_quote[:200]),  # Similar evidence
    ))
```

**Why this works:**
- If "DCF-107 + IR-2 + encryption language" appears 45 times across 12 policies, that's ONE pattern with frequency=45
- Analyzing 2-3 instances of this pattern tells us everything
- The other 42 instances are redundant

**Expected reduction:**
- Input: 5,287 FP instances
- Output: ~200-500 unique patterns (10-25x reduction)
- Each pattern has a `frequency` (how many instances it covers)

---

## Phase 2 (Optional): Pareto + Diversity Sampling

**Only needed if pattern deduplication leaves >500 patterns.**

Once we have patterns, sample using **five buckets**:

### Bucket A: "Pareto Patterns" (~70% Coverage)

**Goal**: Fix the biggest problems first.

```python
# Sort patterns by frequency (descending)
# Take patterns until cumulative coverage reaches ~70%
patterns_sorted = sorted(patterns, key=lambda p: p.frequency, reverse=True)
cumulative = 0
pareto_patterns = []
for p in patterns_sorted:
    pareto_patterns.append(p)
    cumulative += p.frequency
    if cumulative >= total_fps * 0.70:
        break
```

**Yield**: The patterns that explain 70% of all FP instances.

### Bucket B: "Frequent Flyer Controls" (~60 samples)

**Goal**: Ensure we understand the most problematic controls.

- Take the **Top 20 controls** by FP count
- Sample **3 patterns** per control (from patterns not already in Bucket A)

**Why**: Fixing one promiscuous control could eliminate hundreds of FPs.

### Bucket C: "Policy Coverage" (~64 samples)

**Goal**: Ensure every policy document is represented.

- For **every policy** not yet covered
- Sample **2 patterns** from that policy

**Why**: Some policies may have unique failure modes not seen elsewhere.

### Bucket D: "IR Rule Coverage" (~50 samples)

**Goal**: Ensure every Interpretive Rule is represented.

- For **each IR rule (1-10)**
- Sample **5 patterns** where that rule was cited (from remaining)

**Why**: We need to understand how each rule fails.

### Bucket E: "Long Tail" (fill to target)

- Random sample from remaining patterns
- Ensures we don't miss rare but important failure modes

---

## Concrete Implementation

```python
import random
from collections import Counter, defaultdict

def sample_patterns(
    all_fps: list[FalsePositive],
    target_count: int = 200,
    pareto_coverage: float = 0.70,
) -> list[FalsePositive]:
    """
    Intelligent sampling: Patterns × Pareto × Diversity
    """
    # ─────────────────────────────────────────────────────────────
    # Step 1: Deduplicate into patterns
    # ─────────────────────────────────────────────────────────────
    patterns = defaultdict(list)
    for fp in all_fps:
        sig = (fp.control_id, extract_ir_rule(fp.reasoning))
        patterns[sig].append(fp)

    # Sort patterns by frequency
    sorted_patterns = sorted(patterns.items(), key=lambda x: len(x[1]), reverse=True)

    selected = []
    selected_sigs = set()

    def add_pattern(sig, fps, count=2):
        if sig not in selected_sigs:
            selected_sigs.add(sig)
            # Take up to `count` high-confidence examples
            sorted_fps = sorted(fps, key=lambda f: f.llm_confidence, reverse=True)
            selected.extend(sorted_fps[:count])

    # ─────────────────────────────────────────────────────────────
    # Bucket A: Pareto patterns (top patterns until 70% coverage)
    # ─────────────────────────────────────────────────────────────
    total_fps = len(all_fps)
    cumulative = 0
    for sig, fps in sorted_patterns:
        add_pattern(sig, fps, count=3)
        cumulative += len(fps)
        if cumulative >= total_fps * pareto_coverage:
            break

    # ─────────────────────────────────────────────────────────────
    # Bucket B: Top 20 controls (3 patterns each)
    # ─────────────────────────────────────────────────────────────
    control_counts = Counter(fp.control_id for fp in all_fps)
    top_20_controls = [c for c, _ in control_counts.most_common(20)]

    for ctrl in top_20_controls:
        ctrl_patterns = [(s, f) for s, f in sorted_patterns if s[0] == ctrl]
        for sig, fps in ctrl_patterns[:3]:
            add_pattern(sig, fps)

    # ─────────────────────────────────────────────────────────────
    # Bucket C: Every policy represented (2 patterns each)
    # ─────────────────────────────────────────────────────────────
    policies_covered = {fp.policy_name for fp in selected}
    all_policies = {fp.policy_name for fp in all_fps}

    for policy in all_policies - policies_covered:
        policy_fps = [fp for fp in all_fps if fp.policy_name == policy]
        if policy_fps:
            # Find a pattern from this policy
            for sig, fps in sorted_patterns:
                if any(fp.policy_name == policy for fp in fps):
                    add_pattern(sig, [fp for fp in fps if fp.policy_name == policy])
                    break

    # ─────────────────────────────────────────────────────────────
    # Bucket D: Every IR rule represented (5 patterns each)
    # ─────────────────────────────────────────────────────────────
    ir_rules_covered = {extract_ir_rule(fp.reasoning) for fp in selected}
    all_ir_rules = {extract_ir_rule(fp.reasoning) for fp in all_fps}

    for ir_rule in all_ir_rules - ir_rules_covered:
        ir_patterns = [(s, f) for s, f in sorted_patterns if s[1] == ir_rule]
        for sig, fps in ir_patterns[:5]:
            add_pattern(sig, fps)

    # ─────────────────────────────────────────────────────────────
    # Bucket E: Fill to target with random patterns
    # ─────────────────────────────────────────────────────────────
    remaining = [(s, f) for s, f in sorted_patterns if s not in selected_sigs]
    slots_left = target_count - len(selected)

    if slots_left > 0 and remaining:
        for sig, fps in random.sample(remaining, min(len(remaining), slots_left)):
            add_pattern(sig, fps, count=1)

    print(f"Sampled {len(selected)} FPs representing {len(selected_sigs)} patterns")
    print(f"  from population of {len(all_fps)} FPs in {len(patterns)} patterns")
    return selected
```

---

## Phase 3 (Optional): Sequential Expansion

Don't commit to a fixed sample size. Use **iterative refinement**:

1. **Start**: Analyze ~150 patterns from Phase 2
2. **After each batch of 50**: Compute root_cause distribution
3. **Stop when stable**: Last two batches change each category by <3%

```python
def is_distribution_stable(batch_n, batch_n_minus_1, threshold=0.03):
    """Check if root_cause distribution has stabilized."""
    for cause in all_causes:
        pct_n = batch_n.get(cause, 0) / sum(batch_n.values())
        pct_prev = batch_n_minus_1.get(cause, 0) / sum(batch_n_minus_1.values())
        if abs(pct_n - pct_prev) > threshold:
            return False
    return True
```

---

## Bonus: Cheap Pre-Triage (Before Judge)

Before spending judge tokens, auto-tag obvious failure categories:

| Pattern | Auto-Tag | How to Detect |
|---------|----------|---------------|
| Non-binding language | `NON_BINDING_LANGUAGE` | Evidence contains "may", "should", "can", "aim" |
| Missing specificity | `ABSTRACT_VS_SPECIFIC` | Control has numbers; evidence has none |
| Scope mismatch | `SCOPE_OVERREACH` | Control mentions "servers"; evidence mentions "employees" |
| Unrelated domain | `UNRELATED_DOMAIN` | Control is "clock sync"; policy is "HR" |

This pre-triage:
- Helps balance the sample (don't over-sample obvious failures)
- Speeds human review
- May eliminate some judge calls entirely

---

## Expected Results

| Stage | Count | Reduction |
|-------|-------|-----------|
| Raw FP instances | 5,287 | — |
| After pattern dedup | ~300-500 | **10-17x reduction** |
| **Patterns to analyze** | **~300-500** | — |

Each analyzed pattern "covers" many instances. If we analyze 400 patterns with average frequency ~13, we've effectively characterized all 5,287 FPs.

**If pattern count exceeds 500**: Apply optional Pareto + Diversity sampling to reduce to ~200 patterns.

---

## Implementation Plan

### Step 1: Build `analyze_fp_distribution.py` (Zero Cost)
- Parse batch files, output distribution CSVs
- Runtime: ~30 seconds

### Step 2: Build `deduplicate_fps.py`
- Group FPs into patterns by signature
- Output: patterns with frequencies

### Step 3: Review Distribution
- Is it Pareto? (likely yes)
- Which controls/rules dominate?

### Step 4: Implement Sampler in `fp_collector.py`
- Add `--sampling-strategy` flag: `random | stratified | all`
- Implement the bucket-based algorithm above

### Step 5: Run Initial Analysis
- Judge ~150-200 patterns
- Review root_cause distribution
- Decide if more sampling needed

---

## Why This Is Better Than Alternatives

| Approach | Pros | Cons |
|----------|------|------|
| **Analyze all 5,287** | Complete | Expensive, highly redundant |
| **Random 200 instances** | Simple | Misses long tail, over-represents dominant patterns |
| **Pattern dedup → analyze all** | Complete coverage, minimal redundancy | Requires dedup logic |

**The key win**: By deduplicating into patterns first, we analyze ~300-500 patterns instead of 5,287 instances. Those patterns cover ALL FPs, giving us complete understanding at 10-17x lower cost.
