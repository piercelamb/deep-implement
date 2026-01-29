# Understanding Control Clustering: A Complete Guide

## The Problem We're Solving

Imagine you're a compliance officer at a company. You have a **policy document** (like a 50-page "Information Security Policy" PDF) and you need to check whether it addresses **779 different compliance controls** (rules like "Passwords must be at least 12 characters" or "All data must be encrypted at rest").

Checking all 779 controls manually would take forever. So we use an AI (specifically Google's Gemini) to read the document and tell us which controls are addressed.

**But there's a catch**: We can't just send all 779 controls to the AI at once. That would:
1. Cost too much (AI APIs charge per token)
2. Overwhelm the AI (too much to process at once)
3. Hit rate limits (APIs limit how many requests you can make)

So we need to **batch** the controls - send them in groups of ~10 at a time. With 779 controls and groups of 10, that's ~78 API calls per document. We cap this at **50 calls maximum** per document to control costs.

**The key question**: How do we decide which controls go together in each batch?

---

## Why Clustering Matters: A Library Analogy

Imagine you're organizing 779 books into 50 carts to be shelved. You have two options:

### Option A: Random Assignment
Put books in carts randomly. Cart 1 might have a cookbook, a physics textbook, a romance novel, and a legal reference.

**Problem**: When the librarian takes Cart 1 to the shelves, they have to walk all over the library - from cooking to science to fiction to law. It's inefficient and confusing.

### Option B: Thematic Grouping
Put similar books together. Cart 1 has all the cooking books. Cart 2 has all the physics books. And so on.

**Benefit**: The librarian can go straight to the cooking section, shelf everything, and move on. Much faster and easier to verify nothing was missed.

---

## How This Applies to Our Controls

Our 779 compliance controls are like those books. Some controls are about **passwords and authentication**, some are about **encryption**, some are about **vendor management**, etc.

When we send a batch of controls to the AI:
- If they're **similar** (all about encryption), the AI can focus on the "Encryption" section of the document and efficiently check all of them
- If they're **dissimilar** (one about encryption, one about HR policies, one about physical security), the AI has to mentally "jump around" the document

**Clustering** is how we automatically figure out which controls are "similar" so we can group them together.

---

## What is an "Embedding"?

Before we can cluster controls, we need a way to measure "similarity" between them. This is where **embeddings** come in.

### The Concept

An embedding is a way to represent text as a list of numbers (called a "vector"). Think of it like GPS coordinates for ideas:

- GPS: `(latitude, longitude)` = 2 numbers that locate a place on Earth
- Embedding: `(0.23, -0.87, 0.45, ..., 0.12)` = ~768 numbers that locate an idea in "meaning space"

**Key insight**: Things that are similar in meaning end up close together in this number space.

### Example (Simplified)

Imagine embeddings were just 2 numbers (they're actually hundreds). We might get:

| Control | Embedding | Topic |
|---------|-----------|-------|
| "Passwords must be 12+ characters" | (0.8, 0.2) | Authentication |
| "Multi-factor auth required" | (0.75, 0.25) | Authentication |
| "Data encrypted at rest" | (0.1, 0.9) | Encryption |
| "TLS 1.2 for data in transit" | (0.15, 0.85) | Encryption |

Notice how the authentication controls have similar numbers (both near 0.8, 0.2), and encryption controls have similar numbers (both near 0.1, 0.9). They form **clusters** in the number space.

### How We Create Embeddings

We use a specialized AI model called **ColModernVBERT** (Column Modern Vision BERT). This model was trained on millions of documents to understand what text means.

For each control, we:
1. Take the control's **description text** (e.g., "The organization requires multi-factor authentication for all remote access")
2. Feed it through ColModernVBERT
3. Get back a list of ~768 numbers representing its meaning

**Code location**: `ai_services/scripts/experiments/control_detection/predictor.py` (lines 287-336)

---

## What is K-Means Clustering?

Now that we have embeddings (lists of numbers) for each control, we need to automatically group similar controls together. **K-Means** is an algorithm that does this.

### The Algorithm (Plain English)

Imagine you have 779 dots scattered on a piece of paper (each dot is a control's embedding visualized in 2D). You want to group them into 75 clusters.

1. **Random Start**: Drop 75 "centroids" (cluster centers) randomly on the paper
2. **Assign Points**: Each dot joins the nearest centroid (forming 75 groups)
3. **Move Centroids**: Move each centroid to the center of its assigned dots
4. **Repeat**: Go back to step 2, reassigning dots to the (now moved) centroids
5. **Stop**: When centroids stop moving significantly, you're done

After this process, you have 75 groups where:
- Dots within a group are close together (similar controls)
- Dots in different groups are far apart (dissimilar controls)

### Our Configuration

```python
n_clusters = ceil(n_controls / target_batch_size)  # Computed dynamically!
random_state = 42    # Use this "seed" for reproducibility
n_init = 10          # Run the algorithm 10 times, keep the best result
```

The cluster count is **not hardcoded** - it's computed from the number of controls and target batch size. See the "Dynamic Cluster Count" section below for details.

**Code location**: `ai_services/scripts/experiments/control_detection/control_clustering.py`

---

## The Technical Detail: Mean Pooling

There's one wrinkle. When ColModernVBERT processes text, it doesn't give us ONE embedding per control. It gives us **one embedding per word token**.

For example, "Passwords must be 12 characters" might become:
- Token 1 ("Passwords"): [0.23, -0.87, ...]
- Token 2 ("must"): [0.45, 0.12, ...]
- Token 3 ("be"): [-0.33, 0.56, ...]
- ... and so on

But K-Means needs ONE vector per control, not multiple. So we **average** all the token embeddings together:

```
Control Embedding = Average of all token embeddings
```

This is called **mean pooling**. It gives us a single "summary" vector for each control.

**Code location**: `ai_services/scripts/experiments/control_detection/control_clustering.py` (lines 30-56)

---

## How Clustering is Used: Coherent Batching

Once we have cluster assignments (Control A is in Cluster 5, Control B is in Cluster 12, etc.), we use them for **batching**.

### The Default: Coherent Batching

When creating batches for the AI, we put controls from the **same cluster** together:

```
Batch 1: [Control from Cluster 5, Control from Cluster 5, Control from Cluster 5, ...]
Batch 2: [Control from Cluster 12, Control from Cluster 12, Control from Cluster 12, ...]
...
```

**Why this helps the AI**:
- All controls in Batch 1 are semantically similar (e.g., all about authentication)
- The AI can focus on ONE section of the document
- It can compare similar controls side-by-side: "Paragraph 3 addresses Control A but NOT Control B because it lacks the word 'required'"

### The Alternative: Diverse Batching

For comparison, we also support **diverse batching** where we deliberately mix controls from different clusters:

```
Batch 1: [Cluster 5, Cluster 12, Cluster 3, Cluster 47, ...]
Batch 2: [Cluster 5, Cluster 12, Cluster 3, Cluster 47, ...]
...
```

This is rarely used because it forces the AI to "jump around" the document mentally.

**Code location**: `ai_services/scripts/experiments/control_detection/batching.py`

---

## The Complete Data Flow

Here's what happens end-to-end:

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: LOAD CONTROLS                                           │
│                                                                 │
│   779 DCF compliance controls with descriptions like:           │
│   - "The organization requires MFA for remote access"           │
│   - "Data at rest must be encrypted using AES-256"              │
│   - "Vendors must complete security questionnaires"             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: GENERATE EMBEDDINGS (one-time, cached)                  │
│                                                                 │
│   For each control description:                                 │
│   1. Feed text into ColModernVBERT model                        │
│   2. Get token-level embeddings (variable length)               │
│   3. Mean-pool to single vector (768 dimensions)                │
│                                                                 │
│   Result: 779 vectors, each with 768 numbers                    │
│   Saved to: files/dcf_control_embeddings.pt                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: CLUSTER EMBEDDINGS (one-time, cached)                   │
│                                                                 │
│   Run K-Means clustering:                                       │
│   - Input: 779 vectors of 768 dimensions                        │
│   - n_clusters: DYNAMIC (ceil(n_controls / target_batch_size))  │
│   - Output: Cluster ID for each control                         │
│                                                                 │
│   Result: {"DCF-1": 5, "DCF-2": 12, "DCF-3": 5, ...}            │
│   Saved to: files/control_clusters.json                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: PROCESS A POLICY DOCUMENT                               │
│                                                                 │
│   For each policy PDF:                                          │
│   1. Score all 779 controls against document pages              │
│   2. Filter to ~200-400 "candidate" controls (score threshold)  │
│   3. Group candidates by max-score page                         │
│   4. IF any page group > MAX_BATCH_SIZE:                        │
│      - Load cluster assignments from cache (lazy!)              │
│      - Split oversized groups by cluster                        │
│   5. Adjust batch count:                                        │
│      - IF batches > MAX_CALLS: Consolidate (merge small ones)   │
│      - IF MINIMIZE_BATCH_SIZES and batches < MAX_CALLS:         │
│        Expand (split large batches to reach MAX_CALLS)          │
│   6. Send batches to Gemini AI (max 50 calls)                   │
│   7. Aggregate results                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Dynamic Cluster Count

Rather than hardcoding a fixed number of clusters, we **dynamically compute** the cluster count based on the input size and target batch size:

```python
n_clusters = ceil(n_controls / target_batch_size)
```

### Why Dynamic?

1. **Scales with input size**: 50 controls → 5 clusters, 779 controls → 78 clusters
2. **Tied to batching**: Since clustering exists to serve batching, we derive cluster count from batch size
3. **Works for any input**: No need to tune a magic number for different control sets
4. **One cluster ≈ one batch**: Each cluster roughly maps to one LLM batch

### Examples

| Controls | Target Batch Size | Clusters |
|----------|-------------------|----------|
| 50 | 10 | 5 |
| 200 | 10 | 20 |
| 779 | 10 | 78 |
| 8 | 10 | 1 |

### Code

```python
from ai_services.scripts.experiments.control_detection.control_clustering import compute_n_clusters

# Compute dynamically
n_clusters = compute_n_clusters(n_controls=779, target_batch_size=10)  # Returns 78

# Or let ControlClusterCache.compute() do it automatically
cache = ControlClusterCache.compute(
    embeddings=embeddings,
    control_ids=control_ids,
    embedding_hash=hash,
    n_clusters=None,  # Auto-compute!
    target_batch_size=10,
)
```

---

## Design Decisions: Pre-computed vs Dynamic Clustering

This section documents an important architectural decision about **when** and **on what data** we perform clustering.

### The Question

When processing a policy document, ColModernVBERT first scores all 779 controls against the document pages, then filters to only those meeting a score threshold (e.g., ~200-400 "candidate" controls).

**Should we cluster:**
- **Option A**: All 779 controls once (pre-computed, cached)
- **Option B**: Only the filtered candidates per-document (dynamic, computed on-the-fly)

### What We Chose: Pre-computed Clustering (Option A)

We cluster **all 779 DCF controls once** based on their text embeddings (descriptions), then cache the result. When processing a document:

1. ColModernVBERT filters to ~200-400 candidates
2. We look up each candidate's **pre-assigned cluster** from the cache
3. We use these assignments for splitting oversized page groups

```python
# Pre-computed cluster map (for ALL 779 controls)
cluster_map = {"DCF-001": 0, "DCF-002": 3, "DCF-003": 0, ...}

# At runtime, just look up the filtered candidates
for candidate in filtered_candidates:  # ~200 controls
    cluster_id = cluster_map[candidate.control_id]  # Fast lookup
```

### Why Not Dynamic Clustering?

Running K-means on a filtered subset produces **completely different clusters** than running it on the full set. This is because K-means centroids are computed as the **mean of all assigned points**:

```
Full set (779 controls):
┌─────────────────────────────────────────┐
│    ○ ○           Centroid A             │
│   ○ ○ ○ ●          (here)               │
│    ○ ○                                  │
│                                         │
│         ○ ○ ○                           │
│        ○ ○ ○ ○ ●   Centroid B           │
│         ○ ○ ○        (here)             │
└─────────────────────────────────────────┘

Filtered set (200 controls) - only ◆ remain:
┌─────────────────────────────────────────┐
│    ◆              Centroid A            │
│      ◆   ●          (MOVED!)            │
│                                         │
│                                         │
│           ◆ ◆                           │
│          ◆   ●     Centroid B           │
│           ◆          (MOVED!)           │
└─────────────────────────────────────────┘
```

Remove points → centroids shift → cluster boundaries change → same control might be in a different cluster.

**Trade-offs:**

| Approach | Semantic Quality | Speed | Consistency |
|----------|-----------------|-------|-------------|
| Pre-computed (Option A) | Good (static semantic grouping) | Fast (cache lookup) | ✅ Same clusters across documents |
| Dynamic (Option B) | Optimal for filtered set | Slow (K-means per doc) | ❌ Different clusters per document |

**We chose Option A because:**
1. Semantic similarity between controls is **intrinsic** - it doesn't change based on what document we're analyzing
2. "Access control" controls should cluster together regardless of which document is being processed
3. Pre-computation is much faster at runtime (lookup vs K-means)
4. Consistency across documents makes debugging easier

### When Are Clusters Actually Used?

Clusters are **only used when splitting oversized page groups**. The primary batching strategy is:

1. **Group by max-score page**: Controls are first grouped by which page they scored highest on
2. **Split if oversized**: Only if a page group has >MAX_BATCH_SIZE controls do we use clusters to split it
3. **Cluster-based splitting**: Controls in the same cluster stay together in the same sub-batch

**Key insight**: Many documents have no oversized page groups. In those cases, clusters are never used at all.

**Lazy Loading Optimization**: We implemented lazy cluster loading - the cluster cache is only loaded from disk when we detect at least one oversized page group:

```python
# Clusters loaded lazily - only if needed
if num_oversized > 0 and cluster_cache_factory is not None:
    logger.info("Loading cluster cache for %d oversized page groups...", num_oversized)
    cluster_cache = cluster_cache_factory()
    cluster_map = cluster_cache.get_cluster_map()
else:
    cluster_map = {}  # Not needed, use empty map
```

---

## Design Decisions: Choosing n_clusters

Another important decision is **how many clusters** to create. We compute this dynamically:

```python
n_clusters = ceil(n_controls / target_batch_size)
# With 779 controls and target_batch_size=10: n_clusters = 78
```

### The Question

Should we use:
- **Option A**: Batching-driven n_clusters (`ceil(n_controls / target_batch_size)`)
- **Option B**: Data-driven n_clusters (using silhouette score to find the "natural" cluster count)

### What Silhouette Score Would Do

Silhouette score measures how well each point fits in its cluster vs other clusters. Higher is better. You can try multiple values of k and pick the one with the best score:

```python
from sklearn.metrics import silhouette_score

best_k, best_score = None, -1
for k in range(10, 150):
    kmeans = KMeans(n_clusters=k)
    labels = kmeans.fit_predict(embeddings)
    score = silhouette_score(embeddings, labels)
    if score > best_score:
        best_k, best_score = k, score

# best_k = the "natural" number of clusters in the data
```

This finds clusters that reflect the **actual semantic structure** of the controls - maybe there are naturally 30 distinct compliance topics, or maybe 120.

### What We Chose: Batching-Driven (Option A)

We use `n_clusters = ceil(n_controls / target_batch_size)` because:

1. **Purpose-built**: Clustering exists to serve batching. Deriving cluster count from batch size ensures clusters are right-sized.
2. **Predictable sizing**: With 779 controls and target_batch_size=10, we get 78 clusters averaging ~10 controls each. When intersected with a page group, subgroups are likely ≤ MAX_BATCH_SIZE.
3. **No tuning required**: Works automatically for any control count.

### The Trade-off

| Approach | Semantic Quality | Batching Efficiency |
|----------|-----------------|---------------------|
| Silhouette-optimal k | ✅ Natural groupings | ❓ Might need more chunking |
| Batching-driven k | ❓ Arbitrary groupings | ✅ Right-sized for batching |

**Potential issues with silhouette:**
- If optimal k=25, clusters average ~31 controls each. When intersected with a 45-control page group, subgroups could still be large, requiring sequential chunking.
- If optimal k=150, we over-fragment and split related controls unnecessarily.

**A hybrid approach (not implemented):**
```python
# Find natural cluster count
optimal_k = find_optimal_k_by_silhouette(embeddings)

# But ensure clusters aren't too large for batching
min_k = ceil(n_controls / MAX_BATCH_SIZE)  # 78 for 779 controls

final_k = max(optimal_k, min_k)
```

This would give semantically meaningful clusters that are also small enough for batching. However, we decided the current approach is **"good enough"**:
- Controls in the same cluster are still semantically similar (K-means groups similar embeddings)
- The groupings may not be "optimal" but they serve their purpose
- Adding silhouette score computation adds complexity and time

### Future Consideration

If we observe that batches contain semantically unrelated controls (e.g., "encryption" and "HR policies" in the same batch), we could revisit the silhouette score approach. For now, the batching-driven approach works well in practice.

---

## Design Decisions: Consolidation vs Expansion

After page grouping and splitting, we may have more or fewer batches than MAX_CALLS. We have two strategies for adjusting batch count:

### The Question

When we have fewer batches than MAX_CALLS, should we:
- **Option A (Production)**: Leave batches as-is (minimize LLM calls, save cost)
- **Option B (Experiment)**: Expand to reach MAX_CALLS (maximize LLM attention per control)

### What We Implemented: Configurable via `MINIMIZE_BATCH_SIZES`

```python
# In experiment_config.py
MINIMIZE_BATCH_SIZES = True  # Experiment mode: expand to MAX_CALLS
MINIMIZE_BATCH_SIZES = False # Production mode: only consolidate when over MAX_CALLS
```

### How Expansion Works

When `MINIMIZE_BATCH_SIZES=True` and we have fewer batches than MAX_CALLS, we iteratively split the largest batch until reaching the target:

```
┌─────────────────────────────────────────────────────────────────┐
│                    BATCH EXPANSION ALGORITHM                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Input: B batches where B < MAX_CALLS                           │
│  Goal: Reach exactly MAX_CALLS batches (if N >= MAX_CALLS)      │
│                                                                 │
│  while len(batches) < MAX_CALLS:                                │
│    1. Find largest batch (tie-break: lowest primary_page)       │
│    2. If largest batch has <2 controls: STOP (can't split)      │
│    3. Sort batch controls by control_id (deterministic)         │
│    4. Split in half: first half → left batch, second → right    │
│    5. Replace original with left + right                        │
│                                                                 │
│  Special case: If total_controls < MAX_CALLS:                   │
│    → Expand to singletons (one control per batch)               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Behavior Comparison

| Scenario | MINIMIZE_BATCH_SIZES=False | MINIMIZE_BATCH_SIZES=True |
|----------|---------------------------|---------------------------|
| 100 controls, 25 initial batches | 25 batches of ~4 each | 50 batches of 2 each |
| 50 controls, 50 initial batches | 50 batches of 1 each | 50 batches of 1 each (no change) |
| 30 controls, 10 initial batches | 10 batches of ~3 each | 30 batches of 1 each (singletons) |

### Trade-offs

| Mode | Batch Count | Batch Size | LLM Attention | Cost |
|------|-------------|------------|---------------|------|
| Production (`False`) | Natural (≤50) | Larger | Lower per control | Cheaper |
| Experiment (`True`) | Always MAX_CALLS | Minimum | Maximum per control | Full budget |

### Why Two Modes?

**Experiment Mode (`MINIMIZE_BATCH_SIZES=True`)**:
- Establishes a **quality baseline** by giving the LLM maximum attention per control
- Ensures consistent comparison across documents (always 50 calls)
- Helps identify the quality ceiling before optimizing for cost

**Production Mode (`MINIMIZE_BATCH_SIZES=False`)**:
- Minimizes LLM API calls when possible (cost savings)
- Natural batch sizes based on document structure
- May trade some quality for efficiency

### Determinism Rules for Expansion

| Situation | Tie-break Rule |
|-----------|----------------|
| Multiple batches same size | Split batch with **lowest primary_page** |
| Splitting a batch | Sort controls by **control_id**, split in half |
| Source pages after split | Preserved with their controls |

**Code location**: `ai_services/scripts/experiments/control_detection/batching.py` (`expand_batches()`, `_split_batch()`, `_find_largest_batch_idx()`)

### How Consolidation Works

When we have MORE batches than MAX_CALLS, we need to reduce batch count. This happens in two phases:

**Phase A: Merge Small Batches**

The `consolidate_batches()` function iteratively finds the best pair of batches to merge:

```
┌─────────────────────────────────────────────────────────────────┐
│                  BATCH CONSOLIDATION ALGORITHM                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Input: B batches where B > MAX_CALLS                           │
│  Goal: Reduce to MAX_CALLS batches via merging                  │
│                                                                 │
│  while len(batches) > MAX_CALLS:                                │
│    1. Find best pair to merge where combined_size <= MAX_BATCH  │
│       - Prefer smaller combined sizes                           │
│       - Prefer adjacent pages (closer page numbers)             │
│    2. If no valid pair found: STOP (can't merge further)        │
│    3. Merge the pair into one batch                             │
│    4. Remove the two originals, add the merged batch            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Why merging can get stuck:** If all batches are near MAX_BATCH_SIZE, no two can be merged without exceeding the limit. For example, with 64 batches averaging 8 controls each, merging two 8-control batches would create a 16-control batch (exceeding MAX_BATCH_SIZE=10).

**Phase B: Redistribute (Secondary Truncation)**

When merging alone can't reduce batch count to MAX_CALLS, `truncate_batches()` redistributes controls:

```
┌─────────────────────────────────────────────────────────────────┐
│                  BATCH REDISTRIBUTION ALGORITHM                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Input: B batches where B > MAX_CALLS (merging got stuck)       │
│  Goal: Reduce to MAX_CALLS batches while PRESERVING ALL controls│
│                                                                 │
│  while len(batches) > MAX_CALLS:                                │
│    1. Find the SMALLEST batch                                   │
│       - Tie-break: lowest primary_page number                   │
│    2. For each control in smallest batch:                       │
│       - Find a batch with room (size < MAX_BATCH_SIZE)          │
│       - Move the control to that batch                          │
│    3. Remove the (now empty) smallest batch                     │
│                                                                 │
│  Key invariant: If total_controls <= capacity (MAX_CALLS *      │
│  MAX_BATCH_SIZE), ALL controls are preserved. No dropping.      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Why redistribution instead of dropping?**

Previously, `truncate_batches` would drop controls one-by-one from the largest batch until batches started emptying. This caused a severe bug:

| Old Behavior (Buggy) | New Behavior (Fixed) |
|---------------------|----------------------|
| Find largest batch | Find smallest batch |
| Drop one control | Redistribute ALL controls |
| Repeat until batch empties | Remove empty batch |
| Result: 500 controls → 50 (one per batch!) | Result: 500 controls → 500 (50 batches of 10) |

The bug occurred because dropping from the LARGEST batch caused ALL batches to shrink to size 1 before any got removed. The fix redistributes from the SMALLEST batch, efficiently eliminating batches while preserving controls.

**Code location**: `ai_services/scripts/experiments/control_detection/batching.py` (`consolidate_batches()`, `truncate_batches()`)

---

## Cache Invalidation: Staying Up-to-Date

The embedding and clustering computations are expensive (takes a few minutes). So we cache the results to disk:

- **Embeddings cache**: `files/dcf_control_embeddings.pt`
- **Cluster cache**: `files/control_clusters.json`

But what if the controls change? We use a **hash** to detect this:

1. When generating embeddings, we compute a SHA256 hash of all control IDs and descriptions
2. We store this hash in both cache files
3. When loading, we compare the stored hash with the current hash
4. If they differ, we regenerate (controls changed)

**Code location**: `ai_services/scripts/experiments/control_detection/control_clustering.py` (lines 226-237)

---

## Summary

| Concept | What It Is | Why We Need It |
|---------|-----------|----------------|
| **Embedding** | A list of ~768 numbers representing the "meaning" of text | To measure similarity between controls mathematically |
| **ColModernVBERT** | An AI model that converts text to embeddings | To create high-quality embeddings that capture semantic meaning |
| **Mean Pooling** | Averaging multiple vectors into one | K-Means needs one vector per control, not one per word |
| **K-Means** | Algorithm that groups similar vectors together | To automatically find which controls are semantically similar |
| **Cluster** | A group of controls that are similar | The basis for batching decisions |
| **Coherent Batching** | Putting same-cluster controls in the same batch | Helps the AI efficiently process similar controls together |

---

## File Locations

| File | Purpose |
|------|---------|
| `predictor.py` | Generates embeddings using ColModernVBERT |
| `control_clustering.py` | K-Means clustering, dynamic n_clusters computation, cache management |
| `batching.py` | Uses clusters to create coherent/diverse batches |
| `control_centric_decider.py` | Orchestrates the full flow |
| `experiment_config.py` | Configuration (batch sizes, thresholds, etc.) |

---

## Glossary

- **Control**: A compliance requirement (e.g., "Passwords must be 12+ characters")
- **Embedding**: A fixed-length list of numbers representing text meaning
- **Vector**: Another name for embedding (a point in multi-dimensional space)
- **Token**: A word or subword piece from text tokenization
- **Mean Pooling**: Averaging multiple vectors into one
- **K-Means**: An algorithm that groups similar vectors into K clusters
- **Centroid**: The center point of a cluster
- **Cluster ID**: A number (0 to n_clusters-1) identifying which cluster a control belongs to
- **Coherent Batching**: Grouping same-cluster controls in the same batch
- **Diverse Batching**: Spreading different-cluster controls across batches
- **Silhouette Score**: A metric measuring how well points fit in their assigned clusters (-1 to 1, higher is better)
- **Pre-computed Clustering**: Computing clusters once for all controls, then using as a lookup table
- **Dynamic Clustering**: Computing clusters on-the-fly for each document's filtered candidates
- **Page Group**: Controls grouped by which page they scored highest on (before cluster-based splitting)
- **Oversized Page Group**: A page group with more controls than MAX_BATCH_SIZE, requiring splitting
- **Lazy Loading**: Deferring cluster cache loading until we detect an oversized page group that needs it
- **Batch Consolidation**: Merging small batches to reduce batch count below MAX_CALLS (production behavior)
- **Batch Expansion**: Splitting large batches to increase batch count to MAX_CALLS (experiment behavior)
- **MINIMIZE_BATCH_SIZES**: Configuration flag controlling consolidation vs expansion behavior


## Example Scenarios

The following scenarios show the batching flow with different document characteristics.
**Note:** Scenarios 1-4 show `MINIMIZE_BATCH_SIZES=False` (production mode). Scenario 5 shows `MINIMIZE_BATCH_SIZES=True` (experiment mode).

---

### Scenario 1: Under Capacity, No Oversized Groups (Clusters NOT Loaded)

```
# Assumptions:
# - 25-page document
# - 450 total DCF controls
# - ColModernVBERT threshold = 0.25
# - MAX_CALLS = 50, MAX_BATCH_SIZE = 10
# - Capacity = 500
# - MINIMIZE_BATCH_SIZES = False

INFO - Processing pages 1-8 (batch 1)
INFO - Processing pages 9-16 (batch 2)
INFO - Processing pages 17-24 (batch 3)
INFO - Processing pages 25-25 (batch 4)
INFO - ColModernVBERT: 450 controls × 25 pages = 11250 scores, 823 passed threshold (0.25), 25 pages with matches
INFO - Dedupe: 25 pages, 823 scored entries → 200 unique controls
INFO - Page grouping: 200 controls → 25 page groups (0 oversized)
INFO - After splitting: 25 batches (from 25 page groups)
INFO - No adjustment needed: 25 batches <= 50 max_calls
INFO - Created 25 page-aware batches (size: min=4, max=10, avg=8.0), starting LLM calls...
INFO - Creating Gemini cache for 'SOC2-Policy-v3.pdf'...
```

**Key observations:**
- 200 unique controls < 500 capacity → no truncation
- 0 oversized page groups → clusters NOT loaded (lazy loading skipped)
- 25 batches < 50 max_calls → no consolidation (production mode keeps natural count)

---

### Scenario 2: Under Capacity, With Oversized Groups (Clusters Loaded Lazily)

```
# Assumptions:
# - 15-page document with dense compliance sections
# - 450 total DCF controls
# - ColModernVBERT threshold = 0.20 (lower threshold → more matches)
# - MAX_CALLS = 50, MAX_BATCH_SIZE = 10
# - Capacity = 500
# - Pages 3 and 7 are dense (45 and 30 controls respectively)
# - MINIMIZE_BATCH_SIZES = False

INFO - Processing pages 1-8 (batch 1)
INFO - Processing pages 9-15 (batch 2)
INFO - ColModernVBERT: 450 controls × 15 pages = 6750 scores, 412 passed threshold (0.20), 15 pages with matches
INFO - Dedupe: 15 pages, 412 scored entries → 180 unique controls
INFO - Page grouping: 180 controls → 15 page groups (2 oversized)
INFO - Loading cluster cache for 2 oversized page groups...
INFO - Loaded 450 cluster assignments (k=50)
INFO - After splitting: 22 batches (from 15 page groups)
INFO - No adjustment needed: 22 batches <= 50 max_calls
INFO - Created 22 page-aware batches (size: min=5, max=10, avg=8.2), starting LLM calls...
INFO - Creating Gemini cache for 'Dense-Security-Policy.pdf'...
```

**Key observations:**
- 180 unique controls < 500 capacity → no truncation
- 2 oversized page groups → clusters LOADED lazily
- 22 batches < 50 max_calls → no consolidation (production mode)

---

### Scenario 3: Over Capacity (Truncation + Clusters + Consolidation)

```
# Assumptions:
# - 50-page comprehensive document
# - 450 total DCF controls
# - ColModernVBERT threshold = 0.18 (low threshold → many matches)
# - MAX_CALLS = 50, MAX_BATCH_SIZE = 10
# - Capacity = 500
# - MINIMIZE_BATCH_SIZES = False

INFO - Processing pages 1-8 (batch 1)
INFO - Processing pages 9-16 (batch 2)
INFO - Processing pages 17-24 (batch 3)
INFO - Processing pages 25-32 (batch 4)
INFO - Processing pages 33-40 (batch 5)
INFO - Processing pages 41-48 (batch 6)
INFO - Processing pages 49-50 (batch 7)
INFO - ColModernVBERT: 450 controls × 50 pages = 22500 scores, 2847 passed threshold (0.18), 50 pages with matches
INFO - Dedupe: 50 pages, 2847 scored entries → 420 unique controls
INFO - Page grouping: 420 controls → 38 page groups (12 oversized)
INFO - Loading cluster cache for 12 oversized page groups...
INFO - Loaded 450 cluster assignments (k=50)
INFO - After splitting: 62 batches (from 38 page groups)
INFO - Consolidation: 62 → 50 batches (target: 50)
INFO - Created 50 page-aware batches (size: min=7, max=10, avg=8.4), starting LLM calls...
INFO - Creating Gemini cache for 'Comprehensive-Security-Policy.pdf'...
```

**Key observations:**
- 420 unique controls < 500 capacity → no truncation (close but under)
- 12 oversized page groups → clusters LOADED lazily
- 62 batches > 50 max_calls → consolidation merges batches

---

### Scenario 4: Way Over Capacity (Truncation Required)

```
# Assumptions:
# - 80-page exhaustive policy document
# - 779 total DCF controls (full set)
# - ColModernVBERT threshold = 0.12 (very low → most controls match)
# - MAX_CALLS = 50, MAX_BATCH_SIZE = 10
# - Capacity = 500
# - MINIMIZE_BATCH_SIZES = False

INFO - Processing pages 1-8 (batch 1)
...
INFO - Processing pages 73-80 (batch 10)
INFO - ColModernVBERT: 779 controls × 80 pages = 62320 scores, 8934 passed threshold (0.12), 80 pages with matches
INFO - Dedupe: 80 pages, 8934 scored entries → 623 unique controls
WARNING - Truncating 623 candidates to 500 (over capacity)
INFO - Page grouping: 500 controls → 65 page groups (22 oversized)
INFO - Loading cluster cache for 22 oversized page groups...
INFO - Loaded 779 cluster assignments (k=78)
INFO - After splitting: 94 batches (from 65 page groups)
INFO - Consolidation: 94 → 50 batches (target: 50)
INFO - Created 50 page-aware batches (size: min=10, max=10, avg=10.0), starting LLM calls...
INFO - Creating Gemini cache for 'Master-Compliance-Framework.pdf'...
```

**Key observations:**
- 623 unique controls > 500 capacity → TRUNCATION: dropped 123 lowest-scoring
- 22 oversized page groups → clusters LOADED lazily
- 94 batches > 50 max_calls → heavy consolidation
- Final: exactly 50 batches at max size (10 each)

---

### Scenario 5: Experiment Mode with Expansion (MINIMIZE_BATCH_SIZES=True)

```
# Assumptions:
# - 25-page document (same as Scenario 1)
# - 450 total DCF controls
# - ColModernVBERT threshold = 0.25
# - MAX_CALLS = 50, MAX_BATCH_SIZE = 10
# - Capacity = 500
# - MINIMIZE_BATCH_SIZES = True  ← EXPERIMENT MODE

INFO - Processing pages 1-8 (batch 1)
INFO - Processing pages 9-16 (batch 2)
INFO - Processing pages 17-24 (batch 3)
INFO - Processing pages 25-25 (batch 4)
INFO - ColModernVBERT: 450 controls × 25 pages = 11250 scores, 823 passed threshold (0.25), 25 pages with matches
INFO - Dedupe: 25 pages, 823 scored entries → 200 unique controls
INFO - Page grouping: 200 controls → 25 page groups (0 oversized)
INFO - After splitting: 25 batches (from 25 page groups)
INFO - Expansion: 25 → 50 batches (target: 50, minimize_batch_sizes=True)
INFO - Created 50 page-aware batches (size: min=3, max=5, avg=4.0), starting LLM calls...
INFO - Creating Gemini cache for 'SOC2-Policy-v3.pdf'...
```

**Key observations:**
- Same document as Scenario 1, but with `MINIMIZE_BATCH_SIZES=True`
- 25 batches < 50 max_calls → EXPANSION splits large batches
- Final: exactly 50 batches with minimum sizes (avg 4 vs avg 8 in Scenario 1)
- More LLM calls = more attention per control = better quality baseline

**Comparison: Scenario 1 vs Scenario 5**

| Metric | Scenario 1 (Production) | Scenario 5 (Experiment) |
|--------|------------------------|-------------------------|
| Unique controls | 200 | 200 |
| Final batches | 25 | 50 |
| Avg batch size | 8.0 | 4.0 |
| LLM calls | 25 | 50 |
| Cost | Lower | Full budget |
| LLM attention/control | Normal | Maximum |

---

### Scenario 6: Experiment Mode with Few Controls (Singleton Expansion)

```
# Assumptions:
# - 10-page focused document
# - 450 total DCF controls
# - ColModernVBERT threshold = 0.50 (high threshold → few matches)
# - MAX_CALLS = 50, MAX_BATCH_SIZE = 10
# - Capacity = 500
# - MINIMIZE_BATCH_SIZES = True  ← EXPERIMENT MODE

INFO - Processing pages 1-8 (batch 1)
INFO - Processing pages 9-10 (batch 2)
INFO - ColModernVBERT: 450 controls × 10 pages = 4500 scores, 87 passed threshold (0.50), 8 pages with matches
INFO - Dedupe: 10 pages, 87 scored entries → 30 unique controls
INFO - Page grouping: 30 controls → 8 page groups (0 oversized)
INFO - After splitting: 8 batches (from 8 page groups)
INFO - Expansion: 8 → 30 batches (target: 50, minimize_batch_sizes=True)
INFO - Created 30 page-aware batches (size: min=1, max=1, avg=1.0), starting LLM calls...
INFO - Creating Gemini cache for 'Focused-Policy.pdf'...
```

**Key observations:**
- Only 30 unique controls (fewer than MAX_CALLS)
- Cannot reach 50 batches, so expands to **singletons** (1 control per batch)
- Each control gets its own dedicated LLM call for maximum attention

---

## Summary Table

| Scenario | Controls | Mode | Truncated? | Oversized | Clusters? | Adjustment | Final Batches |
|----------|----------|------|------------|-----------|-----------|------------|---------------|
| 1. Under, distributed | 200 | Production | No | 0 | ❌ No | None | 25 |
| 2. Under, dense | 180 | Production | No | 2 | ✅ Yes | None | 22 |
| 3. Over max_calls | 420 | Production | No | 12 | ✅ Yes | Consolidate (62→50) | 50 |
| 4. Over capacity | 623 | Production | Yes (→500) | 22 | ✅ Yes | Consolidate (94→50) | 50 |
| 5. Expansion | 200 | Experiment | No | 0 | ❌ No | Expand (25→50) | 50 |
| 6. Singletons | 30 | Experiment | No | 0 | ❌ No | Expand (8→30) | 30 |