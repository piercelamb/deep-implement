# False Positive Deduplication Analysis

## Executive Summary

The original plan anticipated 10-17x reduction through pattern deduplication based on `(control_id, IR_rule, evidence_hash)`. Testing on real experiment data revealed this assumption doesn't hold because **evidence quotes are unique per policy document**. The implementation was modified to use `(control_id, IR_rule)` as the signature, achieving **2.2x reduction** (4,104 FPs → 1,878 patterns).

---

## Data Source

- **Experiment**: 20251228_172545 (Experiment 5 with expanded IR rules)
- **Ground Truth**: `eval2_to_policy_mapping.json` (702 GT controls after filtering)
- **Policies**: 33 policies with FPs (out of 37 total)
- **Total FPs Collected**: 4,104

---

## Testing Methodology

### Step 1: Collect All False Positives

```python
all_fps = []
for row in eval2_data.get("rows", []):
    policy_name = row.get("policy_name", "")
    gt_controls = set(row.get("controls", []))
    fps = collect_false_positives(
        experiment_timestamp="20251228_172545",
        policy_name=policy_name,
        llm_output_dir=llm_output_dir,
        ground_truth_controls=gt_controls,
        control_metadata=control_metadata,
    )
    all_fps.extend(fps)
# Result: 4,104 FPs
```

### Step 2: Test Different Signature Strategies

Three deduplication strategies were tested:

| Strategy | Signature | Patterns | Reduction |
|----------|-----------|----------|-----------|
| Control only | `control_id` | 702 | 5.8x |
| Control + IR | `(control_id, IR_rule)` | 1,878 | **2.2x** |
| Control + IR + Evidence | `(control_id, IR_rule, evidence_hash)` | 4,100 | 1.0x |

### Step 3: Analyze Why Evidence-Based Deduplication Fails

Investigation revealed the root cause:

```
DCF-13 appears in 31 FPs across 31 policies:
  - Policy: Acceptable Use Policy
    IR: IR-9
    Evidence: "This policy specifies acceptable use of end-user computing d..."
  - Policy: AI Governance Policy
    IR: IR-3
    Evidence: "The purpose of this policy is to outline [COMPANY NAME]'s co..."
  - Policy: AI Risk Management Policy
    IR: IR-6
    Evidence: "This policy outlines the principles and procedures for the r..."
```

**Key Finding**: The same control (DCF-13) is incorrectly mapped across many policies, but with **different evidence quotes** because each quote comes from the actual policy document text. The LLM cites different passages from each policy.

---

## Conclusions

### 1. Original Plan Assumption Was Incorrect

The plan stated:
> If "DCF-107 + IR-2 + encryption language" appears 45 times across 12 policies, that's ONE pattern.

**Reality**: "Encryption language" is different in every policy because it's quoted from the policy itself. Even when the same control is incorrectly mapped using the same IR rule, the evidence is unique.

### 2. The 10-17x Reduction Estimate Was Overly Optimistic

| Expected | Actual |
|----------|--------|
| 5,287 → 300-500 patterns (10-17x) | 4,104 → 1,878 patterns (2.2x) |

### 3. `(control_id, IR_rule)` Is the Most Useful Signature

This grouping answers: "Which controls are being incorrectly mapped using which reasoning patterns?"

Benefits:
- Groups the same failure mode across policies
- 2.2x reduction is meaningful (halves the analysis work)
- Top patterns clearly show problem areas

### 4. Frequency Distribution Shows Clear Pareto Pattern

```
Frequency Distribution:
  Freq 1:     995 patterns (53%)
  Freq 2-5:   764 patterns (41%)
  Freq 6-10:  106 patterns (6%)
  Freq 11-20:  12 patterns (<1%)
  Freq 21+:     1 pattern  (<1%)

Pareto: Top 20% of patterns (375) cover 48% of FPs (1,967)
```

---

## Implementation Modifications

### Original Implementation (from plan)

```python
def compute_pattern_signature(fp: FalsePositive) -> str:
    control_id = fp.control_id
    ir_rule = extract_primary_ir_rule(fp.llm_reasoning) or "NONE"
    evidence_hash = normalize_evidence_hash(fp.llm_evidence_quote)
    signature_parts = f"{control_id}|{ir_rule}|{evidence_hash}"
    return hashlib.md5(signature_parts.encode()).hexdigest()
```

