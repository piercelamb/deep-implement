# Control-Centric Experiment Implementation Plan

## Overview

Implement a new "control-centric" LLM decision mode that:
- Caches full document (all pages) once
- Makes per-batch decisions with **coherent batching** (similar controls together for differentiation)
- Caps total LLM calls at **50 per document**
- **Requires evidence quotes** in responses
- Includes **retrieval anchors** (top pages per control from ColModernVBERT)
- Triggered via CLI flag: `--mode control_centric`

## Key Design Decisions (from user)

| Decision | Choice |
|----------|--------|
| Batching strategy | **Coherent batching** (similar controls together for differentiation) - with toggle for diverse |
| Evidence quotes | Required (LLM must cite specific text) |
| Candidate filtering | ColModernVBERT threshold (0.48) on doc-level max score |

## Design Refinements (from Gemini 3 analysis)

| Issue | Original | Refined |
|-------|----------|---------|
| Batching | Diverse (dissimilar controls) | **Coherent** (similar controls by cluster) - aids LLM differentiation |
| Page numbers | `page_numbers: int[]` | `location_reference: string` - allows section headers, avoids hallucination |
| Binding language | Strict "must/shall/required" | Broadened to include declarative statements ("The CISO reviews...") |
| Rate limits | Semaphore only | Add tenacity retry for 429 Resource Exhausted |
| Metrics | Final P/R/F1 only | Add per-stage logging (candidates filtered, batches created) |

## Design Refinements (from ChatGPT analysis)

| Issue | Original | Refined |
|-------|----------|---------|
| Candidate budgeting | Only threshold filter | Add explicit budget: `max_controls = max_calls × batch_size` with truncation rules |
| Clustering spec | Vague "reuse predictor" | Explicit: mean-pooled token embeddings, seed=42, versioned metadata |
| Retrieval anchors | None | Include top 3 pages per control in prompt as search hints |
| Binding language | Accept all declaratives | Only count declaratives in policy/requirements sections, not descriptions |
| Retry policy | Only ResourceExhausted | Also handle timeouts and add jitter |

---

## Files to Create

### 1. `control_centric_decider.py` (NEW)
Main orchestrator for control-centric LLM decisions.

```
ai_services/scripts/experiments/control_detection/control_centric_decider.py
```

**Classes:**
- `ControlCentricConfig` - Configuration dataclass
- `ControlCentricDecider` - Main decider class
- `ControlBatch` - Batch of controls to evaluate together
- `BatchDecision` - Result for one batch
- `DocumentControlCentricDecision` - Aggregated document-level result

**Key Methods:**
- `decide_document()` - Main entry point
  1. Compute doc-level max score per control (from ColModernVBERT)
  2. Filter to candidates above threshold (with budget enforcement)
  3. Compute retrieval anchors (top 3 pages per control)
  4. Create batches using pre-computed clusters (coherent by default)
  5. Upload document to Gemini cache
  6. Process batches in parallel (semaphore-limited)
  7. Aggregate results
  8. Delete cache (shielded)
- `_create_batches()` - Batching algorithm (coherent or diverse)
- `_process_batch()` - LLM call for one batch
- `_aggregate_batch_decisions()` - Combine batch results

### 2. `control_clustering.py` (NEW)
Pre-computed control clustering for batching.

```
ai_services/scripts/experiments/control_detection/control_clustering.py
```

**Classes:**
- `ControlClusterCache` - Cached cluster assignments

**Key Methods:**
- `compute_clusters()` - K-means on control embeddings
- `load_or_compute()` - Load from disk or compute fresh
- `get_cluster_id()` - Look up cluster for a control

**Clustering Specification (per ChatGPT):**
- **Embedding source**: Mean-pooled token embeddings from ColModernVBERT
  - Each control has (num_tokens, embedding_dim) tensor
  - Mean pool across tokens → single (embedding_dim,) vector per control
- **Algorithm**: K-means with n_clusters=75
- **Determinism**: `random_state=42` for reproducibility
- **Versioning metadata** in `control_clusters.json`:
  ```json
  {
    "embedding_source": "colmodernvbert_mean_pooled",
    "embedding_model_hash": "<hash>",
    "n_clusters": 75,
    "random_seed": 42,
    "created_at": "2025-12-23T...",
    "control_ids": [...],
    "cluster_assignments": [...]
  }
  ```
- **Invalidation**: Recompute if embedding model hash changes

### 3. `prompts/control_centric/` (NEW)
New prompts for control-centric mode with evidence requirements.

```
ai_services/scripts/experiments/control_detection/prompts/control_centric/
├── system
├── user
└── response.json
```

**System Prompt Key Changes:**
- Binary decision per control (not multi-select from page)
- Full document context available
- **Must quote binding language** from document
- Structured output per control in batch

**Response Schema:**
```json
{
  "batch_results": [
    {
      "control_id": "string",
      "addresses_control": "boolean",
      "confidence": "high|medium|low|none",
      "evidence_quote": "string (exact quote from document)",
      "location_reference": "string (page number OR section header)",
      "reasoning": "string"
    }
  ]
}
```

---

## Files to Modify

### 4. `run_experiment.py`
Add CLI flag and routing to control-centric mode.

