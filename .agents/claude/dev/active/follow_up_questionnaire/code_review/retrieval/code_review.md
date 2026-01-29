# Code Review: Follow-up Questionnaire Retrieval Implementation

**Reviewer**: Senior Engineer (skeptical)
**Date**: 2026-01-20
**Verdict**: NEEDS WORK - This has too many rough edges for production

---

## Critical Issues

### 1. Duplicate Regex and Logic Between FollowupResponse and VellumFollowupResponse

We now have TWO classes that parse the same external_id format:

```python
# questionnaire/schema.py - FollowupResponse (no regex, builds external_id)
def build_external_id(self, assessment_id: str, round_number: int) -> str:
    return f"{assessment_id}--{self.DOC_TYPE}--{self.criterion_content_hash}--{round_number}"

# evidence/schema.py - VellumFollowupResponse (regex to parse)
external_id_re = re.compile(...)
```

Why do we need two separate classes for what is essentially the same entity at different lifecycle stages? This is a code smell. When the external_id format changes, we need to update BOTH places.

**Fix**: Either unify into one class with different constructors, or extract the external_id logic into a shared utility.

---

### 2. Naming Inconsistency: content_hash vs criterion_content_hash

```python
# FollowupResponse (questionnaire/schema.py)
criterion_content_hash: str  # Renamed from content_hash

# VellumFollowupResponse (evidence/schema.py)
criterion_content_hash: str  # Also uses this name
content_hash: str  # ALSO has this - inherited from SourcedContent!
```

So `VellumFollowupResponse` has BOTH `content_hash` (from SourcedContent, hash of the embedded text) AND `criterion_content_hash` (hash of criterion_question+question for the external_id). This is confusing as hell.

The DTO serializes `criterion_content_hash` but inherits `content_hash` from SourcedContent. A reader will be confused about which hash does what.

**Fix**: Better documentation, or rename one of them to be clearer (e.g., `external_id_hash` vs `text_hash`).

---

### 3. KeyError Waiting to Happen in to_assessment_webhook_dto

```python
def to_assessment_webhook_dto(self) -> AssessmentSourceWebhookDTO:
    return AssessmentSourceWebhookDTO(
        docExcerpt=self.content,
        documentName=self.metadata.get("FILENAME", "Follow-up Response"),
        fileId=self.metadata["form_id"],  # <-- KEYERROR IF MISSING
        referencedOn=datetime.now(UTC).isoformat(),
    )
```

`form_id` access will raise `KeyError` if the metadata doesn't have it. The test only covers the happy path.

**Fix**: Add defensive `.get()` with default, or add test for missing `form_id`.

---

### 4. Untestable datetime.now() in Production Code

```python
referencedOn=datetime.now(UTC).isoformat(),
```

This is not testable. The test just checks `"referencedOn" in dto` without validating the value. If someone breaks this, we won't catch it.

**Fix**: Inject a clock or make the timestamp a parameter.

---

### 5. FollowupExtractionResult.max_rounds Loses Ordering

```python
if len(matched) > max_rounds:
    matched = sorted(
        matched,
        key=lambda r: int(r.metadata.get("round_number", 0)),
        reverse=True,
    )[:max_rounds]  # Takes LATEST rounds, but they're now in REVERSE order
```

After this, `matched` is in descending round order. Then in retrieve_sources.py:

```python
sorted_followups = sorted(
    extraction.matched,
    key=lambda r: int(r.metadata["round_number"]),
)  # Re-sorts ascending
```

We sort, then re-sort. Also note the first sort uses `.get("round_number", 0)` but the second uses `["round_number"]` without default. If `round_number` is missing in metadata, the second one will raise KeyError.

**Fix**: Consistent metadata access pattern. Document the expected order.

---

### 6. No DTO Round-Trip Test for VellumFollowupResponse

There's `to_dto()` and `from_dto()` on `VellumFollowupResponse`, but no test that serializes then deserializes and verifies equality. This is basic stuff.

```python
# Missing test:
def test_dto_roundtrip(self) -> None:
    original = VellumFollowupResponse(...)
    dto = original.to_dto()
    restored = VellumFollowupResponse.from_dto(dto)
    assert restored == original  # Probably won't work because of float precision
```

---

### 7. Type Mismatch Between DTO and Class

