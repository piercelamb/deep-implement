# Plan: Send Individual Testable Criteria Results in Webhook

## Problem Statement

The `GatherAssessAndReviewCriterionQuestionsWorkflowV1` workflow:
1. Runs `gather_and_assess_activity` for each criterion question → produces `CriterionEvidence` per question
2. Reviews all evidence via `criteria_review_activity` → produces `ReviewedCriterion`
3. Uploads complete data to S3 via `to_s3_dto()` (includes everything)
4. Sends webhook via `to_assessment_webhook_dto()` (sends only aggregate data)

**Current webhook payload (`AssessmentWebhookDTO`):**
```python
status: EvidenceSupportTypes           # Overall criterion status
criteriaName: str                      # Criterion name
analysisSummary: str                   # Overall analysis
source: list[AssessmentSourceWebhookDTO]  # Flattened evidence excerpts (TO BE REMOVED)
```

**What's missing from webhook:** Individual testable criteria results (criterion questions) with their per-question assessment status, explanation, and linked evidence. The flat `source` list will be replaced with structured `testableCriteria`.

## Current Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│ For each criterion_question:                                            │
│   gather_and_assess_activity() → CriterionEvidence                      │
│     - criterion (question text)                                         │
│     - evidence_support_type (MET/NOT_MET/INCONCLUSIVE)                  │
│     - explain (LLM reasoning)                                           │
│     - summary                                                           │
│     - refs (VellumDocExcerpt list)                                      │
│     - reason (if inconclusive)                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ criteria_review_activity() → ReviewedCriterion                          │
│   - name, description                                                   │
│   - analysis_summary (overall)                                          │
│   - classification (overall status)                                     │
│   - testable_criteria: list[CriterionEvidence]  ← ALL question results  │
└─────────────────────────────────────────────────────────────────────────┘
                    │                               │
                    ▼                               ▼
         ┌──────────────────┐            ┌──────────────────────┐
         │ to_s3_dto()      │            │ to_assessment_       │
         │ (FULL DATA)      │            │ webhook_dto()        │
         │ ✓ testable_      │            │ (CURRENT: flat source│
         │   criteria       │            │  NEW: testableCriteria│
         └──────────────────┘            │  with nested sources)│
                                         └──────────────────────┘
```

## Proposed Solution

Replace the flat `source` list with `testableCriteria` containing individual question results and their specific evidence sources.

### New DTO Structures

**Add to `ai_services/shared/schema/dto.py`:**

```python
class TestableCriteriaWebhookDTO(TypedDict):
    """Individual testable criterion (question) result for webhook."""
    question: str                              # The criterion question text
    status: EvidenceSupportTypes               # MET/NOT_MET/INCONCLUSIVE
    explanation: str                           # LLM reasoning for this question
    source: list[AssessmentSourceWebhookDTO]   # Evidence excerpts for this question
```

**Update `AssessmentWebhookDTO`:**

```python
class AssessmentWebhookDTO(TypedDict):
    status: EvidenceSupportTypes
    criteriaName: str
    analysisSummary: str
    # REMOVED: source: list[AssessmentSourceWebhookDTO]  # No longer sent at top level
    testableCriteria: list[TestableCriteriaWebhookDTO]   # REPLACES source field
```

### Schema Changes

**Update `CriterionEvidence` in `ai_services/shared/schema/evidence/schema.py`:**

Add new method:
```python
def to_assessment_webhook_dto(self) -> TestableCriteriaWebhookDTO:
    """Serialize for webhook consumption."""
    return TestableCriteriaWebhookDTO(
        question=self.criterion,
        status=self.evidence_support_type,
        explanation=self.explain,
        source=[ref.to_assessment_webhook_dto() for ref in self.refs],
    )
```

**Update `ReviewedCriterion.to_assessment_webhook_dto()`:**

```python
def to_assessment_webhook_dto(self) -> AssessmentWebhookDTO:
    return AssessmentWebhookDTO(
        status=self.classification,
        criteriaName=self.name,
        analysisSummary=self.analysis_summary,
        # REMOVED: source field - now only sent within testableCriteria
        testableCriteria=[
            tc.to_assessment_webhook_dto()
            for tc in self.testable_criteria
        ],
    )
```

## Files to Modify

| File | Change |
|------|--------|
| `ai_services/shared/schema/dto.py` | Add `TestableCriteriaWebhookDTO`, update `AssessmentWebhookDTO` |
| `ai_services/shared/schema/evidence/schema.py` | Add `CriterionEvidence.to_assessment_webhook_dto()`, update `ReviewedCriterion.to_assessment_webhook_dto()` |
| Tests for schema | Add tests for new serialization methods |

## Implementation Steps

1. **Add `TestableCriteriaWebhookDTO`** to `dto.py`
2. **Update `AssessmentWebhookDTO`** to replace `source` with `testableCriteria` field
3. **Add `CriterionEvidence.to_assessment_webhook_dto()`** method
4. **Update `ReviewedCriterion.to_assessment_webhook_dto()`** to remove `source` and add `testableCriteria`
5. **Add/update tests** for the new serialization

## Considerations

### Backward Compatibility

**This is a breaking change.** The webhook payload will:
- Remove the `source` field at the top level
- Add a new `testableCriteria` field with sources nested within each criterion

The consuming API (Drata webapp) must be updated to handle this change. Coordinate with webapp team for synchronized deployment.

### Payload Size

Payload size should be similar or slightly smaller:
- Current: ~M excerpt objects in flat list
- New: ~M excerpt objects distributed across N question objects (same data, better structure)

No duplication since we're removing the top-level `source` field entirely.

## Testing Strategy

1. Unit tests for `CriterionEvidence.to_assessment_webhook_dto()`
2. Unit tests for updated `ReviewedCriterion.to_assessment_webhook_dto()`
3. Integration test verifying complete data flow from workflow to webhook payload

## Open Questions

1. **Field naming:** Should we use `testableCriteria` (camelCase for webhook consistency) or `testable_criteria` (snake_case for internal consistency)?
   - Recommendation: `testableCriteria` (camelCase) to match existing webhook DTO patterns (`criteriaName`, `analysisSummary`, `docExcerpt`)

2. **Should we include `linkedCriterion` ID in the webhook DTO?**
   - Currently excluded. May be useful for webapp to correlate. Recommend including it.
