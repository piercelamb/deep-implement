# Schema Refactor: Breaking Circular Dependencies

## Executive Summary

This document explains a schema refactor that was required to fix a bug where **follow-up questionnaire responses were being silently dropped** from the evidence output sent to the webapp. The refactor itself is not the feature—it's the prerequisite that unblocked the feature implementation.

---

## Part 1: The Business Problem

### What Was Broken

The VRM (Vendor Risk Management) agent retrieves evidence from multiple sources to assess vendor compliance:
- **Document excerpts** (`VellumDocExcerpt`) - snippets from uploaded PDFs, policies, etc.
- **SOC2 summaries** (`VellumSOC2SummaryTrack`) - AI-generated summaries of SOC2 reports
- **Follow-up responses** (`VellumFollowupResponse`) - answers to questionnaires sent to vendors

All three types were being retrieved and shown to the LLM for assessment. However, **only document excerpts were being returned to the webapp**. Follow-up responses that influenced the LLM's decision were silently dropped.

### The Data Flow Bug

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
│  ──► CriterionEvidence.refs: Sequence[VellumDocExcerpt]  ◄── TYPE TOO NARROW│
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ReviewedCriterion.to_assessment_webhook_dto()             │
│                                                                              │
│  for ref in evidenced_criterion.refs:                                        │
│      ref.to_assessment_webhook_dto() ──► AssessmentSourceWebhookDTO         │
│                                                                              │
│  Result: Webapp only sees document excerpts, never follow-up responses      │
└─────────────────────────────────────────────────────────────────────────────┘
```

The root cause was that `CriterionEvidence.refs` was typed as `Sequence[VellumDocExcerpt]`, which couldn't hold `VellumFollowupResponse` objects.

---

## Part 2: The Proposed Fix

The fix seemed straightforward (see `FOLLOWUP_OUTPUT_PROPOSAL.md` for full details):

1. **Add `to_assessment_webhook_dto()`** to `VellumFollowupResponse` so it can serialize to the webapp format
2. **Widen `CriterionEvidence.refs`** from `Sequence[VellumDocExcerpt]` to `Sequence[CriterionEvidenceRef]` where:
   ```python
   CriterionEvidenceRef = VellumDocExcerpt | VellumFollowupResponse
   ```
3. **Create `convert_to_criterion_refs()`** that keeps follow-up responses instead of dropping them
4. **Add serialization support** so `CriterionEvidence` can serialize/deserialize both ref types

### The Blocker: Circular Import

When we tried to create the union type in `evidence/schema.py`:

```python
# evidence/schema.py
from ai_services.shared.schema.questionnaire.schema import VellumFollowupResponse

CriterionEvidenceRef = VellumDocExcerpt | VellumFollowupResponse  # Needs VellumFollowupResponse
```

Python raised an `ImportError` because of a circular dependency:

```
evidence/schema.py                    questionnaire/schema.py
┌─────────────────────────────┐      ┌─────────────────────────────┐
│ Reference                   │◄─────│ FollowupResponse            │
│ SourcedContent              │◄─────│ (extends Reference)         │
│ VellumQuestionnaireContent  │◄─────│ VellumFollowupResponse      │
│                             │      │ (extends VellumQuestionnaire│
│ CriterionEvidence           │──────►│  Content)                   │
│ (needs VellumFollowupResponse│      │                             │
│  for type alias & from_dto) │      │                             │
└─────────────────────────────┘      └─────────────────────────────┘
              ▲                                    │
              └────────────────────────────────────┘
                         CIRCULAR!
```

**Why the cycle exists:**
- `questionnaire/schema.py` imports `Reference`, `SourcedContent`, and `VellumQuestionnaireContent` from `evidence/schema.py` (inheritance)
- `evidence/schema.py` would need to import `VellumFollowupResponse` from `questionnaire/schema.py` (for the union type and deserialization)

---

## Part 3: Approaches Considered and Rejected

### Approach 1: `TYPE_CHECKING` Guard

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_services.shared.schema.questionnaire.schema import VellumFollowupResponse
```