**Changes:**
- Add `--mode` argument: `page_centric` (default) | `control_centric`
- Add control-centric specific args:
  - `--max-calls`: Max LLM calls per document (default: 50)
  - `--batch-strategy`: `coherent` (default) | `diverse`
- Add branch in main loop to call `ControlCentricDecider.decide_document()`
- Reuse existing: document loading, embedding scoring, evaluation, metrics

**Location:** Lines ~961-969 (add control-centric branch)

### 5. `experiment_config.py`
Add control-centric configuration defaults.

**Changes:**
- Add `MAX_CALLS_PER_DOCUMENT = 50`
- Add `DEFAULT_BATCH_STRATEGY = "coherent"`
- Add `CONTROL_CLUSTER_FILE = "files/control_clusters.json"`

---

## Test Structure

```
tests/scripts/experiments/control_detection/
├── __init__.py
├── test_control_clustering.py      # Unit tests for clustering
├── test_batching.py                # Unit tests for batching algorithms
├── test_retrieval_anchors.py       # Unit tests for anchor computation
├── test_control_centric_decider.py # Integration tests (mocked LLM)
└── conftest.py                     # Shared fixtures
```

### Test Fixtures (conftest.py)

```python
import pytest
from dataclasses import dataclass

@pytest.fixture
def sample_controls() -> list[DCFControl]:
    """10 sample controls for testing."""
    return [
        DCFControl(control_id=f"DCF-{i}", name=f"Control {i}", description=f"Description {i}")
        for i in range(10)
    ]

@pytest.fixture
def sample_cluster_map() -> dict[str, int]:
    """Cluster assignments: DCF-0,1,2 → cluster 0; DCF-3,4,5 → cluster 1; etc."""
    return {f"DCF-{i}": i // 3 for i in range(10)}

@pytest.fixture
def sample_scored_controls(sample_controls) -> list[ScoredControl]:
    """Scored controls with varying scores and page numbers."""
    return [
        ScoredControl(control=c, score=0.9 - i * 0.05, page_num=i % 5 + 1)
        for i, c in enumerate(sample_controls)
    ]

@pytest.fixture
def mock_embeddings() -> list[torch.Tensor]:
    """Mock embeddings: 10 controls, each with (5 tokens, 128 dim)."""
    torch.manual_seed(42)
    return [torch.randn(5, 128) for _ in range(10)]

@pytest.fixture
def sample_document_prediction(sample_controls, sample_scored_controls) -> DocumentPrediction:
    """Mock document prediction with page-level scores."""
    page_predictions = []
    for page_num in range(1, 6):  # 5 pages
        # Each page has some controls with scores
        page_controls = [
            ScoredControl(control=c.control, score=c.score * (1 - 0.1 * page_num), page_num=page_num)
            for c in sample_scored_controls[:5]  # First 5 controls appear on each page
        ]
        page_predictions.append(PagePrediction(page_num=page_num, top_controls=page_controls))

    return DocumentPrediction(
        page_predictions=page_predictions,
        top_control=sample_controls[0],
        top_score=0.9,
        top_page=1,
        reasoning="Test prediction",
    )
```

---

## Implementation Steps (TDD)

Each step follows **Red → Green → Refactor**:
1. **Red**: Write failing tests that define expected behavior
2. **Green**: Write minimal code to make tests pass
3. **Refactor**: Clean up while keeping tests green

---

### Step 1: Control Clustering Module (TDD)

#### 1.1 Write Tests First (Red)

**File: `tests/scripts/experiments/control_detection/test_control_clustering.py`**

