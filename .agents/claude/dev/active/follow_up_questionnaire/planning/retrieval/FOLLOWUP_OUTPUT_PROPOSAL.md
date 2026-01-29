# Follow-up Response Output Proposal

## Problem Statement

Follow-up responses are retrieved and shown to the LLM, but **they are currently dropped** before being returned to the webapp. The data flow is:

1. `gather_and_assess_activity` retrieves evidence (including follow-ups)
2. LLM selects relevant indexes → `relevant_evidence: list[VellumRetrievedContent]`
3. **`convert_to_doc_excerpts()` explicitly skips `VellumFollowupResponse`**
4. `CriterionEvidence.refs` (typed as `Sequence[VellumDocExcerpt]`) receives only doc excerpts
5. Webhook sends `AssessmentSourceWebhookDTO` for each ref

Result: Follow-up responses that influenced the LLM's decision are **never reported to the webapp**.

---

## Current Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        gather_and_assess_activity                            │
│                                                                              │
│  VellumRetrievedContent[] ──► LLM selects indexes ──► relevant_evidence[]   │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           handle_outputs.py                                  │
│                                                                              │
│  convert_to_doc_excerpts(relevant_evidence)                                  │
│    ├─ VellumDocExcerpt ──────────► kept                                     │
│    ├─ VellumSOC2SummaryTrack ────► expanded to source_refs                  │
│    └─ VellumFollowupResponse ────► ❌ SKIPPED (DROPPED!)                    │
│                                                                              │
│  ──► CriterionEvidence.refs: Sequence[VellumDocExcerpt]                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ReviewedCriterion.to_assessment_webhook_dto()             │
│                                                                              │
│  for ref in evidenced_criterion.refs:                                        │
│      ref.to_assessment_webhook_dto() ──► AssessmentSourceWebhookDTO         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Webapp Expected Format

The webapp expects `AssessmentSourceWebhookDTO`:

```python
class AssessmentSourceWebhookDTO(TypedDict):
    docExcerpt: str      # The evidence content
    documentName: str    # Source filename
    fileId: str          # Unique identifier
    referencedOn: str    # ISO timestamp
```

**Key insight**: This format is generic enough to accommodate follow-up responses. We don't need webapp changes.

---

## Proposed Solution

### Step 1: Add `to_assessment_webhook_dto()` to `VellumFollowupResponse`

Location: `ai_services/shared/schema/questionnaire/schema.py`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class VellumFollowupResponse(VellumQuestionnaireContent):
    # ... existing fields ...

    def to_assessment_webhook_dto(self) -> AssessmentSourceWebhookDTO:
        """Convert to webhook DTO format for webapp consumption."""
        return AssessmentSourceWebhookDTO(
            docExcerpt=self.content,
            documentName=self.metadata.get("FILENAME", "Follow-up Response"),
            fileId=self.metadata["form_id"],  # Use form_id from indexed metadata
            referencedOn=datetime.now(UTC).isoformat(),
        )
```

The `fileId` uses `form_id` which is:
- Already indexed as metadata during `FollowupResponse.build_vellum_metadata()`
- The unique identifier for the follow-up questionnaire form in the webapp
- Consistent with how the webapp tracks follow-up questionnaire forms

---

### Step 2: Create Type Alias for Criterion Evidence Refs

Location: `ai_services/shared/schema/evidence/schema.py`

```python
# Ref types that can be stored in CriterionEvidence.refs
# Both implement to_assessment_webhook_dto() for webhook serialization
CriterionEvidenceRef = VellumDocExcerpt | VellumFollowupResponse
```

---

### Step 3: Update `CriterionEvidence.refs` Type

Location: `ai_services/shared/schema/evidence/schema.py`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class CriterionEvidence(LLMEvidence):
    refs: Sequence[CriterionEvidenceRef]  # Was: Sequence[VellumDocExcerpt]
    # ... rest unchanged ...
```

---

### Step 4: Create `convert_to_criterion_refs()` Function

Location: `ai_services/vellum/support/vrm_agent_q3_fy26/gather_evidence/run.py`

Replace the skipping behavior with proper conversion:

