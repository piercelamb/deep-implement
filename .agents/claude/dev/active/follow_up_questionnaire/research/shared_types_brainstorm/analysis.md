# Shared Types: JSON Artifact + Questionnaire Hierarchy

## Goal

Design a type system where:
1. Webapp-submitted data is stored as JSON in S3, creating a proper file-backed Artifact
2. Questionnaire-style content can originate from EITHER JSON artifacts OR Tabular files
3. `Questionnaire` is a distinct semantic category (not all Tabular/JsonData are questionnaires)
4. Follow-up questionnaire responses fit naturally into the evidence hierarchy
5. Types are shared between ingestion and retrieval pipelines

## Key Insight

**The caller invokes our endpoint with a JSON blob. Step 1 of ingestion uploads that JSON to S3.**

This gives us:
- `remote_key`: S3 path to the JSON file
- `bucket`: S3 bucket
- `ext`: `Ext.JSON` (already exists!)
- `artifact_id`: Derived from remote_key or generated

No need for a separate `DataSource` hierarchy - everything stays file-centric.

---

## Current State

### Existing Hierarchy

```
Artifact (artifact_id, remote_key, bucket, ext)
    ├── Document (pages)
    │       └── SOC2
    └── Tabular (sheets)  ← UNUSED

Reference (source: Artifact)
    ├── QuestionnaireAnswer (source: Tabular)  ← UNUSED
    └── SourcedContent (content, content_hash)
            └── DocExcerpt → RankedDocExcerpt → VellumDocExcerpt
```

### Existing Enums

```python
# ai_services/shared/schema/artifact/types.py
class Ext(StrEnum):
    JSON = ".json"  # Already exists!

# ai_services/shared/schema/artifact/metadata.py
class ArtifactType(StrEnum):
    SOC_2_TYPE_2 = "SOC_2_TYPE_2"
    SOC_2_TYPE_1 = "SOC_2_TYPE_1"
    SOC_1_TYPE_2 = "SOC_1_TYPE_2"
    SOC_1_TYPE_1 = "SOC_1_TYPE_1"
```

---

## Proposed Design: Questionnaire as Semantic Category

### Core Design Principle

**Not all Tabular artifacts are questionnaires. Not all JsonData artifacts are questionnaires.**

`Questionnaire` is a semantic category that spans multiple structural types. We establish this distinction early in the hierarchy:

```
Artifact
    ├── Document (pages)
    │       └── SOC2
    │
    ├── Tabular (sheets)
    │       ├── TabularQuestionnaire  ← Questionnaire from spreadsheet
    │       └── (future: TabularReport, TabularInventory, etc.)
    │
    └── JsonData
            ├── JsonQuestionnaire  ← Questionnaire from JSON
            │       └── FollowupQuestionnaire
            └── (future: ApiImportData, WebhookPayload, etc.)


Questionnaire = TabularQuestionnaire | JsonQuestionnaire  (union type)
```

### New Hierarchy

```
Artifact (artifact_id, remote_key, bucket, ext)
    ├── Document (pages)
    │       └── SOC2
    ├── Tabular (sheets)
    │       └── TabularQuestionnaire
    └── JsonData
            └── JsonQuestionnaire
                    └── FollowupQuestionnaire


ArtifactType (add FOLLOWUP_QUESTIONNAIRE)


Questionnaire = TabularQuestionnaire | JsonQuestionnaire


Reference (source: Artifact)
    ├── QuestionnaireResponse (source: Questionnaire)
    │       └── FollowupResponse (source: FollowupQuestionnaire)
    │               └── RankedFollowupResponse (scores)
    │                       └── VellumFollowupResponse (metadata, content)
    │
    └── SourcedContent (content, content_hash)
            └── DocExcerpt → RankedDocExcerpt → VellumDocExcerpt
```

---

## Type Definitions

### ArtifactType Addition

