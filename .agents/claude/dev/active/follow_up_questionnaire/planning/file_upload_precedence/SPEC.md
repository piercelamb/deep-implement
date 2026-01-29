# Follow-up Document Precedence: Conservative Score Boosting

## Problem Statement

VRM Agent allows users to add ad-hoc file upload questions to follow-up questionnaires (e.g., "Please upload your data retention policy"). These uploaded documents are indexed into the same vectorDB namespace as originally uploaded vendor documents.

Unlike text-based follow-up answers, these file uploads:
- Have **no linked criterion_question** (they're ad-hoc additions, not automatic follow-ups from NOT_MET/INCONCLUSIVE results)
- Could be relevant to **any/many criterion_questions**
- Should receive **precedence over original documents** when semantically relevant

## Approach: Conservative Score Boosting

Let semantic similarity determine relevance, but give follow-up document chunks a slight edge when scores are close. This ensures:
- Follow-up documents don't dominate when irrelevant
- Follow-up documents win tiebreakers when equally relevant
- No wasted context on irrelevant follow-up content

## Existing `type` Metadata Field

Documents in the vectorDB namespace already use a `type` metadata field:

| Document Source | `type` Value |
|----------------|--------------|
| Regular vendor documents | `"tc_files"` |
| Follow-up text responses | `"followup_response:{round}"` (e.g., `"followup_response:1"`) |
| SOC2 summary tracks | `"soc2_summary:{track}"` (e.g., `"soc2_summary:overview"`) |
| **Follow-up file uploads** | `"followup_document"` **(NEW)** |

## Design

### 1. Metadata Tagging at Index Time

When documents are uploaded via follow-up questionnaire file upload questions, the Drata backend must pass this metadata when calling the `create_document` API:

```python
{
    "type": "followup_document"
}
```

This is the **only** metadata field needed to identify follow-up document chunks for boosting.

**Implementation location:** Drata backend service when calling `POST /api/v1/vectordb/index/{index_id}/document` for follow-up file uploads.

### 2. Score Boosting After Reranking

Modify the retrieval flow to apply a boost multiplier to follow-up document chunks after Cohere reranking but before final top_k selection.

**Current flow** (`retrieve_sources.py` / `run.py`):
```
Vellum search (70 results)
    → First-stage filtering (dedup, score threshold)
    → Cohere rerank
    → Take top 6
```

**New flow:**
```
Vellum search (70 results)
    → First-stage filtering (dedup, score threshold)
    → Cohere rerank
    → Apply follow-up document boost    <-- NEW
    → Take top 6
```

### 3. Boost Implementation

```python
# New constants in retrieve_sources.py
FOLLOWUP_DOCUMENT_BOOST = 1.15  # 15% score boost for follow-up documents

def apply_followup_boost(
    refs: list[VellumRetrievedContent],
) -> list[VellumRetrievedContent]:
    """
    Apply score boost to follow-up document chunks.

    Conservative approach: small boost lets relevance win,
    but gives follow-up docs an edge in tiebreakers.
    """
    boosted = []
    for ref in refs:
        if ref.metadata.get("type") == "followup_document":
            # Create new ref with boosted score
            boosted_score = ref.score * FOLLOWUP_DOCUMENT_BOOST
            boosted.append(ref.with_score(boosted_score))
        else:
            boosted.append(ref)

    # Re-sort by boosted scores
    return sorted(boosted, key=lambda r: r.score, reverse=True)
```

### 4. Integration Point

In `run.py`, modify `get_reranked_refs()` or add a post-processing step:

```python
def get_reranked_refs(
    ranker: BaseClient | None,
    query: str,
    first_stage_refs: list[VellumRetrievedContent],
    *,
    reranked_ref_count: int,
    relevancy_cutoff: float,
) -> list[VellumRetrievedContent]:
    # Existing reranking logic...
    reranked = cohere_rerank(ranker, query, first_stage_refs)

    # NEW: Apply follow-up document boost
    boosted = apply_followup_boost(reranked)

    # Take top N after boosting
    return [r for r in boosted[:reranked_ref_count] if r.score >= relevancy_cutoff]
```

## Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `FOLLOWUP_DOCUMENT_BOOST` | 1.15 | Conservative 15% boost. A follow-up doc at 0.7 becomes 0.805, beating an original doc at 0.8 only if very close. |
| `type` metadata value | `"followup_document"` | Consistent with existing `type` field pattern; distinct from `"tc_files"` (regular docs) and `"followup_response:{round}"` (text answers) |

### Tuning Considerations

- **Start conservative** (1.15) and increase if follow-up docs aren't getting enough precedence
- **Monitor** cases where follow-up docs should have won but didn't
- **Cap boost** to prevent irrelevant follow-up docs from dominating (e.g., max boosted score = 1.0)

## Edge Cases

### 1. Follow-up document not in first-stage results
- **Behavior:** No boost applied (document wasn't relevant enough to appear in top 70)
- **Acceptable:** If it's not in top 70, it's likely not relevant to this criterion

### 2. Multiple follow-up documents from different rounds
- **Behavior:** All get the same boost
- **Alternative:** Could boost by recency (round 2 > round 1), but adds complexity
- **Recommendation:** Start with uniform boost, add recency weighting if needed

### 3. Large follow-up document floods results
- **Behavior:** Multiple chunks from same doc may appear, all boosted
- **Mitigation:** Existing deduplication by `content_hash` helps; could add per-document chunk limit
- **Recommendation:** Monitor, add limit if problematic

### 4. Follow-up document with very low base score
- **Behavior:** 0.3 * 1.15 = 0.345, still below 0.5 original doc
- **Acceptable:** This is the desired conservative behavior

## Testing Strategy

### Unit Tests
1. `apply_followup_boost` correctly identifies and boosts `type: "followup_document"` chunks
2. Boosted list is re-sorted correctly
3. Non-follow-up docs unchanged (`type: "tc_files"`, etc.)
4. Edge case: empty list, all follow-up, no follow-up

### Integration Tests
1. End-to-end retrieval with follow-up document in namespace
2. Follow-up doc beats original doc when scores are close
3. Original doc wins when significantly more relevant

### Manual Validation
1. Run assessment on vendor with follow-up documents
2. Verify follow-up doc chunks appear when relevant
3. Verify irrelevant follow-up docs don't dominate

## Implementation Steps

### ai-services (this repo)
1. **Retrieval boost:** Implement `apply_followup_boost` in `run.py`
2. **Integration:** Wire boost into `get_reranked_refs`
3. **Tests:** Unit and integration tests
4. **Monitoring:** Log when boost changes result ordering

### Drata backend (separate repo)
1. **Index-time tagging:** When calling `create_document` for follow-up file uploads, pass `metadata: {"type": "followup_document"}`

## Out of Scope

- Boosting based on which follow-up question prompted the upload (no criterion linkage exists)
- Recency-based weighting between follow-up rounds
- Dynamic boost factors based on assessment state
- Separate namespace for follow-up documents

## Open Questions

1. **Boost factor tuning:** Should we start at 1.15 or run experiments to find optimal value?

2. **Score capping:** Should we cap boosted scores at 1.0 to prevent any single chunk from being guaranteed inclusion?