```python
import pytest
import torch
from pathlib import Path

class TestMeanPoolEmbeddings:
    """Test mean pooling of token embeddings."""

    def test_mean_pool_single_control(self, mock_embeddings):
        """Mean pool reduces (num_tokens, dim) → (dim,)."""
        embedding = mock_embeddings[0]  # (5, 128)
        pooled = mean_pool_embedding(embedding)
        assert pooled.shape == (128,)
        assert torch.allclose(pooled, embedding.mean(dim=0))

    def test_mean_pool_all_controls(self, mock_embeddings):
        """Mean pool all controls → (num_controls, dim) matrix."""
        pooled = mean_pool_all_embeddings(mock_embeddings)
        assert pooled.shape == (10, 128)


class TestClusterComputation:
    """Test K-means clustering."""

    def test_compute_clusters_deterministic(self, mock_embeddings):
        """Same seed produces same clusters."""
        clusters1 = compute_clusters(mock_embeddings, n_clusters=3, seed=42)
        clusters2 = compute_clusters(mock_embeddings, n_clusters=3, seed=42)
        assert clusters1 == clusters2

    def test_compute_clusters_correct_count(self, mock_embeddings):
        """Returns assignment for each control."""
        clusters = compute_clusters(mock_embeddings, n_clusters=3, seed=42)
        assert len(clusters) == 10
        assert all(0 <= c < 3 for c in clusters)

    def test_different_seeds_different_clusters(self, mock_embeddings):
        """Different seeds may produce different clusters."""
        clusters1 = compute_clusters(mock_embeddings, n_clusters=3, seed=42)
        clusters2 = compute_clusters(mock_embeddings, n_clusters=3, seed=123)
        # Not guaranteed to differ, but very likely with random data
        # Just verify both are valid
        assert len(clusters1) == len(clusters2) == 10


class TestClusterCache:
    """Test cache load/save and invalidation."""

    def test_save_and_load(self, tmp_path, mock_embeddings, sample_controls):
        """Cache can be saved and loaded."""
        cache_file = tmp_path / "clusters.json"

        # Compute and save
        cache = ControlClusterCache.compute(
            embeddings=mock_embeddings,
            control_ids=[c.control_id for c in sample_controls],
            embedding_hash="abc123",
            n_clusters=3,
            seed=42,
        )
        cache.save(cache_file)

        # Load and verify
        loaded = ControlClusterCache.load(cache_file)
        assert loaded.cluster_assignments == cache.cluster_assignments
        assert loaded.embedding_hash == "abc123"

    def test_invalidation_on_hash_mismatch(self, tmp_path, mock_embeddings, sample_controls):
        """Cache is invalid if embedding hash changed."""
        cache_file = tmp_path / "clusters.json"

        cache = ControlClusterCache.compute(
            embeddings=mock_embeddings,
            control_ids=[c.control_id for c in sample_controls],
            embedding_hash="abc123",
            n_clusters=3,
            seed=42,
        )
        cache.save(cache_file)

        loaded = ControlClusterCache.load(cache_file)
        assert loaded.is_valid_for_hash("abc123") is True
        assert loaded.is_valid_for_hash("different_hash") is False

    def test_get_cluster_id(self, mock_embeddings, sample_controls):
        """Can look up cluster for a control."""
        cache = ControlClusterCache.compute(
            embeddings=mock_embeddings,
            control_ids=[c.control_id for c in sample_controls],
            embedding_hash="abc123",
            n_clusters=3,
            seed=42,
        )

        cluster_id = cache.get_cluster_id("DCF-0")
        assert isinstance(cluster_id, int)
        assert 0 <= cluster_id < 3

    def test_get_cluster_id_unknown_control(self, mock_embeddings, sample_controls):
        """Unknown control raises KeyError."""
        cache = ControlClusterCache.compute(
            embeddings=mock_embeddings,
            control_ids=[c.control_id for c in sample_controls],
            embedding_hash="abc123",
            n_clusters=3,
            seed=42,
        )

        with pytest.raises(KeyError):
            cache.get_cluster_id("DCF-999")
```

#### 1.2 Implement to Pass Tests (Green)

Create `control_clustering.py` with minimal implementation to pass all tests.

#### 1.3 Refactor

- Add logging
- Add docstrings
- Ensure type hints are complete

---

### Step 2: Batching Algorithm (TDD)

#### 2.1 Write Tests First (Red)

**File: `tests/scripts/experiments/control_detection/test_batching.py`**

```python
import pytest
from ai_services.scripts.experiments.control_detection.control_centric_decider import (
    BatchingStrategy,
    create_batches,
    apply_budget,
)

class TestCoherentBatching:
    """Test coherent batching (group by cluster)."""

    def test_groups_same_cluster_together(self, sample_scored_controls, sample_cluster_map):
        """Controls from same cluster end up in same batch."""
        batches = create_batches(
            candidates=sample_scored_controls,
            cluster_map=sample_cluster_map,
            max_calls=50,
            strategy=BatchingStrategy.COHERENT,
        )

        for batch in batches:
            cluster_ids = {sample_cluster_map[c.control.control_id] for c in batch.controls}
            # Coherent: each batch should be predominantly one cluster
            assert len(cluster_ids) <= 2  # Allow some spillover for uneven clusters

    def test_all_candidates_assigned_once(self, sample_scored_controls, sample_cluster_map):
        """Every candidate appears in exactly one batch."""
        batches = create_batches(
            candidates=sample_scored_controls,
            cluster_map=sample_cluster_map,
            max_calls=50,
            strategy=BatchingStrategy.COHERENT,
        )

        all_control_ids = []
        for batch in batches:
            all_control_ids.extend(c.control.control_id for c in batch.controls)

        expected_ids = [c.control.control_id for c in sample_scored_controls]
        assert sorted(all_control_ids) == sorted(expected_ids)

    def test_respects_max_calls(self, sample_scored_controls, sample_cluster_map):
        """Number of batches <= max_calls."""
        batches = create_batches(
            candidates=sample_scored_controls,
            cluster_map=sample_cluster_map,
            max_calls=3,
            strategy=BatchingStrategy.COHERENT,
        )

        assert len(batches) <= 3


class TestDiverseBatching:
    """Test diverse batching (spread across clusters)."""

    def test_spreads_across_clusters(self, sample_scored_controls, sample_cluster_map):
        """Each batch contains controls from different clusters."""
        batches = create_batches(
            candidates=sample_scored_controls,
            cluster_map=sample_cluster_map,
            max_calls=50,
            strategy=BatchingStrategy.DIVERSE,
        )

        for batch in batches:
            if len(batch.controls) > 1:
                cluster_ids = [sample_cluster_map[c.control.control_id] for c in batch.controls]
                # Diverse: should have multiple clusters represented
                unique_clusters = set(cluster_ids)
                assert len(unique_clusters) > 1 or len(batch.controls) <= len(unique_clusters)

    def test_all_candidates_assigned_once(self, sample_scored_controls, sample_cluster_map):
        """Every candidate appears in exactly one batch."""
        batches = create_batches(
            candidates=sample_scored_controls,
            cluster_map=sample_cluster_map,
            max_calls=50,
            strategy=BatchingStrategy.DIVERSE,
        )

        all_control_ids = []
        for batch in batches:
            all_control_ids.extend(c.control.control_id for c in batch.controls)

        expected_ids = [c.control.control_id for c in sample_scored_controls]
        assert sorted(all_control_ids) == sorted(expected_ids)


class TestBudgetEnforcement:
    """Test candidate budget limiting."""

    def test_under_budget_unchanged(self, sample_scored_controls, sample_cluster_map):
        """Candidates under budget are unchanged."""
        result = apply_budget(
            candidates=sample_scored_controls,  # 10 controls
            cluster_map=sample_cluster_map,
            max_controls=400,  # Well above 10
        )

        assert len(result) == len(sample_scored_controls)

    def test_over_budget_truncated(self, sample_scored_controls, sample_cluster_map):
        """Candidates over budget are truncated."""
        result = apply_budget(
            candidates=sample_scored_controls,  # 10 controls
            cluster_map=sample_cluster_map,
            max_controls=5,
        )

        assert len(result) == 5

    def test_keeps_highest_scores(self, sample_scored_controls, sample_cluster_map):
        """Budget keeps highest-scoring controls."""
        result = apply_budget(
            candidates=sample_scored_controls,
            cluster_map=sample_cluster_map,
            max_controls=5,
        )

        result_scores = [c.score for c in result]
        dropped_scores = [c.score for c in sample_scored_controls if c not in result]

        # All kept scores should be >= all dropped scores
        if dropped_scores:
            assert min(result_scores) >= max(dropped_scores)

    def test_maintains_cluster_diversity(self, sample_scored_controls, sample_cluster_map):
        """Budget maintains representation from multiple clusters."""
        result = apply_budget(
            candidates=sample_scored_controls,
            cluster_map=sample_cluster_map,
            max_controls=6,
        )

        cluster_ids = {sample_cluster_map[c.control.control_id] for c in result}
        # Should have controls from multiple clusters, not just highest-scoring cluster
        assert len(cluster_ids) >= 2
```

