# Next Experiments: Low-Impact, Non-LLM Retrieval Improvements

## Date: 2025-12-20

## Problem Recap

ColModernVBERT produces scores that are excellent for **ranking** but terrible for **thresholding**:
- GT and non-GT score distributions overlap heavily (median gap only 0.03)
- At 100% recall, all three scoring modes pass 97-99.5% of controls
- The semantic vs compliance mismatch creates controls with no semantic basis for their association

This document synthesizes the most promising next experiments from three research perspectives.

---

## Selection Criteria

Solutions were filtered for:
1. **Low implementation impact** - Can be built in hours, not weeks
2. **No LLM calls required** - Pure computation or pre-computed data
3. **High potential for material improvement** - Addresses root causes, not symptoms

---

## Experiment 1: Peakiness Filter (Within-Document Z-Score)

### Source
ChatGPT o1 Pro suggestion #2, adapted for arbitrary controls

### Problem It Solves
Generic controls score "kinda high everywhere" across all pages. Truly relevant controls "spike on 1-2 pages" where the actual evidence exists. We need to distinguish these patterns without pre-computed per-control statistics.

### Key Constraint: Arbitrary Controls

**The production scenario receives customer-defined arbitrary text as controls.** We cannot pre-compute background statistics for unknown controls.

**What still works:** Z-scoring across pages *within the document* for each control. This is always available because we score every control against every page.

### The Insight: Peakiness as a Signal

```
Generic Control (e.g., "security policies"):
  Page 1: 0.45    Page 2: 0.47    Page 3: 0.44    Page 4: 0.46
  → High everywhere, low variance, NOT specifically relevant

Relevant Control (e.g., "asset inventory management"):
  Page 1: 0.32    Page 2: 0.58    Page 3: 0.35    Page 4: 0.31
  → Spikes on Page 2 (the actual asset inventory section)
```

The relevant control has **high peakiness** - its max score is much higher than its mean. The generic control has **low peakiness** - uniformly mediocre everywhere.

### Production Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RUNTIME (Per Request)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Input                                Processing                           │
│   ┌─────────────────┐                 ┌─────────────────────────────────┐  │
│   │ PDF Document    │                 │ 1. Extract N pages              │  │
│   │ (N pages)       │                 │ 2. Score all M controls/page    │  │
│   │                 │ ──────────────► │    → score_matrix[N, M]         │  │
│   │ M Controls      │                 │ 3. Compute peakiness per control│  │
│   │ (arbitrary)     │                 │ 4. Filter by peakiness + top-K  │  │
│   └─────────────────┘                 └─────────────────────────────────┘  │
│                                                                             │
│   For each control c:                                                       │
│     scores = score_matrix[:, c]           # scores across all pages        │
│     peakiness = (max - mean) / (std + ε)  # z-score of the peak            │
│                                                                             │
│   Keep controls with high peakiness (evidence is concentrated)             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass
import numpy as np
from scipy.stats import entropy


@dataclass
class ControlPeakiness:
    """Peakiness metrics for a single control across document pages."""
    control_id: str
    max_score: float
    mean_score: float
    std_score: float
    peak: float              # max - mean
    z_peak: float            # (max - mean) / (std + eps)
    best_page: int           # argmax page
    score_entropy: float     # lower = more concentrated evidence


