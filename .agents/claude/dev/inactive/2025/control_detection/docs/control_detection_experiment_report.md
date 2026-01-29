# Control Detection Experiment Report

**Date**: December 2025
**Status**: Ongoing experiments

## Executive Summary

This document describes the policy-to-control mapping experiment, which aims to automatically detect which DCF (Drata Control Framework) controls are addressed by a given security policy document. The system uses a two-stage approach: (1) ColModernVBERT for semantic retrieval of candidate controls, and (2) Gemini LLM for precise control selection from candidates.

Key findings from initial experiments:
- Retrieval stage achieves ~95% recall at threshold 0.48
- Top-K limiting is a significant bottleneck (77% recall at K=50, 82% at K=100)
- LLM performance degrades with larger candidate sets (F1 dropped from 37.7% to 33.2%)
- Optimal top-K is likely closer to 50 than 100

---

## 1. Problem Statement

### The Challenge

Given a security policy document (PDF) and a set of ~779 DCF controls, determine which controls the policy adequately addresses. This is a multi-label classification problem where:

- Each policy document can satisfy multiple controls (typically 8-66 per policy)
- Each control has a specific requirement that must be matched to binding language in the policy
- Topic similarity alone is insufficient - the policy must contain mandates ("must", "shall", "required") that address the control's core requirement

### Why This Matters

Manual policy-to-control mapping is time-consuming and error-prone. Automating this process enables:
- Faster compliance gap analysis
- Consistent control mapping across organizations
- Scalable evidence collection for audits

### Ground Truth Dataset

- **37 template policy documents** from Drata
- **734 total ground truth control mappings** (686 valid after filtering invalid control IDs)
- **779 candidate DCF controls** to evaluate per document

---

## 2. Retrieval Stage: ColModernVBERT

### Overview

The first stage uses ColModernVBERT, a multimodal late-interaction model, to score semantic similarity between policy page images and control descriptions. This produces a ranked list of candidate controls for each page.

### ColBERT-Style MaxSim Scoring

ColBERT uses "late interaction" where both query and document are encoded independently, then similarity is computed via MaxSim:

```
For each QUERY token:
    max_sim = max similarity to any DOCUMENT token
Sum all max_sim values
```

### The Scoring Direction Problem

The initial implementation used **PAGE_COVERAGE** scoring:
- Query: Page tokens (hundreds)
- Document: Control tokens (tens)
- Question: "How much of the page looks like this control?"

**Problem**: Pages contain much more content than any control could match:
- Headers, footers, logos
- Boilerplate language
- Company-specific information
- Multiple control-related topics

Result: Even "perfect" semantic matches only scored ~38-40% of theoretical maximum, with scores compressed in the 0.12-0.40 range.

### Solution: CONTROL_COVERAGE Scoring

We flipped the scoring direction:
- Query: Control tokens
- Document: Page tokens
- Question: "How much of this control's concepts are found in the page?"

```python
class ScoringMode(Enum):
    PAGE_COVERAGE = "page_coverage"       # Original: sum over page tokens
    CONTROL_COVERAGE = "control_coverage" # New: sum over control tokens
```

**Key insight**: Control descriptions are short and specific (~50-200 words). Every token matters. A relevant page SHOULD match most control tokens, giving better discrimination.

### Score Normalization

Scores are normalized using self-similarity as the upper bound:

```python
def normalize(raw_score, upper_bound):
    return (raw_score / upper_bound).clamp(0, 1)
```

For CONTROL_COVERAGE, upper bounds are the control's self-similarity (precomputed once for efficiency).

### Threshold Discovery

Through extensive analysis on template policies:

| Threshold | Embedding Recall | Notes |
|-----------|------------------|-------|
| 0.44 | 100% | All GT captured, minimal filtering |
| 0.48 | ~92-95% | Good balance, 32% filtering |
| 0.50 | ~76% | Too aggressive |

