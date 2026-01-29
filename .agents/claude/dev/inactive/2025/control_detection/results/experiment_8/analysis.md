# Experiment 8 Analysis

**Date:** 2026-01-01
**Comparison:** Experiment 7 (take2) → Experiment 8 (take3)

## Historical Progression

| Experiment | Prompt | Recall | Precision | F1 |
|------------|--------|--------|-----------|-----|
| Exp 6 (baseline) | `fp_additions2` | 66.2% | 48.9% | 56.2% |
| Exp 7 (take2) | `fn_take2` | 72.7% | 35.6% | 47.8% |
| **Exp 8 (take3)** | `fn_take3` | **77.1%** | **31.4%** | **44.6%** |

**Cumulative from baseline:**
- Recall: +10.9pp (+16.5% relative) ✓
- Precision: -17.5pp (-35.8% relative) ✗
- F1: -11.6pp (-20.6% relative)

## Summary

Experiment 8 tested the `control_centric_false_negatives_take3` prompt changes designed to improve recall. The changes successfully increased recall from 72.65% to 77.12% (+4.47 percentage points), but at the cost of precision which dropped from 35.59% to 31.38%.

## Configuration Diff

| Parameter | Experiment 7 | Experiment 8 |
|-----------|--------------|--------------|
| Prompts | `take2` | `take3` |
| Documents | 37 | 36 |
| Ground Truth | 585 | 577 |

Note: One document was excluded in Experiment 8 (likely due to PDF loading issue or ground truth cleanup).

## Results Comparison

### Core Metrics

| Metric | Exp 7 | Exp 8 | Delta | % Change |
|--------|-------|-------|-------|----------|
| **Precision** | 35.59% | 31.38% | -4.21pp | -11.8% |
| **Recall** | 72.65% | 77.12% | +4.47pp | +6.2% |
| **F1** | 47.78% | 44.61% | -3.17pp | -6.6% |

### Counts

| Count | Exp 7 | Exp 8 | Delta | % Change |
|-------|-------|-------|-------|----------|
| Predicted | 1,194 | 1,418 | +224 | +18.8% |
| True Positives | 425 | 445 | +20 | +4.7% |
| False Positives | 769 | 973 | +204 | +26.5% |
| False Negatives | 160 | 132 | -28 | -17.5% |

### Retrieval (Unchanged)

| Metric | Exp 7 | Exp 8 |
|--------|-------|-------|
| Embedding Recall | 98.29% | 98.27% |
| Top-K Recall | 96.92% | 96.88% |

Retrieval performance is stable - changes are within noise margin.

## Analysis

### Recall Improvement: +4.47pp

The take3 prompt changes successfully recovered more ground truth controls:
- **28 fewer false negatives** (160 → 132)
- **20 more true positives** (425 → 445)

Key prompt changes that likely contributed:
1. **G-10 restructure** with Primary vs Secondary qualifiers - reduced over-penalization
2. **PARTIAL redefinition** with Subset Rule - prevented incorrect NO_MATCH
3. **IR-8 Mechanism Subsumption** - allowed implicit mechanism recognition
4. **Soft blocker exception** - frequency gaps no longer block MAPPED

### Precision Drop: -4.21pp

The more permissive prompt also increased false positives significantly:
- **204 more false positives** (769 → 973)
- **FP:TP ratio on new predictions**: 204:20 = **10.2:1**

This was expected - the prompt intentionally relaxed several guardrails to capture more true positives. The 10:1 FP:TP ratio on marginal predictions suggests the boundary cases are predominantly false positives.

### F1 Trade-off

F1 dropped from 47.78% to 44.61% (-3.17pp). The recall gain wasn't sufficient to offset the precision loss. However, **F1 is not our primary optimization target** - we're optimizing for Stage 3 input quality:
- Higher recall means Stage 3 sees more true positives (better coverage)
- Stage 3's job is to reject false positives (precision recovery)

### MAPPED Predictions Statistics

New metric added in Experiment 8:

| Statistic | Value |
|-----------|-------|
| Total MAPPED | 1,418 |
| Mean per document | 39.39 |
| Median per document | 31.5 |
| Min per document | 3 |
| Max per document | 240 |

**Observations:**
- Average ~40 MAPPED controls per document = ~40 Stage 3 verification calls
- High variance (3 to 240) suggests some documents trigger many more mappings
- The max of 240 warrants investigation - possible prompt breakdown on that document

## Stage 3 Implications

With these Stage 2 results, Stage 3 will:
- Process ~1,400 total verification calls across 36 documents
- Average ~40 calls per document (plus ~50 Stage 2 calls = ~90 total LLM calls/doc)
- Need to reject ~70% of MAPPED controls to reach target precision

**Stage 3 precision target calculation:**
- Current: 445 TP, 973 FP (31.4% precision)
- Target 80% precision requires: 445 TP, 111 FP max
- Stage 3 must reject: 973 - 111 = **862 FP** (88.6% of FPs)
- While preserving: **445 TP** (0% TP loss ideal)

This is aggressive. A more realistic scenario:
- Stage 3 rejects 70% of FPs: 973 × 0.70 = 681 rejected → 292 FP remain
- Stage 3 incorrectly rejects 10% of TPs: 445 × 0.10 = 44 rejected → 401 TP remain
- Resulting precision: 401 / (401 + 292) = **57.9%**
- Resulting recall: 401 / 577 = **69.5%**

## Conclusions

1. **Recall goal partially met**: 77% vs target 80-85%. Further prompt tuning may help, but diminishing returns likely.

2. **Precision drop acceptable for Stage 3 pipeline**: The false positives will be Stage 3's problem. Better to have high recall into Stage 3.

3. **Stage 3 call budget**: ~40 verification calls per document is manageable. The max=240 outlier should be investigated.

4. **IR-8 fix validated**: No JSON degeneration errors after adding IR-8 to the enum.

## Recommendations

1. **Proceed to Stage 3 testing** using the current Stage 2 outputs
2. **Investigate the max=240 document** - check which policy and why it triggered so many mappings
3. **Monitor Stage 3 verification rate** - target 25-30% verification rate to achieve acceptable final precision
4. **Consider Stage 3 call cap** for production (e.g., 50 max per document) to bound costs

## Prompt Changes in take3

For reference, the key changes from take2 → take3:

1. **G-10 Restructure**: Primary qualifiers (domain, audience) vs Secondary (frequency, timing)
2. **PARTIAL Redefinition**: Subset Rule prevents incorrect NO_MATCH for subset coverage
3. **G-17 Refinement**: Policy-level test for input validation vs program validation
4. **IR-8 Addition**: Mechanism Subsumption rule for implicit mechanisms
5. **Soft Blocker Exception**: Frequency gaps explicitly not blocking MAPPED
6. **User Prompt Hard Rules**: Added explicit rules for frequency gaps and subset scope