def compute_peakiness(
    score_matrix: np.ndarray,  # shape: (num_pages, num_controls)
    control_ids: list[str],
) -> list[ControlPeakiness]:
    """
    Compute peakiness metrics for each control across document pages.

    Args:
        score_matrix: [num_pages, num_controls] array of scores
        control_ids: List of control IDs matching columns of score_matrix

    Returns:
        List of ControlPeakiness objects, one per control
    """
    num_pages, num_controls = score_matrix.shape
    results = []

    for ctrl_idx, ctrl_id in enumerate(control_ids):
        scores = score_matrix[:, ctrl_idx]

        max_score = float(scores.max())
        mean_score = float(scores.mean())
        std_score = float(scores.std())

        peak = max_score - mean_score
        z_peak = peak / (std_score + 1e-8)
        best_page = int(scores.argmax())

        # Entropy of normalized score distribution (lower = more concentrated)
        # Normalize to probability distribution
        normalized = scores - scores.min() + 1e-8
        probs = normalized / normalized.sum()
        score_entropy = float(entropy(probs))

        results.append(ControlPeakiness(
            control_id=ctrl_id,
            max_score=max_score,
            mean_score=mean_score,
            std_score=std_score,
            peak=peak,
            z_peak=z_peak,
            best_page=best_page,
            score_entropy=score_entropy,
        ))

    return results


def filter_by_peakiness(
    peakiness_results: list[ControlPeakiness],
    z_peak_threshold: float = 1.5,
    max_controls: int = 100,
) -> list[ControlPeakiness]:
    """
    Filter controls by peakiness, keeping those with concentrated evidence.

    Strategy:
    1. Keep controls with z_peak >= threshold (evidence spikes somewhere)
    2. Cap at max_controls by sorting by z_peak descending

    Args:
        peakiness_results: List of ControlPeakiness from compute_peakiness()
        z_peak_threshold: Minimum z_peak to consider (default 1.5σ)
        max_controls: Maximum controls to return

    Returns:
        Filtered list of ControlPeakiness
    """
    # Filter by z_peak threshold
    filtered = [p for p in peakiness_results if p.z_peak >= z_peak_threshold]

    # Sort by z_peak descending (most peaked first)
    filtered.sort(key=lambda p: p.z_peak, reverse=True)

    # Cap at max_controls
    return filtered[:max_controls]


# ============================================================================
# Full retrieval pipeline
# ============================================================================

def retrieve_candidates_with_peakiness(
    predictor,
    page_images: list[tuple[int, bytes]],  # (page_num, image_bytes)
    controls: list[Control],
    z_peak_threshold: float = 1.5,
    top_k_per_page: int = 50,
    max_total_controls: int = 100,
) -> list[tuple[str, int, float]]:
    """
    Two-stage retrieval: top-K per page + peakiness filter.

    Returns:
        List of (control_id, best_page, z_peak) tuples
    """
    num_pages = len(page_images)
    num_controls = len(controls)
    control_ids = [c.control_id for c in controls]

    # Stage 1: Score all controls on all pages
    # Build score matrix [num_pages, num_controls]
    score_matrix = np.zeros((num_pages, num_controls))

    for page_idx, (page_num, image_bytes) in enumerate(page_images):
        page_pred = predictor.predict_page(
            page_num, image_bytes,
            controls=controls,
            score_threshold=0.0  # Get all scores
        )
        for scored_ctrl in page_pred.top_controls:
            ctrl_idx = control_ids.index(scored_ctrl.control.control_id)
            score_matrix[page_idx, ctrl_idx] = scored_ctrl.score

    # Stage 2: Compute peakiness for each control
    peakiness_results = compute_peakiness(score_matrix, control_ids)

    # Stage 3: Filter by peakiness
    filtered = filter_by_peakiness(
        peakiness_results,
        z_peak_threshold=z_peak_threshold,
        max_controls=max_total_controls,
    )

    # Return (control_id, best_page, z_peak)
    return [(p.control_id, p.best_page, p.z_peak) for p in filtered]