**Selected threshold: 0.48** - Captures ~95% of ground truth controls while providing meaningful candidate filtering.

### Why Not Pure Top-K?

Analysis showed ground truth controls can rank anywhere from #1 to #771 among 779 controls:
- Only 7% rank in top 5
- Only 10% rank in top 10
- Only 25% rank in top 50

A pure top-K approach misses many valid controls. The hybrid approach (score threshold + top-K cap) provides better coverage.

---

## 3. LLM Decision Layer

### Architecture

After retrieval, each qualifying page gets its own LLM call with:
1. Page image(s) - primary page plus optional neighbor context
2. Candidate controls - those scoring above threshold, capped at top-K

```
Policy PDF Pages → ColModernVBERT Scoring → Per-Page Threshold Filter →
→ Parallel LLM Calls (1 per qualifying page) → Aggregate → Final Control Selection(s)
```

### Multi-Select Design

Each page can match **zero, one, or many** controls. The LLM evaluates each candidate independently and returns all controls the page adequately addresses.

### Neighbor Page Inclusion

Policy content often spans multiple pages. Adjacent pages are included when they have related controls:

| Level | Check | Threshold |
|-------|-------|-----------|
| Same Control ID | Neighbor has same control | threshold × 0.7 (lenient) |
| Same Domain | Neighbor has control in same domain | full threshold |

### Aggregation

Page-level decisions are aggregated using union with max confidence:
- Collect all selected controls across all pages
- Take the maximum confidence for each control
- Combine reasoning from pages that selected it

---

## 4. LLM Prompts

### System Prompt

```
You are a compliance expert analyzing security policy documents to identify which of the security controls given to you they address.

# Control Selection Instructions

## Your Task

Given page image(s) from a security policy and a list of candidate controls, select ALL controls that this page adequately addresses. A page may match zero, one, or many controls. Evaluate each control independently.

## The Critical Distinction

**Topic similarity does NOT equal a valid match**

A valid match requires the page to contain a **binding mandate** that addresses the control's requirement - not just mention related concepts.

### Binding Language (Required for Match)
- "shall", "must", "required", "will ensure"
- "must not", "prohibited", "forbidden" (for prohibitions)

### Insufficient (Do Not Select)
- "should", "may", "recommended", "encouraged"
- Definitions or background without mandates
- Table of contents, headers, or boilerplate

## Selection Logic (Per Control)

For EACH candidate control, ask:

1. Does the page contain binding language about this control's subject?
   NO -> Do not select this control
   YES -> Continue

2. Does the page mandate action that addresses this control's core requirement?
   NO -> Do not select this control
   YES -> Select this control

3. How specific is the coverage?
   - Explicit procedures/specs/ownership -> HIGH confidence
   - Clear intent but missing details -> MEDIUM confidence
   - Tangential or partial coverage -> LOW confidence

A page can match multiple controls if it contains binding mandates for each.

## Confidence Guide (Per Selected Control)

| Confidence | Criteria |
|------------|----------|
| high | Direct terminology match + binding language + specific details (who, when, how) |
| medium | Semantic equivalence to control intent OR binding language with minor gaps |
| low | Related coverage but significant gaps in specificity or scope |

Only assign confidence to controls you select. Do not select a control just to give it "none" confidence.

## Red Flags -> Select No Controls

- Page only contains headers, TOC, or document metadata
- Terms appear but without "must/shall" language
- Page discusses concepts generally without mandating action
- Scope statement explicitly excludes what control requires

If ALL candidates fail these checks, return an empty selection.

## Quick Heuristics

1. **Look for verbs**: "shall implement", "must maintain", "is required to"
2. **Look for ownership**: "IT Security is responsible for...", "Data owners must..."
3. **Look for specifics**: frequencies, parameters, named standards, artifact requirements
4. **Ignore aspirations**: "We value security", "The goal is to...", "Best practices include..."

## Quality Over Quantity

Select a control only if the page genuinely addresses its requirement. When evaluating:
- Prefer precision over recall (don't stretch to find matches)
- Each selection should stand on its own merit
- If unsure, don't select - false positives are worse than false negatives
```

