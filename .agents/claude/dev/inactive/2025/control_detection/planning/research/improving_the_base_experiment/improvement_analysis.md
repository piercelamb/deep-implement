# Improving the Control Detection System: Research Analysis

**Date**: December 2025

## Executive Summary

The current two-stage system (ColModernVBERT retrieval + Gemini LLM selection) achieves ~95% embedding recall but only ~34-42% end-to-end precision/recall. The LLM is the bottleneck, struggling to select correct controls from large candidate sets.

This document analyzes the root causes and proposes improvement directions, prioritized by feasibility and expected impact.

---

## 1. Diagnosis: Why Is the LLM Performing Poorly?

### 1.1 Multi-Label Decision Overload

**The Problem**: The LLM must make 50-100 independent binary decisions per page. Each control is evaluated separately, but:
- Cognitive load accumulates with candidate count
- Similar controls create confusion
- Attention is divided across many candidates
- Error compounds: 50 decisions × 5% error rate = high cumulative error

**Evidence**: Performance degraded when K increased from 50 to 100. The LLM's recall against candidates it saw dropped from 44.5% to 37.3%.

### 1.2 Semantic Similarity Among Controls

**The Problem**: Among 779 DCF controls, many are semantically similar:
- Multiple controls about "access control" with subtle differences
- Configuration management controls vs change management controls
- Data protection controls that overlap with privacy controls

When the candidate set contains 5-10 similar-looking controls, the LLM struggles to distinguish which specific ones are addressed.

### 1.3 Page-Level Context Limitations

**The Problem**: The LLM sees 1-5 pages at a time, but:
- Policy scope may span the entire document
- A control might be addressed across multiple non-adjacent sections
- Context from document introduction/scope affects interpretation
- Table of contents gives structure the LLM can't see

### 1.4 Overly Conservative Prompt

**The Problem**: The prompt emphasizes precision over recall:
- "Prefer precision over recall - if unsure, don't select"
- "False positives are worse than false negatives"
- Strict "must/shall/required" binding language requirement

This may cause the LLM to reject valid matches that use slightly different language.

### 1.5 Ground Truth Quality Uncertainty

**The Problem**: We assume ground truth is correct, but:
- Some GT mappings may be compliance-based, not semantic
- Auditor standards for "addresses control" may differ from LLM interpretation
- Missing controls in GT would appear as false positives

---

## 2. Improvement Direction: Immediate System Optimizations

### 2.1 Prompt Tuning

**Current State**: Prompt heavily emphasizes precision, strict binding language.

**Experiments to Try**:

| Variant | Change | Hypothesis |
|---------|--------|------------|
| Balanced | Remove "prefer precision over recall" | More selections, better recall |
| Relaxed binding | Accept "should", "recommended" as weak matches | Capture implicit mandates |
| With examples | Add 3-5 examples of correct selections | Better calibration |
| Confidence-weighted | "Select if >50% confident" instead of strict criteria | More nuanced decisions |

**Implementation**: Create prompt variants, run on same dataset, compare P/R/F1.

**Expected Impact**: Medium. Could improve recall by 10-20% with some precision loss.

### 2.2 Confidence-Based Filtering

**Current State**: All selections treated equally regardless of confidence.

**Improvement**: Use confidence levels in post-processing:
- Only accept "high" confidence predictions
- Or weight by confidence in aggregation
- Or use confidence threshold that varies by control domain

**Implementation**:
```python
# Current: accept all
selected = [s for s in selections]

# Improved: confidence filter
selected = [s for s in selections if s.confidence in ["high", "medium"]]

# Or: confidence weighting in aggregation
score = sum(WEIGHTS[s.confidence] for s in selections)
```

**Expected Impact**: Medium. May improve precision significantly with some recall loss.

### 2.3 Control Clustering / Deduplication

**Current State**: All 779 controls treated independently. Similar controls compete.

**Improvement**: Cluster similar controls, present representatives:
1. Pre-compute control embeddings
2. Cluster into ~100-200 groups by semantic similarity
3. Present cluster representatives to LLM
4. Expand selected clusters back to individual controls