```

### Alternative: Combine with Per-Page Top-K

For defense in depth, combine peakiness with per-page top-K:

```python
def hybrid_retrieval(
    score_matrix: np.ndarray,
    control_ids: list[str],
    top_k_per_page: int = 30,
    z_peak_threshold: float = 1.0,
) -> set[str]:
    """
    Hybrid: union of per-page top-K AND peakiness filter.

    - Per-page top-K: catches controls that dominate specific pages
    - Peakiness filter: catches controls with concentrated evidence
    """
    candidates = set()

    # Per-page top-K
    for page_idx in range(score_matrix.shape[0]):
        page_scores = score_matrix[page_idx, :]
        top_k_indices = np.argsort(page_scores)[-top_k_per_page:]
        for idx in top_k_indices:
            candidates.add(control_ids[idx])

    # Peakiness filter (may add controls not in per-page top-K)
    peakiness_results = compute_peakiness(score_matrix, control_ids)
    for p in peakiness_results:
        if p.z_peak >= z_peak_threshold:
            candidates.add(p.control_id)

    return candidates
```

### Why Peakiness Works

| Control Type | Score Pattern | Peakiness | Outcome |
|--------------|---------------|-----------|---------|
| Relevant | Spikes on 1-2 pages | High z_peak (>2) | **KEEP** |
| Generic | High everywhere | Low z_peak (<1) | Filter out |
| Irrelevant | Low everywhere | Low z_peak | Filter out |
| Partially relevant | Moderate spike | Medium z_peak (~1.5) | Keep if above threshold |

**Concrete Example (8-page document):**

| Control | Scores by Page | Mean | Std | Max | z_peak | Decision |
|---------|----------------|------|-----|-----|--------|----------|
| "Asset inventory" | [0.32, **0.58**, 0.35, 0.31, 0.33, 0.30, 0.34, 0.32] | 0.36 | 0.09 | 0.58 | **2.4** | ✅ KEEP |
| "Security policy" | [0.45, 0.47, 0.44, 0.46, 0.48, 0.45, 0.47, 0.46] | 0.46 | 0.01 | 0.48 | **1.5** | ⚠️ Borderline |
| "Data protection" | [0.41, 0.43, **0.52**, 0.40, 0.42, 0.44, 0.41, 0.43] | 0.43 | 0.04 | 0.52 | **2.3** | ✅ KEEP |

### Threshold Tuning

| z_peak Threshold | Interpretation | Expected Behavior |
|------------------|----------------|-------------------|
| 1.0 | Include if max is 1σ above mean | Permissive, larger candidate sets |
| 1.5 | Include if max is 1.5σ above mean | Balanced |
| 2.0 | Include if max is 2σ above mean | Strict, smaller candidate sets |
| 2.5+ | Only keep strong spikes | May miss borderline relevant controls |

**Recommendation**: Start with z_peak >= 1.5, combined with top-30 per page.

### Implementation Cost

**LOW**
- **No offline computation needed** - works with arbitrary controls
- **Runtime**: Score matrix already computed, peakiness is O(num_controls) arithmetic
- **Memory**: Score matrix is (num_pages × num_controls) floats

### Expected Impact

- **Generic controls eliminated**: Controls that score uniformly high get low z_peak
- **Evidence localization**: best_page tells us WHERE the evidence is
- **Complements top-K**: Peakiness catches controls that spike but aren't in per-page top-K

### Measurement

For the Asset Management Policy (Row 4) experiment:
- Compute peakiness for all 779 controls
- Compare GT vs non-GT z_peak distributions
- Measure candidate set size at z_peak thresholds (1.0, 1.5, 2.0)
- Verify GT controls have higher z_peak than non-GT

### Edge Cases

1. **Single-page documents**: z_peak is undefined (std=0). Fall back to raw score top-K.
2. **Very short documents (2-3 pages)**: Peakiness may be noisy. Consider minimum page threshold.
3. **Control matches ALL pages equally well**: Legitimate case (e.g., "Document Control Policy" for a policy document). May need domain-specific handling.

---

## Experiment 2: Domain-First Hierarchical Retrieval

### Source
Gemini 2.5 suggestion #4, Claude semantic_vs_compliance.md 1.2

### Problem It Solves
Matching specific controls is hard because control descriptions are short and varied. Matching **domains** is easier because domains represent broader concepts that are more likely to match page content.

### Key Insight
It's much easier for the retriever to recognize "This page is about Configuration Management" than to match a specific "PowerShell Constrained Language Mode" control.

### Approach

```python
# Offline: Embed domain names/descriptions
DOMAINS = {
    "Access Control": "User access, authentication, authorization, identity management...",
    "Change Management": "Change control, change requests, approval, deployment...",
    "Configuration Management": "System configuration, baselines, hardening, settings...",
    # ... 20-30 domains
}