### User Prompt

```
Analyze this policy document page and select ALL controls that this page adequately addresses.

<page_info>
<previous_pages>{previous_pages}</previous_pages>
<primary_page>{primary_page}</primary_page>
<later_pages>{later_pages}</later_pages>
</page_info>


<candidate_controls>
{controls}
</candidate_controls>

<key_reminders>
- Topic similarity alone is NOT a match - require binding language that addresses the control's requirement
- "should", "may", "recommended" are insufficient - only "must/shall/required" count
- Skip pages with only TOC, headers, boilerplate, or general discussion without mandates
- Confidence: high = specific details (who/when/how), medium = clear intent with minor gaps, low = partial coverage
- Prefer precision over recall - if unsure, don't select (false positives are worse than false negatives)
</key_reminders>

<instructions>
1. Focus your analysis on page {primary_page_num} (the primary page)
2. Use any previous/later pages only for additional context (e.g., continued paragraphs, section headers)
3. Evaluate EACH candidate control independently using the selection logic
4. Select ALL controls where the page contains binding mandates (must/shall/required/will ensure)
5. A page may match zero, one, or many controls
6. For each selected control, provide confidence (high/medium/low) and brief reasoning
7. Return an empty array if no controls are adequately addressed
</instructions>
```

### Response Schema (JSON)

```json
{
  "type": "object",
  "properties": {
    "selected_controls": {
      "type": "array",
      "description": "Controls that this page adequately addresses. Empty array if none match.",
      "items": {
        "type": "object",
        "properties": {
          "control_id": {
            "type": "string",
            "enum": "CONTROL_IDS",
            "description": "The control_id of a matching control"
          },
          "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "Confidence level for this specific control"
          },
          "reasoning": {
            "type": "string",
            "description": "Brief explanation of why this control matches"
          }
        },
        "required": ["control_id", "confidence", "reasoning"]
      }
    }
  },
  "required": ["selected_controls"]
}
```

Note: `CONTROL_IDS` is dynamically replaced at runtime with the actual candidate control IDs for each page.

---

## 5. Experiment Results

### Experiment 1: Baseline (Top-K = 50)

**Configuration:**
| Parameter | Value |
|-----------|-------|
| Embedding model | ColModernVBERT |
| Scoring mode | CONTROL_COVERAGE |
| Score threshold | 0.48 |
| Max controls per LLM call | 50 |
| LLM model | gemini-3-flash-preview |
| Temperature | 0.1 |
| Documents evaluated | 37 |
| Ground truth controls | 686 (filtered) |

**Retrieval Stage Results:**
| Metric | Value |
|--------|-------|
| GT above threshold (0.48) | 654 (95.3%) |
| GT in top-50 (sent to LLM) | 528 (77.0%) |
| GT lost at threshold | 32 |
| GT lost at top-K cap | 126 |

**LLM Stage Results:**
| Metric | Value |
|--------|-------|
| Predicted controls | 560 |
| True positives | 235 |
| False positives | 325 |
| False negatives | 451 |
| **Precision** | **42.0%** |
| **Recall** | **34.3%** |
| **F1** | **37.7%** |

**LLM Performance (Adjusted for Retrieval Ceiling):**
| Metric | Value |
|--------|-------|
| Recall vs GT sent to LLM | 44.5% (235/528) |
| GT lost before LLM | 158 (23%) |
| GT lost by LLM | 293 (42.7%) |

### Experiment 2: Increased Top-K (Top-K = 100)

**Configuration Changes:**
- Max controls per LLM call: **100** (was 50)

**Retrieval Stage Results:**
| Metric | Value |
|--------|-------|
| GT above threshold (0.48) | 480 (93.8%) |
| GT in top-100 (sent to LLM) | 418 (81.6%) |
| GT lost at threshold | 32 |
| GT lost at top-K cap | 62 |