#### 2.2 Implement to Pass Tests (Green)

Implement in `control_centric_decider.py`:

```python
class BatchingStrategy(Enum):
    COHERENT = "coherent"  # Group similar controls (by cluster) - DEFAULT
    DIVERSE = "diverse"    # Spread dissimilar controls across batches

def _create_batches(
    candidates: list[ScoredControl],
    cluster_map: dict[str, int],
    max_calls: int = 50,
    strategy: BatchingStrategy = BatchingStrategy.COHERENT,
) -> list[ControlBatch]:
    """
    Pack N candidates into ≤max_calls batches.

    COHERENT (default): Group by cluster for LLM differentiation
    - All controls from cluster A in batch 1
    - All controls from cluster B in batch 2
    - Helps LLM say "yes to A, no to B because lacks qualifier"

    DIVERSE: Spread across clusters (original idea)
    - One from each cluster per batch
    - May cause context-switching overhead
    """
```

**Why Coherent is Default (Gemini 3 insight):**
- When asking binary yes/no per control, having similar controls together helps differentiation
- LLM can focus attention on one section of text (e.g., Access Control chapter)
- Side-by-side comparison: "Paragraph 3 matches Control A but NOT Control B because..."

#### 2.3 Refactor

- Extract common batch creation logic
- Add logging for batch statistics

---

### Step 3: Retrieval Anchors (TDD)

#### 3.1 Write Tests First (Red)

**File: `tests/scripts/experiments/control_detection/test_retrieval_anchors.py`**

```python
import pytest
from ai_services.scripts.experiments.control_detection.control_centric_decider import (
    compute_retrieval_anchors,
    format_control_xml,
)

class TestRetrievalAnchors:
    """Test retrieval anchor computation."""

    def test_returns_top_3_pages(self, sample_document_prediction):
        """Retrieval anchors include top 3 pages by score."""
        anchors = compute_retrieval_anchors(
            control_id="DCF-1",
            page_predictions=sample_document_prediction.page_predictions,
        )

        assert len(anchors["top_pages"]) <= 3
        assert all(isinstance(p, int) for p in anchors["top_pages"])

    def test_pages_sorted_by_score(self, sample_document_prediction):
        """Top pages are sorted by descending score."""
        anchors = compute_retrieval_anchors(
            control_id="DCF-1",
            page_predictions=sample_document_prediction.page_predictions,
        )

        # First page should have highest score for this control
        if len(anchors["top_pages"]) > 1:
            scores = anchors["page_scores"]
            assert scores[0] >= scores[1]

    def test_includes_best_score(self, sample_document_prediction):
        """Anchors include the best (max) score."""
        anchors = compute_retrieval_anchors(
            control_id="DCF-1",
            page_predictions=sample_document_prediction.page_predictions,
        )

        assert "best_score" in anchors
        assert isinstance(anchors["best_score"], float)

    def test_control_not_in_any_page(self, sample_document_prediction):
        """Control not found on any page returns empty anchors."""
        anchors = compute_retrieval_anchors(
            control_id="DCF-NONEXISTENT",
            page_predictions=sample_document_prediction.page_predictions,
        )

        assert anchors["top_pages"] == []
        assert anchors["best_score"] == 0.0


class TestControlXmlFormat:
    """Test XML formatting for prompts."""

    def test_basic_format(self, sample_controls):
        """Control is formatted as valid XML."""
        control = sample_controls[0]
        anchors = {"top_pages": [1, 2, 3], "best_score": 0.85}

        xml = format_control_xml(control, anchors)

        assert f'<control id="{control.control_id}">' in xml
        assert f"<name>{control.name}</name>" in xml
        assert "<retrieval_hints>" in xml
        assert "<top_pages>1, 2, 3</top_pages>" in xml
        assert "</control>" in xml

    def test_escapes_special_chars(self, sample_controls):
        """XML special characters are escaped."""
        control = DCFControl(
            control_id="DCF-1",
            name="Test & Control",
            description="Description with <tags> and 'quotes'",
        )
        anchors = {"top_pages": [1], "best_score": 0.5}

        xml = format_control_xml(control, anchors)

        assert "&amp;" in xml or "& " not in xml  # Escaped or avoided
        assert "<tags>" not in xml  # Should be escaped
```

