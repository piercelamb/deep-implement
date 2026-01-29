# Experiment 9 Analysis

**Date:** 2026-01-02
**Comparison:** Experiment 8 (take3) → Experiment 9 (plamb_distilled)

## Historical Progression

| Experiment | Prompt | Recall | Precision | F1 |
|------------|--------|--------|-----------|-----|
| Exp 6 (baseline) | `fp_additions2` | 66.2% | 48.9% | 56.2% |
| Exp 7 (take2) | `fn_take2` | 72.7% | 35.6% | 47.8% |
| Exp 8 (take3) | `fn_take3` | 77.1% | 31.4% | 44.6% |
| **Exp 9 (distilled)** | `plamb_distilled` | **65.8%** | **40.2%** | **49.9%** |

**From Exp 8 to Exp 9:**
- Recall: -11.3pp (-14.7% relative)
- Precision: +8.9pp (+28.3% relative) ✓
- F1: +5.3pp (+11.9% relative) ✓

## Summary

Experiment 9 tested the `control_centric_plamb_distilled` prompt - a heavily simplified and distilled version of the prompt. The distilled prompt **dramatically improved precision** from 31.4% to 40.2% (+8.9pp), but at the cost of recall which dropped from 77.1% to 65.8%. Critically, **F1 improved by 5.3pp** to 49.9%, the best F1 score achieved since baseline.

This represents a fundamental trade-off shift: prioritizing precision over recall.

## Configuration Diff

| Parameter | Experiment 8 | Experiment 9 |
|-----------|--------------|--------------|
| Prompts | `control_centric_false_negatives_take3` | `control_centric_plamb_distilled` |
| Documents | 36 | 37 |
| Ground Truth | 577 | 585 |
| Model | `gemini-3-flash-preview` | `gemini-3-flash-preview` |

Note: Experiment 9 includes one additional document compared to Exp 8.

## Results Comparison

### Core Metrics

| Metric | Exp 8 | Exp 9 | Delta | % Change |
|--------|-------|-------|-------|----------|
| **Precision** | 31.38% | 40.23% | **+8.85pp** | +28.2% |
| **Recall** | 77.12% | 65.81% | -11.31pp | -14.7% |
| **F1** | 44.61% | 49.94% | **+5.33pp** | +11.9% |

### Counts

| Count | Exp 8 | Exp 9 | Delta | % Change |
|-------|-------|-------|-------|----------|
| Predicted | 1,418 | 957 | **-461** | -32.5% |
| True Positives | 445 | 385 | -60 | -13.5% |
| False Positives | 973 | 572 | **-401** | -41.2% |
| False Negatives | 132 | 200 | +68 | +51.5% |

### Retrieval (Unchanged)

| Metric | Exp 8 | Exp 9 |
|--------|-------|-------|
| Embedding Recall | 98.27% | 98.29% |
| Top-K Recall | 96.88% | 96.92% |

Retrieval performance is stable - the embedding/ranking stage is unchanged.

## Analysis

### Precision Improvement: +8.85pp

The distilled prompt achieved a massive reduction in false positives:
- **401 fewer false positives** (973 → 572)
- **41% reduction in FP rate**
- FP:TP ratio improved from 2.19:1 to 1.49:1

The distilled prompt appears to apply stricter matching criteria, rejecting marginal cases that the take3 prompt would accept.

### Recall Drop: -11.31pp

The stricter matching came at a cost:
- **60 fewer true positives** (445 → 385)
- **68 more false negatives** (132 → 200)
- The prompt is now missing 200/585 = 34.2% of ground truth controls

### Trade-off Analysis

For every true positive lost, the distilled prompt avoided ~6.7 false positives:
- TP lost: 60
- FP avoided: 401
- Ratio: 401/60 = **6.7 FP avoided per TP lost**

This is a favorable trade-off for F1, which is why F1 improved despite lower recall.

### MAPPED Predictions Statistics

| Statistic | Exp 8 | Exp 9 | Change |
|-----------|-------|-------|--------|
| Total MAPPED | 1,418 | 957 | -32.5% |
| Mean per document | 39.39 | 25.86 | -34.3% |
| Median per document | 31.5 | 20.0 | -36.5% |
| Min per document | 3 | 3 | 0% |
| Max per document | 240 | 193 | -19.6% |

**Observations:**
- ~26 MAPPED controls per document (down from ~39)
- More consistent predictions across documents
- Max outlier reduced from 240 to 193

## Per-Document Pattern Analysis

From the breakdown, documents fall into these categories:

| Pattern | Count | Documents |
|---------|-------|-----------|
| Best (F1 >= 75%) | 2 | Maintenance Mgmt, System Security Planning |
| Good (F1 >= 65%) | 4 | Network Security, PCI DSS, Data Retention, Incident Response |
| Mild over-mapping | 4 | Vendor Mgmt, Business Continuity, SDLC, Password |
| Both problems | 5 | Change Mgmt, Logging, Info Security, Encryption, Data Protection |
| Under-mapping | 3 | Physical Security, Vulnerability Mgmt, Risk Assessment |
| Over-mapping | 4 | AIMS, ISMS 2022, Public Cloud PII, Disaster Recovery |
| Massive over-mapping | 6 | ISMS+PIMS, Personal Data, Shared Responsibility, etc. |
| All wrong | 1 | Breach Notification |

**Key observations:**
- 6 documents still show "massive over-mapping" (precision < 15%, recall > 80%)
- 3 documents under-map (high precision, low recall)
- Only 2 documents achieve "best" performance (F1 >= 75%)

### Problem Documents

**Worst performers:**
1. **Breach Notification Policy** - 0% F1 (0 TP, 11 FP, 1 FN) - total failure
2. **Privacy, Use, and Disclosure Policy** - 5.6% precision, 100% recall - extreme over-mapping
3. **Business Associate Policy** - 8.3% precision - similar pattern

These policies have very few ground truth controls (1-2) but trigger many false positive mappings.

**Best performers:**
1. **Maintenance Management Policy** - 85.7% precision, 75% recall, 80% F1
2. **System Security Planning Policy** - 66.7% precision, 100% recall, 80% F1

These are smaller, more focused policies with clear control alignment.

## Stage 3 Implications

With Experiment 9's Stage 2 results:
- Process ~957 total verification calls across 37 documents
- Average ~26 calls per document (down from ~40)
- Need to reject ~60% of MAPPED controls to reach target precision

**Stage 3 precision target calculation:**
- Current: 385 TP, 572 FP (40.2% precision)
- Target 80% precision requires: 385 TP, 96 FP max
- Stage 3 must reject: 572 - 96 = **476 FP** (83.2% of FPs)
- While preserving: **385 TP** (0% TP loss ideal)

**Realistic scenario:**
- Stage 3 rejects 70% of FPs: 572 × 0.70 = 400 rejected → 172 FP remain
- Stage 3 incorrectly rejects 5% of TPs: 385 × 0.05 = 19 rejected → 366 TP remain
- Resulting precision: 366 / (366 + 172) = **68.0%**
- Resulting recall: 366 / 585 = **62.6%**
- Resulting F1: **65.2%**

This is more achievable than Exp 8's requirements.

## Time to First Prediction

| Statistic | Value |
|-----------|-------|
| Mean | 27.26s |
| Median | 21.28s |
| Min | 7.82s |
| Max | 91.49s |
| Docs with MAPPED | 37/37 (100%) |

**Observations:**
- Median of 21.3s is within the 30s latency target for most documents
- Mean pulled up by outliers
- Max of 91.5s suggests some documents significantly exceed latency budget
- All documents produced at least one MAPPED prediction

## Conclusions

1. **F1 improvement achieved**: 49.9% F1 is the best since baseline, and only ~6pp below baseline's 56.2%

2. **Precision vs recall trade-off shifted**: The distilled prompt prioritizes precision, making Stage 3's job easier but requiring Stage 3 to work harder on recall recovery

3. **Stage 3 workload reduced**: ~26 calls/doc vs ~40 calls/doc saves ~35% on Stage 3 compute

4. **Problem documents identified**: Policies with very few GT controls (1-3) consistently show massive over-mapping

5. **Latency mostly acceptable**: Median 21.3s meets 30s target, but tail cases need optimization

## Recommendations

1. **Proceed to Stage 3 testing** with distilled prompt outputs - the precision improvement makes Stage 3's verification task more tractable

2. **Investigate low-GT document behavior** - policies with 1-3 ground truth controls consistently fail. Consider:
   - Early termination when GT is likely very low
   - Different prompting strategy for sparse-control documents

3. **Hybrid approach consideration**:
   - Use distilled prompt for Stage 2 (precision-focused)
   - If Stage 3 confirms a MAPPED, consider running take3 prompt for that control group to catch missed TPs

4. **Latency optimization**: Investigate the 91.5s max outlier to ensure production SLAs are met

5. **Re-evaluate baseline comparison**: The experiment trajectory shows a classic precision-recall trade-off. The baseline (56.2% F1) might have been optimal, and subsequent experiments may have over-complicated the prompt.

## Prompt Philosophy: Distilled vs Complex

The distilled prompt's success suggests:
- **Simpler rules are more consistently applied** by the LLM
- **Complex nuanced rules** (like take3's G-10 restructure, PARTIAL redefinition, etc.) may confuse the model more than help
- **Strict matching** produces cleaner outputs for Stage 3 to verify

This raises the question: should Stage 3 use similarly distilled prompts, or can it afford more complexity given it's verifying 1 control at a time?