```python
# ai_services/shared/schema/artifact/metadata.py (MODIFIED)

class ArtifactType(StrEnum):
    """Machine names of Artifact Types."""

    SOC_2_TYPE_2 = "SOC_2_TYPE_2"
    SOC_2_TYPE_1 = "SOC_2_TYPE_1"
    SOC_1_TYPE_2 = "SOC_1_TYPE_2"
    SOC_1_TYPE_1 = "SOC_1_TYPE_1"
    FOLLOWUP_QUESTIONNAIRE = "FOLLOWUP_QUESTIONNAIRE"  # NEW
```

### JsonData Artifact

```python
# ai_services/shared/schema/artifact/schema.py (add to existing)

@dataclass(frozen=True, slots=True, kw_only=True)
class JsonData(Artifact):
    """
    An artifact representing structured JSON data stored in S3.

    Unlike Document (which has pages) or Tabular (which has sheets),
    JsonData represents a single JSON object/array.

    This is a structural base class. Subclasses define semantic categories:
    - JsonQuestionnaire: Q&A data from forms/surveys
    - (future) ApiImportData: Data imported from external APIs
    - (future) WebhookPayload: Data received via webhooks
    """

    @classmethod
    def from_metadata_dict(
        cls,
        metadata: Mapping[str, Any],
        *,
        default_bucket: str | None = None,
    ) -> "JsonData":
        """Build JsonData from Vellum metadata dictionary."""
        base = Artifact.from_metadata_dict(metadata, default_bucket=default_bucket)
        return cls(
            artifact_id=base.artifact_id,
            remote_key=base.remote_key,
            bucket=base.bucket,
            ext=base.ext,
        )
```

### Questionnaire Types

```python
# ai_services/shared/schema/artifact/schema.py (continued)

@dataclass(frozen=True, slots=True, kw_only=True)
class TabularQuestionnaire(Tabular):
    """
    A questionnaire stored in a tabular file (CSV, Excel).

    This represents Q&A data extracted from spreadsheets, where
    questions and answers are organized in rows/columns.

    Note: Not all Tabular artifacts are questionnaires. This subclass
    establishes "questionnaire" as a distinct semantic category.
    """

    pass  # Inherits sheets from Tabular


@dataclass(frozen=True, slots=True, kw_only=True)
class JsonQuestionnaire(JsonData):
    """
    A questionnaire stored in a JSON file.

    This represents Q&A data in JSON format, typically from:
    - Webapp form submissions
    - API imports
    - Structured exports from other systems

    Note: Not all JsonData artifacts are questionnaires. This subclass
    establishes "questionnaire" as a distinct semantic category.
    """

    pass  # Base for JSON-based questionnaires


# Union type: A questionnaire can come from either source
Questionnaire = TabularQuestionnaire | JsonQuestionnaire
```

### FollowupQuestionnaire Artifact

