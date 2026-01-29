# The Semantic vs Compliance Retrieval Problem

## Date: 2025-12-19

## Problem Statement

We're using a semantic retrieval system (ColModernVBERT) to reduce the candidate set of DCF controls before LLM analysis. The system matches policy document pages against control descriptions based on **semantic similarity**.

However, ground truth associations are made by human annotators for **compliance reasons**, which often have no semantic basis. For example:

| Control | Associated Policy | Semantic Relationship? |
|---------|------------------|----------------------|
| "PowerShell Constrained Language Mode" | Change Management Policy | **NO** - Changes to this setting should go through change control, but the control description has nothing to do with change management processes |
| "Internet Explorer 11 Disabled" | Change Management Policy | **NO** - Same compliance logic, zero semantic overlap |
| "Production Components Change Control Procedures" | Change Management Policy | **YES** - Directly describes change control processes |

This creates a fundamental mismatch:
- **Retrieval**: Based on semantic similarity (does the text match?)
- **Ground Truth**: Based on compliance logic (should this control be evaluated for this policy?)

The result: We must set the threshold extremely low (0.20) to capture all compliance-associated controls, which includes ~80% of all 779 controls in the candidate set.

## The Core Tension

```
┌─────────────────────────────────────────────────────────────────────┐
│                     COMPLIANCE ASSOCIATION                          │
│  "PowerShell settings changes should go through change control"     │
│                              ↓                                      │
│  Human annotator associates DCF-984 with Change Management Policy   │
└─────────────────────────────────────────────────────────────────────┘
                              ≠
┌─────────────────────────────────────────────────────────────────────┐
│                     SEMANTIC SIMILARITY                             │
│  ColModernVBERT compares:                                          │
│    "PowerShell Constrained Language Mode" description              │
│              vs                                                     │
│    Change Management Policy document content                        │
│                              ↓                                      │
│  Score: 0.22 (low - no semantic overlap)                           │
└─────────────────────────────────────────────────────────────────────┘
```

## Questions to Consider

1. **Is perfect recall actually necessary?** If a control has no semantic relationship to a policy document, can the LLM ever correctly identify it anyway?

2. **What is the ground truth actually for?** Is it "controls this policy can provide evidence for" or "controls this policy semantically describes"? These are different tasks.

3. **Are we solving the right problem?** Maybe retrieval isn't the right approach for compliance-based associations.

---

## Brainstorm: Potential Solutions

### Category 1: Hybrid Retrieval Approaches

#### 1.1 Metadata-Based Pre-Inclusion

Use the "Associated Policies" field in DCF controls as a guaranteed inclusion mechanism.

```python
def build_candidate_set(document, semantic_scores):
    # Always include controls with matching associated policy
    doc_type = classify_document_type(document)  # e.g., "Change Management Policy"
    guaranteed = [c for c in all_controls if doc_type in c.associated_policies]

    # Add semantic matches above threshold
    semantic = [c for c in all_controls if semantic_scores[c] >= THRESHOLD]

    # Union
    return set(guaranteed) | set(semantic)
```

**Pros:**
- Guarantees compliance-associated controls are included
- Can use higher semantic threshold (0.28+) for semantic portion
- Simple to implement

**Cons:**
- Requires document type classification (another model?)
- "Associated Policies" field may not be comprehensive
- Doesn't solve the problem, just works around it

#### 1.2 Domain-Aware Thresholds

Different control domains have systematically different score distributions. Use domain-specific thresholds.

```python
DOMAIN_THRESHOLDS = {
    "Configuration Management": 0.18,  # Low - often semantic mismatches
    "Change Management": 0.28,          # Normal - semantically coherent
    "Logging & Monitoring": 0.22,       # Medium
    # ...
}

def filter_by_domain_threshold(control, score):
    threshold = DOMAIN_THRESHOLDS.get(control.domain, 0.25)
    return score >= threshold
```

**Pros:**
- Acknowledges systematic differences between domains
- More nuanced than single global threshold