**Why rejected:** This is a code smell. It makes the import available for type hints but not at runtime, which would break `CriterionEvidence.from_dto()` when it tries to instantiate `VellumFollowupResponse`.

### Approach 2: Late/Lazy Import

```python
def from_dto(cls, dto):
    from ai_services.shared.schema.questionnaire.schema import VellumFollowupResponse  # Late import
    ...
```

**Why rejected:** Late imports are a code smell indicating architectural problems. They make the code harder to understand and can mask deeper issues.

### Approach 3: Use Base Class in Union

```python
CriterionEvidenceRef = VellumDocExcerpt | VellumQuestionnaireContent  # Base class instead of subclass
```

**Why this worked for the union type:** `VellumQuestionnaireContent` is defined in `evidence/schema.py`, so no circular import. `VellumFollowupResponse` is a subclass, so it satisfies this type.

**But we still had the deserialization problem:** `CriterionEvidence.from_dto()` needs to instantiate the concrete `VellumFollowupResponse` class, not the abstract base class.

### Approach 4: Registry Pattern on Base Class

Add a class-level registry to `VellumQuestionnaireContent` where subclasses register themselves, and `from_dto()` dispatches via the registry.

**Why rejected:** Over-engineered for the current use case (only one subclass). Also created awkward type signature issues—the base class `from_dto()` would need to accept a union type, but subclass `from_dto()` would only accept its specific DTO type, violating Liskov Substitution Principle.

### Approach 5 (Chosen): Extract Foundational Types

Move `Reference` and `SourcedContent` to a new `base.py` module, then move `VellumFollowupResponse` to `evidence/schema.py` where its base class lives.

**Why this works:**
- Breaks the cycle at the right point (foundational types have no business depending on anything)
- Keeps related classes together (`VellumFollowupResponse` next to `VellumQuestionnaireContent`)
- No runtime hacks, no type system violations
- Simple and understandable

---

## Part 4: The Refactor

### New File Structure

```
schema/
├── evidence/
│   ├── base.py              # NEW: Reference, SourcedContent (foundational types)
│   ├── schema.py            # DocExcerpt, Vellum*, CriterionEvidence, VellumFollowupResponse
│   └── types.py
├── questionnaire/
│   ├── __init__.py
│   └── schema.py            # QuestionnaireItem, FollowupQuestionnaireItem, FollowupResponse
```

### New Dependency Graph (No Cycles)

```
evidence/base.py  ←─── questionnaire/schema.py
       ↑                      ↑
       │                      │
       └──────────── evidence/schema.py
```

- `evidence/base.py` → only `artifact/schema.py` (for `Artifact` type)
- `questionnaire/schema.py` → `evidence/base.py` (for `Reference`)
- `evidence/schema.py` → `evidence/base.py` + `questionnaire/schema.py` (for `FollowupQuestionnaireItem`)

---

## Part 5: Code Changes

### 1. New File: `evidence/base.py`

```python
"""
Foundational schema types with no circular dependencies.

This module contains base classes that other schema modules can safely import:
- evidence/schema.py
- questionnaire/schema.py

These types have no dependencies on other schema modules (except artifact/schema.py).
"""

import hashlib
import re
from dataclasses import dataclass

from ai_services.shared.schema.artifact.schema import Artifact


@dataclass(frozen=True, slots=True, kw_only=True)
class Reference:
    """
    Represents a reference that comes from an artifact (document, tabular file, image etc).
    """

    source: Artifact


@dataclass(frozen=True, slots=True, kw_only=True)
class SourcedContent(Reference):
    """
    Base class for text content with provenance back to source documents.

    This captures the shared structure between:
    - Directly extracted content (DocExcerpt): text taken verbatim from a document
    - Generated content (GeneratedContent): AI-synthesized text derived from documents
    """

    content: str
    content_hash: str

    @staticmethod
    def generate_content_hash(content: str) -> str:
        """Generate content hash for deduplication purposes."""
        normalized = re.sub(r"\s+", " ", content.strip()).lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
```

