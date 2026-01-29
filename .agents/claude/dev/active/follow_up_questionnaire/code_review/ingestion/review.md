# Code Review: Follow-up Questionnaire Ingestion

**Reviewer**: Senior Dev (Critical Mode)
**Date**: 2026-01-12
**Verdict**: NEEDS WORK - Several issues that could bite us in production

---

## Critical Issues

### 1. Empty Responses Not Validated at API Layer

`vrm_router.py:117-125`

```python
responses=[
    FollowupQuestionnaireItem(
        criterion_question_text=resp.criterion_question_text,
        question=resp.question_text,
        answer=resp.answer_text,
        notes=resp.notes,
    )
    for resp in body.responses
]
```

**Problem**: No validation that `question_text` or `answer_text` are non-empty strings. A request with `{"questionText": "", "answerText": ""}` would pass validation and get indexed to Vellum as garbage.

**Fix**: Add `min_length=1` validators on `FollowupQuestionnaireResponseInput` fields:
```python
question_text: str = Field(..., alias="questionText", min_length=1)
answer_text: str = Field(..., alias="answerText", min_length=1)
```

### 2. Hash Collision Risk in External ID

`schema.py:213`

```python
return f"{assessment_id}--{self.DOC_TYPE}--{self.content_hash}--{round_number}"
```

The `content_hash` is only 16 hex characters (64 bits). For a single assessment with many follow-up rounds, birthday paradox says you hit 50% collision probability at ~2^32 items. Probably fine for real usage, but:

**Problem**: If two responses have same `criterion_question_text || question_text` (normalized), they get the same external_id. The second one silently OVERWRITES the first in Vellum with no warning to the caller.

**Missing edge case**: What if the vendor submits the same question twice with different answers in the same batch? Both get the same hash, same external_id, and one is silently lost.

**Suggested Fix**: At minimum, log a warning when duplicates are detected in the same batch. Better: fail the request if duplicate hashes exist within a batch.

### 3. Workflow ID Collision Across Tenants

`vrm_router.py:103`

```python
workflow_id = f"followup-questionnaire-index-{body.tenant_id}-{body.job_id}"
```

**Problem**: If `job_id` is generated client-side, a malicious or buggy client could reuse the same `job_id` for different assessments. This would silently skip the workflow due to Temporal's workflow ID deduplication.

**Missing**: `assessment_id` should be in the workflow ID since that's the unique key for this data:
```python
workflow_id = f"followup-questionnaire-index-{body.assessment_id}-{body.job_id}"
```

### 4. Child Workflow ID Missing Assessment ID

`index_followup_questionnaire_workflow_v1.py:170`

```python
def make_workflow_id(response: FollowupResponse) -> str:
    return f"index-followup-response-{input.job_id}-{response.content_hash}-{input.round_number}"
```

**Problem**: Same issue. If the same `job_id` is reused across assessments (intentionally or not), child workflows could collide. Should be:
```python
return f"index-followup-response-{input.assessment_id}-{response.content_hash}-{input.round_number}"
```

### 5. No Idempotency Handling for Re-indexing

`index_followup_response_workflow_v1.py:170-177`

```python
if existing_document.exists:
    workflow.logger.warning(
        "Followup response already exists, upserting",
        ...
    )
```

**Problem**: We log a warning and continue with upsert, but we don't check if the content is actually different. If someone re-submits the same questionnaire, we:
1. Send a SUCCESS webhook (first time)
2. Re-upload identical content
3. Re-poll until indexed
4. Send ANOTHER SUCCESS webhook

The caller has no way to know if this was a no-op or a real update. At minimum, we should compare content hashes and skip if identical.

### 6. Unused `datetime` Import

`vrm.py:1`

```python
from datetime import datetime
```

This import is used, but `submitted_at` is typed as `datetime | None` while being serialized to ISO string. The router converts it:

```python
submitted_at=body.submitted_at.isoformat() if body.submitted_at else "",
```