### Modified Implementation

```python
def compute_pattern_signature(
    fp: FalsePositive,
    include_evidence: bool = False,  # NEW: Optional evidence inclusion
) -> str:
    control_id = fp.control_id
    ir_rule = extract_primary_ir_rule(fp.llm_reasoning) or "NONE"

    if include_evidence:
        evidence_hash = normalize_evidence_hash(fp.llm_evidence_quote)
        signature_parts = f"{control_id}|{ir_rule}|{evidence_hash}"
    else:
        signature_parts = f"{control_id}|{ir_rule}"  # DEFAULT: No evidence

    return hashlib.md5(signature_parts.encode()).hexdigest()
```

**Rationale**: Default to `(control_id, IR_rule)` for practical reduction, but allow `include_evidence=True` for stricter grouping if needed.

---

## Top 10 Patterns (Most Frequent)

These patterns represent the most common failure modes:

| Rank | Control | IR Rule | Frequency | Policies |
|------|---------|---------|-----------|----------|
| 1 | DCF-13 | IR-6 | 23 | 23 |
| 2 | DCF-161 | IR-1 | 20 | 20 |
| 3 | DCF-326 | IR-3 | 19 | 19 |
| 4 | DCF-633 | IR-3 | 16 | 16 |
| 5 | DCF-481 | IR-4 | 14 | 14 |
| 6 | DCF-42 | IR-4 | 13 | 13 |
| 7 | DCF-697 | IR-1 | 13 | 13 |
| 8 | DCF-193 | IR-3 | 13 | 13 |
| 9 | DCF-655 | IR-3 | 12 | 12 |
| 10 | DCF-415 | IR-3 | 11 | 11 |

**Insight**: IR-3 (Semantic Equivalence) appears in 4 of the top 10 patterns, confirming the distribution analysis that IR-3 is the most abused rule.

---

## IR Rule Distribution in FPs

From Split 2 distribution analysis:

| IR Rule | FP Count | % of Total | Pattern Count |
|---------|----------|------------|---------------|
| IR-3 (Semantic Equivalence) | 1,345 | 32.8% | 1,345 |
| IR-1 (Hierarchical Scope) | 671 | 16.3% | 670 |
| IR-2 (Tech→Abstract) | 640 | 15.6% | 640 |
| IR-4 (Governance→Procedure) | 587 | 14.3% | 587 |
| IR-6 (Existence Inference) | 412 | 10.0% | 412 |
| IR-9 (Standard Reference) | 203 | 4.9% | 203 |
| IR-7 (Prohibition Inference) | 64 | 1.6% | 64 |
| IR-5 (Frequency Equivalence) | 62 | 1.5% | 61 |
| None | 52 | 1.3% | 52 |
| IR-10 (Disjunction) | 36 | 0.9% | 36 |
| IR-8 (Binding Inheritance) | 32 | 0.8% | 32 |

---

## Recommendations for Split 4 (Sampling)

Given the 2.2x reduction (not 10-17x), sampling may still be useful:

1. **If analyzing all 1,878 patterns**: ~$100-200 LLM cost (acceptable)
2. **If sampling to ~500 patterns**: Focus on:
   - All patterns with frequency ≥ 6 (119 patterns)
   - Coverage of all IR rules
   - Coverage of all policies
   - Random sample from frequency=1 patterns

### Suggested Sampling Strategy

```
Bucket A: High-frequency patterns (freq ≥ 6)     → 119 patterns (mandatory)
Bucket B: Medium-frequency (freq 2-5)            → Sample 200
Bucket C: Low-frequency (freq 1) for diversity   → Sample 181
Total                                            → ~500 patterns
```

---

## Files Modified

| File | Change |
|------|--------|
| `deduplicate_fps.py` | Added `include_evidence` parameter (default False) |
| `test_deduplicate_fps.py` | Added tests for both signature modes |
| `__init__.py` | Exported new deduplication functions |

---

## Test Results

All tests passing after modifications:

```
tests/scripts/experiments/control_detection/false_positive_validation/
├── test_fp_models.py         (17 tests) ✓
├── test_fp_collector.py      (12 tests) ✓
├── test_analyze_fp_distribution.py (19 tests) ✓
└── test_deduplicate_fps.py   (29 tests) ✓

Total: 77 tests passing
```

---

## Date

2024-12-29

## Author

Claude (Split 3 implementation)