```python
# DTO (dto.py)
class VellumFollowupResponseRefDTO(TypedDict):
    metadata: dict[str, str | None]

# Class (evidence/schema.py)
class VellumFollowupResponse:
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

The DTO says `str | None` values, but the class accepts `Any`. And `to_dto()` does:

```python
metadata=dict(self.metadata),  # Just copies whatever is there
```

If `self.metadata` has non-string values (which `from_vellum_search_res` allows since it passes the raw metadata dict), then `to_dto()` produces an invalid DTO.

---

### 8. Debug Code Left in Production

```python
# retrieve_sources.py lines 303-306
# print(GatherAndAssessEvidence.prompt_str(context={
#     "CRITERION": ctx.criterion_question,
#     "EVIDENCE": refs_str,
#     "CURRENT_DATE": current_date,
# }))
# exit(1)
```

Commented-out debug code in production. At least mark it with a TODO or delete it.

---

### 9. Evidence Priority Not Enforced in Code

The prompt says:
```
1. Follow-up Response (most recent, direct vendor attestation)
2. SOC2 Summary (audited, structured content)
3. Document (raw source material)
```

But the code just appends follow-ups at the end:
```python
all_excerpts = top_reranked_refs + sorted_followups
```

The LLM is told to prioritize follow-ups, but they appear LAST in the context. Research shows LLMs have recency bias - items at the end get more attention. Is this intentional? If so, document it. If not, fix it.

---

### 10. Backwards Compatibility is Fragile

Adding `ref_type` to `EvidenceRefDTO`:
```python
class EvidenceRefDTO(TypedDict):
    ref_type: str  # NEW - Discriminator: "doc_excerpt"
```

Old serialized data won't have this field. The deserialization handles it:
```python
ref_type = d.get("ref_type", "doc_excerpt")
```

But `TypedDict` says `ref_type` is required. Type checker thinks it's always there, but it's not for old data. This is lying to the type system.

**Fix**: Make it `NotRequired[str]` or use a separate DTO version.

---

### 11. No Integration Test for Webhook Payload

We test individual pieces but there's no test that:
1. Creates a `CriterionEvidence` with mixed `VellumDocExcerpt` and `VellumFollowupResponse` refs
2. Calls `to_assessment_webhook_dto()` on the `ReviewedCriterion`
3. Verifies the resulting JSON matches what the webapp expects

The webapp will break if this format is wrong, and we have no automated way to catch it.

---

### 12. Magic Numbers Without Context

```python
TOP_FIRST_STAGE_N = 100  # Expanded from 70 to increase chance of capturing follow-ups
TOP_TO_RERANK_N = 70  # Limit results sent to reranker (original first-stage limit)
TOP_RERANKED_N = 6  # Intuition based on research about how the number of documents effects LLM accuracy
MAX_FOLLOWUP_ROUNDS = 3  # Max follow-up rounds to include in context
```

Why 100? Why 70? Why 6? Why 3? The comments don't explain the reasoning. "Intuition based on research" - link to the research or remove the comment.

Also: we fetch 100 items but only rerank 70. We're paying for 30 items we throw away. Why?

---

## Medium Issues

### 13. Inconsistent Handling of Ad-hoc Questions

Ad-hoc questions (no criterion_question_text) have:
- `criterion_question_hash = None`
- `original_criterion_question_text = ""`

But the extraction logic filters by criterion_hash:
```python
if ref.criterion_question_hash == criterion_hash:
    matched.append(ref)
```

Ad-hoc questions have `criterion_question_hash = None`, so they'll never match and always go to `remaining`. Is this intentional? If ad-hoc questions are relevant to the criterion, they won't be prioritized.

---

### 14. No Metrics or Logging for Follow-up Retrieval Success

We log that we extracted follow-ups:
```python
log.info(
    "Extracted follow-up responses",
    extra={
        "matched_count": len(extraction.matched),
        "remaining_count": len(extraction.remaining),
        "criterion_hash": criterion_hash,
    },
)
```

But we don't track:
- How often do follow-ups actually get used by the LLM?
- How often is the evidence support type MET because of follow-up data?
- What's the correlation between follow-up presence and classification accuracy?

Without metrics, we can't prove this feature is working.

---

### 15. form_id vs fileId Semantic Mismatch

```python
fileId=self.metadata["form_id"],
```

`form_id` is the ID of the questionnaire form. `fileId` is supposed to identify a file/document. These are different concepts being conflated. Will the webapp handle this correctly?

---

## Minor Issues

- Test file `test_questionnaire_schema.py` still imports from `evidence.schema` which feels like it should be the other way around
- `EvidenceSourceType` StrEnum values are user-facing strings ("Follow-up Response") mixed with code concerns - separate display names from identifiers
- `from_followup_dto` method on `FollowupQuestionnaireItem` is called from `from_dto` but there's no test for it
- The comment "# Narrowed from Questionnaire" in the source field doesn't explain WHY it's narrowed

---

## Summary

This implementation feels rushed. The core logic is probably correct, but there are too many places where:
1. Code can silently fail (KeyError, missing metadata)
2. Tests don't cover important paths (round-trip, webhook format)
3. Names are confusing (two content_hash fields)
4. Magic numbers aren't explained
5. Debug code is left in

Before merging:
1. Add DTO round-trip test
2. Add integration test for webhook payload format
3. Fix the `form_id` KeyError
4. Either document the debug code or remove it
5. Clarify the content_hash vs criterion_content_hash naming

---

**Would I approve this PR?** No. Not without the tests for #6 and #11 at minimum.