**Implementation**:
```python
# Cluster controls
from sklearn.cluster import KMeans
clusters = KMeans(n_clusters=150).fit(control_embeddings)

# Select representative per cluster (highest embedding score)
for cluster_id in triggered_clusters:
    representative = get_highest_scoring_control(cluster_id, page_scores)
    candidates.append(representative)

# Post-process: expand selected clusters
for selected in llm_selections:
    cluster_id = control_to_cluster[selected.control_id]
    for control in cluster_members[cluster_id]:
        if page_score[control] > threshold:
            final_selections.append(control)
```

**Expected Impact**: High. Reduces confusion, improves both precision and recall.

### 2.4 Two-Pass Approach

**Current State**: Single-pass selection with strict criteria.

**Improvement**: Separate recall and precision phases:

**Pass 1 (High Recall)**:
- Looser criteria: accept "should", "may", tangential coverage
- Lower confidence threshold
- Goal: capture all potential matches

**Pass 2 (Precision Filter)**:
- Stricter criteria on Pass 1 selections only
- Verify each candidate with focused prompt
- Goal: filter false positives

**Implementation**:
```
Pass 1: "List ALL controls that might be related to this page"
        → 30 candidates

Pass 2: For each of 30 candidates:
        "Does this page adequately address {control}? Yes/No with evidence"
        → 12 confirmed matches
```

**Expected Impact**: High. Decouples recall from precision, allows optimization of each.

---

## 3. Improvement Direction: Full Document + Single Control

### 3.1 Concept

**Flip the prompting paradigm**:
- Current: 1-5 pages + 50-100 controls → multi-select
- Proposed: Full document + 1 control → binary decision

### 3.2 Why This Might Work Better

| Current Approach | Single-Control Approach |
|-----------------|------------------------|
| 50-100 decisions per call | 1 decision per call |
| Limited page context | Full document context |
| Similar controls compete | No confusion |
| Complex multi-select | Simple yes/no |
| Aggregate page decisions | Natural document-level answer |

### 3.3 Implementation with Context Caching

Gemini supports context caching - cache expensive tokens, vary cheap tokens:

```python
# Cache the full document (once per document)
cache = client.caches.create(
    model="gemini-2.0-flash",
    contents=[
        Part.from_text(system_prompt),
        *[Part.from_bytes(page_image) for page_image in document_pages]
    ],
    ttl="3600s"  # 1 hour
)

# For each candidate control (100 calls, but cheap)
for control in candidate_controls:
    response = client.generate_content(
        model="gemini-2.0-flash",
        contents=[
            Part.from_text(f"Does this document address the following control?\n\n{control}")
        ],
        cached_content=cache.name
    )
```

### 3.4 Cost Analysis

**Without caching** (naive approach):
- 37 documents × 100 controls × 50 pages × 1000 tokens = 185B input tokens ❌

**With caching**:
- Cache: 37 documents × 50 pages × 1000 tokens = 1.85M tokens (cached, cheap)
- Variable: 37 × 100 × 200 tokens = 740K tokens (per-call)
- Total effective: ~2.6M tokens ✓

**Latency**: 100 sequential calls per document, but each is fast (~1-2s)
- Could parallelize with multiple caches
- ~2-5 minutes per document

### 3.5 Prompt Design

```
You are a compliance expert. You have been shown a complete security policy document (all pages).

Your task: Determine if this document adequately addresses the following control requirement.

<control>
{control_id}: {control_name}
{control_description}
</control>

<criteria>
A document "addresses" a control if it contains:
1. Binding language (must/shall/required/will) about the control's subject
2. Specific mandates that fulfill the control's core requirement

The mandate does not need to use identical terminology - semantic equivalence counts.
</criteria>

<response_format>
{
  "addresses_control": true/false,
  "confidence": "high" | "medium" | "low" | "none",
  "evidence": "Quote or describe the specific section(s) that address this control",
  "page_numbers": [list of relevant page numbers]
}
</response_format>
```

### 3.6 Expected Impact

