# ColModernVBERT Score Normalization Research

## Date: 2025-12-19

## Problem Statement

The control detection experiment uses ColModernVBERT (a multimodal ColBERT variant) to match policy document pages against 779 DCF control descriptions. The raw similarity scores produced by the MaxSim late interaction mechanism are:

1. **Unbounded** - Raw scores were in the 400-500 range
2. **Incomprehensible** - No intuitive meaning (is 427 good? bad?)
3. **Dependent on page length** - More tokens = higher scores

This made it impossible to set meaningful thresholds for the LLM decision layer, which needs to:
- Decide which pages "trigger" an LLM call
- Decide which controls to include as candidates

## Initial Normalization Approach

### Inspiration from Text-Only ColBERT

In text-only ColBERT reranking, a known technique normalizes scores using:

```python
upper_bound = score(query, query)  # Query against itself (perfect match)
lower_bound = score(query, "")      # Query against empty (baseline)
normalized = (raw_score - lower_bound) / (upper_bound - lower_bound)
```

This produces intuitive 0-1 scores where:
- 1.0 = "as similar as the query is to itself"
- 0.0 = "no similarity beyond baseline"

### Adaptation for Multimodal ColModernVBERT

For image-to-text matching, we adapted this:

```python
def _compute_upper_bounds(self, page_embeddings: torch.Tensor) -> torch.Tensor:
    """Compute upper bounds via page self-similarity (MaxSim of page against itself)."""
    for page_idx in range(num_pages):
        page_emb = page_embeddings[page_idx]  # (num_page_tokens, dim)

        # Self-similarity: MaxSim of page against itself
        self_sim = torch.mm(page_emb, page_emb.t())  # (page_tokens, page_tokens)
        max_self_sim = self_sim.max(dim=1).values     # max over "doc" dimension
        upper_bounds[page_idx] = max_self_sim.sum()   # sum over "query" dimension

    return upper_bounds

def _normalize_scores(self, raw_scores, upper_bounds):
    """Normalize: score / upper_bound, clamped to [0, 1]."""
    return (raw_scores / upper_bounds).clamp(0, 1)
```

**Key insight**: The page's self-similarity represents the maximum possible MaxSim score for that page, accounting for page length (more tokens = higher self-similarity AND higher raw scores, so they cancel out).

## Experimental Validation

### Test Case: Asset Management Policy (Row 4)

We used a 5-page Asset Management Policy document with ground truth control DCF-182.

#### Initial Results (Normalized Scores)

Page 1 top controls:
```
1. DCF-790 (System Security Plans): 0.3725
2. DCF-115 (Privacy Policy Content): 0.3698
3. DCF-668 (Information Governance Policy): 0.3580
4. DCF-171 (Documented procedures): 0.3542
5. DCF-740 (PCI DSS policy): 0.3533
```

**Concern**: Scores are bunched (37.2% to 35.3%) and none relate to asset management.

#### Finding DCF-182 (Ground Truth)

We searched all 779 controls and found:
- DCF-182 (Asset Management Policy) ranked **#19** with score 0.3403
- DCF-20 (Asset Inventory) ranked **#7** with score 0.3499

The document explicitly mentions "Related Controls: DCF-20" on page 1.

### Deep Dive: Page 2 Analysis

Page 2 contains detailed "Asset Inventory Standard" content describing:
- Physical Asset Inventory (workstations, laptops, tablets, networking equipment)
- Virtual Asset Inventory (virtual machines, servers, repositories)
- Asset tagging with owner/project classification

This is a **near-perfect semantic match** for DCF-20 (Asset Inventory):
> "A centralized asset register is maintained for physical, cloud, and other assets that includes descriptive attributes for asset accountability such as owner, description, location, classification..."

#### Page 2 Results

```
Control         Raw Score   Normalized
----------------------------------------
DCF-790            452.37       0.3937
DCF-20             442.43       0.3851  <-- Expected match
DCF-788            434.25       0.3779
DCF-115            432.71       0.3766
...

Upper bound (self-similarity): 1149.00
```

**Key finding**: Even a near-perfect semantic match (DCF-20) only scores **38.5%** of self-similarity.

### Full Distribution Analysis

We computed scores for all 779 controls against Page 2:

```
Score distribution for Page 2:
  Max:    0.3937  (DCF-790)
  DCF-20: 0.3851  (rank #2, expected match)
  P95:    0.3457
  P90:    0.3318
  Median: 0.2825
  P10:    0.2300
  Min:    0.1170
  Std:    0.0392
```

## Key Findings

### 1. The Normalization IS Working Correctly

The math is sound:
- Raw DCF-20 score: 442.43
- Upper bound: 1149.00
- Normalized: 442.43 / 1149.00 = 0.3851 ✓

### 2. The Effective Score Range is 0.12-0.40, Not 0-1

**Why there's a floor (~0.12)**:
- All control descriptions share common policy language patterns
- MaxSim always finds SOME token matches between any page and any control
- Generic policy words (organization, security, procedures, etc.) appear everywhere

**Why there's a ceiling (~0.40)**:
- Page content includes much that no control could match:
  - Logos, headers, footers
  - Specific procedural details
  - Formatting and structure
  - Company-specific information
- Control descriptions are short (~50-200 words) while pages have much more content
- A "perfect" match captures ~40% of the page's information

### 3. The Model IS Discriminating Well

Despite the compressed range, DCF-20's score of 0.3851 is actually exceptional:
- **Top 2.5%** of all 779 controls
- **2.8 standard deviations** above median
- Gap from max to median: 0.11 (significant discrimination)

The scores work perfectly for **ranking** - the issue is setting **absolute thresholds**.

### 4. Raw vs Normalized: Same Ranking, Different Interpretability

| Metric | Raw Scores | Normalized |
|--------|-----------|------------|
| Top score | 452.37 | 0.3937 |
| Range | 134.5-452.4 | 0.117-0.394 |
| Interpretable? | No | Partially |
| Good for ranking? | Yes | Yes |
| Good for thresholds? | No | Needs calibration |

## Implications for LLM Decision Layer

### Threshold Recommendations

Based on the distribution analysis:

| Threshold | Intuitive Value | Calibrated Value | Percentile |
|-----------|----------------|------------------|------------|
| trigger_threshold | 0.60 | **0.33** | ~P90 |
| candidate_threshold | 0.40 | **0.28** | ~P50 (median) |

### Alternative: Percentile-Based Thresholds

Instead of absolute values, use percentile-based thresholds:
```python
trigger_percentile = 0.90  # Top 10% of controls trigger LLM
candidate_percentile = 0.50  # Top 50% become candidates
```

This is more robust across different pages/documents.

## Recommendations

### Short-term (for LLM layer implementation)

1. **Adjust absolute thresholds** in the plan:
   - `trigger_threshold`: 100.0 → **0.33** (normalized)
   - `candidate_threshold`: 60.0 → **0.28** (normalized)

2. **Or implement percentile-based thresholds** which are more intuitive and robust.

### Long-term Considerations

1. **The model finds the right controls** - DCF-20 was rank #2 for the asset inventory page. The retrieval quality is good.

2. **Score compression is inherent to ColBERT** - This is not a bug; it's how MaxSim works with heterogeneous content.

3. **The LLM layer can compensate** - Even if scores are bunched, including top-10 or top-20 controls as candidates should capture the right answer for the LLM to discriminate.

## Code Changes Made

Added to `predictor.py`:

```python
def _compute_upper_bounds(self, page_embeddings: torch.Tensor) -> torch.Tensor:
    """Compute upper bounds for score normalization via page self-similarity."""
    # ... implementation

def _normalize_scores(self, raw_scores: torch.Tensor, upper_bounds: torch.Tensor) -> torch.Tensor:
    """Normalize raw scores to 0-1 range using upper bounds."""
    eps = 1e-8
    normalized = raw_scores / (upper_bounds.unsqueeze(1) + eps)
    return normalized.clamp(0, 1)
```

Updated `predict_page()`, `predict_pages_batched()`, and `predict_document()` with `normalize: bool = True` parameter.

## Files Modified

- `ai_services/scripts/experiments/control_detection/predictor.py`
  - Added `_compute_upper_bounds()` method
  - Added `_normalize_scores()` method
  - Added `normalize` parameter to all predict methods (default: True)
  - Fixed incomplete `to_debug()` method on `PagePrediction`

---

## Ground Truth Correction (2025-12-19)

**Important**: The initial analysis used the wrong column for ground truth.

| Column | Description | Use |
|--------|-------------|-----|
| `_Policy Control` | Primary DCF control (1-2 per policy) | ❌ Initially used incorrectly |
| `_Controls` | All related DCF controls (8-66 per policy) | ✅ Correct ground truth |

The `_Controls` column contains all DCF controls that a policy document can satisfy as evidence. This is the correct ground truth because:
1. A policy document may satisfy multiple controls
2. The LLM should identify ANY of the valid controls, not just a specific "primary" one
3. Using the full set gives a more realistic evaluation

**Files updated:**
- `run_experiment.py` - Changed `ground_truth_controls` to use `_Controls` column
- `analyze_ground_truth_scores.py` - Re-ran with corrected ground truth
- All `ground_truth_scores.json` files regenerated

---

## Full Experiment Analysis (15 Documents)

### Methodology

We ran the predictor across all 15 policy documents with the corrected ground truth (from `_Controls` column). For each document:
1. Computed normalized scores for all 779 controls on each page
2. For each ground truth DCF, recorded its score and rank on every page
3. Identified the best page for each ground truth control
4. Saved results to `files/parsed_policies/<policy>/ground_truth_scores.json`

### Dataset Statistics

- **15 policy documents**
- **89 total pages**
- **401 ground truth controls** (across all documents)

### Critical Discovery: Missing Controls

**19 ground truth controls (4.7%) don't exist in our DCF control set.**

```
Available DCF controls: 779
Ground truth controls (original): 401
Valid GT controls (in DCF set): 382
Missing GT controls: 19 (4.7%)

Missing DCF IDs: DCF-1, DCF-128, DCF-129, DCF-133, DCF-177, DCF-2, DCF-23, DCF-24,
                 DCF-43, DCF-53, DCF-594, DCF-603, DCF-80, DCF-81, DCF-93
```

**Policies affected:**
- Data Protection Policy: 6 missing (DCF-1, DCF-177, DCF-594, DCF-80, DCF-81, DCF-93)
- Vendor Management Policy: 3 missing (DCF-128, DCF-129, DCF-133)
- System Access Control Policy: 2 missing (DCF-2, DCF-43)
- Encryption Policy: 2 missing (DCF-53, DCF-93)
- Vulnerability Management Policy: 2 missing (DCF-23, DCF-24)
- Asset Management Policy: 1 missing (DCF-1)
- Business Continuity Plan: 1 missing (DCF-603)
- Disaster Recovery Plan: 1 missing (DCF-603)
- Information Security Policy: 1 missing (DCF-1)

**Implication**: These 19 controls can NEVER be retrieved regardless of threshold. Maximum theoretical recall is 95.3% (382/401).

---

## Threshold Analysis

### The Right Question

**What threshold guarantees that EVERY ground truth control for EVERY document is captured on at least one page?**

**Why This Matters**: The retrieval layer must capture ALL ground truth controls because:
1. The LLM should be able to select ANY valid control
2. If a GT control isn't in the candidate set, the LLM can never select it
3. Missing GT controls = unavoidable false negatives

### Bottleneck Analysis

For each document, we find the **bottleneck control** - the valid GT control with the LOWEST best score across all pages. The optimal threshold is the minimum of these bottleneck scores.

| Policy | Valid/Total GT | Bottleneck Score | Bottleneck Control |
|--------|----------------|------------------|-------------------|
| Change Management Policy | 39/39 | **0.2064** | DCF-935 |
| Asset Management Policy | 38/39 | 0.2154 | DCF-622 |
| Data Protection Policy | 38/44 | 0.2175 | DCF-592 |
| Information Security Policy | 36/37 | 0.2227 | DCF-915 |
| Logging and Monitoring Policy | 39/39 | 0.2350 | DCF-421 |
| Software Development Life Cycle | 19/19 | 0.2389 | DCF-646 |
| Encryption Policy | 16/18 | 0.2546 | DCF-55 |
| Vendor Management Policy | 17/20 | 0.2547 | DCF-943 |
| Vulnerability Management Policy | 24/26 | 0.2585 | DCF-903 |
| System Access Control Policy | 64/66 | 0.2735 | DCF-75 |
| Data Retention Policy | 11/11 | 0.2743 | DCF-391 |
| Business Continuity Plan | 7/8 | 0.2761 | DCF-602 |
| Disaster Recovery Plan | 5/6 | 0.2761 | DCF-602 |
| Risk Assessment Policy | 21/21 | 0.2766 | DCF-911 |
| Data Classification Policy | 8/8 | 0.3160 | DCF-569 |

**OPTIMAL THRESHOLD: 0.2064**

- Bottleneck: Change Management Policy / DCF-935
- At this threshold: 100% of valid GT controls captured (382/382)
- At this threshold: All 15 documents fully covered

### Threshold Comparison

| Threshold | Docs at 100% | GT Capture Rate | Notes |
|-----------|--------------|-----------------|-------|
| **0.20** | 15/15 (100%) | 100% | **RECOMMENDED** |
| **0.2064** | 15/15 (100%) | 100% | Optimal (exact) |
| 0.22 | 12/15 (80%) | 99.0% | 3 policies lose coverage |
| 0.24 | 9/15 (60%) | 96.1% | |
| 0.26 | 6/15 (40%) | 90.8% | |
| 0.28 | 1/15 (7%) | 79.6% | |
| 0.30 | 1/15 (7%) | 63.6% | |
| 0.33 | 1/15 (7%) | 63.6% | INSUFFICIENT |

---

## Final Recommendations

### 1. Candidate Inclusion Threshold: **0.20**

```python
SCORE_THRESHOLD = 0.20
```

**How to use:**
- For each page, compute scores for all 779 controls
- Include controls with score ≥ 0.20 in the LLM candidate set
- This guarantees 100% recall of all valid ground truth controls

### 2. Expected Behavior

With threshold = 0.20:
- Every document will have ALL valid ground truth controls captured
- The LLM can select ANY correct control from the candidate set
- **Candidate sets will be large** - requires secondary filtering

### 3. Why NOT Use Top-K?

Analysis showed that ground truth controls can rank anywhere from #1 to #771 among 779 controls:
- Only 7% rank in top 5
- Only 10% rank in top 10
- Only 25% rank in top 50

A top-k approach would miss many valid controls. Score-based thresholding is more reliable.

### 4. Missing Controls Require Data Fix