```python
# ai_services/shared/schema/artifact/schema.py (continued)

@dataclass(frozen=True, slots=True, kw_only=True)
class FollowupQuestionnaire(JsonQuestionnaire):
    """
    A follow-up questionnaire JSON artifact.

    The JSON file in S3 contains the complete questionnaire submission:
    - Submission metadata (vendor_id, round_number, timestamp, etc.)
    - Array of Q&A responses

    This artifact represents the source file; individual responses are
    represented by FollowupResponse instances that reference this.

    Semantic type: ArtifactType.FOLLOWUP_QUESTIONNAIRE
    """

    # Submission-level metadata (parsed from JSON)
    tenant_id: str
    vendor_id: str
    vendor_name: str
    round_number: int
    submitted_at: datetime
    job_id: str

    @property
    def artifact_type(self) -> ArtifactType:
        """The semantic type of this artifact."""
        return ArtifactType.FOLLOWUP_QUESTIONNAIRE

    @classmethod
    def from_s3_upload(
        cls,
        *,
        artifact_id: UUID,
        remote_key: str,
        bucket: str,
        tenant_id: str,
        vendor_id: str,
        vendor_name: str,
        round_number: int,
        submitted_at: datetime,
        job_id: str,
    ) -> Self:
        """Create after uploading JSON to S3."""
        return cls(
            artifact_id=artifact_id,
            remote_key=remote_key,
            bucket=bucket,
            ext=Ext.JSON,
            tenant_id=tenant_id,
            vendor_id=vendor_id,
            vendor_name=vendor_name,
            round_number=round_number,
            submitted_at=submitted_at,
            job_id=job_id,
        )

    def to_dto(self) -> "FollowupQuestionnaireDTO":
        """Serialize for transport."""
        return FollowupQuestionnaireDTO(
            artifact_id=str(self.artifact_id),
            remote_key=self.remote_key,
            bucket=self.bucket,
            ext=self.ext,
            artifact_type=self.artifact_type,
            tenant_id=self.tenant_id,
            vendor_id=self.vendor_id,
            vendor_name=self.vendor_name,
            round_number=self.round_number,
            submitted_at=self.submitted_at.isoformat(),
            job_id=self.job_id,
        )
```

---

### Response Types (Evidence Hierarchy)

```python
# ai_services/shared/schema/questionnaire/schema.py (NEW file)

from dataclasses import dataclass, field
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Self
from uuid import UUID
import re

from ai_services.shared.schema.artifact.schema import (
    Questionnaire,
    FollowupQuestionnaire,
    Ext,
)
from ai_services.shared.schema.artifact.metadata import ArtifactType
from ai_services.shared.schema.evidence.schema import Reference, SourcedContent
from ai_services.shared.vectordb.vectordb_search_result import VectorDbSearchResult


@dataclass(frozen=True, slots=True, kw_only=True)
class QuestionnaireItem:
    """
    A single question-answer pair (source-agnostic).

    This captures the core Q&A content without any source or
    retrieval metadata, making it reusable across contexts.
    """

    question: str
    answer: str
    notes: str | None = None

    @property
    def embedding_content(self) -> str:
        """Format Q&A for vector embedding."""
        return f"Question: {self.question} Answer: {self.answer}"

    def to_dto(self) -> "QuestionnaireItemDTO":
        """Serialize for transport."""
        return QuestionnaireItemDTO(
            question=self.question,
            answer=self.answer,
            notes=self.notes,
        )

    @classmethod
    def from_dto(cls, dto: "QuestionnaireItemDTO") -> Self:
        """Deserialize from transport."""
        return cls(
            question=dto["question"],
            answer=dto["answer"],
            notes=dto.get("notes"),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class QuestionnaireResponse(Reference):
    """
    A Q&A response with provenance to its source questionnaire artifact.

    Extends Reference to integrate with the evidence hierarchy.
    The source must be a Questionnaire (TabularQuestionnaire | JsonQuestionnaire).
    """

    source: Questionnaire
    item: QuestionnaireItem


@dataclass(frozen=True, slots=True, kw_only=True)
class FollowupResponse(QuestionnaireResponse):
    """
    A follow-up questionnaire response with criterion linkage.

    Extends QuestionnaireResponse with:
    - Criterion hash for deterministic linking during retrieval
    - Original criterion text for auditability
    """

    source: FollowupQuestionnaire  # Narrowed type

    # Criterion linkage
    criterion_hash: str
    original_criterion_text: str

    @property
    def round_number(self) -> int:
        """Convenience accessor for source round number."""
        return self.source.round_number

    @property
    def vendor_id(self) -> str:
        """Convenience accessor for source vendor_id."""
        return self.source.vendor_id

    @property
    def tenant_id(self) -> str:
        """Convenience accessor for source tenant_id."""
        return self.source.tenant_id

    @property
    def external_id(self) -> str:
        """Build external ID for Vellum indexing."""
        return f"followup-{self.vendor_id}-{self.criterion_hash}-round{self.round_number}"

    def build_vellum_metadata(self) -> dict[str, str]:
        """Build metadata dict for Vellum document indexing."""
        return {
            "source_type": "follow_up_response",
            "artifact_type": ArtifactType.FOLLOWUP_QUESTIONNAIRE,
            "type": f"followup_response:{self.round_number}",
            "criterion_content_hash": self.criterion_hash,
            "original_criterion_text": self.original_criterion_text,
            "question_text": self.item.question,
            "answer_text": self.item.answer,
            "vendor_id": self.vendor_id,
            "round_number": str(self.round_number),
            "timestamp": self.source.submitted_at.isoformat(),
            "tenant_id": self.tenant_id,
            # Artifact provenance
            "S3_OBJECT_KEY": self.source.remote_key,
            "S3_BUCKET": self.source.bucket,
            "ARTIFACT_ID": str(self.source.artifact_id),
        }

    def to_dto(self) -> "FollowupResponseDTO":
        """Serialize for transport."""
        return FollowupResponseDTO(
            source=self.source.to_dto(),
            item=self.item.to_dto(),
            criterion_hash=self.criterion_hash,
            original_criterion_text=self.original_criterion_text,
        )
```