### 2. Updated `questionnaire/schema.py` Imports

**Before:**
```python
from ai_services.shared.schema.evidence.schema import Reference, SourcedContent, VellumQuestionnaireContent
```

**After:**
```python
from ai_services.shared.schema.evidence.base import Reference
```

The file no longer imports `SourcedContent` or `VellumQuestionnaireContent` because:
- `SourcedContent` was only used by `VellumFollowupResponse` (now moved)
- `VellumQuestionnaireContent` was the base class for `VellumFollowupResponse` (now moved)

### 3. Moved `VellumFollowupResponse` to `evidence/schema.py`

The entire `VellumFollowupResponse` class was moved from `questionnaire/schema.py` to `evidence/schema.py`, where its base class `VellumQuestionnaireContent` is defined.

**Key imports added to `evidence/schema.py`:**
```python
from ai_services.shared.schema.artifact.schema import Document, FollowupQuestionnaire, Questionnaire, Tabular
from ai_services.shared.schema.artifact.util import require_str
from ai_services.shared.schema.dto import (
    # ... existing imports ...
    FollowupQuestionnaireDTO,
    VellumFollowupResponseRefDTO,
)
from ai_services.shared.schema.evidence.base import Reference, SourcedContent
from ai_services.shared.schema.questionnaire.schema import FollowupQuestionnaireItem
```

### 4. Added Abstract Methods to `VellumQuestionnaireContent`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class VellumQuestionnaireContent(RankedQuestionnaireContent):
    """
    Questionnaire content retrieved from Vellum document indexes.

    Base class for questionnaire-based evidence indexed in Vellum.
    Subclasses implement domain-specific parsing and fields:
    - VellumFollowupResponse: Follow-up questionnaire responses
    - (Future) Tabular questionnaire response types
    """

    metadata: Mapping[str, Any] = field(default_factory=dict)

    @abstractmethod
    def to_assessment_webhook_dto(self) -> AssessmentSourceWebhookDTO:
        """Convert to webhook DTO format for webapp consumption. Subclasses must implement."""
        ...

    @abstractmethod
    def to_dto(self) -> CriterionEvidenceRefDTO:
        """Serialize to DTO for transport. Subclasses must implement."""
        ...