19 DCF IDs in eval ground truth don't exist in DCF controls CSV:
- These need to be either added to DCF controls or removed from eval
- Until fixed, maximum theoretical recall is 95.3%

### 5. Scripts Created

- `analyze_ground_truth_scores.py` - Computes ground truth scores per page per document
- `analyze_threshold_statistics.py` - Analyzes thresholds for 100% GT recall

---

## Conclusion

The score normalization produces interpretable results in the 0.12-0.40 range. The key insight is framing the threshold question correctly:

**The threshold that guarantees "at least one" GT control per document (0.34) is VERY DIFFERENT from the threshold that guarantees "ALL" GT controls (0.2064).**

**Final threshold: 0.20**
- Guarantees 100% recall of all valid GT controls
- All 15 documents fully covered
- Provides safety margin below optimal (0.2064)
- **Candidate set size is a separate problem to solve**

---

## Problem: Candidate Set Size

### The Issue

While the 0.20 threshold guarantees 100% GT recall, it produces **very large candidate sets**. At the previous (incorrect) 0.33 threshold, we observed:

| Page | Controls Above Threshold |
|------|-------------------------|
| Page 2 | 93 controls |
| Page 3 | **119 controls** |

At 0.20, candidate sets will be even larger.

Sending 100+ controls to an LLM for each page is problematic:
1. **Token cost** - Each control description is ~50-200 words
2. **LLM context limits** - 119 controls × 100 words = 11,900 words just for candidates
3. **Decision quality** - LLMs may struggle to discriminate among 100+ similar options
4. **Latency** - Larger prompts = slower inference

### The Tradeoff

This is a **precision vs recall** tradeoff:
- Lower threshold (0.20) = 100% GT recall, but large candidate sets
- Higher threshold (0.30+) = smaller candidate sets, but missed GT controls

### Potential Solutions to Explore

1. **Two-stage filtering**: Use 0.20 for ensuring GT recall, then apply secondary filtering

2. **Per-page adaptive threshold**: Set threshold relative to max score on that page (e.g., top score - 0.10)

3. **Hybrid approach**: Score threshold + top-k cap (e.g., score >= 0.20 AND rank <= 50)

4. **Clustering**: Group similar controls and send cluster representatives to LLM

5. **Hierarchical classification**: First classify into control categories, then fine-grained selection

### Next Steps

The LLM layer implementation needs to address candidate set size. Options:
- Accept large candidate sets and optimize prompt structure
- Implement secondary filtering before LLM
- Use a lightweight re-ranker between retrieval and LLM

---

## Deep Dive: Why Is The Threshold So Low? (2025-12-19)

### Executive Summary

The 0.2064 threshold is driven by a **semantic mismatch problem**, not a model quality issue. Specifically:

1. **Change Management Policy is an extreme outlier** - 64% of its GT controls are from Configuration Management domain
2. **Configuration Management controls** (Windows hardening settings) are associated with policies for **compliance reasons**, not **semantic reasons**
3. A threshold of 0.26 achieves 90% recall while dramatically reducing candidate set size

### The Global Bottleneck: DCF-935

The single control dragging the threshold to 0.2064:

| Control | Score | Name | Description |
|---------|-------|------|-------------|
| DCF-935 | **0.2064** | Central Configuration Management | "The Organization manages configurations centrally." |

**Why it scores so low**: The description is extremely vague (7 words) and talks about *centralized management*, not *change management processes*.

### Score Distribution of All 382 GT Controls

```
Min:    0.2064  (DCF-935)
P5:     0.2436
P10:    0.2616
P25:    0.2867
Median: 0.3158
P75:    0.3478
P90:    0.3708
Max:    0.4297
Std:    0.0416
```

**Key insight**: The median is 0.3158, but the minimum is 0.2064. The bottom 5% (19 controls) are dragging down the threshold by 0.10 points.

### The Bottom 20 Controls (The Bottlenecks)

| Policy | Control | Score | Name |
|--------|---------|-------|------|
| Change Management | DCF-935 | 0.2064 | Central Configuration Management |
| Change Management | DCF-988 | 0.2151 | Internet Explorer 11 Disabled |
| Asset Management | DCF-622 | 0.2154 | Access Control for Output Devices |
| Data Protection | DCF-592 | 0.2175 | Limit PII in Audit Logs |
| Change Management | DCF-941 | 0.2211 | Immutable Infrastructure |
| Change Management | DCF-984 | 0.2217 | PowerShell Constrained Language Mode |
| Change Management | DCF-965 | 0.2223 | Credential Guard |
| Information Security | DCF-915 | 0.2227 | List of Teleworkers |
| Change Management | DCF-966 | 0.2237 | Remote Credential Guard |
| Change Management | DCF-976 | 0.2244 | Microsoft Office Macro API Calls |
| ... | ... | ... | ... |

**Pattern**: 16 of the bottom 20 are from **Configuration Management domain**, and 16 of those are from **Change Management Policy**.

### Change Management Policy: The Outlier Document

This single document is responsible for the low threshold:

| Metric | Value |
|--------|-------|
| Total GT controls | 39 |
| Configuration Management domain | 25 (64%) |
| Change Management domain | 10 (26%) |
| Other domains | 4 (10%) |

**By domain within Change Management Policy:**

| Domain | Count | Avg Score | Min Score | Problem? |
|--------|-------|-----------|-----------|----------|
| Configuration Management | 25 | **0.2558** | 0.2064 | YES |
| Change Management | 10 | 0.3302 | 0.2941 | No |
| Application Security | 3 | 0.2745 | 0.2656 | Minor |
| Cryptography | 1 | 0.2714 | 0.2714 | Minor |

### The Semantic Mismatch

**Low-scoring controls** (associated for compliance reasons, not semantic similarity):
- "Internet Explorer 11 Disabled" - Windows browser setting
- "PowerShell Constrained Language Mode" - Windows scripting restriction
- "Credential Guard" - Windows credential protection
- "Immutable Infrastructure" - DevOps architecture pattern

**High-scoring controls** (semantically related to change management):
- "Production Components Change Control Procedures" (0.3792)
- "Critical Change Management" (0.3504)
- "Change Management Policy" (0.3385)

The low-scorers are Windows security hardening configurations. They're associated with Change Management Policy because changes to them should go through change control. But the actual *content* of a Change Management Policy document describes the *process* of managing changes, not specific Windows settings.

**ColModernVBERT matches on semantic similarity, not compliance association.**

### Document-Level Recall at Different Thresholds

| Document | 0.20 | 0.22 | 0.24 | 0.26 | 0.28 | 0.30 |
|----------|------|------|------|------|------|------|
| Change Management | 100% | 95% | **77%** | **59%** | **41%** | **31%** |
| Asset Management | 100% | 97% | 97% | 92% | 82% | 61% |
| Data Protection | 100% | 97% | 97% | 84% | 66% | 34% |
| Logging & Monitoring | 100% | 100% | 95% | 90% | 74% | 44% |
| All others | 100% | 100% | 95-100% | 94-100% | 60-95% | 40-86% |

**Change Management Policy collapses first** and drags down the global threshold.

### Recall vs Threshold Tradeoff

