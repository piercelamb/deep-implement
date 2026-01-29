# Shared Types Changes for Ad-hoc Questions Support

## Problem Statement

The current type system assumes every follow-up questionnaire response is linked to a criterion. However, users can:

1. **Add ad-hoc questions** not tied to any criterion
2. **Copy-paste an existing criterion** as a new question without modifying it

Both scenarios break the current design where `criterion_hash` alone determines uniqueness.

### Current External ID Format
```
{tenant_id}--{vendor_id}--FOLLOWUPQUESTIONNAIRE--{criterion_hash}--{round}
```

**Problem**: Two responses with the same criterion but different questions would collide.

### New External ID Format
```
{tenant_id}--{vendor_id}--FOLLOWUPQUESTIONNAIRE--{content_hash}--{round}
```

Where `content_hash = hash(criterion_question_text || question_text)`, ensuring uniqueness for:
- Same criterion with different questions
- Ad-hoc questions (criterion_question_text is empty)

---

## Files to Modify

### 1. `ai_services/shared/schema/questionnaire/schema.py`

#### `FollowupResponse` Class Changes

**Current:**
```python
@dataclass(frozen=True, slots=True, kw_only=True)
class FollowupResponse(QuestionnaireResponse):
    source: FollowupQuestionnaire
    criterion_hash: str
    original_criterion_question_text: str
```

**New:**
```python
@dataclass(frozen=True, slots=True, kw_only=True)
class FollowupResponse(QuestionnaireResponse):
    source: FollowupQuestionnaire
    content_hash: str  # hash(criterion_question_text || question_text) - for external_id
    criterion_question_hash: str | None  # hash(criterion_question_text) - for retrieval, None for ad-hoc
    original_criterion_question_text: str  # Empty string for ad-hoc questions
```

**Why:**
- `content_hash`: Guarantees uniqueness when same criterion has multiple questions
- `criterion_question_hash`: Enables retrieval filtering by criterion (existing behavior)
- `criterion_question_hash` is `None` for ad-hoc questions (no criterion to filter by)
- `original_criterion_question_text` is empty string (not None) for ad-hoc to simplify string handling

#### Add `is_adhoc` Property

```python
@property
def is_adhoc(self) -> bool:
    """True if this is an ad-hoc question not tied to a criterion."""
    return not self.original_criterion_question_text
```

**Why:** Convenient check for downstream code that handles ad-hoc differently.

#### Update `build_external_id()` Method

**Current:**
```python
def build_external_id(self, tenant_id: str, vendor_id: str, round_number: int) -> str:
    return f"{tenant_id}--{vendor_id}--{self.DOC_TYPE}--{self.criterion_hash}--{round_number}"
```

**New:**
```python
def build_external_id(self, tenant_id: str, vendor_id: str, round_number: int) -> str:
    return f"{tenant_id}--{vendor_id}--{self.DOC_TYPE}--{self.content_hash}--{round_number}"
```

**Why:** Use `content_hash` (criterion + question) for uniqueness instead of just criterion.

#### Update `build_vellum_metadata()` Method

**Current:**
```python
def build_vellum_metadata(self, ...) -> dict[str, str]:
    return {
        ...
        "criterion_question_hash": self.criterion_hash,
        ...
    }
```

**New:**
```python
def build_vellum_metadata(self, ...) -> dict[str, str | None]:
    return {
        ...
        "content_hash": self.content_hash,
        "criterion_question_hash": self.criterion_question_hash,  # None for ad-hoc
        "original_criterion_question_text": self.original_criterion_question_text or None,
        ...
    }
```

**Why:**
- Add `content_hash` for external_id reconstruction
- Return type includes `None` for ad-hoc fields
- Convert empty string to `None` in metadata (cleaner for vector DB)

#### Add Static Hash Methods

```python
@staticmethod
def compute_content_hash(criterion_question_text: str, question_text: str) -> str:
    """Compute content hash for external_id uniqueness."""
    from ai_services.shared.helpers.strings import normalize_and_hash
    return normalize_and_hash(f"{criterion_question_text}||{question_text}")

@staticmethod
def compute_criterion_question_hash(criterion_question_text: str) -> str | None:
    """Compute criterion hash for retrieval filtering. Returns None for empty criterion."""
    if not criterion_question_text:
        return None
    from ai_services.shared.helpers.strings import normalize_and_hash
    return normalize_and_hash(criterion_question_text)
```

**Why:** Centralize hash computation logic. API layer calls these before creating workflow input.

---

#### `VellumFollowupResponse` Class Changes

**Update Regex:**

