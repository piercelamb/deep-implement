# Control-Centric Design Decisions

## Overview

This document explains the key design decisions made during the control-centric implementation, including rationale and trade-offs considered.

## 1. Coherent vs Diverse Batching

### Decision: Default to Coherent Batching

**What it means:**
- Controls from the same cluster are grouped together in batches
- Similar controls are evaluated side-by-side

**Rationale (from Gemini 3 analysis):**
- When asking binary yes/no per control, having similar controls together helps differentiation
- LLM can focus attention on one section of text (e.g., Access Control chapter)
- Enables side-by-side comparison: "Paragraph 3 matches Control A but NOT Control B because..."

**Alternative considered: Diverse Batching**
- Spread dissimilar controls across batches
- Original hypothesis: reduces context-switching overhead
- Rejected because it doesn't leverage LLM's comparison capabilities

**Implementation:**
- Coherent is the default (`--batch-strategy coherent`)
- Diverse batching is parsed but raises `NotImplementedError`
- Can be implemented later if needed for comparison

## 2. Evidence Requirements

### Decision: Require Exact Quotes

**What it means:**
- LLM must quote the specific text serving as evidence
- `evidence_quote` field is required in response schema

**Rationale:**
- Enables human verification of LLM decisions
- Reduces hallucination risk
- Provides audit trail for compliance

**Trade-off:**
- Slightly longer response times
- More tokens in output
- Worth it for interpretability

## 3. Retrieval Anchors

### Decision: Include Top 3 Pages per Control

**What it means:**
- Each control in the prompt includes `<retrieval_hints>` with:
  - Top 3 pages where ColModernVBERT scored highest
  - Best score for reference

**Rationale (from ChatGPT analysis):**
- Guides LLM to most relevant sections first
- Reduces search time in large documents
- Leverages existing embedding model investment

**Example in prompt:**
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

**Trade-off:**
- Slight bias toward suggested pages
- Mitigated by instruction: "evidence found elsewhere is valid"

## 4. Score Threshold (0.48)

### Decision: Use 0.48 as Candidate Filter

**What it means:**
- Only controls with doc-max score ≥ 0.48 are sent to LLM
- Typically filters ~30% of controls

**Rationale (from threshold analysis):**
- 0.48 achieves ~92% recall of ground truth controls
- Meaningful candidate reduction (32% filtered)
- Balance between coverage and efficiency

**Analysis results:**
| Threshold | Recall | Candidates Passing |
|-----------|--------|-------------------|
| 0.44 | 100% | 746/779 (4% filtered) |
| 0.48 | ~92% | 530/779 (32% filtered) |
| 0.50 | ~76% | 360/779 (54% filtered) |

**Trade-off:**
- ~8% of GT controls filtered out
- These are typically compliance-associated controls with weak semantic relationship

## 5. Budget Enforcement (50 Calls Max)

### Decision: Hard Cap at 50 LLM Calls per Document

**What it means:**
- Never exceed 50 API calls per document
- Batches are sized to fit within budget

**Rationale:**
- Predictable costs
- Prevents runaway API usage
- Forces efficient batching

**Budget calculation:**
```
max_controls = max_calls × target_batch_size
            = 50 × 8
            = 400 controls per document
```

**What happens if exceeded:**
- Batch size increases to fit all candidates
- Lower-scoring candidates may be grouped into larger batches
- Logged as warning

## 6. Cluster Configuration

### Decision: 75 K-means Clusters

**What it means:**
- 779 DCF controls grouped into 75 clusters
- ~10 controls per cluster on average

**Rationale:**
- Matches well with target batch size (8)
- Provides meaningful semantic grouping
- Not so many that clusters become singleton

**Clustering method:**
- Mean-pooled ColModernVBERT token embeddings
- K-means with random_state=42 for reproducibility
- Stored in `control_clusters.json`

## 7. Cache Lifecycle Management

### Decision: Upload Once, Delete on Completion

**What it means:**
- PDF uploaded to Gemini cache at start
- Cache used for all batch queries
- Cache deleted immediately after (even on error)

**Rationale:**
- Cache has time-limited billing
- Prevents orphaned caches
- `asyncio.shield()` ensures cleanup even on cancellation

**Implementation:**
```python
try:
    cache_name = await self._upload_document_cache(pdf_bytes, policy_name)
    # ... process batches ...
finally:
    await self._delete_cache(cache_name)  # Shielded
```

## 8. Location Reference vs Page Numbers

### Decision: Use `location_reference: string` Instead of `page_numbers: int[]`

**What it means:**
- LLM reports location as free-form string
- Can include section headers, not just page numbers

**Rationale (from Gemini 3 analysis):**
- Avoids hallucinated page numbers
- Allows more descriptive references: "Section 4.2 - Access Control"
- More useful for human reviewers

**Examples:**
- "Page 12"
- "Section 4.2 - Access Control"
- "Page 12, Section 4.2"
- "Appendix A - Security Policies"

## 9. Binding Language Definition

### Decision: Broaden to Include Declarative Statements

**What it means:**
- Accept both explicit mandates and declarative policy statements
- BUT only in policy/requirements sections

**Valid binding language:**
- Explicit mandates: "must", "shall", "required"
- Declarative statements: "Passwords are 12 characters"
- Responsibility assignments: "The CISO reviews logs"

**Not binding:**
- "Should", "recommended", "best practice"
- Future plans: "We aim to..."
- Definitions without mandates
- Background/context sections

**Rationale (from Gemini 3 + ChatGPT):**
- Pure "must/shall" is too restrictive for real policies
- Many policies use declarative statements as requirements
- Context matters: same sentence in different sections has different meaning

## 10. Parallel Processing with Semaphore

### Decision: 10 Concurrent API Calls

**What it means:**
- Up to 10 batch queries run simultaneously
- Additional batches wait in queue

**Rationale:**
- Balances throughput vs rate limits
- Gemini Flash has generous rate limits
- 10 is conservative; could increase if needed

**Implementation:**
```python
async with self._get_semaphore():  # Semaphore(10)
    response = await self._call_gemini(cache_name, user_prompt)
```

## 11. Retry Policy

### Decision: Exponential Backoff with Jitter

**What it means:**
- Retry on ResourceExhausted (429) and DeadlineExceeded
- Wait increases exponentially: 1s, 2s, 4s, 8s...
- Random jitter prevents thundering herd
- Max 5 attempts

**Rationale (from ChatGPT):**
- Rate limits are temporary; retrying works
- Jitter prevents synchronized retries from multiple batches
- 5 attempts is usually sufficient

**Implementation:**
```python
@retry(
    retry=retry_if_exception_type((ResourceExhausted, DeadlineExceeded)),
    wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def _call_gemini(...):
    ...
```

## Summary of Trade-offs

| Decision | Benefit | Trade-off |
|----------|---------|-----------|
| Coherent batching | Better differentiation | May miss cross-section matches |
| Evidence quotes | Audit trail | More output tokens |
| Retrieval anchors | Faster search | Slight page bias |
| 0.48 threshold | 32% reduction | ~8% recall loss |
| 50 call budget | Predictable cost | May truncate candidates |
| 75 clusters | Meaningful groups | Fixed granularity |
| Delete cache immediately | No orphans | Re-upload if needed |
| Free-form location | Flexible | Less structured |
| Broad binding language | More matches | Some false positives |
| 10 concurrent | Good throughput | Not maximal |
| Retry with jitter | Handles rate limits | Adds latency |