#### 3.2 Implement to Pass Tests (Green)

Add to `control_centric_decider.py`:

```python
def compute_retrieval_anchors(
    control_id: str,
    page_predictions: list[PagePrediction],
    top_k: int = 3,
) -> dict:
    """Compute top pages for a control based on ColModernVBERT scores."""
    ...

def format_control_xml(control: DCFControl, anchors: dict) -> str:
    """Format control with retrieval hints as XML."""
    ...
```

#### 3.3 Refactor

- Use xml.etree for proper escaping
- Add type hints for anchor dict (or create dataclass)

---

### Step 4: Control-Centric Prompts

Create `prompts/control_centric/`:

**System prompt:**
- "You are reviewing a complete policy document"
- "For EACH control in the batch, determine if the document addresses it"
- "You MUST quote evidence from the document"
- "If you cannot quote evidence, mark as addresses_control: false"

**Binding Language Definition (broadened per Gemini 3, constrained per ChatGPT):**
```
Valid binding language includes:
- Explicit mandates: "must", "shall", "required", "will", "is prohibited"
- Declarative policy statements: "Passwords are 12 characters", "The CISO reviews logs"
  → BUT only if presented as requirements, not descriptions or background
- Responsibility assignments: "The Engineering Team is responsible for..."

NOT binding (do not select):
- "Should", "recommended", "best practice", "encouraged"
- Future plans: "We aim to...", "We plan to..."
- Definitions without mandates
- Background/context sections describing what others do
```

**User prompt (with retrieval anchors per ChatGPT):**
```
Analyze this policy document for the following controls.

<controls_to_evaluate>
{controls_xml}

Each control includes retrieval_hints with the most relevant pages.
Start your search at those pages, but evidence found elsewhere is valid.
</controls_to_evaluate>

For EACH control:
1. Check the suggested pages first (retrieval_hints)
2. Search for binding language (see system prompt for definitions)
3. If found, quote the exact text and describe where it appears
4. If not found, mark addresses_control: false

Return results for ALL controls in the batch.
```

**Control XML format (with anchors):**
```xml
<control id="DCF-182">
  <name>Encryption at Rest</name>
  <description>...</description>
  <retrieval_hints>
    <top_pages>12, 13, 14</top_pages>
    <best_score>0.72</best_score>
  </retrieval_hints>
</control>
```

### Step 5: Control-Centric Decider (TDD)

#### 5.1 Write Tests First (Red)

**File: `tests/scripts/experiments/control_detection/test_control_centric_decider.py`**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ai_services.scripts.experiments.control_detection.control_centric_decider import (
    ControlCentricDecider,
    ControlCentricConfig,
    BatchingStrategy,
)