---

### Vellum Retrieval Types

Following the `DocExcerpt → RankedDocExcerpt → VellumDocExcerpt` pattern:

```python
# ai_services/shared/schema/questionnaire/schema.py (continued)

@dataclass(frozen=True, slots=True, kw_only=True)
class RankedFollowupResponse(FollowupResponse):
    """
    Follow-up response with search ranking scores.

    Mirrors the RankedDocExcerpt pattern for consistency.
    """

    first_stage_score: float
    second_stage_score: float | None = None
    third_stage_score: float | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class VellumFollowupResponse(RankedFollowupResponse):
    """
    Follow-up response retrieved from Vellum search.

    External ID format:
        followup-{vendor_id}-{criterion_hash}-round{round_number}

    Metadata type field format:
        followup_response:{round_number}
    """

    # Raw Vellum metadata
    metadata: Mapping[str, Any] = field(default_factory=dict)

    # Content fields (from Vellum document text)
    content: str
    content_hash: str

    external_id_re = re.compile(
        r"""
        ^followup-                           # prefix
        (?P<vendor_id>[^-]+)                 # vendor_id
        -                                    # separator
        (?P<criterion_hash>[0-9a-f]{16})     # 16 char hex hash
        -round                               # separator
        (?P<round_number>\d+)                # round number
        $
        """,
        re.VERBOSE,
    )

    @classmethod
    def from_vector_db_search_result(cls, result: VectorDbSearchResult) -> Self:
        """Create VellumFollowupResponse from search result."""
        if not result.external_id:
            raise ValueError("VectorDbSearchResult must have an external_id")

        parsed = cls.external_id_re.match(result.external_id)
        if not parsed:
            raise ValueError(
                f"External ID '{result.external_id}' doesn't match followup pattern: "
                "followup-{vendor_id}-{criterion_hash}-round{round_number}"
            )

        metadata = result.metadata
        vendor_id = parsed.group("vendor_id")
        criterion_hash = parsed.group("criterion_hash")
        round_number = int(parsed.group("round_number"))

        # Reconstruct the source artifact from metadata
        source = FollowupQuestionnaire(
            artifact_id=UUID(str(metadata.get("ARTIFACT_ID", metadata.get("artifact_id", UUID(int=0))))),
            remote_key=str(metadata.get("S3_OBJECT_KEY", metadata.get("remote_key", ""))),
            bucket=str(metadata.get("S3_BUCKET", metadata.get("bucket", ""))),
            ext=Ext.JSON,
            tenant_id=str(metadata.get("tenant_id", "")),
            vendor_id=vendor_id,
            vendor_name=str(metadata.get("vendor_name", "")),
            round_number=round_number,
            submitted_at=datetime.fromisoformat(str(metadata.get("timestamp", datetime.min.isoformat()))),
            job_id=str(metadata.get("job_id", "")),
        )

        # Reconstruct the Q&A item from metadata
        item = QuestionnaireItem(
            question=str(metadata.get("question_text", "")),
            answer=str(metadata.get("answer_text", "")),
        )

        return cls(
            source=source,
            item=item,
            criterion_hash=criterion_hash,
            original_criterion_text=str(metadata.get("original_criterion_text", "")),
            first_stage_score=result.score,
            metadata=metadata,
            content=result.text,
            content_hash=SourcedContent.generate_content_hash(result.text),
        )

    def to_item(self) -> QuestionnaireItem:
        """Extract the core Q&A data."""
        return self.item
```