```python
def convert_to_criterion_refs(refs: list[VellumRetrievedContent]) -> list[CriterionEvidenceRef]:
    """
    Convert VellumRetrievedContent to types that can be serialized for webhook.

    - VellumDocExcerpt: kept as-is
    - VellumSOC2SummaryTrack: expanded to source_refs (underlying VellumDocExcerpts)
    - VellumFollowupResponse: kept as-is (has to_assessment_webhook_dto)

    Results are deduplicated by content_hash.
    """
    result: list[CriterionEvidenceRef] = []
    seen_hashes: set[str] = set()

    for ref in refs:
        if isinstance(ref, VellumSOC2SummaryTrack):
            # Expand SOC2 summaries to their source documents
            for source_ref in ref.source_refs:
                if source_ref.content_hash not in seen_hashes:
                    result.append(source_ref)
                    seen_hashes.add(source_ref.content_hash)
        elif isinstance(ref, (VellumDocExcerpt, VellumFollowupResponse)):
            if ref.content_hash not in seen_hashes:
                result.append(ref)
                seen_hashes.add(ref.content_hash)

    return result
```

---

### Step 5: Update `handle_outputs.py`

Change from `convert_to_doc_excerpts` to `convert_to_criterion_refs`:

```python
from ai_services.vellum.support.vrm_agent_q3_fy26.gather_evidence.run import (
    GatherEvidenceContext,
    convert_to_criterion_refs,  # Was: convert_to_doc_excerpts
)

# In run():
converted_refs = convert_to_criterion_refs(loaded_generation.relevant_evidence)
```

---

### Step 6: Update `ReviewedCriterion.to_assessment_webhook_dto()`

The iteration already works because both types implement `to_assessment_webhook_dto()`:

```python
def to_assessment_webhook_dto(self) -> AssessmentWebhookDTO:
    return AssessmentWebhookDTO(
        status=self.classification,
        criteriaName=self.name,
        analysisSummary=self.analysis_summary,
        source=[
            ref.to_assessment_webhook_dto()  # Works for both types
            for evidenced_criterion in self.testable_criteria
            for ref in evidenced_criterion.refs
        ],
    )
```

---

## Why This Design

| Decision | Rationale |
|----------|-----------|
| **Add method to VellumFollowupResponse** | Duck typing - both types implement same interface |
| **Use `form_id` for `fileId`** | Already indexed, webapp knows this ID, consistent tracking |
| **Type alias `CriterionEvidenceRef`** | Clear relationship to `CriterionEvidence.refs`, avoids conflict with `EvidenceRefDTO` |
| **Keep `convert_to_doc_excerpts`** | May be needed elsewhere; create new function instead |
| **No webapp changes needed** | Existing DTO format is generic enough |

---

## Files to Modify

| File | Changes |
|------|---------|
| `ai_services/shared/schema/questionnaire/schema.py` | Add `to_assessment_webhook_dto()` to `VellumFollowupResponse` |
| `ai_services/shared/schema/evidence/schema.py` | Add `CriterionEvidenceRef` type alias, update `CriterionEvidence.refs` type |
| `ai_services/vellum/support/vrm_agent_q3_fy26/gather_evidence/run.py` | Add `convert_to_criterion_refs()` function |
| `ai_services/vellum/workflows/vrm_agent_q3_fy26/gather_evidence/nodes/handle_outputs.py` | Use new conversion function |
| `ai_services/shared/schema/dto.py` | Update `EvidenceAssessmentResultDTO.refs` type if needed |

---

## Example Webhook Output

Before (follow-up dropped):
```json
{
  "source": [
    {"docExcerpt": "...", "documentName": "policy.pdf", "fileId": "123", ...}
  ]
}
```

After (follow-up included):
```json
{
  "source": [
    {"docExcerpt": "...", "documentName": "policy.pdf", "fileId": "123", ...},
    {"docExcerpt": "Question: Does the vendor...? Answer: Yes, we...",
     "documentName": "Followup_Response_Round_1.pdf",
     "fileId": "550e8400-e29b-41d4-a716-446655440000", ...}
  ]
}
```

---

## Testing Plan

1. Unit test `VellumFollowupResponse.to_assessment_webhook_dto()` - verify `form_id` is used
2. Unit test `convert_to_criterion_refs()` with mixed input types
3. Integration test: verify follow-up appears in final webhook payload

---

## Open Questions

1. **Backward compatibility**: Should we version the workflow or is this a safe change?
2. **Deduplication**: Should follow-ups be deduplicated separately from docs, or mixed?