**Pros**:
- Eliminates multi-control confusion (biggest current problem)
- Full document context improves understanding
- Simple binary decision is more reliable
- Page numbers in response provide interpretability

**Cons**:
- More LLM calls (100 per document vs ~10-20 currently)
- Sequential nature adds latency
- Cost depends on caching effectiveness

**Expected Impact**: High. This addresses the core problem of multi-label confusion.

---

## 4. Improvement Direction: RAG as Supplementary Signal

### 4.1 Concept

Use text-based RAG retrieval alongside visual ColModernVBERT:
- Different modalities find different matches
- Agreement = higher confidence
- RAG can find keyword matches that visual model misses

### 4.2 Implementation

**Indexing**:
```python
# Extract text from PDF pages
texts = [extract_text(page) for page in document.pages]

# Chunk with overlap
chunks = []
for page_num, text in enumerate(texts):
    for chunk in chunk_text(text, size=500, overlap=100):
        chunks.append({
            "text": chunk,
            "page_num": page_num,
            "document_id": document.id
        })

# Index with hybrid search (BM25 + semantic)
index.add(chunks, embeddings=embed(chunks))
```

**Query per control**:
```python
def get_rag_evidence(control: DCFControl, document_id: str) -> list[Chunk]:
    # Semantic search
    semantic_hits = index.search(
        query=control.description,
        filter={"document_id": document_id},
        top_k=10
    )

    # Keyword search (BM25)
    keywords = extract_keywords(control.description)
    keyword_hits = index.keyword_search(
        query=keywords,
        filter={"document_id": document_id},
        top_k=10
    )

    # Combine and deduplicate
    return merge_hits(semantic_hits, keyword_hits)
```

**Integration with existing pipeline**:
```python
# For each control in candidates:
rag_hits = get_rag_evidence(control, document_id)
visual_score = colmodernvbert_score[control.id]

# Boost score if RAG agrees
if rag_hits and max(h.score for h in rag_hits) > 0.7:
    combined_score = visual_score * 1.3  # 30% boost
else:
    combined_score = visual_score

# Or use RAG evidence in LLM prompt
llm_input.add_evidence(rag_hits)
```

### 4.3 Expected Impact

**Pros**:
- Catches keyword matches that visual model misses
- Text search can find specific control terminology
- Hybrid approach more robust than single modality

**Cons**:
- PDF text extraction can be lossy (especially for tables, formatting)
- Chunking breaks context
- Additional infrastructure (vector store, indexing)

**Expected Impact**: Medium. Useful as supplementary signal, not replacement.

---

## 5. Improvement Direction: Agentic Retrieval

### 5.1 Concept

Give an LLM agent tools to investigate each control dynamically:
- Start with ColModernVBERT candidates
- Agent decides what to explore
- Builds evidence incrementally
- More like how a human auditor would work

### 5.2 Tool Design

```python
tools = [
    {
        "name": "search_document",
        "description": "Search the document for text matching a query",
        "parameters": {"query": "string"}
    },
    {
        "name": "view_page",
        "description": "Load and view a specific page image",
        "parameters": {"page_num": "int"}
    },
    {
        "name": "get_page_text",
        "description": "Get extracted text from a page",
        "parameters": {"page_num": "int"}
    },
    {
        "name": "get_embedding_scores",
        "description": "Get ColModernVBERT scores for a control across all pages",
        "parameters": {"control_id": "string"}
    },
    {
        "name": "submit_finding",
        "description": "Record that a control is addressed by specific evidence",
        "parameters": {
            "control_id": "string",
            "evidence": "string",
            "page_nums": "list[int]",
            "confidence": "high|medium|low"
        }
    },
    {
        "name": "mark_not_addressed",
        "description": "Record that a control is NOT addressed after investigation",
        "parameters": {"control_id": "string", "reason": "string"}
    }
]
```

### 5.3 Agent Workflow