---

## Complete Type Hierarchy Diagram

```
Artifact (artifact_id, remote_key, bucket, ext)
    │
    ├── Document (pages)
    │       └── SOC2
    │
    ├── Tabular (sheets)
    │       ├── TabularQuestionnaire ← Questionnaire from spreadsheet
    │       └── (future: TabularReport, TabularInventory, etc.)
    │
    └── JsonData
            ├── JsonQuestionnaire ← Questionnaire from JSON
            │       └── FollowupQuestionnaire (tenant_id, vendor_id, round_number, ...)
            └── (future: ApiImportData, WebhookPayload, etc.)


Questionnaire = TabularQuestionnaire | JsonQuestionnaire  (union type)


ArtifactType (semantic types)
    ├── SOC_2_TYPE_2, SOC_2_TYPE_1, SOC_1_TYPE_2, SOC_1_TYPE_1
    └── FOLLOWUP_QUESTIONNAIRE ← NEW


Reference (source: Artifact)
    │
    └── QuestionnaireResponse (source: Questionnaire, item: QuestionnaireItem)
            │
            └── FollowupResponse (criterion_hash, original_criterion_text)
                    │
                    └── RankedFollowupResponse (first_stage_score, ...)
                            │
                            └── VellumFollowupResponse (metadata, content, content_hash)


QuestionnaireItem (question, answer, notes) ← Source-agnostic Q&A data
```

---

## Design Rationale

### Why Questionnaire as a Distinct Category?

Not all `Tabular` artifacts are questionnaires:
- `TabularQuestionnaire`: Q&A data from surveys/forms
- (future) `TabularReport`: Financial reports, compliance matrices
- (future) `TabularInventory`: Asset lists, vendor catalogs

Not all `JsonData` artifacts are questionnaires:
- `JsonQuestionnaire`: Q&A data from webapp forms
- (future) `ApiImportData`: Data pulled from external APIs
- (future) `WebhookPayload`: Event data received via webhooks

By establishing `Questionnaire` early in the hierarchy, we:
1. **Prevent semantic confusion**: A `Tabular` could be anything; a `TabularQuestionnaire` is specifically Q&A data
2. **Enable type-safe handling**: Functions that work with questionnaires accept `Questionnaire`, not generic `Tabular | JsonData`
3. **Support future extensibility**: New questionnaire sources just need to be added to the union type

### Why Union Type Instead of Abstract Base?

Python doesn't support "inherit from A or B" at definition time. The union type approach:
- Provides type safety: `Questionnaire = TabularQuestionnaire | JsonQuestionnaire`
- Works with `isinstance()`: `isinstance(artifact, TabularQuestionnaire | JsonQuestionnaire)`
- Enables exhaustive matching in pattern matching

---

## Ingestion Flow

