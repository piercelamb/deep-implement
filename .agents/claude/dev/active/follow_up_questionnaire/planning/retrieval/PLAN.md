# Follow-up Questionnaire Retrieval Precedence

## Problem Statement

Follow-up questionnaire responses should take precedence over other evidence sources when assessing a criterion. The current pure semantic search may fail to surface follow-ups when questions are modified or answers are terse.

## Solution: Post-Retrieval Hash Extraction

Instead of separate searches or metadata filtering, we:
1. Expand first-stage retrieval to capture more results
2. Post-filter by criterion hash to extract linked follow-ups
3. Rerank only the non-follow-up results
4. Format follow-ups specially and append to the end of context

This approach is simple, requires no Vellum API changes, and guarantees follow-ups appear last in the LLM context window (recency bias).

---

## Implementation Spec

### Step 1: Compute Criterion Hash

Use the same hashing function from ingestion to compute the criterion question hash:

```python
from ai_services.shared.helpers.strings import normalize_and_hash

criterion_hash = normalize_and_hash(ctx.criterion_question)
```

This hash matches what's stored in `VellumFollowupResponse.criterion_question_hash` during indexing.

---

### Step 2: Expand First-Stage Retrieval

Change `TOP_FIRST_STAGE_N` from 70 to 100 to increase the chance of capturing follow-ups:

```python
TOP_FIRST_STAGE_N = 100  # Was 70
```

The search itself remains unchanged - single semantic search against the index.

---

### Step 3: Extract Hash-Matched Follow-ups

After parsing first-stage results, scan for follow-ups matching the criterion hash:

```python
from dataclasses import dataclass
from typing import Self

@dataclass(frozen=True, slots=True, kw_only=True)
class FollowupExtractionResult:
    """Result of extracting follow-up responses from first-stage retrieval."""

    matched: list[VellumFollowupResponse]  # Follow-ups matching the criterion hash
    remaining: list[VellumRetrievedContent]  # All other results for reranking

    @classmethod
    def from_first_stage_refs(
        cls,
        *,
        first_stage_refs: list[VellumRetrievedContent],
        criterion_hash: str,
        max_rounds: int = 3,
    ) -> Self:
        """
        Extract follow-up responses matching the criterion hash.

        Args:
            first_stage_refs: All results from first-stage retrieval.
            criterion_hash: Hash of the criterion question to match.
            max_rounds: Maximum number of follow-up rounds to retain.

        Returns:
            FollowupExtractionResult with matched follow-ups and remaining results.

        """
        matched: list[VellumFollowupResponse] = []
        remaining: list[VellumRetrievedContent] = []

        for ref in first_stage_refs:
            if isinstance(ref, VellumFollowupResponse):
                if ref.criterion_question_hash == criterion_hash:
                    matched.append(ref)
                else:
                    remaining.append(ref)
            else:
                remaining.append(ref)

        # If multiple matches, keep only the latest N rounds
        if len(matched) > max_rounds:
            # Sort by round_number descending, take top N
            matched = sorted(
                matched,
                key=lambda r: int(r.metadata.get("round_number", 0)),
                reverse=True,
            )[:max_rounds]

        return cls(matched=matched, remaining=remaining)
```

---

### Step 4: Rerank Remaining Results

Send only the remaining (non-matched) results to Cohere reranker, limited to top 70 by first_stage_score:

```python
# Extract follow-ups first
extraction = FollowupExtractionResult.from_first_stage_refs(
    first_stage_refs=first_stage_refs,
    criterion_hash=criterion_hash,
    max_rounds=MAX_FOLLOWUP_ROUNDS,
)

log.info(
    "Extracted follow-up responses",
    extra={
        "matched_count": len(extraction.matched),
        "remaining_count": len(extraction.remaining),
        "criterion_hash": criterion_hash,
    },
)

# Limit to top 70 by first_stage_score before reranking
to_rerank = sorted(
    extraction.remaining,
    key=lambda r: r.first_stage_score,
    reverse=True,
)[:TOP_TO_RERANK_N]

# Rerank only the top remaining results
top_reranked_refs = get_reranked_refs(
    reranker,
    ctx.criterion_question,
    to_rerank,
    reranked_ref_count=TOP_RERANKED_N,
    relevancy_cutoff=COHERE_SCORE_THRESHOLD,
)
```

---

### Step 5: Format Follow-ups for LLM Context

Follow-ups need special XML formatting:

**Single follow-up:** Standard XML format (same as other excerpts)

**Multiple follow-ups:** Combined into ONE `<index_N>` entry showing Q&A progression ordered by round number ascending

```python
def format_followup_responses_xml(
    followups: list[VellumFollowupResponse],
    start_index: int,
) -> str:
    """
    Format follow-up responses as XML for LLM context.

    Args:
        followups: List of matched follow-up responses
        start_index: The index number to use (e.g., 7 for <index_7>)

    Returns:
        XML string for insertion into evidence excerpts
    """
    if not followups:
        return ""

    if len(followups) == 1:
        # Single follow-up: standard format
        fu = followups[0]
        filename = fu.metadata.get("FILENAME", "Follow-up Response")
        return f"""<index_{start_index}>
<source>{filename}</source>
<content>
{fu.content}
</content>
</index_{start_index}>"""

    # Multiple follow-ups: combine into progression
    # Sort by round_number ascending for chronological order
    sorted_followups = sorted(
        followups,
        key=lambda r: int(r.metadata.get("round_number", 0)),
    )

    # Build progression content
    progression_parts = []
    for fu in sorted_followups:
        round_num = fu.metadata.get("round_number", "?")
        question = fu.item.question
        answer = fu.item.answer
        progression_parts.append(f"[Round {round_num}]\nQuestion: {question}\nAnswer: {answer}")

    progression_content = "\n\n".join(progression_parts)

    # Use filename from most recent (last in sorted list)
    filename = sorted_followups[-1].metadata.get("FILENAME", "Follow-up Responses")

    return f"""<index_{start_index}>
<source>{filename} (Multiple Rounds)</source>
<content>
{progression_content}
</content>
</index_{start_index}>"""
```

