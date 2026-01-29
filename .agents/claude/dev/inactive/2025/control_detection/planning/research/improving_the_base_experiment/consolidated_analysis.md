# Consolidated Analysis: Improving the Control Detection System

**Date**: December 2025
**Sources**: Claude (improvement_analysis.md), ChatGPT (chatgpt_analysis.md), Gemini (gemini_3_analysis.md)

---

## Executive Summary

Three different LLM analyses converge on a core diagnosis: **the current system's bottleneck is the LLM's inability to make accurate multi-label decisions when presented with many semantically similar controls**. The retrieval stage (ColModernVBERT) works well (~95% recall at threshold), but the LLM struggles when asked to select from 50-100 candidates.

All three analyses strongly recommend **flipping the paradigm from "page → many controls" to "control → evidence"**. This emerges as the highest-impact architectural change.

---

## 1. Core Diagnosis (Unanimous Agreement)

### 1.1 Multi-Label Decision Overload

The LLM must make 50-100 independent binary decisions per page. This causes:
- Cognitive load that compounds with candidate count
- Attention collapse / "satisficing" (picking a few that sound right)
- Error compounding: 50 decisions × 5% error rate = high cumulative error

**Evidence**: Performance degraded when K increased from 50→100. LLM recall against candidates shown dropped from 44.5%→37.3%.

### 1.2 Semantic Similarity Creates Confusion

Among 779 DCF controls, many are near-duplicates:
- Multiple "access control" variants with subtle differences
- Configuration management vs change management overlap
- Data protection / privacy overlap

When showing 100 candidates, you're giving "more near-duplicates," not "more signal."

### 1.3 Page-Level Context Fragmentation

The LLM sees 1-5 pages at a time, but:
- Definitions may be on page 2, mandates on page 10
- Policy scope spans the entire document
- Controls may be addressed across non-adjacent sections

### 1.4 Metrics Verification Note (ChatGPT)

Before optimizing, verify evaluation plumbing is consistent:
- Exp 2 shows "GT above threshold = 480 (93.8%)" but GT is 686
- 480/686 ≠ 93.8% — this may indicate per-page vs per-doc aggregation difference
- Confirm baseline is apples-to-apples before chasing optimizations

---

## 2. High-Impact Direction: Control-Centric / Inverted Context (All Three Agree)

### 2.1 The Paradigm Flip

| Current | Proposed |
|---------|----------|
| Page-centric: "For each page, which of these 100 controls?" | Control-centric: "For each control, does this document address it?" |
| Multi-select (hard) | Binary decision (easy) |
| Limited page context | Full document context |
| 50-100 decisions per call | 1 decision per call |
| Similar controls compete | No confusion |

### 2.2 Why This Works

1. **Eliminates multi-control confusion** (the core problem)
2. **Full document context** — no more fragmented definitions/mandates
3. **Simple binary decision** — more reliable than multi-select
4. **Natural handling of multi-page content** — no aggregation needed

### 2.3 Implementation with Context Caching (Gemini/Claude)

```python
# Cache the full document once (~50 pages × 1000 tokens)
cache = client.caches.create(
    model="gemini-2.0-flash",
    contents=[
        Part.from_text(system_prompt),
        *[Part.from_bytes(page_image) for page_image in document_pages]
    ],
    ttl="3600s"
)

# For each candidate control (cheap per-call)
for control in candidate_controls:
    response = client.generate_content(
        model="gemini-2.0-flash",
        contents=[
            Part.from_text(f"Does this document address control {control.id}?\n\n{control.description}")
        ],
        cached_content=cache.name
    )
```

### 2.4 Cost Analysis

**Without caching**: 37 docs × 100 controls × 50 pages × 1000 tokens = 185B tokens ❌
**With caching**:
- Cache: 37 × 50 × 1000 = 1.85M tokens (cached, cheap)
- Variable: 37 × 100 × 200 = 740K tokens (per-call)
- Effective: ~2.6M tokens ✓

### 2.5 Computational Feasibility (ChatGPT)

You don't run 779 LLM calls blindly:
1. Use ColModernVBERT to filter to "relevant ~150" controls per document (doc-level max score per control)
2. For each kept control, attach top evidence pages (by score)
3. Even 150 small LLM calls can be cheaper/more accurate than fewer giant calls