domain_embeddings = {
    name: colmodernvbert.encode(description)
    for name, description in DOMAINS.items()
}

# Group controls by domain
controls_by_domain = defaultdict(list)
for control in all_controls:
    controls_by_domain[control.domain].append(control)

# Runtime: Domain-first retrieval
def retrieve_hierarchical(page_image):
    # Step 1: Score page against domains
    page_embedding = colmodernvbert.encode(page_image)
    domain_scores = {
        name: similarity(page_embedding, emb)
        for name, emb in domain_embeddings.items()
    }

    # Step 2: Get matched domains
    matched_domains = [name for name, score in domain_scores.items() if score >= DOMAIN_THRESHOLD]

    # Step 3: Include ALL controls from matched domains
    candidates = set()
    for domain in matched_domains:
        candidates.update(controls_by_domain[domain])

    # Step 4: Also include top-K semantic matches (safety net)
    semantic_top_k = get_top_k_controls(page_image, k=50)

    return candidates | set(semantic_top_k)
```

### Limitation: Controls Without Domain Metadata

Not all controls have domain metadata. For arbitrary customer-defined controls, domain may be absent entirely.

**Fallback Strategy: Semantic Domain Assignment**

At runtime, assign domainless controls to the closest domain based on their text:

```python
def assign_control_to_domain(control_text: str, domain_embeddings: dict) -> str | None:
    """Assign a control to its closest domain based on semantic similarity."""
    control_embedding = colmodernvbert.encode(control_text)

    best_domain = None
    best_score = DOMAIN_ASSIGNMENT_THRESHOLD  # e.g., 0.3

    for domain_name, domain_emb in domain_embeddings.items():
        score = similarity(control_embedding, domain_emb)
        if score > best_score:
            best_score = score
            best_domain = domain_name

    return best_domain  # None if no domain scores above threshold

# Runtime: Handle controls with and without domain metadata
def group_controls_by_domain(controls: list[Control], domain_embeddings: dict) -> dict:
    controls_by_domain = defaultdict(list)
    domainless_controls = []

    for control in controls:
        if control.domain:
            # Use existing domain metadata
            controls_by_domain[control.domain].append(control)
        else:
            # Infer domain from control text
            inferred_domain = assign_control_to_domain(control.description, domain_embeddings)
            if inferred_domain:
                controls_by_domain[inferred_domain].append(control)
            else:
                # Truly unmappable - will rely on semantic top-K safety net
                domainless_controls.append(control)

    return controls_by_domain, domainless_controls
