# Control-Centric Mode Usage Guide

## Quick Start

```bash
# Run control-centric mode on a single document
python -m ai_services.scripts.experiments.control_detection.run_experiment \
    --mode control_centric \
    --row 0 \
    --experiment template_policies \
    --verbose
```

## CLI Arguments

### Mode Selection

| Argument | Values | Default | Description |
|----------|--------|---------|-------------|
| `--mode` | `page_centric`, `control_centric` | `page_centric` | Decision mode |
| `--batch-strategy` | `coherent`, `diverse` | `coherent` | Batching strategy (control-centric only) |
| `--max-calls` | integer | 50 | Max LLM calls per document |

### Common Arguments

| Argument | Description |
|----------|-------------|
| `--experiment` | Experiment name (`original` or `template_policies`) |
| `--row` | Process specific row index only |
| `--max-rows` | Limit number of documents to process |
| `--verbose` | Print detailed per-stage statistics |
| `--save` | Save results to JSON file |

### GCP/Gemini Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--gcp-project` | `ai-team-gemini-dev` | GCP project for Vertex AI |
| `--gcp-region` | `global` | GCP region |
| `--llm-model` | `gemini-3-flash-preview` | Gemini model to use |

## Usage Examples

### 1. Single Document Test

Test on a single policy document with verbose output:

```bash
python -m ai_services.scripts.experiments.control_detection.run_experiment \
    --mode control_centric \
    --row 0 \
    --experiment template_policies \
    --verbose
```

**Expected output:**
```
2025-12-23 10:30:45 - INFO - Running experiment: template_policies
2025-12-23 10:30:45 - INFO - Processing row 0: Information Security Policy
2025-12-23 10:30:46 - INFO - Filtered to 156 candidates (threshold=0.48)
2025-12-23 10:30:46 - INFO - Created 20 batches from 156 candidates
2025-12-23 10:30:47 - INFO - Created Gemini cache: projects/.../caches/abc123
2025-12-23 10:31:15 - INFO - Deleted Gemini cache: projects/.../caches/abc123
2025-12-23 10:31:15 - INFO -   P=75.0% R=82.1% F1=78.4% | Predicted: 28, GT: 23, TP: 21

======================================================================
EXPERIMENT RESULTS
======================================================================
Documents evaluated: 1
...
```

### 2. Full Experiment Run

Run on all template policies and save results:

```bash
python -m ai_services.scripts.experiments.control_detection.run_experiment \
    --mode control_centric \
    --experiment template_policies \
    --save
```

### 3. Compare with Page-Centric Baseline

```bash
# Run page-centric baseline
python -m ai_services.scripts.experiments.control_detection.run_experiment \
    --mode page_centric \
    --use-llm \
    --experiment template_policies \
    --row 0

# Run control-centric
python -m ai_services.scripts.experiments.control_detection.run_experiment \
    --mode control_centric \
    --experiment template_policies \
    --row 0
```

### 4. Custom Budget

Reduce LLM calls for faster/cheaper runs:

```bash
python -m ai_services.scripts.experiments.control_detection.run_experiment \
    --mode control_centric \
    --max-calls 25 \
    --row 0
```

### 5. Using Environment Variables

```bash
export CONTROL_DETECTION_GCP_PROJECT=my-gcp-project
export GCP_REGION=us-central1

python -m ai_services.scripts.experiments.control_detection.run_experiment \
    --mode control_centric \
    --experiment template_policies
```

## Understanding the Output

### Per-Document Metrics

```
P=75.0% R=82.1% F1=78.4% | Predicted: 28, GT: 23, TP: 21, FP: 7, FN: 2
```

- **P (Precision)**: Of predicted controls, how many are correct?
- **R (Recall)**: Of ground truth controls, how many were found?
- **F1**: Harmonic mean of precision and recall
- **Predicted**: Total controls predicted by the model
- **GT**: Ground truth controls for this document
- **TP**: True positives (correct predictions)
- **FP**: False positives (incorrect predictions)
- **FN**: False negatives (missed controls)

### Aggregate Metrics