### 2.6 Reducing the number of calls

  Instead of 1 control per call, batch 5-10 dissimilar controls per call:

  # Cluster controls first, then batch across clusters (not within)
  clusters = cluster_controls(candidates, n_clusters=20)
  batches = []
  for i in range(max(len(c) for c in clusters)):
      batch = [c[i] for c in clusters if i < len(c)]  # One from each cluster
      batches.append(batch[:10])

  # Now 100 controls → ~10-15 calls with diverse batches

  The key insight: 5-10 unrelated controls shouldn't cause the same confusion as 50-100 similar controls competing. You get full-doc context with manageable call count.

---

## 3. High-Impact Direction: Reduce Candidate Overload (All Three Agree)

### 3.1 Stop Giving LLM 50-100 Raw Controls

If staying page-centric, you must shrink and diversify the candidate set.

### 3.2 Diversification Strategies

| Strategy | Description | Source |
|----------|-------------|--------|
| **MMR / Diversity Sampling** | Keep high-score items, penalize controls too similar to already-chosen ones | ChatGPT |
| **Cluster Then Representatives** | Cluster candidates by embedding similarity, keep top 1-3 per cluster | All |
| **Per-Domain Caps** | If 70% of candidates are in one domain, cap that domain to N | ChatGPT |
| **Dynamic K by Score Gap** | Include all above threshold until score gap drops below delta | ChatGPT |

### 3.3 Post-Processing Expansion (Claude)

```python
# Cluster controls
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

### 3.4 Expected Impact

- Precision up (less confusion)
- LLM recall-vs-shown up (cleaner decisions)
- Often improves end-to-end recall (removing confusion ≠ removing signal)

---

## 4. High-Impact Direction: Mandate-First / Evidence-Based (All Three Agree)

### 4.1 The Core Insight

Policy documents are ~80% fluff (headers, definitions, intros) and ~20% rules. By extracting only rules, signal-to-noise ratio increases dramatically.

### 4.2 "Evidence or Nothing" Rule (ChatGPT)

Make selection contingent on quoting:
- Require exact quote(s) containing must/shall/required
- Require paraphrase mapping quote → requirement
- **If it can't quote, it can't select**

This usually:
- Drops FP significantly
- May drop recall initially (model forced to be honest)
- Recover recall via better retrieval + section aggregation

### 4.3 Mandate Extraction Pre-Processing (Gemini)

**Step 1 (Extraction)**: Run fast LLM over every page:
```
"Extract every sentence containing a binding mandate (must, shall, required, will ensure).
Return JSON: [{text: '...', page: 1}]. Ignore definitions."
```

**Step 2 (Mapping)**: Map aggregated binding statements against controls

**Step 3 (Grounding)**: Map matched mandates back to original page images for verification

### 4.4 RAG for Mandate-First Evidence (ChatGPT)

Use text RAG not as primary retriever, but for precision boosting:

1. Index chunks with page numbers preserved
2. Query recipe per control:
   - Control keywords + synonyms
   - Binding verbs ("must", "shall", "required", "prohibited")
   - Artifact nouns ("review", "log", "approve", "annually")
3. Retrieve top evidence snippets
4. LLM judges control using those snippets

**Key**: This makes RAG a precision booster, not another fuzzy matcher.

---

## 5. Medium-Impact Direction: Reranking Layer (ChatGPT, Gemini)

### 5.1 Cross-Encoder Reranking

ColBERT scores independently (late interaction). A Cross-Encoder takes `(Control Text, Page Text)` as single input and outputs relevance score, seeing word *interactions*.

**Flow**:
1. ColModernVBERT retrieves Top-200 (threshold 0.44 for 100% recall)
2. Cross-Encoder reranks (e.g., BGE-Reranker or cheap LLM zero-shot)
3. Take Top-15-20 from reranker
4. Send to final LLM for decision

### 5.2 Lightweight Supervised Model (ChatGPT)

Insert between retrieval and LLM:
```
embedding recall → cheap scorer → LLM
```

The "cheap scorer" can be:
- Logistic regression / XGBoost on features:
  - ColModernVBERT score
  - BM25 score
  - Keyword overlap
  - Presence of binding verbs near matched terms
  - Domain match with section title
  - Control length / specificity priors
- Or small cross-encoder trained on 686 labeled positives + hard negatives

**ROI**: Giant lever because dataset is already labeled.

### 5.3 Hard Negative Training (ChatGPT)

Current ranking is bad (GT can be #771) because no training against hard negatives.

**Concrete steps**:
- For each GT (policy, control) positive pair:
  - Sample top-50 non-GT controls by embedding score as hard negatives
- Fine-tune embedding model (contrastive) or reranker
- Even modest reranker can turn "GT anywhere" → "GT usually in top 50"

---

## 6. Medium-Impact Direction: Section-Level Understanding (ChatGPT)

### 6.1 The Problem

Neighbor inclusion logic is a patch for a real issue: policies are structured in sections, not pages.

### 6.2 Upgrade Granularity

1. Detect headings / section boundaries (from PDF text or layout)
2. Create "section objects" spanning 1-N pages
3. Run retrieval on sections
4. Adjudicate at section level

### 6.3 Benefits

- Fewer LLM calls
- Less fragmentation (mandate + definition stay together)
- Better match to how controls are actually addressed

---

## 7. Medium-Impact Direction: Agentic Approach (All Three Agree)

### 7.1 Concept

Give an LLM agent tools to investigate dynamically, like a human auditor.

### 7.2 Tool Design

```python
tools = [
    "search_document(query)" → snippets + page numbers,
    "read_page(page_num)" → full text + image,
    "get_candidate_controls(page_text)" → ColModernVBERT suggestions,
    "submit_finding(control_id, evidence, page_nums, confidence)",
    "mark_not_addressed(control_id, reason)"
]
```

### 7.3 Constrained Agent Loop (ChatGPT)

Key is tight budgets and deterministic steps, not open-ended reasoning:

1. Start from retrieval candidates (thresholded)
2. For each candidate control:
   - Query RAG for binding sentences + synonyms
   - If evidence found → verify
   - Else → reject quickly
3. Escalate only uncertain cases to deeper page inspection

### 7.4 Hybrid: Agent for Uncertain Cases Only (Claude)

```python
for control, score in candidates:
    if score > 0.75 and has_binding_language(pages, control):
        selections.append(control)  # Auto-accept
    elif score > 0.55:
        uncertain_controls.append(control)  # Use agent
    else:
        pass  # Skip