**Cons:**
- Requires careful calibration per domain
- Doesn't address root cause
- May not generalize to new controls

#### 1.3 Multi-Signal Retrieval Fusion

Combine multiple retrieval signals, not just semantic similarity.

```python
def compute_relevance_score(control, document):
    # Signal 1: Semantic similarity (ColModernVBERT)
    semantic_score = colmodernvbert.score(document, control.description)

    # Signal 2: Keyword overlap
    keyword_score = jaccard(control.keywords, document.extracted_keywords)

    # Signal 3: Policy association match
    policy_match = 1.0 if document.type in control.associated_policies else 0.0

    # Signal 4: Domain relevance
    domain_score = domain_classifier.score(document, control.domain)

    # Weighted fusion
    return (
        0.4 * semantic_score +
        0.2 * keyword_score +
        0.3 * policy_match +
        0.1 * domain_score
    )
```

**Pros:**
- Captures multiple types of relevance
- Policy association becomes an explicit signal
- More robust to any single signal's weaknesses

**Cons:**
- Complexity - multiple models/systems
- Requires tuning weights
- Still need to determine threshold

---

### Category 2: Ground Truth / Data Solutions

#### 2.1 Dual Ground Truth Annotations

Create two types of associations for each control-policy pair:

| Association Type | Definition | Use Case |
|-----------------|------------|----------|
| **Semantic** | Control description semantically relates to policy content | Retrieval |
| **Compliance** | Control is relevant for compliance/evidence purposes | Final validation |

```
DCF-984 (PowerShell) + Change Management Policy:
  - Semantic Association: NO
  - Compliance Association: YES

DCF-305 (Change Control Procedures) + Change Management Policy:
  - Semantic Association: YES
  - Compliance Association: YES
```

**Pros:**
- Explicitly acknowledges the two types of relevance
- Retrieval can target semantic associations
- Compliance associations inform final evaluation

**Cons:**
- Requires re-annotation of entire ground truth
- Expensive and time-consuming
- May not be feasible at scale

#### 2.2 Control Description Enrichment

Add contextual information to control descriptions explaining WHY they relate to certain policies.

**Before:**
```
DCF-984: "The Organization has configured PowerShell to use constrained language mode."
```

**After:**
```
DCF-984: "The Organization has configured PowerShell to use constrained language mode.
This security configuration relates to change management because modifications to
PowerShell settings should follow formal change control procedures. It relates to
endpoint security as a protective measure against malicious scripts."
```

**Pros:**
- Enriched descriptions may score better semantically
- Captures the compliance reasoning in text form
- Could be generated by LLM

**Cons:**
- Modifies source data
- May not fully bridge the semantic gap
- Risk of introducing noise

#### 2.3 Question the Ground Truth

Maybe some associations shouldn't be ground truth for a retrieval task.

**Key Question:** If a control has no semantic relationship to a policy document, can the LLM ever correctly identify it from the document content alone?

If not, then:
- These associations are not suitable for a "policy → control detection" task
- They belong to a different task: "given this control, what policies provide evidence?"
- The ground truth may be for a different use case than we're solving

**Action:** Analyze how many "semantic mismatch" controls could realistically be identified by an LLM reading the policy document.

---

### Category 3: Architecture Changes

#### 3.1 Two-Stage LLM System

Instead of retrieval → LLM, use retrieval → lightweight LLM filter → main LLM.

```
Stage 1: Broad Semantic Retrieval
  - Threshold: 0.20 (captures everything)
  - Output: ~620 controls per page

Stage 2: LLM-Based Relevance Filter
  - Input: Page + 620 controls (just IDs and names)
  - Prompt: "Which of these controls MIGHT be relevant to this page?"
  - Output: ~50-100 controls

Stage 3: Full LLM Classification
  - Input: Page + 50-100 controls (full descriptions)
  - Prompt: "Which controls does this page provide evidence for?"
  - Output: Final predictions
```

