# LLM-Based Experiments for Control Detection

## Date: 2025-12-20

## Overview

This document aggregates LLM-based approaches for solving the semantic vs compliance retrieval problem. After filtering for the **arbitrary controls + arbitrary documents** production constraint, only two approaches are viable.

**Sources:**
- `semantic_vs_compliance_retrieval.md` (Claude's original analysis)
- `gemini_3_threshold_suggestions.md` (Gemini 2.5's suggestions)
- `chatgpt_52_pro_threshold_suggestions.md` (ChatGPT o1 Pro's suggestions)

---

## Problem Recap

ColModernVBERT scores are excellent for **ranking** but terrible for **thresholding**:
- GT and non-GT score distributions overlap heavily
- At 100% recall, 97%+ of controls pass the threshold
- **Root cause**: Semantic similarity ≠ compliance association

LLM-based approaches can bridge this gap because LLMs understand compliance reasoning, not just semantic similarity.

---

## Viable Experiments

Only two experiments work with the production constraint: **arbitrary PDFs and arbitrary controls at runtime**.

---

## Experiment 1: Two-Stage LLM Filtering

**Source:** Claude (Section 3.1)

### The Problem

Low threshold (0.20) returns ~620 controls per page. Too many for expensive LLM classification.

### The Solution

Insert a lightweight LLM filter between retrieval and classification.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 1: Broad Semantic Retrieval                                           │
│   - Threshold: 0.20 (captures everything)                                   │
│   - Output: ~620 controls per page                                          │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 2: LLM-Based Relevance Filter (FAST MODEL)                            │
│   - Input: Page image + 620 control NAMES (not descriptions)                │
│   - Prompt: "Which of these controls MIGHT be relevant to this page?"       │
│   - Model: Flash / Haiku (fast, cheap)                                      │
│   - Output: ~50-100 controls                                                │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 3: Full LLM Classification (SMART MODEL)                              │
│   - Input: Page image + 50-100 control full descriptions                    │
│   - Prompt: "Which controls does this page provide evidence for?"           │
│   - Model: Sonnet / GPT-4 (accurate)                                        │
│   - Output: Final predictions                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
def two_stage_filter(
    page_image: bytes,
    candidate_controls: list[Control],  # ~620 from low-threshold retrieval
    fast_model: str = "gemini-2.0-flash",
    smart_model: str = "claude-sonnet",
) -> list[ControlPrediction]:
    """
    Stage 1: Already done (semantic retrieval with low threshold)
    Stage 2: Fast LLM filters to manageable set
    Stage 3: Smart LLM does final classification
    """

    # Stage 2: Fast filter (send only names to save tokens)
    control_names = [{"id": c.id, "name": c.name} for c in candidate_controls]

    filter_prompt = f"""
    Look at this policy page. Review the list of {len(control_names)} control names.
    Return a JSON list of IDs for controls that MIGHT be relevant to this page.
    Be generous - include anything potentially related.

    Controls: {json.dumps(control_names)}
    """

    filtered_ids = fast_llm.generate(page_image, filter_prompt, model=fast_model)
    filtered_ids = json.loads(filtered_ids)  # ~50-100 IDs

    # Stage 3: Full classification with descriptions
    filtered_controls = [c for c in candidate_controls if c.id in filtered_ids]

    classify_prompt = f"""
    Analyze this policy page against the following controls.
    For each control, determine if this page provides evidence for it.

    Controls:
    {format_controls_with_descriptions(filtered_controls)}

    Return JSON: [{{"id": "...", "supported": true/false, "evidence": "..."}}]
    """

    predictions = smart_llm.generate(page_image, classify_prompt, model=smart_model)
    return parse_predictions(predictions)
```

### Why It Works

- Stage 2 LLM understands compliance relationships (not just semantic similarity)
- Filtering 620→100 is much cheaper than classifying 620
- Stage 3 gets a manageable candidate set for accurate classification

### Pros

- Guarantees high recall (low threshold in Stage 1)
- LLM does the compliance reasoning
- Separates filtering (cheap) from classification (expensive)
- Works with any controls - no pre-computation needed

### Cons

- Three stages = more latency
- Stage 2 LLM calls add cost (~$0.01-0.02 per page with Flash)
- Complexity in orchestration

### Cost Estimate

| Stage | Model | Input Tokens | Output Tokens | Cost/Page |
|-------|-------|--------------|---------------|-----------|
| Stage 2 | Flash 2.0 | ~5K (names) + image | ~500 (IDs) | ~$0.005 |
| Stage 3 | Sonnet | ~10K (descriptions) + image | ~2K (predictions) | ~$0.05 |
| **Total** | | | | **~$0.055/page** |

---

## Experiment 2: Visual Listwise Reranking (Flash Filter)

**Source:** Gemini 2.5 (Solution 2)

### The Problem

Same as above - too many candidates from low threshold retrieval.

### The Solution

Use a fast VLM to scan the page image AND a list of 500+ control titles simultaneously, returning a ranked subset.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 1: Broad Semantic Retrieval                                           │
│   - Threshold: 0.20                                                         │
│   - Output: ~500+ control TITLES (not descriptions, to save tokens)         │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 2: VLM Listwise Reranking (SINGLE CALL)                               │
│   - Input: Page Image + JSON list of 500 control titles                     │
│   - Prompt: "You are an auditor. Return top 50 potentially relevant IDs."   │
│   - Model: Flash 2.5 / Haiku                                                │
│   - Output: Ranked list of ~50 control IDs                                  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 3: Full LLM Classification                                            │
│   - Input: Page Image + 50 control full descriptions                        │
│   - Output: Final predictions                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
def visual_listwise_rerank(
    page_image: bytes,
    candidate_controls: list[Control],  # ~500+ from retrieval
    top_k: int = 50,
    model: str = "gemini-2.0-flash",
) -> list[str]:
    """
    Fast VLM scans page + control list simultaneously.
    Returns IDs of top-K potentially relevant controls.
    """
    # Only send titles to save tokens
    control_list = [{"id": c.id, "title": c.name} for c in candidate_controls]

    prompt = f"""
    You are a compliance auditor reviewing a policy document.

    Look at this policy page image carefully.
    Below is a list of {len(control_list)} security control titles.

    Return a JSON array of the IDs of the top {top_k} controls that are
    POTENTIALLY relevant to the content visible on this page.

    Be generous with relevance - it's better to include a control that
    might be relevant than to miss one that is.

    Controls:
    {json.dumps(control_list)}

    Return only the JSON array of IDs, nothing else.
    """

    response = vlm.generate(page_image, prompt, model=model)
    return json.loads(response)  # List of control IDs
```

### Key Insight

VLMs are excellent at **scanning an image and skimming a text list simultaneously**. This is like giving an auditor a checklist - they can quickly skim and identify relevant items without reading each one in detail.

The model treats the control list as a "menu" to select from, not a set of items to evaluate individually.

### Pros

- Single VLM call for 500+ controls (very efficient)
- Uses vision capabilities (sees actual page content, not OCR)
- Flash/Haiku are very fast (~1-2 seconds) and cheap
- Works with any controls - no pre-computation needed

### Cons

- Token limits may restrict list size (~500 titles ≈ 5K tokens)
- Relies on VLM understanding compliance relationships
- May miss subtle matches that require reading full descriptions

### Cost Estimate

| Stage | Model | Input Tokens | Output Tokens | Cost/Page |
|-------|-------|--------------|---------------|-----------|
| Stage 2 | Flash 2.0 | ~5K (titles) + image | ~200 (IDs) | ~$0.003 |
| Stage 3 | Sonnet | ~10K (descriptions) + image | ~2K | ~$0.05 |
| **Total** | | | | **~$0.053/page** |

---

## Comparison: Experiment 1 vs Experiment 2

| Aspect | Two-Stage LLM Filtering | Visual Listwise Reranking |
|--------|------------------------|---------------------------|
| **Stage 2 Approach** | "Filter to relevant" | "Rank and take top-K" |
| **Stage 2 Output** | Variable size (~50-100) | Fixed size (top-K) |
| **Prompt Style** | Binary relevance | Ranking/selection |
| **Token Efficiency** | Similar | Similar |
| **Latency** | Similar | Similar |
| **Cost** | ~$0.055/page | ~$0.053/page |

**Key Difference:** Experiment 1 asks "which are relevant?" (variable output), Experiment 2 asks "which are MOST relevant?" (fixed output).

**Recommendation:** Start with Experiment 2 (Visual Listwise Reranking) because:
1. Fixed output size is more predictable
2. Ranking framing may be more natural for the model
3. Slightly lower cost

---

## Recommended Implementation Plan

### Phase 1: Prototype Visual Listwise Reranking

1. Implement Stage 2 with Gemini Flash 2.0
2. Test on Asset Management Policy (Row 4) with 779 controls
3. Measure: recall at top-50, top-100, top-150
4. Evaluate: latency, cost, quality of selections

### Phase 2: Optimize

1. Tune prompt for better compliance reasoning
2. Test different K values (50, 75, 100)
3. Compare Flash vs Haiku performance
4. Consider batching multiple pages

### Phase 3: Production Integration

1. Integrate as Stage 2 in the pipeline
2. Add caching for repeated control sets
3. Monitor recall and cost metrics

---

## Success Metrics

| Metric | Current Baseline | Target |
|--------|------------------|--------|
| Candidate set size at 100% recall | 755/779 (97%) | < 100/779 (13%) |
| Candidate set size at 95% recall | - | < 75/779 (10%) |
| Stage 2 latency | N/A | < 2 seconds |
| Stage 2 cost per page | N/A | < $0.01 |
| Total pipeline cost per page | - | < $0.10 |

---

## Non-Viable Experiments (For Reference)

The following LLM-based approaches were suggested but **do not work** with the arbitrary controls/documents constraint:

| Experiment | Source | Why Not Viable |
|------------|--------|----------------|
| **Hypothetical Policy Generation** | Gemini | Requires LLM call per control at ingestion; adds latency to control creation |
| **Control Description Enrichment** | Claude | Same - requires LLM processing of each control |
| **Policy-Language Query Expansion** | ChatGPT | Same - requires offline LLM processing per control |
| **Policy-Type Classification** | Claude, ChatGPT | Requires pre-built mapping from policy types to controls |
| **LLM-First Domain Identification** | Claude | Requires controls to have domain metadata |
| **Control-Centric Verification** | ChatGPT | N parallel LLM calls (one per candidate) is too expensive/slow |
| **Fine-Tune Retriever** | Claude | Requires fixed control set for training |
| **Cross-Encoder Reranking** | Claude | Fine-tuning requires fixed control set |

These approaches may be viable if constraints change (e.g., if control ingestion can include LLM enrichment, or if control set becomes fixed).