```

**Why abstract methods:**
- Ensures all questionnaire content types can be serialized
- Duck typing—`ReviewedCriterion.to_assessment_webhook_dto()` can call `ref.to_assessment_webhook_dto()` without caring about the concrete type

### 5. `VellumFollowupResponse` Implementation (in `evidence/schema.py`)

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class VellumFollowupResponse(VellumQuestionnaireContent):
    """
    Follow-up response retrieved from Vellum search.
    """

    source: FollowupQuestionnaire
    item: FollowupQuestionnaireItem

    criterion_content_hash: str
    criterion_question_hash: str | None
    original_criterion_question_text: str
    question_similarity_score: float | None

    @classmethod
    def from_dto(cls, dto: VellumFollowupResponseRefDTO) -> Self:
        """Deserialize from DTO."""
        from ai_services.shared.schema.artifact.types import Ext

        source = FollowupQuestionnaire(
            artifact_id=UUID(dto["source"]["artifact_id"]),
            remote_key=dto["source"]["remote_key"],
            bucket=dto["source"]["bucket"],
            ext=Ext(dto["source"]["ext"]),
        )
        item = FollowupQuestionnaireItem.from_followup_dto(dto["item"])

        return cls(
            source=source,
            item=item,
            content=dto["content"],
            content_hash=dto["content_hash"],
            first_stage_score=dto["first_stage_score"],
            second_stage_score=dto.get("second_stage_score"),
            third_stage_score=dto.get("third_stage_score"),
            metadata=dto["metadata"],
            criterion_content_hash=dto["criterion_content_hash"],
            criterion_question_hash=dto.get("criterion_question_hash"),
            original_criterion_question_text=dto["original_criterion_question_text"],
            question_similarity_score=dto.get("question_similarity_score"),
        )

    def to_assessment_webhook_dto(self) -> AssessmentSourceWebhookDTO:
        """Convert to webhook DTO format for webapp consumption."""
        return AssessmentSourceWebhookDTO(
            docExcerpt=self.content,
            documentName=self.metadata.get("FILENAME", "Follow-up Response"),
            fileId=self.metadata["form_id"],  # Uses form_id from indexed metadata
            referencedOn=datetime.now(UTC).isoformat(),
        )

    def to_dto(self) -> VellumFollowupResponseRefDTO:
        """Convert to DTO for serialization."""
        return VellumFollowupResponseRefDTO(
            ref_type="followup_response",  # Discriminator for deserialization
            source=FollowupQuestionnaireDTO(
                artifact_id=str(self.source.artifact_id),
                remote_key=self.source.remote_key,
                bucket=self.source.bucket,
                ext=self.source.ext.value,
            ),
            item=self.item.to_dto(),
            content=self.content,
            content_hash=self.content_hash,
            first_stage_score=self.first_stage_score,
            second_stage_score=self.second_stage_score,
            third_stage_score=self.third_stage_score,
            criterion_content_hash=self.criterion_content_hash,
            criterion_question_hash=self.criterion_question_hash,
            original_criterion_question_text=self.original_criterion_question_text,
            question_similarity_score=self.question_similarity_score,
            metadata=dict(self.metadata),
        )
```

**Note on `fileId`:** Uses `form_id` from the indexed metadata, which is the unique identifier the webapp uses to track follow-up questionnaire forms. This was a deliberate choice per the original proposal.

### 6. Updated `CriterionEvidence.from_dto()` with Type Discrimination

```python
@classmethod
def from_dto(cls, *, dto: EvidenceAssessmentResultDTO) -> "CriterionEvidence":
    """
    Construct a CriterionEvidence where the serialized data was created
    from Vellum search results.

    Dispatches to the correct ref type based on the ref_type discriminator.
    """
    refs: list[CriterionEvidenceRef] = []
    for d in dto["refs"]:
        ref_type = d.get("ref_type", "doc_excerpt")  # backwards compatibility
        if ref_type == "doc_excerpt":
            refs.append(VellumDocExcerpt.from_dto(cast(EvidenceRefDTO, d)))
        elif ref_type == "followup_response":
            refs.append(VellumFollowupResponse.from_dto(cast(VellumFollowupResponseRefDTO, d)))
        else:
            raise ValueError(f"Unknown ref_type: {ref_type}")

    return cls(
        linked_criterion=dto.get("linked_criterion"),
        evidence_support_type=EvidenceSupportTypes(dto["evidence_support_type"]),
        criterion=dto["criterion"],
        refs=refs,
        summary=dto["summary"],
        explain=dto["explain"],
        reason=InconclusiveReason(dto["reason"]) if dto.get("reason") else None,
    )
```

**Key design decisions:**

1. **`ref_type` discriminator**: Each DTO has a `ref_type` field (`"doc_excerpt"` or `"followup_response"`) that tells us which class to deserialize to. This is a common pattern for polymorphic JSON.

2. **`cast()` for type narrowing**: After checking `ref_type`, we use `cast()` to tell the type checker the exact DTO type. This is safe because we've already validated the discriminator.

3. **Backwards compatibility**: Default `ref_type` to `"doc_excerpt"` for DTOs that don't have the field (pre-existing serialized data).

4. **No abstract `from_dto()` on base class**: We intentionally did NOT add an abstract `from_dto()` to `VellumQuestionnaireContent` because:
   - It would violate Liskov Substitution Principle (base class method would accept union type, but subclass method would only accept specific DTO type—subclass has narrower contract)
   - The dispatcher logic belongs in `CriterionEvidence.from_dto()` which knows about all ref types and can dispatch appropriately