| Recall | Threshold | Controls Lost | What We Lose |
|--------|-----------|---------------|--------------|
| 100% | 0.2064 | 0 | Nothing |
| 99% | 0.2175 | 3 | Config Mgmt (2), Physical (1) |
| 98% | 0.2227 | 7 | Config Mgmt (5), Physical (1), Logging (1) |
| 97% | 0.2344 | 11 | Config Mgmt (8), Physical (1), Logging (1) |
| **96%** | **0.2418** | **15** | **Config Mgmt (9), Logging (2), Physical (1)** |
| 95% | 0.2436 | 19 | Config Mgmt (9), Logging (3), Crypto (2) |
| 90% | 0.2616 | 38 | Config Mgmt (18), Logging (5), Crypto (4) |

### The Problem with 0.20 Threshold

From earlier distribution analysis, a 0.20 threshold includes controls at ~P20 of the overall score distribution. That means:

| Threshold | Est. Percentile | Est. Controls/Page |
|-----------|-----------------|-------------------|
| 0.20 | ~P20 | **~620 of 779** (80%) |
| 0.26 | ~P45 | ~430 of 779 (55%) |
| 0.33 | ~P85 | ~120 of 779 (15%) |

**A 0.20 threshold would send 80% of all controls to the LLM!**

### Recommendations

#### Option 1: Accept 96% Recall, Use Threshold 0.24

```python
SCORE_THRESHOLD = 0.24
```

- **Recall**: 96% (lose 15 controls, mostly Configuration Management)
- **Change Management Policy**: Drops to 77% recall (loses Windows hardening controls)
- **Candidate set**: Reduced from ~620 to ~470 per page
- **Rationale**: The lost controls are semantic mismatches anyway

#### Option 2: Accept 90% Recall, Use Threshold 0.26

```python
SCORE_THRESHOLD = 0.26
```

- **Recall**: 90% (lose 38 controls)
- **Candidate set**: Reduced to ~430 per page
- **Better precision**: Fewer false positives for LLM to filter

#### Option 3: Two-Stage Filtering (Recommended)

```python
# Stage 1: Ensure we don't miss any documents
INITIAL_THRESHOLD = 0.20  # Guarantees 100% document coverage

# Stage 2: Per-page filtering for LLM
MAX_CANDIDATES_PER_PAGE = 100  # Cap at top-100 by score
```

This ensures no GT control is completely unretrievable while keeping LLM candidate sets manageable.

#### Option 4: Per-Document Adaptive Threshold

For each document, use a threshold that captures the top X% of its controls:
- Handles outlier documents like Change Management gracefully
- Ensures every document contributes candidates proportionally

### Key Takeaway

**The 0.20 threshold is not a model quality problem. It's a data/ground-truth problem.**

Configuration Management controls are associated with Change Management Policy for compliance purposes, but they have no semantic relationship to change management content. ColModernVBERT correctly identifies this semantic gap.

Options:
1. **Accept lower recall** on these semantically-mismatched controls (threshold 0.24-0.26)
2. **Use two-stage filtering** with initial low threshold + secondary cap
3. **Fix the ground truth data** by reconsidering these associations

---

## Template Policies Experiment (2025-12-20)

### Background

The original experiment used "adjacent" policy documents - policies that were manually collected and somewhat related to the ground truth data but not the exact source documents. This raised the question: **would using the actual Drata template policies improve semantic alignment?**

The actual template policies are the exact documents that Drata provides to customers and that were used to establish the ground truth control mappings in `eval.csv`.

### Experiment Infrastructure

To enable isolated experiment runs, we created a configuration system:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ExperimentConfig:
    name: str
    policies_dir: Path           # Where policy PDFs are located
    mapping_file: Path           # eval_to_policy_mapping.json
    parsed_policies_dir: Path    # Cached page images
    results_file: Path           # experiment_results.json
    policy_name_to_pdf: dict[str, str]  # Policy name → PDF filename mapping
```

**Experiment isolation:**
- `original`: Uses `files/` (backwards-compatible with existing data)
- `template_policies`: Uses `files/experiments/template_policies/`

All scripts now accept `--experiment` flag to select which configuration to use.

### Dataset Comparison

| Metric | Original | Template Policies |
|--------|----------|-------------------|
| Policy documents | 15 | 37 |
| Total pages | 89 | 416 |
| Ground truth controls (original) | 401 | 734 |
| Valid GT controls (in DCF set) | 382 | 686 |
| Missing GT controls | 19 (4.7%) | 48 (6.5%) |

The template policies experiment covers **2.5x more documents** and **1.8x more ground truth controls**.

### Key Finding: Higher Optimal Threshold

| Metric | Original | Template Policies | Change |
|--------|----------|-------------------|--------|
| **Optimal Threshold** | **0.2064** | **0.2248** | **+9%** |
| Bottleneck Document | Change Management Policy | PCI DSS Compliance Policy | Different |
| Bottleneck Control | DCF-935 | DCF-424 | Different |

**The template policies have a 9% higher optimal threshold - this is better!**

### Why Template Policies Perform Better

1. **Better semantic alignment**: The actual template policies contain content that more directly corresponds to the control descriptions they're mapped to.

2. **Different bottleneck**: The original experiment's bottleneck was Change Management Policy with Configuration Management controls (Windows hardening settings with no semantic relationship). The template policies' bottleneck is PCI DSS Compliance Policy with DCF-424, which still has semantic challenges but at a higher threshold.

3. **The "adjacent" policies had worse mismatches**: The manually-collected policies in the original experiment were proxies that didn't perfectly match the ground truth mappings.

### Per-Document Bottleneck Analysis (Template Policies)

Top bottleneck documents:

| Policy | Valid/Total GT | Worst Best Score | Bottleneck Control |
|--------|----------------|------------------|-------------------|
| PCI DSS Compliance Policy | 151/151 | **0.2248** | DCF-424 |
| Information Security Policy | 36/37 | 0.2305 | DCF-915 |
| Change Management Policy | 39/39 | 0.2391 | DCF-988 |
| Logging and Monitoring Policy | 39/39 | 0.2440 | DCF-421 |
| Asset Management Policy | 38/39 | 0.2495 | DCF-622 |

**Key observation**: Change Management Policy is no longer the global bottleneck. Its worst score improved from 0.2064 to 0.2391 (+16%) with the template policies.

### Threshold Comparison

| Threshold | Original (Docs 100%) | Template (Docs 100%) | Original GT Capture | Template GT Capture |
|-----------|---------------------|---------------------|--------------------|--------------------|
| 0.20 | 15/15 (100%) | 37/37 (100%) | 100% | 100% |
| 0.22 | 12/15 (80%) | 37/37 (100%) | 99.0% | 100% |
| 0.2248 | - | **37/37 (100%)** | - | **100% (optimal)** |
| 0.24 | 9/15 (60%) | 34/37 (92%) | 96.1% | 99.6% |
| 0.26 | 6/15 (40%) | 30/37 (81%) | 90.8% | 98.3% |
| 0.28 | 1/15 (7%) | 23/37 (62%) | 79.6% | 94.8% |

### Impact on Candidate Set Size

With the higher threshold (0.22 vs 0.20), we can expect:
- ~5-10% fewer candidates per page
- Same 100% GT recall
- Slightly better precision for LLM filtering

### Recommendations Updated

Based on the template policies experiment:

1. **Use threshold 0.22** (rounded down from 0.2248 for safety margin)
   - Achieves 100% GT recall on actual template policies
   - 10% higher than original 0.20 threshold
   - Reduces candidate set size

2. **Template policies are the correct evaluation baseline**
   - Higher semantic alignment with ground truth
   - More comprehensive coverage (37 documents vs 15)
   - Results are more representative of production behavior

3. **The semantic vs compliance mismatch is real but less severe**
   - Still present (PCI DSS / DCF-424 bottleneck)
   - But not as extreme as original experiment suggested
   - Change Management Policy improved significantly

### Files Created/Modified

**New files:**
- `experiment_config.py` - Central experiment configuration
- `files/experiments/template_policies/` - Isolated output directory

**Modified files:**
- `generate_mapping.py` - Added `--experiment` flag
- `run_experiment.py` - Added `--experiment` flag
- `analyze_ground_truth_scores.py` - Added `--experiment` flag
- `analyze_threshold_statistics.py` - Added `--experiment` flag

### Running the Experiments

```bash
# Original experiment (backwards-compatible)
python -m ai_services.scripts.experiments.control_detection.generate_mapping --experiment original
python -m ai_services.scripts.experiments.control_detection.analyze_ground_truth_scores --experiment original
python -m ai_services.scripts.experiments.control_detection.analyze_threshold_statistics --experiment original