if uncertain_controls:
    agent_results = run_agent(document, uncertain_controls)
    selections.extend(agent_results)
```

### 7.5 Expected Impact

**Pros**: Highest potential accuracy, explainable chain-of-thought
**Cons**: Slow, expensive, complex to orchestrate

---

## 8. Quick Wins: Prompt Tuning (Claude, Gemini)

### 8.1 Current Prompt Issues

Prompt heavily emphasizes precision:
- "Prefer precision over recall - if unsure, don't select"
- "False positives are worse than false negatives"
- Strict "must/shall/required" binding language

May cause rejection of valid matches with slightly different language.

### 8.2 Prompt Variants to Test

| Variant | Change | Hypothesis |
|---------|--------|------------|
| Balanced | Remove "prefer precision over recall" | More selections, better recall |
| Relaxed binding | Accept "should", "recommended" as weak/low matches | Capture implicit mandates |
| With examples | Add 3-5 examples of correct selections | Better calibration |
| Confidence-weighted | "Select if >50% confident" | More nuanced decisions |

### 8.3 Negative Constraint Prompting (Gemini)

Add explicit rejection step before selection:

**New Prompt Structure**:
1. **Analyze Page**: List all topics discussed
2. **Analyze Candidate**: For each control:
   - Check 1: Does page mention the topic? (Yes/No)
   - Check 2: Is there "must/shall" verb attached? (Yes/No)
   - **Check 3 (The Kicker)**: "Generate a counter-argument: Why might this control NOT be a match?"
3. **Final Verdict**: Only select if Check 2 is YES and Check 3 is weak

---

## 9. Quick Wins: Confidence Filtering (Claude)

### 9.1 Current State

All LLM selections treated equally regardless of confidence.

### 9.2 Improvement Options

```python
# Option 1: Accept high/medium only
selected = [s for s in selections if s.confidence in ["high", "medium"]]

# Option 2: Weighted aggregation
WEIGHTS = {"high": 1.0, "medium": 0.6, "low": 0.3}
score = sum(WEIGHTS[s.confidence] for s in selections)