---

## Part 6: Updated Exports and Imports

### Updated `questionnaire/__init__.py`

```python
from ai_services.shared.schema.questionnaire.schema import (
    FollowupQuestionnaireItem,
    FollowupResponse,
    QuestionnaireItem,
)

__all__ = [
    "FollowupQuestionnaireItem",
    "FollowupResponse",
    "QuestionnaireItem",
]
```

`VellumFollowupResponse` is no longer exported from `questionnaire`—it's now imported from `evidence.schema`.

### Files That Needed Import Updates

| File | Change |
|------|--------|
| `ai_services/vellum/support/vrm_agent_q3_fy26/gather_evidence/run.py` | Import `VellumFollowupResponse` from `evidence.schema` |
| `tests/shared/schema/questionnaire/test_questionnaire_schema.py` | Import `VellumFollowupResponse` from `evidence.schema` |
| `tests/vellum/support/vrm_agent_q3_fy26/gather_evidence/test_followup_extraction.py` | Import `VellumFollowupResponse` from `evidence.schema` |

---

## Part 7: Why This Design Works

1. **No circular imports**: The dependency graph is acyclic. `base.py` has no schema dependencies, `questionnaire` only depends on `base.py`, and `evidence/schema.py` can safely import from both.

2. **Backwards compatible**: Existing code that imports `Reference` or `SourcedContent` from `evidence/schema.py` continues to work because those names are re-exported (imported into `evidence/schema.py` from `base.py`).

3. **Type-safe serialization**: The `ref_type` discriminator pattern allows us to deserialize polymorphic collections without runtime type checking hacks.

4. **Clean separation of concerns**:
   - `base.py`: Pure data structures (no business logic, no Vellum-specific code)
   - `questionnaire/schema.py`: Questionnaire-specific types for **indexing** (creating documents to upload to Vellum)
   - `evidence/schema.py`: Vellum **retrieval** types (parsing search results) and evidence assessment logic

5. **Extensible**: Adding new questionnaire content types (e.g., tabular questionnaire responses) follows the same pattern:
   - Add the class to `evidence/schema.py`
   - Add a DTO to `dto.py`
   - Add a case to the `from_dto()` dispatcher
   - Update the union type if needed

---

## Part 8: Test Results

All 96 related tests pass:
- `tests/shared/schema/questionnaire/` - 30 tests
- `tests/vellum/support/vrm_agent_q3_fy26/gather_evidence/` - 27 tests
- Additional evidence/criterion tests - 39 tests

Type checking (mypy) and linting (ruff) pass with no errors on the modified files.

---

## Part 9: What's Next

With this refactor complete, the original feature can now be implemented:

1. ✅ `CriterionEvidence.refs` now accepts `VellumFollowupResponse`
2. ✅ `VellumFollowupResponse` has `to_assessment_webhook_dto()` and `to_dto()`
3. ✅ `CriterionEvidence.from_dto()` can deserialize both ref types
4. 🔲 Update `convert_to_criterion_refs()` in `run.py` to keep follow-up responses (was `convert_to_doc_excerpts()`)
5. 🔲 Update `handle_outputs.py` to use the new conversion function

The webapp will then receive follow-up responses in the evidence output, fixing the original bug.

---

## Summary

| What | Why |
|------|-----|
| **Business problem** | Follow-up responses were being dropped from evidence output |
| **Technical fix** | Widen `CriterionEvidence.refs` to include `VellumFollowupResponse` |
| **Blocker** | Circular import between `evidence/schema.py` and `questionnaire/schema.py` |
| **Solution** | Extract foundational types to `evidence/base.py`, move `VellumFollowupResponse` to `evidence/schema.py` |
| **Pattern used** | `ref_type` discriminator for polymorphic DTO deserialization |