**Pros:**
- Stage 2 can understand compliance relationships
- Manageable candidate set for Stage 3
- Leverages LLM's reasoning for filtering

**Cons:**
- Three stages = more latency
- Stage 2 LLM calls add cost
- Complexity

#### 3.2 Policy-Type Classification First

Classify the document type, then use that to inform control selection.

```
Step 1: Classify Document
  - Input: Document pages
  - Output: "Change Management Policy" (with confidence)

Step 2: Control Selection
  - If high confidence: Include all controls with matching Associated Policy
  - Always: Include top-K semantic matches
  - Result: Guaranteed coverage + semantic relevance

Step 3: LLM Classification
  - Input: Document + selected controls
  - Output: Final predictions
```

**Pros:**
- Document classification is simpler than control matching
- Leverages existing "Associated Policies" metadata
- Guarantees compliance-relevant controls are included

**Cons:**
- Requires document type classifier
- What if document doesn't match any type?
- Associated Policies may not be complete

#### 3.3 Ensemble Retrieval with Rank Fusion

Run multiple retrieval strategies in parallel, merge with rank fusion.

```python
def ensemble_retrieve(document, k=100):
    # Strategy 1: Semantic (ColModernVBERT)
    semantic_ranking = colmodernvbert.rank(document, all_controls)

    # Strategy 2: Keyword (BM25 on extracted text)
    bm25_ranking = bm25.rank(document.text, control_descriptions)

    # Strategy 3: Policy Association
    doc_type = classify(document)
    assoc_ranking = [c for c in all_controls if doc_type in c.associated_policies]

    # Reciprocal Rank Fusion
    fused = reciprocal_rank_fusion([semantic_ranking, bm25_ranking, assoc_ranking])

    return fused[:k]
```

**Pros:**
- Multiple retrieval strategies cover different types of relevance
- Rank fusion is well-studied
- Robust to weaknesses in any single method

**Cons:**
- Computational overhead of multiple retrievers
- Complexity in implementation
- Still need to determine k

---

### Category 4: Model / Embedding Solutions

#### 4.1 Fine-Tune on Compliance Associations

Train a retrieval model specifically on policy-control compliance pairs.

```
Training Data:
  - Positive: (Change Management Policy, DCF-984) - associated in ground truth
  - Negative: (Change Management Policy, DCF-XXX) - not associated

Model learns:
  - "Change Management" context should embed near "PowerShell" controls
  - Compliance relationships, not just semantic similarity
```

**Pros:**
- Model learns the compliance associations directly
- Could achieve much better retrieval performance
- Tailored to the specific task

**Cons:**
- Requires significant training data
- Fine-tuning multimodal models is complex
- May overfit to existing associations

#### 4.2 Control Embedding Augmentation

For each control, create multiple embedding variants.

```python
class AugmentedControl:
    def __init__(self, control):
        self.base_embedding = embed(control.description)
        self.augmented_embedding = embed(
            f"{control.description}. "
            f"Related to: {', '.join(control.associated_policies)}. "
            f"Keywords: {', '.join(control.keywords)}."
        )
        self.keyword_embedding = embed(' '.join(control.keywords))

    def score(self, document_embedding):
        return max(
            cosine(document_embedding, self.base_embedding),
            cosine(document_embedding, self.augmented_embedding),
            cosine(document_embedding, self.keyword_embedding),
        )
```

**Pros:**
- Captures multiple facets of each control
- Simple to implement
- No model training required

**Cons:**
- May not significantly improve semantic gap
- Increases computational cost
- Associated policy text may not help

#### 4.3 Cross-Encoder Reranking

Use ColModernVBERT for initial retrieval, cross-encoder for reranking.

```
Stage 1: ColModernVBERT retrieves top-500 controls

Stage 2: Cross-encoder scores each (document, control) pair
  - Cross-encoder can be fine-tuned on compliance associations
  - Sees full context of both inputs
  - More accurate but expensive

Stage 3: Take top-100 from cross-encoder ranking
```