class TestControlCentricDecider:
    """Integration tests for the decider (mocked LLM)."""

    @pytest.fixture
    def mock_gemini_client(self):
        """Mock Gemini client that returns valid batch results."""
        client = MagicMock()
        client.aio.caches.create = AsyncMock(return_value=MagicMock(name="cache/123"))
        client.aio.caches.delete = AsyncMock()
        client.aio.models.generate_content = AsyncMock(return_value=MagicMock(
            text='{"batch_results": [{"control_id": "DCF-1", "addresses_control": true, "confidence": "high", "evidence_quote": "test quote", "location_reference": "Page 1", "reasoning": "test"}]}'
        ))
        return client

    @pytest.fixture
    def decider(self, mock_gemini_client):
        """Decider with mocked Gemini client."""
        config = ControlCentricConfig(
            max_calls=50,
            batch_strategy=BatchingStrategy.COHERENT,
            threshold=0.48,
        )
        decider = ControlCentricDecider(config)
        decider._client = mock_gemini_client
        return decider

    @pytest.mark.asyncio
    async def test_decide_document_filters_by_threshold(
        self, decider, sample_document_prediction
    ):
        """Only controls above threshold are evaluated."""
        # Add controls with varying scores
        result = await decider.decide_document(
            pdf_bytes=b"fake pdf",
            document_prediction=sample_document_prediction,
            cluster_cache=MagicMock(),
        )

        # Should have filtered to only above-threshold controls
        assert result.n_candidates_evaluated <= result.n_total_controls

    @pytest.mark.asyncio
    async def test_decide_document_respects_max_calls(
        self, decider, sample_document_prediction
    ):
        """Number of LLM calls never exceeds max_calls."""
        decider.config = ControlCentricConfig(
            max_calls=3,
            batch_strategy=BatchingStrategy.COHERENT,
            threshold=0.0,  # Low threshold = many candidates
        )

        result = await decider.decide_document(
            pdf_bytes=b"fake pdf",
            document_prediction=sample_document_prediction,
            cluster_cache=MagicMock(),
        )

        assert result.n_batches <= 3

    @pytest.mark.asyncio
    async def test_decide_document_deletes_cache_on_success(
        self, decider, mock_gemini_client, sample_document_prediction
    ):
        """Cache is deleted after successful processing."""
        await decider.decide_document(
            pdf_bytes=b"fake pdf",
            document_prediction=sample_document_prediction,
            cluster_cache=MagicMock(),
        )

        mock_gemini_client.aio.caches.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_decide_document_deletes_cache_on_error(
        self, decider, mock_gemini_client, sample_document_prediction
    ):
        """Cache is deleted even when processing fails."""
        mock_gemini_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("LLM error")
        )

        with pytest.raises(Exception):
            await decider.decide_document(
                pdf_bytes=b"fake pdf",
                document_prediction=sample_document_prediction,
                cluster_cache=MagicMock(),
            )

        mock_gemini_client.aio.caches.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_aggregates_batch_results(
        self, decider, mock_gemini_client, sample_document_prediction
    ):
        """Results from all batches are aggregated."""
        result = await decider.decide_document(
            pdf_bytes=b"fake pdf",
            document_prediction=sample_document_prediction,
            cluster_cache=MagicMock(),
        )

        assert hasattr(result, "matched_controls")
        assert hasattr(result, "evidence_quotes")


class TestDeciderDataclasses:
    """Test dataclass conversions."""

    def test_to_prediction(self):
        """DocumentControlCentricDecision converts to prediction format."""
        decision = DocumentControlCentricDecision(
            matched_control_ids={"DCF-1", "DCF-2"},
            evidence={"DCF-1": {"quote": "test", "location": "Page 1"}},
            n_total_controls=100,
            n_candidates_evaluated=50,
            n_batches=5,
        )

        prediction = decision.to_prediction()

        assert "DCF-1" in prediction.control_ids
        assert "DCF-2" in prediction.control_ids
```

#### 5.2 Implement to Pass Tests (Green)

Create `control_centric_decider.py`:

**Reuse from `control_mapping_reasons/`:**
- `GeminiCacheManager` pattern (upload PDF once)
- Semaphore-based concurrency
- Signal handler cleanup with `_active_caches`
- `asyncio.shield()` for cache deletion
- Retry with exponential backoff

**Add: Retry Logic for Rate Limits (per Gemini 3 + ChatGPT):**
```python
from tenacity import (
    retry, stop_after_attempt, wait_exponential_jitter,
    retry_if_exception_type
)
from google.api_core.exceptions import ResourceExhausted, DeadlineExceeded
import asyncio

@retry(
    retry=retry_if_exception_type((ResourceExhausted, DeadlineExceeded, asyncio.TimeoutError)),
    wait=wait_exponential_jitter(initial=4, max=60, jitter=5),  # Add jitter per ChatGPT
    stop=stop_after_attempt(5)
)
async def _process_batch_with_retry(self, batch, cache_name):
    return await self._process_batch(batch, cache_name)
```

**Add: Candidate Budgeting (per ChatGPT):**
```python
# Budget calculation
MAX_CALLS_PER_DOC = 50
TARGET_BATCH_SIZE = 8
MAX_CONTROLS_PER_DOC = MAX_CALLS_PER_DOC * TARGET_BATCH_SIZE  # 400

def _apply_budget(candidates: list[ScoredControl], cluster_map: dict) -> list[ScoredControl]:
    """Enforce candidate budget while maintaining cluster diversity."""
    if len(candidates) <= MAX_CONTROLS_PER_DOC:
        return candidates

    # Keep highest-scoring controls with per-cluster diversity
    # For each cluster, keep top M controls (M computed to fit budget)
    clusters = group_by_cluster(candidates, cluster_map)
    n_clusters = len(clusters)
    per_cluster_budget = MAX_CONTROLS_PER_DOC // n_clusters

    kept = []
    for cluster_id, controls in clusters.items():
        sorted_controls = sorted(controls, key=lambda c: c.score, reverse=True)
        kept.extend(sorted_controls[:per_cluster_budget])

    logger.warning(
        "Budget enforced: %d → %d candidates (dropped %d, min_score_dropped=%.3f)",
        len(candidates), len(kept), len(candidates) - len(kept),
        min(c.score for c in candidates if c not in kept)
    )
    return kept
```

**Add: Per-Stage Metrics Logging (per Gemini 3):**
```python
logger.info(
    "Control filtering: total=%d, above_threshold=%d, lost=%d (%.1f%%)",
    n_total_controls,
    n_candidates,
    n_total_controls - n_candidates,
    (n_total_controls - n_candidates) / n_total_controls * 100
)
logger.info("Batches created: %d (strategy=%s)", n_batches, strategy.value)
```

**Flow:**
```
decide_document(document, scored_controls):
    1. Filter controls: doc_max_score >= threshold
       → Log: n_total, n_candidates, n_lost
    2. Apply budget if n_candidates > MAX_CONTROLS_PER_DOC
       → Log: n_dropped, min_score_dropped
    3. Load cluster map
    4. Compute retrieval anchors (top 3 pages per control)
    5. Create batches (coherent by default, max 50)
       → Log: n_batches, strategy
    6. Upload full document to cache (wait for ACTIVE state)
    7. Process batches in parallel (semaphore=10, with retry for 429s/timeouts)
    8. Aggregate results
    9. Delete cache (shielded)
    return DocumentControlCentricDecision
