# Control-Centric LLM Decision Architecture

## Overview

The control-centric mode is an alternative approach to policy-to-control mapping that processes entire documents at once, rather than page-by-page. It uses Gemini's context caching to upload a policy document once, then makes batched LLM calls to evaluate groups of controls against the cached document.

## Comparison: Page-Centric vs Control-Centric

| Aspect | Page-Centric | Control-Centric |
|--------|--------------|-----------------|
| **Unit of analysis** | Single page | Entire document |
| **LLM calls** | 1 per triggered page | 1 per batch of controls |
| **Context** | Page image only | Full PDF (cached) |
| **Control grouping** | All candidates per page | Batched by cluster similarity |
| **Evidence** | Page number only | Exact quote + location |
| **Cost model** | Pay per page processed | Pay for cache + queries |

## Architecture Diagram

```
run_experiment.py --mode control_centric
    │
    ├── Load policy document (existing)
    │   └── PolicyDocument with page images
    │
    ├── ColModernVBERT scoring (existing)
    │   └── predictor.predict_document() → DocumentPrediction
    │       └── Per-page scores for all 779 DCF controls
    │
    └── ControlCentricDecider.decide_document()
        │
        ├── 1. Filter candidates
        │   └── doc_max_score[control] >= 0.48
        │   └── Typically ~100-200 candidates
        │
        ├── 2. Load cluster assignments
        │   └── ControlClusterCache.load(control_clusters.json)
        │   └── K-means clusters for coherent batching
        │
        ├── 3. Create coherent batches
        │   └── create_batches(candidates, cluster_map, max_calls=50)
        │   └── Groups similar controls together
        │
        ├── 4. Upload PDF to Gemini cache
        │   └── client.caches.create(model, pdf_bytes, system_prompt)
        │   └── Returns cache_name for reuse
        │
        ├── 5. Process batches in parallel
        │   └── asyncio.Semaphore(10) for rate limiting
        │   └── asyncio.gather(*[process_batch(b) for b in batches])
        │       └── Each batch: generate_content(cached_content=cache_name)
        │       └── Includes retrieval anchors (top pages per control)
        │
        ├── 6. Aggregate results
        │   └── Union of controls with addresses_control=True
        │   └── Evidence quotes and location references preserved
        │
        └── 7. Delete cache (shielded from cancellation)
            └── asyncio.shield(client.caches.delete(cache_name))
```

## Key Components

### 1. ControlCentricDecider (`control_centric_decider.py`)

The main orchestrator class that:
- Filters candidate controls by ColModernVBERT score threshold
- Creates batches using cluster assignments
- Manages Gemini cache lifecycle
- Coordinates parallel batch processing
- Aggregates results across all batches

**Key Configuration:**
```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ControlCentricConfig:
    max_calls_per_document: int = 50      # Budget for LLM calls
    target_batch_size: int = 8            # Controls per batch
    score_threshold: float = 0.48         # ColModernVBERT filter
    semaphore_limit: int = 10             # Concurrent API calls
    gcp_project: str = "ai-team-gemini-dev"
    vertex_location: str = "global"
    model_name: str = "gemini-3-flash-preview"
```

### 2. Control Clustering (`control_clustering.py`)

Pre-computed K-means clusters for coherent batching:
- **Purpose**: Group similar controls together so LLM can differentiate
- **Method**: Mean-pooled ColModernVBERT token embeddings
- **Clusters**: 75 clusters for 779 controls
- **Storage**: `files/control_clusters.json`

**Cluster Cache Structure:**
```json
{
  "embedding_source": "colmodernvbert_mean_pooled",
  "n_clusters": 75,
  "random_seed": 42,
  "control_ids": ["DCF-1", "DCF-2", ...],
  "cluster_assignments": [0, 0, 1, 2, ...]
}
```

### 3. Batching Algorithm (`batching.py`)

**Coherent Batching** (default):
- Groups controls from the same cluster together
- Helps LLM differentiate between similar controls
- "Yes to Control A, no to Control B because it lacks the qualifier..."

**Algorithm:**
1. Group candidates by cluster ID
2. Process clusters in order of total score (highest first)
3. Fill batches with controls from same cluster until target size
4. If cluster is smaller than target, continue to next cluster
5. Ensure total batches ≤ max_calls