```
System: You are a compliance auditor. Your task is to determine which controls
from the candidate list are addressed by this policy document.

You have access to tools to search and view the document. For each candidate
control, investigate whether the document addresses it, then submit your finding.

Candidate controls (ranked by embedding similarity):
1. DCF-182: Encryption at Rest (score: 0.72)
2. DCF-183: Key Management (score: 0.68)
3. DCF-55: Data Classification (score: 0.65)
...

Begin your investigation.

---

Agent: I'll start with DCF-182 (Encryption at Rest) since it has the highest score.
Let me search for encryption-related content.

<tool_call>search_document("encryption at rest")</tool_call>

Results: Found matches on pages 3, 7, 12

<tool_call>view_page(7)</tool_call>

[Views page 7]

This page contains "All data at rest must be encrypted using AES-256..."
This directly addresses DCF-182.

<tool_call>submit_finding(
    control_id="DCF-182",
    evidence="Page 7: 'All data at rest must be encrypted using AES-256'",
    page_nums=[7],
    confidence="high"
)</tool_call>

Now let me check DCF-183 (Key Management)...
```

### 5.4 Hybrid Approach: Agent for Uncertain Cases Only

Full agentic approach is expensive. Hybrid version:

```python
# Easy cases: high embedding score + passes simple heuristic
for control, score in candidates:
    if score > 0.75 and has_binding_language(pages, control):
        # Auto-accept without agent
        selections.append(control)
    elif score > 0.55:
        # Uncertain: use agent
        uncertain_controls.append(control)
    else:
        # Low score: skip
        pass

# Run agent only on uncertain controls
if uncertain_controls:
    agent_results = run_agent(document, uncertain_controls)
    selections.extend(agent_results)
```

### 5.5 Expected Impact

**Pros**:
- Most human-like approach
- Can dig deeper when uncertain
- Builds explicit evidence chain
- Interpretable reasoning

**Cons**:
- Slowest approach (multi-turn loops)
- Most expensive (many LLM calls per control)
- Harder to debug/reproduce
- Agent may get stuck or make mistakes

**Expected Impact**: High quality but high cost. Best for high-stakes decisions.

---

## 6. Improvement Direction: Control-Centric Approach

### 6.1 Concept

**Current**: Page-centric - "For each page, which controls?"
**Proposed**: Control-centric - "For each control, which pages?"

### 6.2 Implementation

```python
for control in all_controls:
    # Find pages most relevant to this control
    page_scores = colmodernvbert.score_control_vs_all_pages(control, document)
    top_pages = sorted(page_scores, reverse=True)[:5]

    if top_pages[0].score < threshold:
        continue  # No relevant pages

    # Ask LLM: does this set of pages address this control?
    response = llm.generate(
        system="You are evaluating whether a set of policy pages addresses a specific control.",
        images=[page.image for page in top_pages],
        user=f"""
        Control: {control.id} - {control.name}
        {control.description}

        Do these pages adequately address this control?
        """
    )

    if response.addresses_control:
        selections.append(control)
```

### 6.3 Why This Helps

| Aspect | Page-Centric | Control-Centric |
|--------|--------------|-----------------|
| Focus | Broad (many controls) | Narrow (one control) |
| Context | Single page | Multiple relevant pages |
| Decision | Multi-select (hard) | Binary (easier) |
| Multi-page content | Aggregation needed | Natural handling |

### 6.4 Expected Impact

**Pros**:
- Simple binary decision per control
- Naturally handles multi-page content
- LLM focuses on one control at a time
- Can present most relevant pages together

**Cons**:
- More LLM calls (one per control candidate)
- Retrieval must work at control level

**Expected Impact**: High. Simpler decisions, better context.

---

## 7. Other Directions to Consider

### 7.1 Fine-Tuning

**Concept**: Fine-tune a model on the ground truth data.

**Approach**:
- Use 686 positive examples (control-document pairs)
- Generate negative examples (controls not mapped to document)
- Fine-tune classification head or full model

**Challenges**:
- Small dataset (686 positives)
- Need negative sampling strategy
- Requires training infrastructure

**Expected Impact**: Medium-High if done well, but requires significant effort.

### 7.2 Hierarchical Domain-First