**Pros:**
- Cross-encoders are more accurate than bi-encoders
- Can be fine-tuned on compliance associations
- Well-established reranking pattern

**Cons:**
- Expensive (N forward passes instead of 1)
- Requires training cross-encoder
- Still need initial retrieval

---

### Category 5: Pragmatic Solutions

#### 5.1 Accept Imperfect Recall

Acknowledge that some controls can't be retrieved semantically.

**Argument:**
- If DCF-984 (PowerShell) has no semantic relationship to Change Management content...
- And the LLM only sees the Change Management Policy document...
- How would the LLM ever correctly identify DCF-984?

The LLM would need to reason: "This document describes change management processes. PowerShell configuration changes should go through change management. Therefore DCF-984 applies."

**This is multi-hop reasoning that requires knowledge not in the document.**

**Conclusion:** Maybe we shouldn't expect to retrieve these controls, and shouldn't evaluate on them.

**Proposed Action:**
- Threshold: 0.26 (90% recall)
- Accept that 10% of controls are "unretrievable" semantic mismatches
- Evaluate retrieval system only on semantically-retrievable controls

#### 5.2 Guaranteed Controls via Heuristics

Simple heuristics to guarantee certain controls are included.

```python
POLICY_KEYWORD_TO_CONTROLS = {
    "change management": ["DCF-935", "DCF-988", "DCF-941", ...],  # Config Mgmt controls
    "asset management": ["DCF-622", ...],
    # ...
}

def get_guaranteed_controls(document_title):
    guaranteed = set()
    for keyword, controls in POLICY_KEYWORD_TO_CONTROLS.items():
        if keyword in document_title.lower():
            guaranteed.update(controls)
    return guaranteed
```

**Pros:**
- Dead simple
- Guaranteed coverage of known problem cases
- No model changes needed

**Cons:**
- Doesn't generalize
- Requires manual maintenance
- Brittle to new documents/controls

#### 5.3 Maximum Candidate Cap

Use low threshold but cap the candidate set.

```python
SCORE_THRESHOLD = 0.20  # Low - guarantees recall
MAX_CANDIDATES = 150    # Cap - keeps LLM manageable

def get_candidates(page_scores):
    # Get all above threshold
    above_threshold = [(c, s) for c, s in page_scores if s >= SCORE_THRESHOLD]

    # Sort by score and take top MAX_CANDIDATES
    sorted_candidates = sorted(above_threshold, key=lambda x: x[1], reverse=True)
    return sorted_candidates[:MAX_CANDIDATES]
```

**Pros:**
- Simple implementation
- Guarantees threshold-based recall (up to cap)
- Manageable candidate set for LLM

**Cons:**
- May still miss low-scoring but important controls
- Cap is arbitrary
- Doesn't solve fundamental problem

---

### Category 6: Rethinking the Problem

#### 6.1 Is This the Right Task?

The ground truth seems to answer: "What controls can this policy document provide evidence for?"

But retrieval optimizes for: "What controls does this policy document semantically describe?"

These are fundamentally different questions.

**Alternative Task Formulation:**

| Task | Input | Output | Right Approach |
|------|-------|--------|----------------|
| Policy → Controls (semantic) | Policy document | Controls described by document | Semantic retrieval |
| Policy → Controls (compliance) | Policy document | Controls the policy provides evidence for | Classification / Knowledge graph |
| Control → Policies | Control description | Policies that provide evidence | Retrieval over policy corpus |

**Insight:** Maybe we're framing the problem wrong. If the goal is compliance mapping, semantic retrieval may be the wrong tool.

#### 6.2 LLM-First Approach

Instead of retrieval → LLM, try LLM → retrieval.

```
Step 1: LLM reads document, identifies relevant control DOMAINS
  - Input: Full document
  - Prompt: "What control domains does this policy address?"
  - Output: ["Change Management", "Configuration Management", ...]

Step 2: Retrieve within identified domains
  - Filter controls to identified domains
  - Apply semantic retrieval within those domains
  - Much smaller search space

Step 3: LLM classification
  - Input: Document + domain-filtered controls
  - Output: Final control predictions
```