### 4. Retrieval Anchors (`retrieval_anchors.py`)

Provides "search hints" to the LLM:
- Top 3 pages where each control scored highest
- Best score for that control
- Formatted as XML in the prompt

**Example Anchor:**
```xml
<retrieval_hints>
  <top_pages>12, 13, 14</top_pages>
  <best_score>0.72</best_score>
</retrieval_hints>
```

### 5. Prompts (`prompts/control_centric/`)

**System Prompt** (`system`):
- Defines the task: binary decision per control
- Specifies what counts as "binding language"
- Requires evidence quotes

**User Prompt** (`user`):
- Contains controls in XML format with retrieval hints
- Instructions for systematic evaluation

**Response Schema** (`response.json`):
```json
{
  "batch_results": [{
    "control_id": "DCF-182",
    "addresses_control": true,
    "confidence": "high",
    "evidence_quote": "All employees must complete...",
    "location_reference": "Page 3, Section 2.1",
    "reasoning": "Document contains binding requirement..."
  }]
}
```

## Data Flow

### Input → Output

```
Input:
├── policy_name: str (e.g., "Information Security Policy")
├── pdf_bytes: bytes (raw PDF content)
└── document_prediction: DocumentPrediction
    └── page_predictions: list[PagePrediction]
        └── top_controls: list[ScoredControl]
            ├── control: DCFControl
            ├── score: float
            └── page_num: int

Output:
└── DocumentControlCentricDecision
    ├── policy_name: str
    ├── total_candidates: int
    ├── total_batches: int
    └── batch_decisions: list[BatchDecision]
        └── results: list[ControlDecisionResult]
            ├── control_id: str
            ├── addresses_control: bool
            ├── confidence: str
            ├── evidence_quote: str
            ├── location_reference: str
            └── reasoning: str
```

### Conversion to Prediction

The `convert_control_centric_decision_to_prediction()` function transforms the control-centric output to the standard `Prediction` format for evaluation:

```python
def convert_control_centric_decision_to_prediction(
    decision: DocumentControlCentricDecision,
) -> Prediction:
    addressed = decision.get_addressed_controls()

    predicted_controls = tuple(
        ControlPrediction(
            control_id=result.control_id,
            confidence=result.confidence,
            reasoning=f"{result.reasoning} | Evidence: {result.evidence_quote}",
        )
        for result in addressed
    )

    return Prediction(
        predicted_controls=predicted_controls,
        source="control_centric",
    )
```

## Error Handling

### Retry Logic

Rate limits and timeouts are handled with tenacity:

```python
@retry(
    retry=retry_if_exception_type((ResourceExhausted, DeadlineExceeded)),
    wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def _call_gemini(self, cache_name: str, user_prompt: str) -> Any:
    ...
```

### Cache Cleanup

Cache deletion is shielded from cancellation to prevent orphaned caches:

```python
async def _delete_cache(self, cache_name: str) -> None:
    try:
        await asyncio.shield(loop.run_in_executor(None, delete))
    except asyncio.CancelledError:
        # Still try to delete even if cancelled
        await loop.run_in_executor(None, delete)
```

## Performance Characteristics

| Metric | Typical Value |
|--------|---------------|
| Candidates per document | 100-200 |
| Batches per document | 15-25 |
| Controls per batch | 5-10 |
| LLM calls per document | ≤50 (capped) |
| Concurrent API calls | 10 (semaphore) |
| Cache upload time | 5-15 seconds |
| Batch processing time | 2-5 seconds each |
| Total document time | 30-90 seconds |

## File Locations

```
ai_services/scripts/experiments/control_detection/
├── control_centric_decider.py    # Main orchestrator
├── control_clustering.py         # K-means clustering
├── batching.py                   # Batch creation algorithms
├── retrieval_anchors.py          # Top-page hints
├── experiment_config.py          # Configuration constants
├── run_experiment.py             # CLI entry point
├── prompts/
│   └── control_centric/
│       ├── system                # System prompt
│       ├── user                  # User prompt template
│       └── response.json         # JSON schema
└── files/
    └── control_clusters.json     # Pre-computed clusters

tests/scripts/experiments/control_detection/
├── test_control_centric_decider.py
├── test_control_clustering.py
├── test_batching.py
├── test_retrieval_anchors.py
└── test_run_experiment_integration.py
```