**Current:**
```python
external_id_re = re.compile(
    r"""
    ^(?P<tenant_id>[^-]+(?:-[^-]+)*)
    --
    (?P<vendor_id>[^-]+(?:-[^-]+)*)
    --
    (?P<doc_type>FOLLOWUPQUESTIONNAIRE)
    --
    (?P<criterion_hash>[0-9a-f]{16})
    --
    (?P<round_number>\d+)
    $
    """,
    re.VERBOSE,
)
```

**New:**
```python
external_id_re = re.compile(
    r"""
    ^(?P<tenant_id>[^-]+(?:-[^-]+)*)
    --
    (?P<vendor_id>[^-]+(?:-[^-]+)*)
    --
    (?P<doc_type>FOLLOWUPQUESTIONNAIRE)
    --
    (?P<content_hash>[0-9a-f]{16})
    --
    (?P<round_number>\d+)
    $
    """,
    re.VERBOSE,
)
```

**Why:** Rename capture group to reflect semantic change (it's now content_hash, not criterion_hash).

**Update `from_vellum_search_res()`:**

**Current:**
```python
criterion_hash = parsed.group("criterion_hash")
...
return cls(
    ...
    criterion_hash=criterion_hash,
    ...
)
```

**New:**
```python
content_hash = parsed.group("content_hash")
criterion_question_hash = metadata.get("criterion_question_hash")  # May be None for ad-hoc
...
return cls(
    ...
    content_hash=content_hash,
    criterion_question_hash=criterion_question_hash,
    ...
)
```

**Why:** Handle ad-hoc responses where `criterion_question_hash` is `None` in metadata.

---

### 2. `ai_services/shared/schema/artifact/schema.py`

**No changes required.** The `FollowupQuestionnaire` artifact class is just an S3 pointer and doesn't need modification.

---

### 3. `ai_services/shared/schema/dto.py`

If `FollowupResponseDTO` exists, update it:

**Current (if exists):**
```python
class FollowupResponseDTO(TypedDict):
    source: FollowupQuestionnaireDTO
    item: QuestionnaireItemDTO
    criterion_hash: str
    original_criterion_question_text: str
```

**New:**
```python
class FollowupResponseDTO(TypedDict):
    source: FollowupQuestionnaireDTO
    item: QuestionnaireItemDTO
    content_hash: str
    criterion_question_hash: str | None
    original_criterion_question_text: str
```

---

## Summary of Changes

| Location | Change | Reason |
|----------|--------|--------|
| `FollowupResponse.criterion_hash` | Rename to `content_hash` | Now hashes criterion+question, not just criterion |
| `FollowupResponse` | Add `criterion_question_hash: str \| None` | Separate field for retrieval filtering |
| `FollowupResponse.original_criterion_question_text` | Keep, but empty for ad-hoc | No semantic change, just clarify usage |
| `FollowupResponse.is_adhoc` | Add property | Convenient check |
| `FollowupResponse.compute_content_hash()` | Add static method | Centralize hash logic |
| `FollowupResponse.compute_criterion_question_hash()` | Add static method | Centralize hash logic, returns None for empty |
| `FollowupResponse.build_external_id()` | Use `content_hash` | Uniqueness based on criterion+question |
| `FollowupResponse.build_vellum_metadata()` | Add both hash fields | Support retrieval and reconstruction |
| `VellumFollowupResponse.external_id_re` | Rename group | Semantic clarity |
| `VellumFollowupResponse.from_vellum_search_res()` | Handle None criterion_question_hash | Support ad-hoc questions |

---

## Migration Notes

### Breaking Changes

1. **Field rename**: `criterion_hash` → `content_hash`
   - All code constructing `FollowupResponse` must update field name
   - All code reading `criterion_hash` must update to `content_hash` or `criterion_question_hash` depending on use case

2. **New required field**: `criterion_question_hash`
   - Must be computed and passed when constructing `FollowupResponse`
   - Can be `None` for ad-hoc questions

### Backward Compatibility

- Existing indexed documents in Vellum won't have `content_hash` metadata
- `from_vellum_search_res()` should extract `content_hash` from external_id (already parsed from regex)
- `criterion_question_hash` can fall back to parsing from external_id for old documents (though they won't have ad-hoc questions)

---

## Test Cases to Add

1. **Ad-hoc question**: `criterion_question_text=""`, `question_text="Custom question"`
   - `content_hash` should be computed from `"||Custom question"`
   - `criterion_question_hash` should be `None`
   - `is_adhoc` should return `True`

2. **Same criterion, different questions**:
   - Response A: `criterion="CC6.1..."`, `question="How do you..."`
   - Response B: `criterion="CC6.1..."`, `question="Please describe..."`
   - Should have different `content_hash` values
   - Should have same `criterion_question_hash` value

3. **Metadata round-trip**:
   - Build metadata with `build_vellum_metadata()`
   - Reconstruct with `from_vellum_search_res()`
   - All fields should match