**LLM Stage Results:**
| Metric | Value |
|--------|-------|
| Predicted controls | 429 |
| True positives | 156 |
| False positives | 273 |
| False negatives | 356 |
| **Precision** | **36.4%** |
| **Recall** | **30.5%** |
| **F1** | **33.2%** |

**LLM Performance (Adjusted for Retrieval Ceiling):**
| Metric | Value |
|--------|-------|
| Recall vs GT sent to LLM | 37.3% (156/418) |
| GT lost before LLM | 94 (18.4%) |
| GT lost by LLM | 262 (51.2%) |

---

## 6. Comparative Analysis

### Side-by-Side Comparison

| Metric | Exp 1 (K=50) | Exp 2 (K=100) | Change |
|--------|--------------|---------------|--------|
| Retrieval Ceiling (Top-K Recall) | 77.0% | 81.6% | **+4.6%** |
| LLM Precision | 42.0% | 36.4% | **-5.6%** |
| LLM Recall | 34.3% | 30.5% | **-3.8%** |
| LLM F1 | 37.7% | 33.2% | **-4.5%** |
| LLM Recall vs Candidates Sent | 44.5% | 37.3% | **-7.2%** |
| GT Lost by LLM | 293 (42.7%) | 262 (51.2%) | **+8.5%** |

### Key Observations

#### 1. Retrieval Ceiling Improved

Increasing top-K from 50 to 100 improved the retrieval ceiling by 4.6% (77.0% → 81.6%). More ground truth controls were sent to the LLM.

#### 2. LLM Performance Degraded

Despite seeing more candidates, the LLM performed **worse** on all metrics:
- Precision dropped 5.6 percentage points
- Recall dropped 3.8 percentage points
- F1 dropped 4.5 percentage points

#### 3. Candidate Overload Hypothesis

The LLM's recall against candidates it was shown dropped from 44.5% to 37.3%. This suggests the LLM is:
- Overwhelmed by too many similar-looking controls
- Making more mistakes with larger candidate sets
- Unable to effectively discriminate among 100 candidates

#### 4. The Controls Added (50→100) Were Low-Quality

The additional 50 controls that ranked 51-100 were borderline matches that:
- Confused the model rather than helping it
- Added noise without adding signal
- May have pushed better candidates out of the LLM's attention

### What This Tells Us About System Performance

#### Retrieval Stage is Working Well

- 95%+ of GT controls pass the score threshold
- The embedding model is finding the right controls
- The bottleneck is the top-K cap, not the threshold

#### LLM is the Weak Link

- Even with candidates sent, the LLM only selects ~37-44% of GT controls
- Precision around 36-42% means many false positives
- The LLM struggles to distinguish between semantically similar controls

#### Trade-off Between Coverage and Accuracy

- More candidates = better retrieval ceiling but worse LLM accuracy
- Fewer candidates = lower retrieval ceiling but better LLM accuracy
- Sweet spot is likely 50-60 candidates, not 100

---

## 8. New Directions

Your task is to deeply understand the current system and its issues then brainstorm ideas for how we can improve this overall system. This is completely green field. Here is some brainstorming I've done:

- Is there some immediately obvious way to massive improve the existing system as it stands?
- We have the ability to dump the documents into a vanilla RAG system (PDF -> text blob, random chunking/overlap, no page numbers, hybrid search over the store). Can this somehow help?
- We could flip the LLM prompting where, instead of one to few pages and many controls, we upload the entire policy into the context cache and ask about single controls
- We could introduce an agentic retrieval approach that gives an agent tools to collect exactly which controls are relevant. It could start with the scored controls from colmodernvbert as a starting point. It could query the RAG store, load page images etc.
- Any other directions we should take? And why?

Your are welcome to come up with completely new directions or build on one or many of mine