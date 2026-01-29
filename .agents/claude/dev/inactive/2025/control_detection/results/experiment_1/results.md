# Experiment 1: Baseline LLM Control Detection

**Date**: 2025-12-23
**Experiment**: `template_policies`

## Hyperparameters

### Embedding Stage (ColModernVBERT)
| Parameter | Value |
|-----------|-------|
| Scoring mode | `control_coverage` |
| Score threshold | `0.48` |
| Max controls per LLM call | `50` |

### LLM Stage (Gemini)
| Parameter | Value |
|-----------|-------|
| Model | `gemini-3-flash-preview` |
| Vertex location | `global` |
| Temperature | `0.1` |
| Trigger threshold | `0.48` |
| Candidate threshold | `0.48` |
| Max candidates | `50` |
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
| Documents evaluated | 37 |
| Ground truth controls (filtered) | 686 |
| GT controls filtered (invalid) | 48 of 734 |

## Retrieval Stage Metrics

These metrics measure the ColModernVBERT embedding recall before the LLM stage.

### Counts
| Metric | Value |
|--------|-------|
| Ground truth controls | 686 |
| GT above threshold (0.48) | 654 |
| GT in top-50 (sent to LLM) | 528 |
| GT lost at threshold | 32 |
| GT lost at top-K cap | 126 |

### Recall Metrics
| Metric | Micro | Macro |
|--------|-------|-------|
| Embedding recall (>= threshold) | 95.3% (654/686) | 93.2% |
| Top-K recall (top 50) | 77.0% (528/686) | 77.9% |

**Interpretation**: The embedding stage captures 95.3% of ground truth controls above the threshold, but the top-50 cap reduces this to 77.0%. This means the **maximum possible recall for the LLM stage is 77%** - any GT control not in the top-50 candidates cannot be selected.

## LLM Stage Results

### Counts
| Metric | Value |
|--------|-------|
| Ground truth controls | 686 |
| Predicted controls | 560 |
| True positives | 235 |
| False positives | 325 |
| False negatives | 451 |

### Micro-averaged (pooled across all docs)
| Metric | Value |
|--------|-------|
| Precision | 42.0% |
| Recall | 34.3% |
| F1 | 37.7% |

### Macro-averaged (mean of per-doc metrics)
| Metric | Value |
|--------|-------|
| Precision | 40.0% |
| Recall | 37.9% |
| F1 | 32.2% |

### LLM Performance (adjusted for retrieval ceiling)
| Metric | Value |
|--------|-------|
| Recall vs GT sent to LLM | 44.5% (235/528) |
| GT lost before LLM | 158 (23%) |
| GT lost by LLM | 293 (42.7%) |

## Analysis

### Retrieval Stage Findings

1. **Embedding threshold (0.48) is effective**: 95.3% of GT controls score above threshold, meaning only 32 controls are lost due to low similarity scores.

2. **Top-K cap is the bottleneck**: The 50-control cap loses 126 GT controls (18.4%) that would otherwise pass threshold. This creates a hard ceiling of 77% on recall.

3. **Retrieval ceiling limits LLM potential**: Even a perfect LLM could only achieve 77% recall given the current pipeline.

### LLM Stage Findings

1. **Low Recall (34.3%)**: The LLM is missing ~65% of ground truth controls. However:
   - 23% (158 controls) were never shown to the LLM (lost at top-K)
   - 42.7% (293 controls) were shown but not selected
   - LLM recall on candidates it actually sees: 44.5%

2. **Moderate Precision (42.0%)**: Of the controls the LLM selects, ~42% are correct. This means:
   - The LLM is predicting some controls that aren't in ground truth
   - Could be over-interpreting policy language
   - Or ground truth may be incomplete

3. **Predicted < Ground Truth (560 vs 686)**: The LLM is predicting fewer controls than exist in ground truth.

### Potential Improvements

1. **Increase top-K limit**: Raising from 50 to 100 candidates would improve the retrieval ceiling
2. **Prompt tuning**: Adjust prompts to be more inclusive of implied controls
3. **Lower LLM confidence threshold**: Accept more "medium" confidence predictions
4. **Multi-pass approach**: Run multiple passes with different prompts
5. **Ground truth analysis**: Verify ground truth quality and completeness

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