**Pros:**
- LLM understands compliance relationships
- Retrieval happens in constrained space
- More aligned with compliance reasoning

**Cons:**
- LLM must process full document (expensive)
- Domain identification may miss things
- Complex pipeline

#### 6.3 Knowledge Graph Approach

Build a knowledge graph of compliance relationships, query it alongside retrieval.

```
Knowledge Graph:
  - (PowerShell settings) --[requires]--> (Change Control)
  - (Change Control) --[implemented_by]--> (Change Management Policy)
  - (DCF-984) --[about]--> (PowerShell settings)

Query:
  - Document classified as "Change Management Policy"
  - Graph traversal finds all controls related to change control
  - Union with semantic retrieval results
```

**Pros:**
- Captures compliance reasoning explicitly
- Can represent multi-hop relationships
- Interpretable

**Cons:**
- Requires building and maintaining knowledge graph
- Significant engineering effort
- May not cover all relationships

---

## Analysis Framework

To evaluate these solutions, consider:

| Criterion | Weight | Notes |
|-----------|--------|-------|
| Recall | High | Must capture ground truth controls |
| Candidate Set Size | High | Must be manageable for LLM |
| Implementation Complexity | Medium | Engineering effort |
| Generalization | Medium | Works for new documents/controls |
| Latency | Medium | Real-time requirements |
| Cost | Medium | LLM API calls, compute |
| Interpretability | Low | Nice to have |

## Recommended Exploration Path

Based on the analysis, I'd suggest exploring in this order:

### Quick Wins (Low Effort, Good Impact)

1. **5.3 Maximum Candidate Cap** - Use 0.20 threshold + cap at 100-150 controls. Simple, effective.

2. **1.1 Metadata-Based Pre-Inclusion** - If document is "Change Management Policy", auto-include all controls with that Associated Policy. Requires document classification.

3. **5.1 Accept Imperfect Recall** - Analyze which controls are truly "unretrievable" semantically. Maybe 90% recall is the right target.

### Medium Investment (Worth Exploring)

4. **3.1 Two-Stage LLM System** - Use a lightweight LLM to filter 620→100 candidates. Adds latency but solves the problem.

5. **1.3 Multi-Signal Retrieval Fusion** - Combine semantic + keyword + association signals. More robust retrieval.

6. **4.3 Cross-Encoder Reranking** - Fine-tune a reranker on compliance associations. Better than bi-encoder for this task.

### Strategic (If Problem Persists)

7. **6.1 Rethink the Task** - Are we solving the right problem? Maybe ground truth needs to be reconsidered.

8. **4.1 Fine-Tune on Compliance Associations** - Train a model that understands compliance relationships. Significant effort but addresses root cause.

9. **2.1 Dual Ground Truth** - Separate semantic vs compliance annotations. Clean but expensive.

---

## Key Insight

**The fundamental issue is using a semantic similarity tool to solve a compliance reasoning problem.**

Semantic retrieval asks: "Does this text match that text?"
Compliance association asks: "Does this document satisfy this control requirement?"

These are different questions. Our options are:
1. Accept the limitations of semantic retrieval (imperfect recall)
2. Augment semantic retrieval with compliance signals (hybrid approaches)
3. Replace semantic retrieval with compliance-aware methods (rethink the problem)

The right choice depends on how critical perfect recall is vs. engineering effort available.

---

## Next Steps

1. **Quantify the "unretrievable" controls** - How many controls truly cannot be identified from document content alone?

2. **Test maximum candidate cap** - What recall do we achieve with 0.20 threshold + top-150 cap?

3. **Prototype document type classification** - How accurately can we classify policy types? This enables metadata-based pre-inclusion.

4. **Evaluate two-stage LLM filtering** - Latency and accuracy of using LLM to filter 620→100 candidates.