---

### Step 6: Append Follow-ups to End of XML

Follow-ups are always appended LAST to the evidence XML, ensuring they appear at the end of the LLM context window:

```python
# Convert reranked results to XML (indexes 1-6)
reranked_xml = vellum_doc_excerpts_to_xml(top_reranked_refs)

# Append follow-up XML (index 7 if we have 6 reranked results)
if extraction.matched:
    followup_xml = format_followup_responses_xml(
        extraction.matched,
        start_index=len(top_reranked_refs) + 1,
    )
    refs_str = reranked_xml + "\n" + followup_xml
else:
    refs_str = reranked_xml
```

---

## Flow Diagram

```
criterion_question
       │
       ├─────────────────────────────────────────────────────┐
       │                                                     │
       ▼                                                     ▼
┌─────────────────┐                                 ┌───────────────────┐
│ normalize_and_  │                                 │ Vellum Search     │
│ hash()          │                                 │ limit: 100        │
└────────┬────────┘                                 └─────────┬─────────┘
         │                                                    │
         │ criterion_hash                                     │ 100 results
         │                                                    │
         └──────────────────────┬─────────────────────────────┘
                                │
                                ▼
                   ┌────────────────────────┐
                   │ FollowupExtraction     │
                   │ Result.from_first_     │
                   │ stage_refs()           │
                   │                        │
                   │ - Match by hash        │
                   │ - Keep max 3 rounds    │
                   └───────────┬────────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
    ┌─────────────────┐               ┌─────────────────┐
    │ extraction      │               │ extraction      │
    │ .matched        │               │ .remaining      │
    │ (0-3 items)     │               │ (non-followups) │
    └────────┬────────┘               └────────┬────────┘
             │                                 │
             │                                 ▼
             │                        ┌─────────────────┐
             │                        │ Cohere Reranker │
             │                        │ → top 6         │
             │                        └────────┬────────┘
             │                                 │
             │                                 ▼
             │                        ┌─────────────────┐
             │                        │ vellum_doc_     │
             │                        │ excerpts_to_xml │
             │                        │ (indexes 1-6)   │
             │                        └────────┬────────┘
             │                                 │
             ▼                                 │
    ┌─────────────────┐                        │
    │ format_followup │                        │
    │ _responses_xml  │                        │
    │ (index 7)       │                        │
    └────────┬────────┘                        │
             │                                 │
             └─────────────┬───────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Combined XML    │
                  │                 │
                  │ <index_1>...</>  │
                  │ <index_2>...</>  │
                  │ ...              │
                  │ <index_6>...</>  │
                  │ <index_7>        │  ← Follow-ups LAST
                  │   (followups)   │
                  │ </index_7>      │
                  └─────────────────┘
```

---

## Why This Design

| Design Choice | Rationale |
|---------------|-----------|
| **Post-filter, not pre-filter** | No Vellum API changes needed; simple Python logic |
| **100 results first-stage** | Higher chance of capturing follow-ups even with semantic drift |
| **Extract before reranking** | Guarantees follow-ups aren't demoted by reranker |
| **Max 3 rounds** | Bounds context size; most recent rounds are most relevant |
| **Combined XML for multi-round** | Shows progression without wasting index slots |
| **Append to end** | LLM recency bias ensures follow-ups are prioritized |

---

## Constants

```python
# In retrieve_sources.py
TOP_FIRST_STAGE_N = 100  # Expanded from 70 to capture more follow-ups
TOP_TO_RERANK_N = 70     # Limit sent to reranker (original first-stage limit)
TOP_RERANKED_N = 6       # Unchanged
MAX_FOLLOWUP_ROUNDS = 3  # New: max rounds to include
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `ai_services/vellum/support/vrm_agent_q3_fy26/gather_evidence/run.py` | Add `FollowupExtractionResult` dataclass, `format_followup_responses_xml()` |
| `ai_services/vellum/workflows/vrm_agent_q3_fy26/gather_evidence/nodes/retrieve_sources.py` | Update `TOP_FIRST_STAGE_N`, integrate extraction and XML formatting |

---

## Testing Scenarios

| Scenario | Expected Behavior |
|----------|-------------------|
| No follow-ups in index | Reranked results only (indexes 1-6) |
| Single follow-up matches | Standard XML at index 7 |
| 3 follow-ups (rounds 1, 2, 3) | Combined progression at index 7 |
| 5 follow-ups (rounds 1-5) | Only rounds 3, 4, 5 kept; combined at index 7 |
| Follow-up with different hash | Treated as regular result, goes to reranker |
| Modified question (hash matches) | Still extracted; question_similarity_score available for logging |

---

## Implementation Checklist

- [ ] Add `FollowupExtractionResult` dataclass to `run.py`
- [ ] Add `format_followup_responses_xml()` to `run.py`
- [ ] Update `TOP_FIRST_STAGE_N` to 100 in `retrieve_sources.py`
- [ ] Add `MAX_FOLLOWUP_ROUNDS` constant
- [ ] Integrate extraction in `RetrieveSources.run()`
- [ ] Update XML concatenation logic
- [ ] Update `get_dynamic_structured_out()` to include follow-up index
- [ ] Write unit tests for `FollowupExtractionResult.from_first_stage_refs()`
- [ ] Write unit tests for `format_followup_responses_xml()`
- [ ] Integration test with mock follow-up data