```
======================================================================
EXPERIMENT RESULTS
======================================================================
Documents evaluated: 37

Counts:
  Ground truth controls: 779
  Predicted controls:    892
  True positives:        623
  False positives:       269
  False negatives:       156

Micro-averaged (pooled across all docs):
  Precision: 69.8%
  Recall:    80.0%
  F1:        74.5%

Macro-averaged (mean of per-doc metrics):
  Precision: 72.3%
  Recall:    78.5%
  F1:        75.2%
======================================================================
```

## Output Files

### Results JSON

When using `--save`, results are written to:
```
ai_services/scripts/experiments/control_detection/files/experiments/<experiment>/experiment_results.json
```

**Structure:**
```json
{
  "summary": {
    "total_documents": 37,
    "total_ground_truth": 779,
    "total_predicted": 892,
    "total_true_positives": 623,
    "total_false_positives": 269,
    "total_false_negatives": 156,
    "micro_precision": 0.698,
    "micro_recall": 0.800,
    "micro_f1": 0.745
  },
  "results": [
    {
      "row_index": 0,
      "policy_name": "Information Security Policy",
      "ground_truth": ["DCF-1", "DCF-5", ...],
      "predicted": ["DCF-1", "DCF-5", "DCF-12", ...],
      "true_positives": ["DCF-1", "DCF-5", ...],
      "false_positives": ["DCF-12", ...],
      "false_negatives": [...],
      "precision": 0.75,
      "recall": 0.821,
      "f1": 0.784,
      "source": "control_centric"
    }
  ]
}
```

## Troubleshooting

### "Cache creation failed"

**Cause**: PDF too large or invalid format

**Solutions:**
1. Check PDF file exists and is valid
2. Try a smaller PDF first
3. Check GCP project quota

### "ResourceExhausted" errors

**Cause**: Gemini API rate limits

**Solutions:**
1. Reduce `--max-calls` (fewer batches)
2. Reduce semaphore limit in config
3. Wait and retry (automatic with tenacity)

### "No candidates above threshold"

**Cause**: All controls scored below 0.48 threshold

**Solutions:**
1. Check document content is relevant
2. Verify ColModernVBERT embeddings are correct
3. Consider lowering threshold (in config)

### Orphaned Gemini Caches

If interrupted, caches should auto-delete via `asyncio.shield()`. To manually clean up:

```python
from google.genai import Client

client = Client(vertexai=True, project="ai-team-gemini-dev", location="global")
for cache in client.caches.list():
    if cache.display_name.startswith("control_centric_"):
        client.caches.delete(name=cache.name)
        print(f"Deleted: {cache.name}")
```

## Configuration Reference

### Default Values (`experiment_config.py`)

```python
# Score threshold for candidate filtering
SCORE_THRESHOLD = 0.48

# Maximum LLM calls per document
MAX_CALLS_PER_DOCUMENT = 50

# Target controls per batch
TARGET_BATCH_SIZE = 8

# Concurrent API calls
CONTROL_CENTRIC_SEMAPHORE_LIMIT = 10

# Gemini model
DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"

# GCP settings
DEFAULT_GCP_PROJECT = "ai-team-gemini-dev"
DEFAULT_VERTEX_LOCATION = "global"
```

### Cluster Cache Location

```
ai_services/scripts/experiments/control_detection/files/control_clusters.json
```

This file is pre-computed and should not need regeneration unless:
- The embedding model changes
- New controls are added to dcf_controls.csv

## Testing

### Run Unit Tests

```bash
# All control-centric tests
uv run pytest tests/scripts/experiments/control_detection/test_control_centric_decider.py -v

# CLI integration tests
uv run pytest tests/scripts/experiments/control_detection/test_run_experiment_integration.py -v

# All related tests
uv run pytest tests/scripts/experiments/control_detection/ -k "control_centric or batching or clustering or retrieval_anchors" -v
```

### Smoke Test

```bash
# Quick sanity check on one document
python -m ai_services.scripts.experiments.control_detection.run_experiment \
    --mode control_centric \
    --row 0 \
    --experiment template_policies \
    --max-calls 5 \
    --verbose
```