```
1. API receives JSON request body
        │
        ▼
2. Upload JSON to S3
   bucket: "ai-services-artifacts"
   remote_key: "followup-questionnaires/{tenant_id}/{vendor_id}/{job_id}.json"
        │
        ▼
3. Create FollowupQuestionnaire artifact
   - artifact_id from remote_key hash
   - ext = Ext.JSON
   - artifact_type = ArtifactType.FOLLOWUP_QUESTIONNAIRE
        │
        ▼
4. For each Q&A response in JSON:
   - Create QuestionnaireItem(question, answer)
   - Compute criterion_hash
   - Create FollowupResponse(source=artifact, item=item, criterion_hash=...)
   - Build external_id and metadata
   - Upload to Vellum with item.embedding_content
        │
        ▼
5. Poll until INDEXED status
        │
        ▼
6. Send webhook with results
```

### Benefits of S3-First Approach

| Benefit | Description |
|---------|-------------|
| **Auditability** | Original JSON payload preserved in S3 |
| **Artifact traceability** | Full provenance chain: JSON file → individual responses |
| **Consistency** | Same file-centric model as documents/spreadsheets |
| **Reprocessing** | Can re-ingest from S3 if needed |
| **No special cases** | Uses existing Artifact infrastructure |

---

## File Organization

```
ai_services/shared/schema/
├── artifact/
│   ├── schema.py          # Artifact, Document, Tabular, JsonData,
│   │                      # TabularQuestionnaire, JsonQuestionnaire,
│   │                      # FollowupQuestionnaire, Questionnaire (MODIFIED)
│   ├── metadata.py        # ArtifactType (add FOLLOWUP_QUESTIONNAIRE)
│   └── types.py           # Ext, MimeType (existing, unchanged)
│
├── questionnaire/         # NEW directory
│   ├── __init__.py
│   └── schema.py          # QuestionnaireItem, QuestionnaireResponse,
│                          # FollowupResponse, RankedFollowupResponse,
│                          # VellumFollowupResponse
│
├── dto.py                 # Add QuestionnaireItemDTO,
│                          # FollowupQuestionnaireDTO, etc. (MODIFIED)
│
└── evidence/
    └── schema.py          # Reference, DocExcerpt, etc. (existing, unchanged)
```

---

## Shared Types Summary

### Types Shared Between Ingestion and Retrieval

| Type | Location | Purpose |
|------|----------|---------|
| `ArtifactType.FOLLOWUP_QUESTIONNAIRE` | `artifact/metadata.py` | Semantic type identifier |
| `JsonData` | `artifact/schema.py` | Base for JSON file artifacts |
| `JsonQuestionnaire` | `artifact/schema.py` | Base for JSON questionnaires |
| `TabularQuestionnaire` | `artifact/schema.py` | Base for spreadsheet questionnaires |
| `Questionnaire` | `artifact/schema.py` | Union type for any questionnaire |
| `FollowupQuestionnaire` | `artifact/schema.py` | Follow-up submission artifact |
| `QuestionnaireItem` | `questionnaire/schema.py` | Core Q&A structure |
| `FollowupResponse` | `questionnaire/schema.py` | Q&A with criterion linkage + artifact source |
| `compute_criterion_hash()` | `shared/utils.py` | Hash computation |

### Types Used Only for Retrieval

| Type | Purpose |
|------|---------|
| `RankedFollowupResponse` | Search result with scores |
| `VellumFollowupResponse` | Parsed Vellum result with full reconstruction |

### Types Used Only for Ingestion

| Type | Purpose |
|------|---------|
| API Pydantic models | Request validation |
| Workflow input dataclasses | Temporal serialization (may use shared types internally) |

---

## Utility Functions

```python
# ai_services/shared/utils.py

import hashlib
import unicodedata


def compute_criterion_hash(criterion_text: str) -> str:
    """
    Compute stable SHA256 hash of normalized criterion text.

    Returns first 16 hex characters for compact external IDs.

    Normalization:
    - Unicode NFC normalization
    - Lowercase
    - Whitespace collapsed to single spaces
    - Leading/trailing whitespace stripped
    """
    normalized = unicodedata.normalize("NFC", criterion_text.lower().strip())
    normalized = " ".join(normalized.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def format_followup_embedding_content(question: str, answer: str) -> str:
    """
    Format Q&A for vector embedding.

    Prefixes help embedding models understand structure.
    """
    return f"Question: {question} Answer: {answer}"
```

