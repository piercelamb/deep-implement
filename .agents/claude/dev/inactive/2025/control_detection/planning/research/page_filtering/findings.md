# Page Filtering Research Findings

**Date**: 2023-12-23
**Experiment**: `template_policies`
**Scoring Mode**: `CONTROL_COVERAGE`
**Threshold**: `SCORE_THRESHOLD = 0.48`

## Research Question

> Given our setup with ColModernVBERT and the score threshold defined in `experiment_config.py`, does a single page of a policy ever get filtered out (across all policies)?

## Key Finding

**No pages are filtered out.** Every page in every policy has at least one control scoring above the 0.48 threshold.

However, the threshold **is effective at filtering controls per page**, reducing the LLM's workload significantly.

## Data

### Page-Level Analysis (100 pages sampled from 10 policies)

| Metric | Value |
|--------|-------|
| Total policies analyzed | 37 |
| Total pages | 416 |
| Pages triggering LLM | 416 (100%) |
| Pages filtered out | 0 (0%) |

### Max Score Per Page Distribution

The maximum control score on each page (i.e., the score that determines if the page triggers an LLM call):

| Percentile | Max Score |
|------------|-----------|
| Min | 0.5167 |
| P10 | 0.5461 |
| P25 | 0.5680 |
| Median | 0.5882 |
| P75 | 0.6076 |
| P90 | 0.6215 |
| Max | 0.6623 |

**The minimum max-score (0.517) is already above our threshold (0.48).** ColModernVBERT consistently finds at least one high-scoring control on every page.

### Threshold Required for Page Filtering

To filter X% of pages, you would need:

| Pages Filtered | Threshold Required |
|----------------|-------------------|
| 5% | > 0.5348 |
| 10% | > 0.5461 |
| 20% | > 0.5642 |
| 30% | > 0.5738 |

### Control-Level Filtering (Where Reduction Actually Happens)

| Metric | Value |
|--------|-------|
| Total DCF controls | 779 |
| Controls above threshold per page (min) | 1 |
| Controls above threshold per page (median) | 97 |
| Controls above threshold per page (mean) | 128.5 |
| Controls above threshold per page (max) | 505 |
| **Average controls filtered per page** | **651/779 (83.5%)** |

## Actual Reduction Pipeline

```
779 total controls
    │
    ▼ SCORE_THRESHOLD (0.48) filters 83.5%
    │
~128 controls avg (median: 97)
    │
    ▼ MAX_CONTROLS_PER_LLM_CALL caps at 50
    │
50 controls max sent to LLM
```

**Overall reduction: 779 → 50 controls = 93.6% reduction per LLM call**

## Conclusions

1. **Page-level filtering is not happening** with the current threshold (0.48). Every page triggers an LLM call.

2. **Control-level filtering is highly effective.** The threshold filters out 83.5% of controls per page on average.

3. **The hard cap (50 controls) provides additional reduction.** Combined with threshold filtering, we go from 779 → 50 controls per page.

4. **ColModernVBERT is "promiscuous"** - it always finds at least one control that scores reasonably high on any page of a policy document. This is expected behavior for a retrieval model.

5. **Raising the threshold would reduce recall.** Our 0.48 threshold was chosen for ~92% recall of ground truth controls. Raising it to filter pages would significantly hurt recall.

## Recommendations

1. **Keep current threshold (0.48)** - it's optimized for recall while still providing 83.5% control filtering.

2. **Don't expect page-level filtering** with semantic scoring. Policy documents are dense with compliance-relevant content.

3. **The 50-control cap is the key constraint** - ensures LLM prompt doesn't overflow regardless of how many controls pass threshold.

4. **Consider page-level heuristics** if page filtering is truly needed:
   - Skip pages with < N words (likely TOC/cover pages)
   - Skip pages matching boilerplate patterns
   - These would be pre-retrieval filters, not score-based

## Script Created

`ai_services/scripts/experiments/control_detection/analyze_filtered_pages.py`

Usage:
```bash
python -m ai_services.scripts.experiments.control_detection.analyze_filtered_pages
python -m ai_services.scripts.experiments.control_detection.analyze_filtered_pages --threshold 0.55
```