**Concept**: Use DCF control hierarchy to narrow search.

**Approach**:
1. First: "Which domains does this policy address?" (e.g., "Change Management", "Cryptography")
2. Then: "Within Change Management domain, which specific controls?"

**Benefits**:
- Reduces search space
- Groups related controls
- More natural for human review

**Challenges**:
- Requires domain annotations (may exist in DCF data)
- Two-stage pipeline complexity

### 7.3 Ensemble Methods

**Concept**: Combine multiple approaches, vote/stack predictions.

**Components**:
- ColModernVBERT page scores
- RAG text retrieval
- LLM page-level decisions
- LLM document-level decisions

**Combination**:
```python
# Simple voting
selected = control if (
    colbert_score > 0.6 and
    rag_score > 0.5 and
    llm_page_decision == True
)

# Or learned stacking
features = [colbert_score, rag_score, llm_confidence, ...]
prediction = stacking_model.predict(features)
```

### 7.4 Active Learning / Human-in-the-Loop

**Concept**: Flag uncertain predictions for human review, learn from feedback.

**Implementation**:
- Identify low-confidence predictions
- Present to human for verification
- Use feedback to improve prompts/thresholds
- Build labeled dataset over time

---

## 8. Prioritized Recommendations

### Tier 1: Quick Wins (1-2 days each)

| # | Improvement | Expected Impact | Effort |
|---|-------------|-----------------|--------|
| 1 | **Prompt tuning** - Balance precision/recall | +10-20% recall | Low |
| 2 | **Confidence filtering** - Accept high/medium only | +5-10% precision | Low |
| 3 | **Reduce K to 40** - Based on degradation at K=100 | +2-5% F1 | Trivial |

### Tier 2: Moderate Effort, High Potential (1-2 weeks each)

| # | Improvement | Expected Impact | Effort |
|---|-------------|-----------------|--------|
| 4 | **Full doc + single control** with context caching | +15-25% F1 | Medium |
| 5 | **Control-centric approach** | +10-20% F1 | Medium |
| 6 | **Control clustering** | +10-15% F1 | Medium |
| 7 | **Two-pass (recall then precision)** | +10-15% F1 | Medium |

### Tier 3: Higher Effort (2-4 weeks each)

| # | Improvement | Expected Impact | Effort |
|---|-------------|-----------------|--------|
| 8 | **RAG supplementary signal** | +5-10% F1 | High |
| 9 | **Agentic approach** (uncertain cases) | +10-20% F1 | High |
| 10 | **Fine-tuning** | +15-25% F1 | High |

---

## 9. Recommended Experiment Sequence

### Phase 1: Quick Iterations (Week 1)

1. **Experiment 3**: K=40, same prompt
   - Test if smaller K helps (based on K=100 degradation)

2. **Experiment 4**: K=50, balanced prompt
   - Remove "prefer precision over recall"
   - Accept "should/may" as low confidence

3. **Experiment 5**: K=50, confidence filtering
   - Only accept high+medium confidence in aggregation

### Phase 2: Architecture Change (Week 2-3)

4. **Experiment 6**: Full document + single control
   - Use context caching
   - Test on subset (10 documents)
   - Compare P/R/F1 to baseline

5. **Experiment 7**: Control-centric approach
   - For each candidate control, find top-5 pages
   - Binary decision per control

### Phase 3: Hybrid Approaches (Week 4+)

6. **Experiment 8**: Best of Phase 1 + Phase 2
   - Combine winning approaches

7. **Experiment 9**: Add RAG signal
   - If still seeing issues with specific controls

---

## 10. Conclusion

The current system's main bottleneck is the LLM's inability to make accurate multi-label decisions when presented with many similar controls. The most promising improvements attack this problem directly:

1. **Reduce decision complexity**: Single-control prompting instead of multi-select
2. **Improve context**: Full document visibility instead of page-level
3. **Reduce confusion**: Cluster similar controls

The "full document + single control" approach (Section 3) addresses all three issues and is the recommended next major experiment after quick prompt-tuning wins.