# Template policies experiment
python -m ai_services.scripts.experiments.control_detection.generate_mapping --experiment template_policies
python -m ai_services.scripts.experiments.control_detection.analyze_ground_truth_scores --experiment template_policies
python -m ai_services.scripts.experiments.control_detection.analyze_threshold_statistics --experiment template_policies
```

### Conclusion

**Using the actual Drata template policies improves the optimal threshold from 0.2064 to 0.2248 (+9%).**

This validates that:
1. The retrieval approach is sound
2. The original "adjacent" policies had worse semantic alignment
3. A threshold of 0.22 is appropriate for production use with template policies
4. The semantic vs compliance mismatch exists but is less severe than originally measured

---

## Scoring Direction Change: CONTROL_COVERAGE (2025-12-20)

### Background: The Semantic vs Compliance Mismatch Revisited

The original PAGE_COVERAGE scoring measures "how much of the page looks like this control". But this creates a fundamental issue: **pages contain much more content than any single control could match**. A policy page includes:
- Logos, headers, footers
- Formatting and structure
- Company-specific information
- Broad procedural language
- Multiple control-related topics

Even a "perfect" semantic match only captures ~40% of the page content, leading to compressed scores in the 0.12-0.40 range.

### The Key Insight: Flip the Scoring Direction

**Original (PAGE_COVERAGE):**
```
For each PAGE token:
    max_sim = max similarity to any CONTROL token
Sum all max_sim values → "How much of the page looks like this control?"
```

**Proposed (CONTROL_COVERAGE):**
```
For each CONTROL token:
    max_sim = max similarity to any PAGE token
Sum all max_sim values → "How much of this control is covered by the page?"
```

The question changes from "What percentage of this page matches the control?" to **"What percentage of this control's concepts are found in the page?"**

### Why This Makes Sense

1. **Control descriptions are concise** (~50-200 words) - every token is meaningful
2. **Pages have variable content density** - lots of "noise" that won't match any control
3. **We care about control coverage** - Is the control's full meaning present in the page?

A page might have low PAGE_COVERAGE (only 25% of page content matches) but high CONTROL_COVERAGE (95% of the control's tokens find matches in the page).

### Implementation

Added to `predictor.py`:

```python
class ScoringMode(Enum):
    PAGE_COVERAGE = "page_coverage"      # Original: sum over page tokens
    CONTROL_COVERAGE = "control_coverage" # New: sum over control tokens
    BIDIRECTIONAL = "bidirectional"      # Harmonic mean of both
```

**Control Coverage Scoring:**
```python
def _compute_control_coverage_scores(self, page_embeddings: torch.Tensor) -> torch.Tensor:
    """Compute CONTROL_COVERAGE: For each control token, max over page tokens, then sum."""
    for ctrl_idx, ctrl_emb in enumerate(self.control_embeddings):
        sim = torch.mm(ctrl_emb, page_emb.t())      # (ctrl_tokens, page_tokens)
        max_sim = sim.max(dim=1).values             # max over page tokens
        scores[page_idx, ctrl_idx] = max_sim.sum()  # sum over control tokens
    return scores
```

**Control Self-Similarity (for normalization):**
```python
def _compute_control_upper_bounds(self) -> torch.Tensor:
    """Precompute control self-similarities for CONTROL_COVERAGE normalization."""
    for ctrl_idx, ctrl_emb in enumerate(self.control_embeddings):
        self_sim = torch.mm(ctrl_emb, ctrl_emb.t())  # (ctrl_tokens, ctrl_tokens)
        max_self_sim = self_sim.max(dim=1).values    # max over self
        upper_bounds[ctrl_idx] = max_self_sim.sum()  # sum over control tokens
    return upper_bounds  # Can be precomputed once!
