# Peakiness (Within-Document Z-Score) Experiment Results

## Status: FAILED - No Improvement Over Raw Score Thresholding

## The Problem

When using ColModernVBERT for control-to-policy matching, we face a filtering challenge:

**Score Distribution Overlap**: Ground-truth (GT) and non-GT controls have heavily overlapping score distributions. This makes raw score thresholding ineffective at high recall levels.

| Threshold | Recall | Controls Passing | Filtered |
|-----------|--------|------------------|----------|
| 0.44      | 100%   | 746/779          | 4%       |
| 0.48      | ~92%   | 530/779          | 32%      |
| 0.50      | ~76%   | 360/779          | 54%      |

At 100% recall, we can only filter 4% of controls - leaving far too many candidates for downstream processing.

## The Hypothesis

**Peakiness**: Relevant controls should "spike" on 1-2 specific pages (the pages that actually address that control), while irrelevant controls should score more uniformly across all pages.

We hypothesized that computing a within-document z-score ("peakiness") for each control would reveal this pattern:

```
z_peak = (max_score - mean_score) / (std_score + epsilon)
```

Where:
- `max_score` = highest score across all pages for this control
- `mean_score` = average score across all pages
- `std_score` = standard deviation of scores across pages
- `epsilon` = small constant to avoid division by zero

**Expected Behavior**:
- **Relevant controls**: High z_peak (concentrated signal on specific pages)
- **Irrelevant controls**: Low z_peak (diffuse signal across pages)

## The Experiment

### Implementation

Created `analyze_peakiness.py` to:
1. Build a score matrix (num_pages x num_controls) using CONTROL_COVERAGE scoring
2. Compute peakiness statistics for each control
3. Compare z_peak distributions between GT and non-GT controls
4. Test filtering at various z_peak thresholds

### Test Data

- **Document**: Asset Management Policy (Row 4 from DCF dataset)
- **Controls**: 779 total (17 ground-truth, 762 non-GT)
- **Pages**: 2 pages
- **Scoring Mode**: CONTROL_COVERAGE ("How much of this control is covered by the page?")

## Results

### Peakiness Distribution Analysis

```
GT Controls (n=17):
  z_peak: mean=1.42, std=0.78, median=1.21, min=0.54, max=3.25

Non-GT Controls (n=762):
  z_peak: mean=1.40, std=0.67, median=1.16, min=0.10, max=4.20

Median Gap: 0.05 (GT median only 0.05 higher than non-GT)
```

**The distributions overlap almost completely.** There is no meaningful separation between GT and non-GT z_peak values.

### Filtering Results (Peakiness Only)

| z_peak Threshold | Recall | Controls Passing | Filtered |
|------------------|--------|------------------|----------|
| 0.50             | 100%   | 779/779          | 0%       |
| 0.75             | 100%   | 766/779          | 2%       |
| 1.00             | 94%    | 632/779          | 19%      |
| 1.25             | 65%    | 417/779          | 46%      |
| 1.50             | 59%    | 315/779          | 60%      |

At 100% recall, peakiness filtering removes 0% of controls - worse than raw score thresholding.

### Combined Filtering (Raw Score + Peakiness)

We tested whether combining both filters could improve over raw score alone:

```
Pass = (max_score >= raw_threshold) AND (z_peak >= z_threshold)
```

**Result**: Combined filtering provides +0% improvement over raw score alone at matched recall levels.

At ~92% recall:
- Raw score only: 530/779 pass (32% filtered)
- Combined: 530/779 pass (32% filtered) - identical

## Why It Failed

### The Hypothesis Was Wrong

The assumption that relevant controls "spike" on specific pages while irrelevant controls score uniformly is **not supported by the data**.

**Actual Behavior**:
- Both relevant and irrelevant controls show similar peakiness patterns
- The z_peak distributions overlap almost completely
- There is no signal in peakiness that isn't already captured by raw score

### Possible Explanations

1. **Document characteristics**: With only 2 pages, there may not be enough variance to distinguish peakiness patterns.

2. **Control structure similarity**: Both relevant and irrelevant controls may have similar linguistic structures that cause similar score variance patterns.

3. **CONTROL_COVERAGE scoring behavior**: The scoring method may naturally produce similar variance patterns regardless of semantic relevance.

4. **The spike hypothesis is fundamentally flawed**: Controls may not exhibit the expected "spike vs uniform" behavior in practice.

## Conclusion

**Peakiness (within-document z-score) is not a viable filtering mechanism for this task.**

The recommended approach is to use raw CONTROL_COVERAGE score thresholding with threshold 0.48, accepting:
- ~92% recall (may miss ~8% of relevant controls)
- 32% filtering (reduces candidate set by nearly 1/3)

## Future Directions

Given this failure, the following experiments from `next_experiments.md` remain candidates:

1. **Control Co-occurrence Graph (Anchor & Drag)** - Use high-confidence matches to pull related controls
2. **Domain-First Hierarchical Retrieval** - Coarse domain filtering before fine-grained scoring
3. **BiModernVBERT** - Page-centric scoring instead of control-centric
4. **Lightweight Score Calibrator** - Train a small calibration model on validation set

## Files

- `analyze_peakiness.py` - Implementation of the peakiness experiment
- `run_experiment.py` - Updated with SCORE_THRESHOLD = 0.48
- `next_experiments.md` - Original experiment proposals