**Problem**: Empty string for missing timestamp is weird. Downstream code has to handle both `None` and `""`. Pick one:
- Use `None` throughout (change workflow input type to `str | None`)
- Or require the field (no default)

---

## Medium Issues

### 7. Missing Workflow Tests

There are NO tests for:
- `IndexFollowupQuestionnaireWorkflowV1`
- `IndexFollowupResponseWorkflowV1`
- `send_followup_questionnaire_webhook` activity

The only tests are for schema classes. For something going to production, we need at minimum:
- Happy path workflow test
- Error handling test (webhook failure)
- Duplicate detection test

### 8. Fire-and-Forget Without Completion Tracking

The parent workflow returns after starting child workflows but before they complete. The initial webhook sends `pending_external_ids`, but there's no mechanism for the caller to know when ALL responses are indexed.

**Missing**: A "batch complete" webhook when all child workflows finish. Otherwise the caller has to track `total_count` separate per-response webhooks and correlate them.

### 9. Inconsistent Error Handling

`index_followup_response_workflow_v1.py:221-247`

```python
if poll_result.status == VectorDbDocumentStatus.PROCESSED:
    await self._send_webhook(input, external_id=external_id, status=WebhookStatus.SUCCESS)
else:
    workflow.logger.error(...)
    await self._send_webhook(
        input,
        external_id=external_id,
        status=WebhookStatus.FAILURE,
        error_message=f"Response failed to index: {poll_result.status.value}",
    )
```

**Problem**: When indexing fails, we:
1. Send a FAILURE webhook
2. Don't raise an exception
3. Workflow completes "successfully"

This is inconsistent with the TEMPORAL_ERRORS catch block which sends a webhook AND re-raises. Non-PROCESSED status should probably also raise after sending webhook so the workflow is marked as failed in Temporal.

### 10. Hardcoded Poll Config

`index_followup_response_workflow_v1.py:212`

```python
poll_config = DocumentIndexingPollConfig()
```

Using defaults everywhere. If Vellum indexing slows down, every deployment needs a code change. Should be configurable via settings or workflow input.

---

## Minor Issues

### 11. Seed Script Hardcoded Values

`seed_followup_response_index.py` has hardcoded tenant/vendor IDs. Fine for a dev script, but it's going to confuse someone eventually. Add a docstring warning or make them CLI args.

### 12. Type Annotation `log_extra: dict`

`index_followup_response_workflow_v1.py:155`

```python
async def _run_indexing(
    self,
    input: IndexFollowupResponseWorkflowInputV1,
    external_id: str,
    log_extra: dict,  # <- should be dict[str, Any]
) -> None:
```

Bare `dict` type annotation. Should be `dict[str, Any]` for consistency with rest of codebase.

### 13. Magic String "followup_response:"

`schema.py:114`

```python
TYPE_PREFIX = "followup_response:"
```

This prefix appears in metadata and is used for filtering. If someone changes it, existing indexed documents become unfindable. Should have a comment or be in a constants module.

### 14. Missing `__init__.py` Export

New files added:
- `send_followup_questionnaire_webhook_activity.py`
- `index_followup_questionnaire_workflow_v1.py`
- `index_followup_response_workflow_v1.py`

None are exported from their package `__init__.py`. Probably fine since they're registered directly, but inconsistent with other modules.

---

## Questions for Author

1. **Why fire-and-forget?** What's the product requirement driving this pattern vs waiting for all responses to index?

2. **Webhook retry behavior**: If the per-response webhook fails, does the workflow retry forever? What's the DLQ story?

3. **Round number collisions**: What happens if someone calls this twice with round_number=1 for the same assessment? Same external_ids, silent overwrites?

4. **Vellum rate limits**: With fire-and-forget child workflows, could we accidentally DDoS Vellum by submitting 1000 responses at once?

---

## Summary

The core logic is sound but there are several edge cases that will cause silent data loss or confusing behavior:
- Duplicate responses in same batch
- Empty question/answer strings
- Re-submission of same questionnaire
- Workflow ID collisions

Recommend addressing Critical Issues 1-5 before merge. Medium issues can be follow-up tickets.