```

**When This Approach Fails**:
- If most controls are domainless AND their text doesn't map well to standard domains
- Example: Highly custom controls like "Ensure TPS reports are filed on Fridays" won't map to any compliance domain
- In this case, the semantic top-K safety net (Step 4) becomes the primary retrieval mechanism

**Recommendation**: If >50% of controls are domainless and unmappable, skip domain-first entirely and use raw semantic matching.

### Why It Should Work

- Domain matching is more robust than individual control matching
- Guarantees all controls from matched domains are included
- Semantic top-K provides safety net for cross-domain matches
- Semantic domain assignment handles domainless controls gracefully

### Implementation Cost

**LOW**
- Define ~20-30 domain descriptions (can derive from DCF metadata)
- Embed domains once
- Score page against domains at runtime (20-30 comparisons, fast)
- Map domains to controls (static lookup)

### Expected Impact

- Configuration Management controls get included when page matches Config Mgmt domain
- Should capture compliance-associated controls that match domain but not specific text
- Domain matching is coarser but more reliable

### Measurement

- Domain classification accuracy (manual review)
- Per-domain recall
- Candidate set size (controls per matched domain)

---

## Experiment 3: BiModernVBERT (Different Model Architecture)

### Source
ChatGPT o1 Pro, ModernVBERT model family

### Problem It Solves
ColModernVBERT (late interaction) may have intrinsic score distribution properties that make thresholding difficult. A different architecture might produce more separable distributions.

### Model Family Options

| Model | Type | Description |
|-------|------|-------------|
| **ColModernVBERT** (current) | Late interaction | Token-level matching, best for ranking |
| **BiModernVBERT** | Bi-encoder | Single embedding per document/query, faster |
| **ModernVBERT-embed** | Bi-encoder | Contrastive learning, no document specialization |
| **ModernVBERT** | Base model | Just modality alignment |

### Why BiModernVBERT Might Be Better

- **Simpler score**: Single cosine similarity instead of MaxSim aggregation
- **Different distribution**: Bi-encoders often have wider score ranges
- **Faster**: No token-level interaction, just dot product

### Approach

```python
# Swap model
from colpali_engine import BiModernVBERT  # hypothetical import

# Same inference flow, different model
def predict_with_bimodernvbert(page_image, controls):
    page_embedding = bimodernvbert.encode_image(page_image)  # (1, dim)
    control_embeddings = bimodernvbert.encode_text(controls)  # (N, dim)

    # Simple cosine similarity
    scores = cosine_similarity(page_embedding, control_embeddings)
    return scores
```

### Implementation Cost

**LOW**
- Just model swap (same colpali_engine library)
- Re-run experiments with new model
- Compare score distributions

### Expected Impact

- Unknown - need to test empirically
- Bi-encoders trade precision for speed, may or may not help thresholding
- Worth testing given low cost

### Measurement

- Score distribution comparison (min, max, median, std)
- GT vs non-GT separation
- Ranking quality (are GT controls still ranked well?)

---

## Recommended Experiment Order

Based on impact potential and implementation cost:

### Phase 1: Quick Wins

1. **Peakiness Filter** - ❌ TESTED, FAILED (see peakiness_experiment_results.md)
2. **BiModernVBERT** - Simplest change, just swap model and re-run

### Phase 2: Hierarchical

3. **Domain-First Retrieval** - Requires domain definitions and embedding, more infrastructure

---

## Success Metrics

For each experiment, measure:

| Metric | Current Baseline | Target |
|--------|------------------|--------|
| GT vs Non-GT median gap | 0.03 | > 0.10 |
| Candidate set size at 100% recall | 755/779 (97%) | < 400/779 (50%) |
| Candidate set size at 90% recall | 530/779 (68%) | < 200/779 (25%) |

If any experiment achieves the targets, we can:
- Use it as the primary retrieval strategy
- Or combine multiple approaches for robust filtering

---

## Non-Starters (What We're NOT Trying)

Based on the selection criteria, these were explicitly excluded:

| Approach | Why Excluded |
|----------|--------------|
| Lightweight Score Calibrator | Supervised ML model trained on specific dataset; unlikely to generalize to arbitrary controls/documents |
| Control Co-occurrence Graph (Anchor & Drag) | Requires pre-built graph from known controls; won't work with arbitrary customer-defined controls |
| Hypothetical Policy Generation (Gemini #1) | Requires LLM for each control (779 calls) |
| Visual Listwise Reranking (Gemini #2) | Requires VLM calls at runtime |
| Two-Stage LLM Filtering | Requires LLM calls |
| Control Description Enrichment | Requires LLM, modifies source data |
| Fine-Tuning on Compliance Associations | High implementation cost |
| Policy Type Classification | Requires LLM or separate classifier |

These may be worth exploring later if the non-LLM approaches don't work.