Note: `format_followup_embedding_content` can also be accessed via `QuestionnaireItem.embedding_content` property.

---

## DTOs (TypedDict Definitions)

```python
# ai_services/shared/schema/dto.py (additions)

from typing import TypedDict


class QuestionnaireItemDTO(TypedDict):
    """Serialized QuestionnaireItem."""
    question: str
    answer: str
    notes: str | None


class FollowupQuestionnaireDTO(TypedDict):
    """Serialized FollowupQuestionnaire artifact."""
    artifact_id: str
    remote_key: str
    bucket: str
    ext: str
    artifact_type: str  # ArtifactType.FOLLOWUP_QUESTIONNAIRE
    tenant_id: str
    vendor_id: str
    vendor_name: str
    round_number: int
    submitted_at: str  # ISO format
    job_id: str


class FollowupResponseDTO(TypedDict):
    """Serialized FollowupResponse."""
    source: FollowupQuestionnaireDTO
    item: QuestionnaireItemDTO
    criterion_hash: str
    original_criterion_text: str
```

---

## Implementation Impact on Ingestion Plan

The ingestion plan should be updated to:

1. **Add `FOLLOWUP_QUESTIONNAIRE`** to `ArtifactType` in `artifact/metadata.py`

2. **Add artifact types** to `artifact/schema.py`:
   - `JsonData` (structural base)
   - `TabularQuestionnaire` (questionnaire from spreadsheet)
   - `JsonQuestionnaire` (questionnaire from JSON)
   - `FollowupQuestionnaire` (follow-up specific)
   - `Questionnaire` (union type)

3. **Create `questionnaire/schema.py`** with the response type hierarchy

4. **Add S3 upload step** at the start of the workflow:
   - Upload incoming JSON payload to S3
   - Create `FollowupQuestionnaire` artifact from the upload

5. **Update workflow to use shared types**:
   - Create `FollowupResponse` instances for each Q&A
   - Use `response.external_id` and `response.build_vellum_metadata()`
   - Use `response.item.embedding_content` for Vellum document text

6. **Add DTOs** to `schema/dto.py`

7. **Keep utility functions** in `shared/utils.py` as planned

---

## Benefits of This Design

### 1. Clear Semantic Categories

- `Questionnaire` is distinct from generic `Tabular`/`JsonData`
- Type system prevents confusion: can't accidentally treat a financial report as a questionnaire
- Future artifact types (reports, inventories) won't be conflated with questionnaires

### 2. File-Centric Consistency

- All data sources are S3-backed artifacts
- Same infrastructure for documents, spreadsheets, and JSON data
- `Ext.JSON` already exists - no changes to type system

### 3. Full Artifact Traceability

- Original JSON payload preserved in S3
- Each `FollowupResponse` references its source artifact
- Vellum metadata includes `S3_OBJECT_KEY`, `S3_BUCKET`, `ARTIFACT_ID`, `artifact_type`

### 4. Polymorphic Questionnaire Sources

- `QuestionnaireResponse.source: Questionnaire` (TabularQuestionnaire | JsonQuestionnaire)
- Same Q&A handling logic works for uploaded spreadsheets and JSON submissions
- Future extensibility: add new questionnaire sources to the union type

### 5. Clean Inheritance Hierarchy

- `FollowupResponse → RankedFollowupResponse → VellumFollowupResponse`
- Mirrors established `DocExcerpt → RankedDocExcerpt → VellumDocExcerpt`
- `QuestionnaireResponse` extends `Reference` - integrates with evidence system

### 6. Reprocessing Capability

- If indexing fails or schema changes, can re-process from S3
- JSON file is the source of truth
- Workflow becomes idempotent with S3 as checkpoint