```

### Key Optimization: Precomputed Control Self-Similarities

Unlike PAGE_COVERAGE where upper bounds depend on each page, CONTROL_COVERAGE upper bounds are **fixed per control**. We precompute all 779 control self-similarities at initialization, making scoring faster.

### Experimental Results: CONTROL_COVERAGE on Template Policies

Running `analyze_ground_truth_scores.py --experiment template_policies --scoring-mode control_coverage`:

#### Score Distribution Comparison

| Metric | PAGE_COVERAGE | CONTROL_COVERAGE | Change |
|--------|---------------|------------------|--------|
| Min | 0.2248 | 0.4341 | +93% |
| Max | ~0.47 | ~0.69 | +47% |
| Mean | ~0.35 | ~0.53 | +51% |
| Range | 0.25 | 0.26 | Similar |

**The scores are dramatically higher!** Control coverage naturally produces higher scores because controls are concise - most of their tokens DO find good matches somewhere in a relevant page.

#### Optimal Threshold for 100% GT Recall

| Metric | PAGE_COVERAGE | CONTROL_COVERAGE | Change |
|--------|---------------|------------------|--------|
| **Optimal Threshold** | **0.2248** | **0.4341** | **+93%** |
| Bottleneck Document | PCI DSS Compliance | Disaster Recovery | Different |
| Bottleneck Control | DCF-424 | DCF-27 | Different |

#### Per-Document Bottleneck Analysis (Top 10)

| Policy | Valid/Total GT | Worst Best Score | Bottleneck Control |
|--------|----------------|------------------|-------------------|
| Disaster Recovery Plan | 5/6 | **0.4341** | DCF-27 |
| System Security Planning Policy | 5/5 | 0.4363 | DCF-581 |
| Change Management Policy | 39/39 | 0.4371 | DCF-978 |
| Logging and Monitoring Policy | 39/39 | 0.4401 | DCF-72 |
| Asset Management Policy | 38/39 | 0.4454 | DCF-891 |
| Data Protection Policy | 38/44 | 0.4497 | DCF-197 |
| Data Retention Policy | 11/11 | 0.4566 | DCF-797 |
| Business Continuity Plan | 7/8 | 0.4632 | DCF-602 |
| Public Cloud PII Protection Policy | 8/14 | 0.4643 | DCF-386 |
| Physical Security Policy | 28/30 | 0.4671 | DCF-109 |

#### Threshold Comparison

| Threshold | Docs at 100% | GT Captured | Notes |
|-----------|--------------|-------------|-------|
| 0.4341 | 37/37 (100%) | 686/686 (100%) | **OPTIMAL** |
| 0.4441 | 33/37 (89%) | 682/686 (99.4%) | +0.01 from optimal |
| 0.4541 | 31/37 (84%) | 678/686 (98.8%) | +0.02 from optimal |
| 0.4841 | 18/37 (49%) | - | +0.05 from optimal |
| 0.5341 | 3/37 (8%) | - | +0.10 from optimal |

### Analysis: Why CONTROL_COVERAGE Has Higher Threshold

The 0.43+ threshold makes intuitive sense:
- **Control descriptions are focused** - every word matters
- **A relevant page SHOULD match most control tokens**
- **43% control coverage = partial semantic match** - reasonable minimum

Compare to PAGE_COVERAGE's 0.22 threshold:
- **Pages have lots of non-matching content**
- **Even perfect matches only hit ~40% of page tokens**
- **22% page coverage = significant match** - reasonable given page noise

### Impact on Candidate Set Size

With a 0.43 threshold vs 0.22:
- **Fewer controls will pass threshold** (higher bar)
- **But we still capture 100% GT recall**
- **Precision should improve** - fewer false positives

### Verification: All 37 Documents Pass

At threshold 0.4341:
- All 37 policy documents achieve 100% GT recall
- Total 686 valid ground truth controls captured
- No false negatives

### Implications

1. **CONTROL_COVERAGE produces more interpretable scores**
   - 0.43 threshold vs 0.22 is easier to understand
   - "At least 43% of control content is covered" vs "at least 22% of page content matches"

2. **Higher threshold = better precision**
   - Fewer controls pass the threshold
   - More targeted candidate sets for LLM

3. **The semantic vs compliance mismatch persists**
   - Still have bottleneck controls with low coverage
   - DCF-27 (Disaster Recovery) is the new bottleneck
   - But overall performance is better

4. **Next step: Test BIDIRECTIONAL scoring**
   - Combines both directions via harmonic mean
   - Requires BOTH high page coverage AND high control coverage
   - May provide even better discrimination

### Files Modified

- `ai_services/scripts/experiments/control_detection/predictor.py`
  - Added `ScoringMode` enum
  - Added `_compute_control_upper_bounds()` method
  - Added `_compute_control_coverage_scores()` method
  - Added `_normalize_control_coverage_scores()` method
  - Added `_compute_scores_with_mode()` unified method
  - Updated `predict_page()`, `predict_pages_batched()`, `predict_document()` with `scoring_mode` parameter

- `ai_services/scripts/experiments/control_detection/analyze_ground_truth_scores.py`
  - Added `--scoring-mode` CLI argument
  - Passes scoring mode to predictor

### Documentation

Detailed documentation of the scoring direction change is in:
`.agents/claude/dev/active/control_detection/planning/docs/scoring_direction_change.md`

---

## BIDIRECTIONAL Scoring Results (2025-12-20)

### What is BIDIRECTIONAL?

BIDIRECTIONAL scoring combines both PAGE_COVERAGE and CONTROL_COVERAGE using the harmonic mean:

```
BIDIRECTIONAL = 2 * (PAGE_COVERAGE * CONTROL_COVERAGE) / (PAGE_COVERAGE + CONTROL_COVERAGE)
```

This requires BOTH directions to score well - a match must:
1. Cover a significant portion of the page (PAGE_COVERAGE)
2. Cover a significant portion of the control (CONTROL_COVERAGE)

The harmonic mean penalizes imbalanced scores - if either direction is low, the combined score is low.

### Experimental Results: BIDIRECTIONAL on Template Policies

Running `analyze_ground_truth_scores.py --experiment template_policies --scoring-mode bidirectional`:

#### Optimal Threshold for 100% GT Recall

| Metric | PAGE_COVERAGE | CONTROL_COVERAGE | BIDIRECTIONAL |
|--------|---------------|------------------|---------------|
| **Optimal Threshold** | **0.2248** | **0.4341** | **0.2996** |
| Bottleneck Document | PCI DSS Compliance | Disaster Recovery | Information Security |
| Bottleneck Control | DCF-424 | DCF-27 | DCF-915 |

**BIDIRECTIONAL threshold (0.30) is between PAGE_COVERAGE (0.22) and CONTROL_COVERAGE (0.43)**

This makes sense:
- Harmonic mean is bounded by the lower of the two values
- PAGE_COVERAGE scores (~0.22-0.47) set the floor
- CONTROL_COVERAGE scores (~0.43-0.69) are higher
- Combined scores fall in between

#### Per-Document Bottleneck Analysis (Top 10)

| Policy | Valid/Total GT | Worst Best Score | Bottleneck Control |
|--------|----------------|------------------|-------------------|
| Information Security Policy | 36/37 | **0.2996** | DCF-915 |
| Change Management Policy | 39/39 | 0.3055 | DCF-988 |
| PCI DSS Compliance Policy | 151/151 | 0.3152 | DCF-424 |
| Software Development Life Cycle Policy | 19/19 | 0.3266 | DCF-646 |
| Network Security Policy | 25/25 | 0.3268 | DCF-972 |
| Asset Management Policy | 38/39 | 0.3307 | DCF-622 |
| System Security Planning Policy | 5/5 | 0.3339 | DCF-581 |
| Logging and Monitoring Policy | 39/39 | 0.3374 | DCF-421 |
| Vendor Management Policy | 17/20 | 0.3427 | DCF-943 |
| Data Protection Policy | 38/44 | 0.3446 | DCF-197 |

#### Threshold Sensitivity

| Threshold | Docs at 100% | GT Captured | Notes |
|-----------|--------------|-------------|-------|
| 0.2996 | 37/37 (100%) | 686/686 (100%) | **OPTIMAL** |
| 0.3000 | 36/37 (97%) | 685/686 (99.9%) | +0.0004 from optimal |
| 0.3096 | 35/37 (95%) | 684/686 (99.7%) | +0.01 from optimal |
| 0.3196 | 34/37 (92%) | 682/686 (99.4%) | +0.02 from optimal |
| 0.3496 | 23/37 (62%) | - | +0.05 from optimal |

---

## Comprehensive Comparison: All Three Scoring Modes

### Summary Table

| Metric | PAGE_COVERAGE | CONTROL_COVERAGE | BIDIRECTIONAL |
|--------|---------------|------------------|---------------|
| **Optimal Threshold** | 0.2248 | 0.4341 | 0.2996 |
| **Score Range (typical)** | 0.22-0.47 | 0.43-0.69 | 0.30-0.50 |
| **Interpretation** | "How much of page matches control?" | "How much of control is in page?" | "Both directions agree?" |
| **Bottleneck Document** | PCI DSS Compliance | Disaster Recovery | Information Security |
| **Bottleneck Control** | DCF-424 | DCF-27 | DCF-915 |

### Threshold Characteristics

| Scoring Mode | Threshold | Intuitive Meaning |
|--------------|-----------|-------------------|
| PAGE_COVERAGE | 0.22 | "At least 22% of page content matches the control" |
| CONTROL_COVERAGE | 0.43 | "At least 43% of control content is found in the page" |
| BIDIRECTIONAL | 0.30 | "Harmonic mean of both ≥30% - balanced agreement" |

### Which Scoring Mode is Best?

**For candidate retrieval (high recall, manageable precision):**

| Mode | Pros | Cons |
|------|------|------|
| PAGE_COVERAGE | Lowest threshold, more safety margin | Larger candidate sets |
| CONTROL_COVERAGE | Highest threshold, smaller candidate sets | Tightest margin (+0.01 loses 4 docs) |
| BIDIRECTIONAL | Middle ground, balanced approach | Moderate candidate sets |

### Recommendations

1. **For Maximum Recall with Safety Margin**: Use **PAGE_COVERAGE with 0.20 threshold**
   - 10% safety margin below optimal (0.2248)
   - Most forgiving of score variation
   - Larger candidate sets (need secondary filtering)

2. **For Tighter Candidate Sets**: Use **CONTROL_COVERAGE with 0.43 threshold**
   - Higher threshold means fewer candidates
   - Very tight margin (0.01 drop loses 4 documents)
   - Requires careful monitoring

3. **For Balanced Approach**: Use **BIDIRECTIONAL with 0.29 threshold**
   - Middle ground on threshold and candidate sets
   - Requires both directions to agree
   - Good semantic interpretability ("both coverage directions satisfied")

### Key Insight: Different Bottlenecks

Each scoring mode has a different bottleneck control:

| Mode | Bottleneck Control | Why It's Hard |
|------|-------------------|---------------|
| PAGE_COVERAGE | DCF-424 | PCI DSS compliance control - very specific audit requirements |
| CONTROL_COVERAGE | DCF-27 | Disaster recovery - generic backup language |
| BIDIRECTIONAL | DCF-915 | "List of Teleworkers" - specific HR-related control |

This suggests the bottleneck controls represent genuinely different types of semantic mismatches:
- DCF-424: Compliance jargon that doesn't match page layout
- DCF-27: Generic terms that match many pages weakly
- DCF-915: Very specific requirement that pages describe generally

### Final Recommendation

**Use BIDIRECTIONAL scoring with threshold 0.29** for production:
1. **Balanced approach** - requires both page and control coverage
2. **Reasonable threshold** - 0.29 is interpretable ("30% agreement in both directions")
3. **Different bottleneck** - not the same failure modes as single-direction scoring
4. **10% safety margin** below optimal (0.2996)

```python
SCORE_THRESHOLD = 0.29  # BIDIRECTIONAL scoring mode
```

### Files Modified

- `ai_services/scripts/experiments/control_detection/predictor.py`
  - Updated `_compute_scores_with_mode()` to support BIDIRECTIONAL via harmonic mean

- `ai_services/scripts/experiments/control_detection/analyze_ground_truth_scores.py`
  - Supports `--scoring-mode bidirectional` option

---

## CONTROL_COVERAGE: Failed to Reduce Candidate Sets (2025-12-20)

### Goal Reminder

We're searching for the **highest threshold that allows 100% GT recall while reducing the set of controls we need to process by as much as possible.**

### Experiment: Asset Management Policy with CONTROL_COVERAGE

Running `run_experiment.py --experiment template_policies --row 4 --scoring-mode control_coverage --verbose` with threshold 0.4341:

#### Results

| Page | Controls Above Threshold | % of 779 Total |
|------|-------------------------|----------------|
| 1 | 611 | **78%** |
| 2 | 682 | **88%** |
| 3 | 620 | **80%** |
| 4 | 678 | **87%** |
| 5 | 517 | **66%** |
| 6 | 616 | **79%** |
| 7 | 565 | **73%** |
| 8 | 9 | 1% (metadata page) |

**Total unique controls above threshold: 755/779 (97%)**

### Verdict: CONTROL_COVERAGE FAILS

**CONTROL_COVERAGE at its optimal threshold (0.4341) only filters out 3% of controls.**

This is unacceptable. The scoring mode provides virtually no filtering benefit:
- We still pass **755 out of 779 controls** to downstream processing
- Per-page candidate sets are 500-680 controls
- The "higher threshold" (0.43 vs 0.22) is meaningless if it doesn't actually filter

### Why CONTROL_COVERAGE Fails

CONTROL_COVERAGE asks: "What % of this control's tokens can find a match in the page?"

The problem: **Policy pages are token-rich environments.** Even a control about disaster recovery can find 43%+ of its tokens matching somewhere in an Asset Management Policy because:
- Generic policy language ("organization", "shall", "must", "ensure")
- Shared compliance vocabulary
- Overlapping procedural terms

CONTROL_COVERAGE produces high scores for almost everything because it only requires **partial token coverage**, not semantic relevance.

### Comparison: Does PAGE_COVERAGE Do Better?

PAGE_COVERAGE at threshold 0.22 needs to be tested to compare candidate set sizes. However, the score distribution analysis suggests PAGE_COVERAGE may be more discriminating because:
- It asks "Does this page discuss the control?" not "Can control words be found?"
- Page noise (headers, logos, generic text) won't match specific control vocabulary
- More spread in the score distribution (0.12-0.47) suggests better discrimination

### Conclusion

**CONTROL_COVERAGE is NOT a viable approach for reducing candidate sets.**

Despite the higher nominal threshold (0.43 vs 0.22), it provides no practical filtering. The flipped scoring direction was an interesting hypothesis, but it fails our key requirement: **maximizing filtering while maintaining 100% recall.**

---

## BIDIRECTIONAL: Also Failed (2025-12-20)

### Experiment: Asset Management Policy with BIDIRECTIONAL

Running `run_experiment.py --experiment template_policies --row 4 --scoring-mode bidirectional --verbose` with threshold 0.2996:

#### Results

| Page | Controls Above Threshold | % of 779 Total |
|------|-------------------------|----------------|
| 1 | 749 | **96%** |
| 2 | 758 | **97%** |
| 3 | 742 | **95%** |
| 4 | 737 | **95%** |
| 5 | 699 | **90%** |
| 6 | 747 | **96%** |
| 7 | 745 | **96%** |
| 8 | 470 | 60% |

**Total unique controls above threshold: 775/779 (99.5%)**

### Verdict: BIDIRECTIONAL ALSO FAILS

**BIDIRECTIONAL at its optimal threshold (0.2996) only filters out 0.5% of controls.**

This is even worse than CONTROL_COVERAGE (which filtered 3%). The harmonic mean of two high scores is still a high score.

---

## Summary: ALL Scoring Modes Failed to Filter

### Asset Management Policy (Row 4) - Per-Page Control Counts

| Page | PAGE_COVERAGE (0.2248) | CONTROL_COVERAGE (0.4341) | BIDIRECTIONAL (0.2996) |
|------|------------------------|---------------------------|------------------------|
| 1 | 758 (97%) | 611 (78%) | 749 (96%) |
| 2 | 762 (98%) | 682 (88%) | 758 (97%) |
| 3 | 750 (96%) | 620 (80%) | 742 (95%) |
| 4 | 744 (95%) | 678 (87%) | 737 (95%) |
| 5 | 725 (93%) | 517 (66%) | 699 (90%) |
| 6 | 753 (97%) | 616 (79%) | 747 (96%) |
| 7 | 754 (97%) | 565 (73%) | 745 (96%) |
| 8 | 708 (91%) | 9 (1%) | 470 (60%) |

### Total Unique Controls Above Threshold

| Scoring Mode | Optimal Threshold | Controls Passing | Controls Filtered | Verdict |
|--------------|------------------|------------------|-------------------|---------|
| PAGE_COVERAGE | 0.2248 | 775/779 (99.5%) | 0.5% (4/779) | **FAIL** |
| CONTROL_COVERAGE | 0.4341 | 755/779 (97%) | 3% (24/779) | **FAIL** |
| BIDIRECTIONAL | 0.2996 | 775/779 (99.5%) | 0.5% (4/779) | **FAIL** |

**All three scoring modes fail to provide meaningful filtering at their optimal thresholds for 100% GT recall.**

Ironically, CONTROL_COVERAGE is the "best" at filtering (3% vs 0.5%), but 3% is still useless for our goal.

### Root Cause

The fundamental problem is that **ColBERT-style MaxSim scoring is not designed for hard filtering**. It produces scores that are useful for **ranking** but not for **thresholding**:

1. **Score compression**: All scores cluster in a narrow range
2. **High baseline**: Even unrelated content produces moderate similarity scores
3. **Optimal thresholds are necessarily low**: To capture ALL GT controls, we must set thresholds that capture most NON-GT controls too

### What Actually Works for Filtering?

The only viable approaches for reducing candidate sets while maintaining 100% recall are:

1. **Top-k per page**: Take top 50-100 controls per page regardless of score
2. **Rank-based filtering**: Include controls in top N% of scores
3. **Two-stage retrieval**: Use ColBERT for ranking, then apply a secondary filter

**Score-based thresholding alone cannot solve the candidate set size problem.**

### Recommendation

Abandon the pursuit of "optimal thresholds for filtering" and instead:

1. Use a **very low threshold** (e.g., 0.15-0.20) as a sanity check floor
2. Apply **top-k filtering** (e.g., top 100 per page) as the primary filter
3. Focus retrieval optimization on **improving ranking quality**, not threshold tuning

---

## Deep Dive: CONTROL_COVERAGE Threshold vs Recall Tradeoff (2025-12-20)

### Analysis Setup

Using `analyze_threshold_recall.py` on Asset Management Policy (Row 4) with CONTROL_COVERAGE scoring mode. This analysis examines:
1. Score distributions for GT vs non-GT controls
2. Recall at various thresholds
3. Finding optimal threshold for high recall with good filtering

### Score Distribution: GT vs Non-GT Controls

| Metric | GT Controls (38) | Non-GT Controls (741) | Gap |
|--------|------------------|----------------------|-----|
| Min | 0.4454 | 0.3943 | +0.05 |
| P10 | 0.4866 | 0.4540 | +0.03 |
| **Median** | **0.5198** | **0.4943** | **+0.03** |
| Mean | 0.5289 | 0.4961 | +0.03 |
| P90 | 0.6019 | 0.5395 | +0.06 |
| Max | 0.6482 | 0.6057 | +0.04 |
| Std | 0.0450 | 0.0340 | - |

### Key Finding: Distributions Heavily Overlap

The GT median (0.52) is only **0.03 points higher** than the non-GT median (0.49). This tiny gap explains why thresholding fails:

- To capture all GT controls, threshold must be ≤ 0.4454 (GT min)
- But 95% of non-GT controls score above 0.4540
- **There's no threshold that separates GT from non-GT**

### Bottom 10 GT Controls (Hardest to Capture)

| Control | Score | Description |
|---------|-------|-------------|
| DCF-891 | 0.4454 | Asset inventory attributes |
| DCF-924 | 0.4546 | Asset disposal |
| DCF-890 | 0.4672 | Asset lifecycle |
| DCF-87 | 0.4833 | Asset management |
| DCF-21 | 0.4879 | Asset inventory |
| DCF-920 | 0.4949 | Asset classification |
| DCF-893 | 0.4963 | Asset tracking |
| DCF-892 | 0.4973 | Asset ownership |
| DCF-32 | 0.4992 | Policy documentation |
| DCF-385 | 0.5008 | Data protection |

These are legitimate GT controls that score in the same range as non-GT controls.

### Top 10 Non-GT Controls (Highest False Positives)

| Control | Score | Description |
|---------|-------|-------------|
| DCF-556 | 0.6057 | Data inventory |
| DCF-52 | 0.6031 | Access control |
| DCF-49 | 0.5957 | Identity management |
| DCF-384 | 0.5912 | Data classification |
| DCF-381 | 0.5870 | Data handling |
| DCF-223 | 0.5865 | Audit logging |
| DCF-157 | 0.5816 | Change management |
| DCF-649 | 0.5811 | System inventory |
| DCF-172 | 0.5793 | Policy review |
| DCF-350 | 0.5769 | Access review |

These non-GT controls score **higher than most GT controls** because they share vocabulary with asset management (inventory, data, classification, etc.).

### Threshold vs Recall vs Filtering

| Threshold | Recall | GT Pass | Total Pass | Filtered |
|-----------|--------|---------|------------|----------|
| 0.40 | 100% | 38/38 | 776/779 | 0.4% |
| 0.44 | **100%** | 38/38 | 746/779 | **4.2%** |
| 0.45 | 97.4% | 37/38 | 713/779 | 8.5% |
| 0.46 | 94.7% | 36/38 | 673/779 | 13.6% |
| 0.47 | 92.1% | 35/38 | 606/779 | 22.2% |
| **0.48** | **92.1%** | 35/38 | 530/779 | **32.0%** |
| 0.49 | 86.8% | 33/38 | 451/779 | 42.1% |
| 0.50 | 76.3% | 29/38 | 360/779 | 53.8% |
| 0.52 | 50.0% | 19/38 | 195/779 | 75.0% |
| 0.55 | 26.3% | 10/38 | 53/779 | 93.2% |
| 0.60 | 10.5% | 4/38 | 6/779 | 99.2% |

### Key Threshold Decision Points

| Target | Threshold | Recall | Controls Passing | Filtered |
|--------|-----------|--------|------------------|----------|
| **100% Recall** | 0.44 | 100% | 746/779 | 4.2% |
| **95% Recall** | 0.45 | 97.4% | 713/779 | 8.5% |
| **90% Recall** | 0.48 | 92.1% | 530/779 | 32.0% |
| **85% Recall** | 0.49 | 86.8% | 451/779 | 42.1% |
| **75% Recall** | 0.50 | 76.3% | 360/779 | 53.8% |

### Analysis

1. **100% recall is expensive**: At threshold 0.44, only 4.2% of controls are filtered. We pass 746 controls to downstream processing.

2. **90% recall is the sweet spot**: At threshold 0.48, we filter 32% of controls (530 pass) while maintaining 92% recall. We lose 3 GT controls but reduce candidates by ~250.

3. **Diminishing returns below 85%**: Going from 90% to 75% recall (0.48 → 0.50) only filters an additional 22% (530 → 360). The tradeoff becomes unfavorable.

4. **The distributions simply overlap too much**: Even at 50% recall, 195 non-GT controls still pass. There's no clean separation.

### Recommendation: Accept 90% Recall

For CONTROL_COVERAGE, use **threshold 0.48** as a practical compromise:

```python
SCORE_THRESHOLD = 0.48  # CONTROL_COVERAGE
# Expected: ~90% recall, ~530 candidates per document
```

This accepts losing ~10% of GT controls in exchange for filtering 32% of candidates. Combined with top-k filtering (e.g., top 100 per page), this could reduce candidates to manageable levels.

### Why Perfect Recall is Impractical

The fundamental issue is that **compliance controls share vocabulary**. An Asset Management Policy discusses:
- Inventory, classification, ownership, lifecycle
- Data handling, access control, audit trails
- Policy documentation, review processes

These concepts appear in hundreds of DCF controls, not just the 38 GT controls. ColBERT correctly identifies semantic similarity - the problem is that many controls ARE semantically similar to any given policy page.

**Perfect recall requires including all semantically similar controls, which defeats the purpose of filtering.**