# Option 3: Threshold by domain
threshold = domain_thresholds.get(control.domain, 0.5)
```

---

## 10. Other Directions

### 10.1 Fine-Tuning (Claude)

- Use 686 positive examples (control-document pairs)
- Generate negatives (controls not mapped to document)
- Fine-tune classification head or full model
- Challenge: Small dataset, needs training infrastructure

### 10.2 Hierarchical Domain-First (Claude)

1. First: "Which domains does this policy address?" (e.g., "Change Management", "Cryptography")
2. Then: "Within that domain, which specific controls?"

Reduces search space, groups related controls.

### 10.3 Ensemble Methods (Claude)

Combine multiple approaches:
- ColModernVBERT page scores
- RAG text retrieval
- LLM page-level decisions
- LLM document-level decisions

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

### 10.4 Active Learning / Human-in-the-Loop (Claude)

- Flag low-confidence predictions for human review
- Use feedback to improve prompts/thresholds
- Build labeled dataset over time

### 10.5 Two-Pass Approach (Claude, ChatGPT)

**Pass 1 (High Recall)**: Looser criteria, accept "should"/"may", lower confidence threshold
**Pass 2 (Precision Filter)**: Verify each Pass 1 selection with focused prompt

```
Pass 1: "List ALL controls that might be related" → 30 candidates
Pass 2: For each: "Does this page adequately address {control}? Yes/No with evidence" → 12 confirmed
```

---

## 11. Prioritized Recommendations

### Tier 1: Quick Wins (Days)

| # | Improvement | Expected Impact | Effort |
|---|-------------|-----------------|--------|
| 1 | Reduce K to 40-50 | +2-5% F1 | Trivial |
| 2 | Prompt tuning (balanced, with examples) | +10-20% recall | Low |
| 3 | Confidence filtering (high/medium only) | +5-10% precision | Low |
| 4 | Negative constraint prompting | +5-10% precision | Low |

### Tier 2: High-Impact Architecture (1-2 Weeks)

| # | Improvement | Expected Impact | Effort |
|---|-------------|-----------------|--------|
| 5 | **Full doc + single control** with context caching | +15-25% F1 | Medium |
| 6 | Mandate extraction pre-processing | +10-15% precision | Medium |
| 7 | Control clustering / diversity sampling | +10-15% F1 | Medium |
| 8 | Cross-encoder / supervised reranker | +10-15% F1 | Medium |

### Tier 3: Higher Effort (2-4 Weeks)

| # | Improvement | Expected Impact | Effort |
|---|-------------|-----------------|--------|
| 9 | Section-level understanding | +5-10% F1 | High |
| 10 | RAG mandate extraction pipeline | +5-10% F1 | High |
| 11 | Agentic approach (uncertain cases) | +10-20% F1 | High |
| 12 | Hard negative training / fine-tuning | +15-25% F1 | High |

---

## 12. Recommended Experiment Sequence

### Phase 1: Quick Iterations (Week 1)

1. **Experiment 3**: K=40, same prompt — test if smaller K helps
2. **Experiment 4**: K=50, balanced prompt — remove precision emphasis
3. **Experiment 5**: K=50, confidence filtering (high/medium only)
4. **Experiment 6**: K=50, negative constraint prompting (counter-argument step)

### Phase 2: Architecture Pivot (Weeks 2-3)

5. **Experiment 7**: Full document + single control (pilot on 5-10 docs)
   - Use context caching
   - Binary decision per control
   - Compare P/R/F1 to baseline

6. **Experiment 8**: Mandate extraction pre-processing
   - Extract binding sentences first
   - Run mapping on extracted content

### Phase 3: Refinement (Week 4+)

7. **Experiment 9**: Best of Phase 1 + Phase 2 combined
8. **Experiment 10**: Add cross-encoder reranking
9. **Experiment 11**: Add RAG mandate extraction signal
10. **Experiment 12**: Agentic approach for uncertain cases

---

## 13. If You Had to Pick 2-3 Steps (ChatGPT)

1. **Switch to control-first adjudication** (control → top evidence pages/snippets → binary decision with quotes)
2. **Add diversified candidate selection** (MMR/clustering + per-domain caps) before any LLM step
3. **Use RAG mandate extraction** to feed LLM evidence, require quotes to select

This combination attacks:
- Candidate overload
- False positives
- "Control spread across pages/sections"

---

## 14. Conclusion

All three analyses converge on:

1. **The bottleneck is multi-label confusion**, not retrieval quality
2. **Flip from page-centric to control-centric** is the highest-impact change
3. **Require evidence/quotes** to kill false positives
4. **Reduce/diversify candidates** if staying page-centric
5. **Quick prompt tuning** can yield immediate gains

The **"full document + single control"** approach with context caching addresses all core problems and should be the primary architectural experiment after quick prompt-tuning wins.
