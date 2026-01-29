# Experiment 2: Increased Top-K Limit (100)

**Date**: 2025-12-23
**Experiment**: `template_policies`

## Changes from Experiment 1

- **Top-K limit increased**: 50 → 100 candidates per LLM call
- Goal: Improve retrieval ceiling to allow LLM to see more GT controls

## Hyperparameters

### Embedding Stage (ColModernVBERT)
| Parameter | Value |
|-----------|-------|
| Scoring mode | `control_coverage` |
| Score threshold | `0.48` |
| Max controls per LLM call | `100` |

### LLM Stage (Gemini)
| Parameter | Value |
|-----------|-------|
| Model | `gemini-3-flash-preview` |
| Vertex location | `global` |
| Temperature | `0.1` |
| Trigger threshold | `0.48` |
| Candidate threshold | `0.48` |
| Max candidates | `100` |
| Max concurrent calls | `10` |

### Neighbor Inclusion
| Parameter | Value |
|-----------|-------|
| Enabled | `true` |
| Threshold ratio | `0.5` |
| Max total pages | `5` |

## Dataset

| Metric | Value |
|--------|-------|
| Experiment | `template_policies` |
| Documents evaluated | 35 |
| Ground truth controls | 512 |

## Retrieval Stage Metrics

### Counts
| Metric | Value |
|--------|-------|
| Ground truth controls | 512 |
| GT above threshold (0.48) | 480 |
| GT in top-100 (sent to LLM) | 418 |
| GT lost at threshold | 32 |
| GT lost at top-K cap | 62 |

### Recall Metrics
| Metric | Value |
|--------|-------|
| Embedding recall (>= threshold) | 93.8% (480/512) |
| Top-K recall (top 100) | 81.6% (418/512) |

**Interpretation**: Increasing top-K from 50 to 100 improved the retrieval ceiling from 77.0% to 81.6%. The **maximum possible recall for the LLM stage is now 81.6%**.

## LLM Stage Results

### Counts
| Metric | Value |
|--------|-------|
| Ground truth controls | 512 |
| Predicted controls | 429 |
| True positives | 156 |
| False positives | 273 |
| False negatives | 356 |

### Micro-averaged (pooled across all docs)
| Metric | Value |
|--------|-------|
| Precision | 36.4% |
| Recall | 30.5% |
| F1 | 33.2% |

### Macro-averaged (mean of per-doc metrics)
| Metric | Value |
|--------|-------|
| Precision | 40.3% |
| Recall | 37.4% |
| F1 | 31.7% |

### LLM Performance (adjusted for retrieval ceiling)
| Metric | Value |
|--------|-------|
| Recall vs GT sent to LLM | 37.3% (156/418) |
| GT lost before LLM | 94 (18.4%) |
| GT lost by LLM | 262 (51.2%) |

## Comparison with Experiment 1

| Metric | Exp 1 (top-50) | Exp 2 (top-100) | Change |
|--------|----------------|-----------------|--------|
| Top-K Recall | 77.0% | 81.6% | +4.6% |
| LLM Precision | 42.0% | 36.4% | -5.6% |
| LLM Recall | 34.3% | 30.5% | -3.8% |
| LLM F1 | 37.7% | 33.2% | -4.5% |
| Recall vs candidates | 44.5% | 37.3% | -7.2% |

## Analysis

### Key Findings

1. **Retrieval ceiling improved**: Top-K recall increased from 77.0% to 81.6%, meaning more GT controls are now sent to the LLM.

2. **LLM performance degraded**: Despite seeing more candidates, the LLM performed worse:
   - Precision dropped from 42.0% to 36.4%
   - Recall dropped from 34.3% to 30.5%
   - LLM-adjusted recall dropped from 44.5% to 37.3%

3. **More candidates hurt accuracy**: With 100 candidates instead of 50, the LLM appears to be:
   - Overwhelmed by too many similar controls
   - Making more false positives (273 vs 325, but lower precision)
   - Missing more GT controls it was shown (37.3% vs 44.5%)

### Hypothesis

The LLM may be struggling with the larger candidate set because:
1. More similar-looking controls create confusion
2. Context window is diluted with low-relevance candidates
3. The 50→100 controls that were added are borderline matches that confuse the model

### Potential Next Steps

1. **Find optimal top-K**: Try values between 50-100 (e.g., 60, 70, 75)
2. **Prompt tuning**: Adjust prompts to be more selective with larger candidate sets
3. **Two-stage approach**: Use top-100 for recall, then re-rank to top-50 for precision
4. **Better threshold tuning**: Instead of fixed top-K, use score-based cutoff

## Commands

```bash
# Full experiment with LLM
uv run python -m ai_services.scripts.experiments.control_detection.run_experiment \
    --experiment template_policies \
    --use-llm

# Retrieval metrics only (no LLM calls)
uv run python -m ai_services.scripts.experiments.control_detection.compute_retrieval_metrics \
    --experiment template_policies
```