```

#### 5.3 Refactor

- Add comprehensive logging
- Extract retry logic to decorator
- Add metrics collection

---

### Step 6: run_experiment.py Integration (TDD)

#### 6.1 Write Tests First (Red)

**File: `tests/scripts/experiments/control_detection/test_run_experiment_integration.py`**

```python
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

class TestCLIArgs:
    """Test CLI argument parsing."""

    def test_mode_arg_defaults_to_page_centric(self):
        """--mode defaults to page_centric."""
        runner = CliRunner()
        with patch("ai_services.scripts.experiments.control_detection.run_experiment.main") as mock:
            result = runner.invoke(run_experiment_cli, ["--row", "0"])
            # Should use page_centric by default
            assert mock.call_args.kwargs.get("mode", "page_centric") == "page_centric"

    def test_mode_control_centric_accepted(self):
        """--mode control_centric is valid."""
        runner = CliRunner()
        with patch("ai_services.scripts.experiments.control_detection.run_experiment.main") as mock:
            result = runner.invoke(run_experiment_cli, ["--mode", "control_centric", "--row", "0"])
            assert result.exit_code == 0

    def test_batch_strategy_coherent_default(self):
        """--batch-strategy defaults to coherent."""
        runner = CliRunner()
        with patch("ai_services.scripts.experiments.control_detection.run_experiment.main") as mock:
            result = runner.invoke(run_experiment_cli, ["--mode", "control_centric", "--row", "0"])
            assert mock.call_args.kwargs.get("batch_strategy", "coherent") == "coherent"

    def test_batch_strategy_diverse_accepted(self):
        """--batch-strategy diverse is valid."""
        runner = CliRunner()
        with patch("ai_services.scripts.experiments.control_detection.run_experiment.main") as mock:
            result = runner.invoke(run_experiment_cli, [
                "--mode", "control_centric",
                "--batch-strategy", "diverse",
                "--row", "0"
            ])
            assert result.exit_code == 0

    def test_max_calls_arg(self):
        """--max-calls accepts integer."""
        runner = CliRunner()
        with patch("ai_services.scripts.experiments.control_detection.run_experiment.main") as mock:
            result = runner.invoke(run_experiment_cli, [
                "--mode", "control_centric",
                "--max-calls", "25",
                "--row", "0"
            ])
            assert mock.call_args.kwargs.get("max_calls") == 25


class TestModeRouting:
    """Test routing to correct decider based on mode."""

    @pytest.mark.asyncio
    async def test_page_centric_uses_llm_decider(self):
        """page_centric mode uses LLMDecider."""
        with patch("ai_services.scripts.experiments.control_detection.run_experiment.predict_control_with_llm") as mock:
            await process_document(mode="page_centric", ...)
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_control_centric_uses_control_centric_decider(self):
        """control_centric mode uses ControlCentricDecider."""
        with patch("ai_services.scripts.experiments.control_detection.run_experiment.ControlCentricDecider") as mock:
            await process_document(mode="control_centric", ...)
            mock.return_value.decide_document.assert_called()
```

#### 6.2 Implement to Pass Tests (Green)

Add routing based on `--mode`:

```python
if args.mode == "control_centric":
    from .control_centric_decider import (
        ControlCentricDecider,
        ControlCentricConfig,
        BatchingStrategy,
    )

    decider = ControlCentricDecider(ControlCentricConfig(
        max_calls=args.max_calls,
        batch_strategy=BatchingStrategy(args.batch_strategy),
        threshold=args.trigger_threshold,
        ...
    ))
    decision = await decider.decide_document(document, doc_prediction)
    prediction = decision.to_prediction()
else:
    # Existing page-centric flow
    prediction = await predict_control_with_llm(...)
```

#### 6.3 Refactor

- Extract mode-specific logic to separate functions
- Add validation for mode-specific args

---

### Step 7: End-to-End Testing

After all unit tests pass, run end-to-end tests:

```bash
# 1. Generate cluster cache (run once)
python -m ai_services.scripts.experiments.control_detection.control_clustering

# 2. Run unit tests
uv run pytest tests/scripts/experiments/control_detection/ -v

# 3. Test on single document (smoke test)
python -m ai_services.scripts.experiments.control_detection.run_experiment \
    --mode control_centric \
    --row 0 \
    --experiment template_policies

# 4. Verify output
# - Check logs for: n_candidates, n_batches, strategy
# - Check output JSON for: evidence_quotes, location_references
# - Verify cache was deleted (check Gemini console or logs)

# 5. Compare with baseline
python -m ai_services.scripts.experiments.control_detection.run_experiment \
    --mode page_centric \
    --row 0 \
    --experiment template_policies

# 6. Full experiment run (when ready)
python -m ai_services.scripts.experiments.control_detection.run_experiment \
    --mode control_centric \
    --experiment template_policies
```

---

## Critical Files Reference

| File | Purpose |
|------|---------|
| `run_experiment.py` | Entry point, CLI args, main loop |
| `llm_decider.py` | Page-centric approach (reference) |
| `predictor.py` | ColModernVBERT scoring, embeddings cache |
| `control_mapping_reasons/cache_manager.py` | Gemini caching patterns to reuse |
| `control_mapping_reasons/reason_generator.py` | Parallel coroutine patterns to reuse |
| `experiment_config.py` | Configuration constants |
| `dcf_controls.py` | DCF control models |

---

## Architecture Diagram

```
run_experiment.py --mode control_centric
    │
    ├─ Load policy document (existing)
    ├─ ColModernVBERT scoring (existing)
    │   └─ predictor.predict_document() → DocumentPrediction
    │
    └─ ControlCentricDecider.decide_document()
        │
        ├─ Filter: doc_max_score[control] >= 0.48
        │   └─ ~100-200 candidate controls
        │
        ├─ Apply budget (if > MAX_CONTROLS_PER_DOC)
        │   └─ Keep top M per cluster, log dropped
        │
        ├─ Load control clusters (from disk cache)
        │
        ├─ Compute retrieval anchors (top 3 pages per control)
        │
        ├─ Create batches (COHERENT by default)
        │   └─ _create_batches(candidates, clusters, max_calls=50, strategy=COHERENT)
        │   └─ → Group similar controls together for differentiation
        │
        ├─ Upload document to Gemini cache
        │   └─ cache_manager.upload_pdf(pdf_bytes, display_name)
        │
        ├─ Process batches in parallel
        │   └─ asyncio.Semaphore(10)
        │   └─ asyncio.gather(*[process_batch(b) for b in batches])
        │       └─ generate_content(cached_content=cache_name)
        │       └─ Includes retrieval_hints per control
        │
        ├─ Aggregate batch decisions
        │   └─ Union of controls with addresses_control=true
        │   └─ Include evidence quotes and location_reference
        │
        └─ Delete cache (shielded)
            └─ asyncio.shield(cache_manager.delete_cache())
```

---

## Success Criteria

1. **CLI works**: `--mode control_centric` triggers new flow
2. **Bounded calls**: Never >50 LLM calls per document
3. **Batching works** (per ChatGPT):
   - **Coherent mode**: Batches are predominantly single-cluster (similar controls together)
   - **Diverse mode**: Batches maximize cluster spread
   - **Both**: Every candidate appears in exactly one batch; n_batches <= max_calls
4. **Evidence**: Output includes quotes and location_reference
5. **Retrieval anchors**: Each control includes top_pages hints in prompt
6. **Metrics comparable**: Can compare P/R/F1 vs page-centric baseline
7. **Cleanup**: Caches deleted even on interruption

---

## Estimated Effort (TDD)

| Step | Tests | Implementation | Total |
|------|-------|----------------|-------|
| Step 1: Control clustering | 30 min | 1-1.5 hours | ~2 hours |
| Step 2: Batching algorithm | 30 min | 1-1.5 hours | ~2 hours |
| Step 3: Retrieval anchors | 20 min | 40 min | ~1 hour |
| Step 4: Prompts | - | 30 min | ~30 min |
| Step 5: Control-centric decider | 45 min | 2-3 hours | ~3.5 hours |
| Step 6: run_experiment.py integration | 30 min | 1 hour | ~1.5 hours |
| Step 7: End-to-end testing | - | 1-2 hours | ~1.5 hours |
| **Total** | **~2.5 hours** | **~8-10 hours** | **~12 hours** |

**TDD Benefits:**
- Tests define expected behavior upfront → fewer bugs
- Faster debugging when tests fail → pinpoint exact issue
- Confidence to refactor → cleaner code
- Documentation via test names → self-documenting


⏺ Let me estimate the costs for 50 LLM calls with context caching.

  Token Estimates

  | Content             | Tokens  | Notes                            |
  |---------------------|---------|----------------------------------|
  | Instructions prompt | ~10,000 | The 400-line markdown file       |
  | 10-page PDF         | ~40,000 | ~4,000 tokens/page average       |
  | Cached total        | ~50,000 | Read once, reused 50×            |
  | Per-call controls   | ~1,000  | Small batches in experiment mode |
  | Output per call     | ~500    | Structured decision format       |

  Cost Calculation

  | Component     | Tokens                | Rate       | Cost   |
  |---------------|-----------------------|------------|--------|
  | Cached input  | 50K × 50 calls = 2.5M | $0.05/1M   | $0.125 |
  | Regular input | 1K × 50 calls = 50K   | $0.50/1M   | $0.025 |
  | Output        | 500 × 50 = 25K        | ~$1.50/1M* | ~$0.04 |
  | Total         |                       |            | ~$0.19 |

  *Output pricing assumed; verify with current Gemini 3 Flash docs.

  Comparison: With vs Without Caching

  | Scenario      | Input Cost | Savings |
  |---------------|------------|---------|
  | With cache    | $0.15      | -       |
  | Without cache | $1.28      | -       |
  | Savings       | $1.13      | 88%     |

  Bottom line: ~$0.19 total for 50 calls with caching, versus ~$1.32 without. The 90% discount on cached tokens makes this very cheap given the large context (instructions + PDF) that gets reused every call.