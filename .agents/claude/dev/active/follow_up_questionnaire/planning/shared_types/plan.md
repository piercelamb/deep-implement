# Shared Types Implementation Plan

## Overview

Implement the shared type system for follow-up questionnaire responses that will be used by both ingestion and retrieval pipelines. Based on the design in `.agents/claude/dev/active/follow_up_questionnaire/research/shared_types_brainstorm/analysis.md`.

## Design Summary

- **S3-first approach**: Upload JSON payload to S3 first, creating a proper file-backed Artifact
- **Questionnaire as semantic category**: `Questionnaire = TabularQuestionnaire | JsonQuestionnaire`
- **Evidence hierarchy pattern**: `FollowupResponse → RankedFollowupResponse → VellumFollowupResponse`
- **External ID format**: `followup-{vendor_id}-{content_hash}-round{round_number}`
  - `content_hash` = hash of `criterion_question_text || question_text` (supports ad-hoc questions where criterion_question_text is empty)
- **Ad-hoc questions**: `criterion_question_text` can be empty for user-added questions not tied to a criterion

---

## Implementation Steps

### Step 1: Add ArtifactType

**File**: `ai_services/shared/schema/artifact/metadata.py`

Add to existing `ArtifactType` enum:

```python
class ArtifactType(StrEnum):
    """Machine names of Artifact Types."""

    SOC_2_TYPE_2 = "SOC_2_TYPE_2"
    SOC_2_TYPE_1 = "SOC_2_TYPE_1"
    SOC_1_TYPE_2 = "SOC_1_TYPE_2"
    SOC_1_TYPE_1 = "SOC_1_TYPE_1"
    FOLLOWUP_QUESTIONNAIRE = "FOLLOWUP_QUESTIONNAIRE"  # NEW
```

---

### Step 2: Add Artifact Types

**File**: `ai_services/shared/schema/artifact/schema.py`

Add structural base + questionnaire types:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class JsonData(Artifact):
    """
    An artifact representing structured JSON data stored in S3.

    Structural base class. Subclasses define semantic categories:
    - JsonQuestionnaire: Q&A data from forms/surveys
    """

    @classmethod
    def from_metadata_dict(
        cls,
        metadata: Mapping[str, Any],
        *,
        default_bucket: str | None = None,
    ) -> Self:
        """Build JsonData from metadata dictionary."""
        base = Artifact.from_metadata_dict(metadata, default_bucket=default_bucket)
        return cls(
            artifact_id=base.artifact_id,
            remote_key=base.remote_key,
            bucket=base.bucket,
            ext=base.ext,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class TabularQuestionnaire(Tabular):
    """
    A questionnaire stored in a tabular file (CSV, Excel).

    Note: Not all Tabular artifacts are questionnaires.
    """
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class JsonQuestionnaire(JsonData):
    """
    A questionnaire stored in a JSON file.

    Note: Not all JsonData artifacts are questionnaires.
    """
    pass


# Union type: questionnaire from either source
Questionnaire = TabularQuestionnaire | JsonQuestionnaire


@dataclass(frozen=True, slots=True, kw_only=True)
class FollowupQuestionnaire(JsonQuestionnaire):
    """
    A follow-up questionnaire JSON artifact.

    Represents the source file; individual responses are
    represented by FollowupResponse instances.
    """

    tenant_id: str
    vendor_id: str
    vendor_name: str
    round_number: int
    submitted_at: datetime
    job_id: str

    @property
    def artifact_type(self) -> ArtifactType:
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

**Imports to add**: `datetime` (if not already), `Self`, `ArtifactType`

---

### Step 3: Create Questionnaire Schema Module

**File**: `ai_services/shared/schema/questionnaire/__init__.py` (new)

```python
from ai_services.shared.schema.questionnaire.schema import (
    FollowupResponse,
    QuestionnaireItem,
    QuestionnaireResponse,
    RankedFollowupResponse,
    VellumFollowupResponse,
)

__all__ = [
    "FollowupResponse",
    "QuestionnaireItem",
    "QuestionnaireResponse",
    "RankedFollowupResponse",
    "VellumFollowupResponse",
]
```

**File**: `ai_services/shared/schema/questionnaire/schema.py` (new)

```python
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Self
from uuid import UUID

from ai_services.shared.schema.artifact.metadata import ArtifactType
from ai_services.shared.schema.artifact.schema import (
    FollowupQuestionnaire,
    Questionnaire,
)
from ai_services.shared.schema.artifact.types import Ext
from ai_services.shared.schema.dto import (
    FollowupQuestionnaireDTO,
    FollowupResponseDTO,
    QuestionnaireItemDTO,
)
from ai_services.shared.schema.evidence.schema import Reference, SourcedContent
from ai_services.shared.vectordb.vectordb_search_result import VectorDbSearchResult


@dataclass(frozen=True, slots=True, kw_only=True)
class QuestionnaireItem:
    """
    A single question-answer pair (source-agnostic).
    """

    question: str
    answer: str
    notes: str | None = None

    @property
    def embedding_content(self) -> str:
        """Format Q&A for vector embedding."""
        return f"Question: {self.question} Answer: {self.answer}"

    def to_dto(self) -> QuestionnaireItemDTO:
        return QuestionnaireItemDTO(
            question=self.question,
            answer=self.answer,
            notes=self.notes,
        )

    @classmethod
    def from_dto(cls, dto: QuestionnaireItemDTO) -> Self:
        return cls(
            question=dto["question"],
            answer=dto["answer"],
            notes=dto.get("notes"),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class QuestionnaireResponse(Reference):
    """
    A Q&A response with provenance to its source questionnaire artifact.
    """

    source: Questionnaire
    item: QuestionnaireItem


@dataclass(frozen=True, slots=True, kw_only=True)
class FollowupResponse(QuestionnaireResponse):
    """
    A follow-up questionnaire response with criterion linkage.

    Supports both criterion-linked responses and ad-hoc questions:
    - Criterion-linked: original_criterion_question_text is set, criterion_question_hash computed from it
    - Ad-hoc: original_criterion_question_text is empty, criterion_question_hash is None

    The content_hash (used for external_id) is always computed from criterion_question_text + question_text,
    ensuring uniqueness even for same criterion with different questions.
    """

    source: FollowupQuestionnaire

    content_hash: str  # hash(criterion_question_text || question_text) - used for external_id uniqueness
    criterion_question_hash: str | None  # hash(criterion_question_text) - used for retrieval filtering, None for ad-hoc
    original_criterion_question_text: str  # Empty string for ad-hoc questions

    @property
    def round_number(self) -> int:
        return self.source.round_number

    @property
    def vendor_id(self) -> str:
        return self.source.vendor_id

    @property
    def tenant_id(self) -> str:
        return self.source.tenant_id

    @property
    def external_id(self) -> str:
        """Build external ID for Vellum indexing."""
        return f"followup-{self.vendor_id}-{self.content_hash}-round{self.round_number}"

    @property
    def is_adhoc(self) -> bool:
        """True if this is an ad-hoc question not tied to a criterion."""
        return not self.original_criterion_question_text

    def build_vellum_metadata(self) -> dict[str, str | None]:
        """Build metadata dict for Vellum document indexing."""
        return {
            "source_type": "follow_up_response",
            "artifact_type": ArtifactType.FOLLOWUP_QUESTIONNAIRE,
            "type": f"followup_response:{self.round_number}",
            "content_hash": self.content_hash,  # For external_id reconstruction
            "criterion_question_hash": self.criterion_question_hash,  # For retrieval filtering (None for ad-hoc)
            "original_criterion_question_text": self.original_criterion_question_text or None,  # Empty string → None
            "question_text": self.item.question,
            "answer_text": self.item.answer,
            "vendor_id": self.vendor_id,
            "round_number": str(self.round_number),
            "timestamp": self.source.submitted_at.isoformat(),
            "tenant_id": self.tenant_id,
            "S3_OBJECT_KEY": self.source.remote_key,
            "S3_BUCKET": self.source.bucket,
            "ARTIFACT_ID": str(self.source.artifact_id),
        }

    @staticmethod
    def compute_content_hash(criterion_question_text: str, question_text: str) -> str:
        """Compute content hash for external_id from criterion + question."""
        from ai_services.shared.helpers.strings import normalize_and_hash
        return normalize_and_hash(f"{criterion_question_text}||{question_text}")

    @staticmethod
    def compute_criterion_question_hash(criterion_question_text: str) -> str | None:
        """Compute criterion hash for retrieval filtering. Returns None for empty criterion."""
        if not criterion_question_text:
            return None
        from ai_services.shared.helpers.strings import normalize_and_hash
        return normalize_and_hash(criterion_question_text)

    def to_dto(self) -> FollowupResponseDTO:
        return FollowupResponseDTO(
            source=self.source.to_dto(),
            item=self.item.to_dto(),
            content_hash=self.content_hash,
            criterion_question_hash=self.criterion_question_hash,
            original_criterion_question_text=self.original_criterion_question_text,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class RankedFollowupResponse(FollowupResponse):
    """
    Follow-up response with search ranking scores.
    """

    first_stage_score: float
    second_stage_score: float | None = None
    third_stage_score: float | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class VellumFollowupResponse(RankedFollowupResponse):
    """
    Follow-up response retrieved from Vellum search.

    External ID format: followup-{vendor_id}-{content_hash}-round{round_number}
    where content_hash = hash(criterion_question_text || question_text)
    """

    metadata: Mapping[str, Any] = field(default_factory=dict)
    content: str
    embedding_content_hash: str  # Hash of the embedded content (for deduplication)

    external_id_re = re.compile(
        r"""
        ^followup-                           # prefix
        (?P<vendor_id>[^-]+)                 # vendor_id
        -                                    # separator
        (?P<content_hash>[0-9a-f]{16})       # 16 char hex hash (criterion+question)
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
                f"External ID '{result.external_id}' doesn't match followup pattern"
            )

        metadata = result.metadata
        vendor_id = parsed.group("vendor_id")
        content_hash = parsed.group("content_hash")
        round_number = int(parsed.group("round_number"))

        # Get criterion_question_hash from metadata (may be None for ad-hoc questions)
        criterion_question_hash = metadata.get("criterion_question_hash")

        # Reconstruct source artifact from metadata
        source = FollowupQuestionnaire(
            artifact_id=UUID(str(metadata.get("ARTIFACT_ID", metadata.get("artifact_id", str(UUID(int=0)))))),
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

        item = QuestionnaireItem(
            question=str(metadata.get("question_text", "")),
            answer=str(metadata.get("answer_text", "")),
        )

        return cls(
            source=source,
            item=item,
            content_hash=content_hash,
            criterion_question_hash=criterion_question_hash,  # May be None for ad-hoc
            original_criterion_question_text=str(metadata.get("original_criterion_question_text") or ""),
            first_stage_score=result.score,
            metadata=metadata,
            content=result.text,
            embedding_content_hash=SourcedContent.generate_content_hash(result.text),
        )
```

---

### Step 4: Add DTOs

**File**: `ai_services/shared/schema/dto.py` (add to existing)

```python
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
    artifact_type: str
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
    content_hash: str  # hash(criterion_question_text || question_text) - for external_id
    criterion_question_hash: str | None  # hash(criterion_question_text) - for retrieval, None for ad-hoc
    original_criterion_question_text: str  # Empty string for ad-hoc questions
```

---

### Step 5: Add String Utility Functions

**File**: `ai_services/shared/helpers/strings.py` (new)

Pattern inspired by `ai_services/vellum/libs/strings.py`:

```python
"""String normalization and hashing utilities for stable content identification."""

import hashlib
import unicodedata


def normalize_for_hash(text: str) -> str:
    """
    Normalize text for stable hashing.

    Normalization steps:
    - Unicode NFC normalization (canonical composition)
    - Lowercase
    - Whitespace collapsed to single spaces
    - Leading/trailing whitespace stripped

    Args:
        text: Raw text to normalize

    Returns:
        Normalized text suitable for hashing
    """
    normalized = unicodedata.normalize("NFC", text.lower().strip())
    return " ".join(normalized.split())


def compute_sha256_prefix(text: str, length: int = 16) -> str:
    """
    Compute SHA256 hash prefix of text.

    Args:
        text: Text to hash (should be pre-normalized)
        length: Number of hex characters to return (default 16)

    Returns:
        First `length` hex characters of SHA256 hash
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def normalize_and_hash(text: str, length: int = 16) -> str:
    """
    Normalize text and compute SHA256 hash prefix.

    Combines normalization and hashing for convenience.

    Args:
        text: Raw text to normalize and hash
        length: Number of hex characters to return (default 16)

    Returns:
        First `length` hex characters of SHA256 hash of normalized text
    """
    normalized = normalize_for_hash(text)
    return compute_sha256_prefix(normalized, length=length)
```

**Note**: `format_qa_for_embedding` is NOT needed as a standalone function.
`QuestionnaireItem.embedding_content` property already provides this:
```python
@property
def embedding_content(self) -> str:
    return f"Question: {self.question} Answer: {self.answer}"
```

Access via `response.item.embedding_content` on any `FollowupResponse`.

**File**: `ai_services/shared/helpers/__init__.py` (new or add to existing)

```python
from ai_services.shared.helpers.strings import (
    compute_sha256_prefix,
    normalize_and_hash,
    normalize_for_hash,
)

__all__ = [
    "compute_sha256_prefix",
    "normalize_and_hash",
    "normalize_for_hash",
]
```

---

## Tests

### Step 6: Unit Tests for String Utilities

**File**: `tests/shared/helpers/test_strings.py` (new)

```python
import pytest

from ai_services.shared.helpers.strings import (
    compute_sha256_prefix,
    normalize_and_hash,
    normalize_for_hash,
)


class TestNormalizeForHash:
    def test_basic(self):
        """Basic normalization."""
        result = normalize_for_hash("Test Text")
        assert result == "test text"

    def test_whitespace_collapse(self):
        """Collapses multiple whitespace."""
        result = normalize_for_hash("Test   \n\t  Text")
        assert result == "test text"

    def test_strip_leading_trailing(self):
        """Strips leading/trailing whitespace."""
        result = normalize_for_hash("  Test Text  ")
        assert result == "test text"

    def test_unicode_nfc(self):
        """NFC normalization for unicode."""
        # café composed vs decomposed should normalize to same
        composed = normalize_for_hash("café")
        decomposed = normalize_for_hash("cafe\u0301")
        assert composed == decomposed


class TestComputeSha256Prefix:
    def test_default_length(self):
        """Returns 16 chars by default."""
        result = compute_sha256_prefix("test")
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_custom_length(self):
        """Respects custom length parameter."""
        result = compute_sha256_prefix("test", length=8)
        assert len(result) == 8

    def test_deterministic(self):
        """Same input produces same output."""
        h1 = compute_sha256_prefix("test")
        h2 = compute_sha256_prefix("test")
        assert h1 == h2


class TestNormalizeAndHash:
    def test_basic(self):
        """Returns 16 char hex string by default."""
        result = normalize_and_hash("Test criterion")
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_custom_length(self):
        """Respects custom length parameter."""
        result = normalize_and_hash("Test criterion", length=8)
        assert len(result) == 8

    def test_whitespace_normalization(self):
        """Collapses multiple whitespace."""
        h1 = normalize_and_hash("Test  criterion")
        h2 = normalize_and_hash("Test criterion")
        assert h1 == h2

    def test_case_insensitive(self):
        """Lowercase normalization."""
        h1 = normalize_and_hash("TEST CRITERION")
        h2 = normalize_and_hash("test criterion")
        assert h1 == h2

    def test_unicode_normalization(self):
        """NFC normalization."""
        h1 = normalize_and_hash("café")
        h2 = normalize_and_hash("cafe\u0301")
        assert h1 == h2
```

### Step 7: Tests for Questionnaire Schema

**File**: `tests/shared/schema/questionnaire/test_questionnaire_schema.py` (new)

```python
class TestQuestionnaireItem:
    def test_embedding_content(self):
        item = QuestionnaireItem(question="Q?", answer="A")
        assert item.embedding_content == "Question: Q? Answer: A"

    def test_to_dto_from_dto_roundtrip(self):
        item = QuestionnaireItem(question="Q?", answer="A", notes="Note")
        dto = item.to_dto()
        recovered = QuestionnaireItem.from_dto(dto)
        assert recovered == item


class TestFollowupResponse:
    def test_external_id_format(self):
        source = FollowupQuestionnaire(
            artifact_id=UUID("12345678-1234-1234-1234-123456789012"),
            remote_key="test/path.json",
            bucket="test-bucket",
            ext=Ext.JSON,
            tenant_id="tenant1",
            vendor_id="vendor1",
            vendor_name="Vendor One",
            round_number=2,
            submitted_at=datetime(2024, 1, 1),
            job_id="job123",
        )
        item = QuestionnaireItem(question="Q?", answer="A")
        response = FollowupResponse(
            source=source,
            item=item,
            content_hash="abcdef1234567890",  # hash(criterion || question)
            criterion_question_hash="1234567890abcdef",  # hash(criterion)
            original_criterion_question_text="Original criterion",
        )
        assert response.external_id == "followup-vendor1-abcdef1234567890-round2"
        assert response.is_adhoc is False

    def test_adhoc_question(self):
        """Ad-hoc questions have no criterion."""
        source = FollowupQuestionnaire(
            artifact_id=UUID("12345678-1234-1234-1234-123456789012"),
            remote_key="test/path.json",
            bucket="test-bucket",
            ext=Ext.JSON,
            tenant_id="tenant1",
            vendor_id="vendor1",
            vendor_name="Vendor One",
            round_number=2,
            submitted_at=datetime(2024, 1, 1),
            job_id="job123",
        )
        item = QuestionnaireItem(question="Custom question?", answer="A")
        response = FollowupResponse(
            source=source,
            item=item,
            content_hash="fedcba0987654321",  # hash("" || question)
            criterion_question_hash=None,  # No criterion
            original_criterion_question_text="",  # Empty for ad-hoc
        )
        assert response.is_adhoc is True
        metadata = response.build_vellum_metadata()
        assert metadata["criterion_question_hash"] is None

    def test_build_vellum_metadata(self):
        # Verify all required fields present
        ...


class TestVellumFollowupResponse:
    def test_from_vector_db_search_result(self):
        result = VectorDbSearchResult(
            id="doc1",
            score=0.95,
            text="Question: Q? Answer: A",
            metadata={
                "tenant_id": "tenant1",
                "vendor_id": "vendor1",
                "content_hash": "abcdef1234567890",  # hash(criterion || question)
                "criterion_question_hash": "1234567890abcdef",  # hash(criterion)
                "round_number": "2",
                "question_text": "Q?",
                "answer_text": "A",
                "original_criterion_question_text": "Original",
                "timestamp": "2024-01-01T00:00:00",
                "ARTIFACT_ID": "12345678-1234-1234-1234-123456789012",
                "S3_OBJECT_KEY": "test/path.json",
                "S3_BUCKET": "test-bucket",
            },
            external_id="followup-vendor1-abcdef1234567890-round2",
        )
        response = VellumFollowupResponse.from_vector_db_search_result(result)
        assert response.vendor_id == "vendor1"
        assert response.content_hash == "abcdef1234567890"
        assert response.criterion_question_hash == "1234567890abcdef"
        assert response.round_number == 2
        assert response.is_adhoc is False

    def test_from_vector_db_search_result_adhoc(self):
        """Ad-hoc questions have no criterion_question_hash."""
        result = VectorDbSearchResult(
            id="doc1",
            score=0.95,
            text="Question: Custom? Answer: A",
            metadata={
                "tenant_id": "tenant1",
                "vendor_id": "vendor1",
                "content_hash": "fedcba0987654321",
                "criterion_question_hash": None,  # Ad-hoc
                "round_number": "2",
                "question_text": "Custom?",
                "answer_text": "A",
                "original_criterion_question_text": "",  # Empty for ad-hoc
                "timestamp": "2024-01-01T00:00:00",
                "ARTIFACT_ID": "12345678-1234-1234-1234-123456789012",
                "S3_OBJECT_KEY": "test/path.json",
                "S3_BUCKET": "test-bucket",
            },
            external_id="followup-vendor1-fedcba0987654321-round2",
        )
        response = VellumFollowupResponse.from_vector_db_search_result(result)
        assert response.criterion_question_hash is None
        assert response.is_adhoc is True

    def test_invalid_external_id_raises(self):
        result = VectorDbSearchResult(
            id="doc1",
            score=0.95,
            text="content",
            metadata={},
            external_id="invalid-format",
        )
        with pytest.raises(ValueError, match="doesn't match followup pattern"):
            VellumFollowupResponse.from_vector_db_search_result(result)
```

### Step 8: Tests for Artifact Types

**File**: `tests/shared/schema/artifact/test_artifact_schema.py` (add to existing or create)

```python
class TestFollowupQuestionnaire:
    def test_from_s3_upload(self):
        fq = FollowupQuestionnaire.from_s3_upload(
            artifact_id=UUID("12345678-1234-1234-1234-123456789012"),
            remote_key="followup/tenant1/vendor1/job123.json",
            bucket="ai-services-artifacts",
            tenant_id="tenant1",
            vendor_id="vendor1",
            vendor_name="Vendor One",
            round_number=1,
            submitted_at=datetime(2024, 1, 1),
            job_id="job123",
        )
        assert fq.ext == Ext.JSON
        assert fq.artifact_type == ArtifactType.FOLLOWUP_QUESTIONNAIRE

    def test_to_dto(self):
        # Verify DTO structure
        ...
```

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `ai_services/shared/schema/artifact/metadata.py` | Add `FOLLOWUP_QUESTIONNAIRE` to `ArtifactType` |
| `ai_services/shared/schema/artifact/schema.py` | Add `JsonData`, `TabularQuestionnaire`, `JsonQuestionnaire`, `FollowupQuestionnaire`, `Questionnaire` |
| `ai_services/shared/schema/questionnaire/__init__.py` | **New** |
| `ai_services/shared/schema/questionnaire/schema.py` | **New** |
| `ai_services/shared/schema/dto.py` | Add `QuestionnaireItemDTO`, `FollowupQuestionnaireDTO`, `FollowupResponseDTO` |
| `ai_services/shared/helpers/strings.py` | **New** - `normalize_for_hash()`, `compute_sha256_prefix()`, `normalize_and_hash()` |
| `ai_services/shared/helpers/__init__.py` | **New** or update - export string functions |
| `tests/shared/helpers/test_strings.py` | **New** - string utility tests |
| `tests/shared/schema/questionnaire/test_questionnaire_schema.py` | **New** |
| `tests/shared/schema/artifact/test_artifact_schema.py` | Add artifact type tests |

---

## Implementation Order

1. `artifact/metadata.py` - Add `FOLLOWUP_QUESTIONNAIRE` to `ArtifactType`
2. `artifact/schema.py` - Add artifact types (imports `ArtifactType`)
3. `dto.py` - Add DTOs (no dependencies on schema)
4. `helpers/strings.py` - Add string utility functions
5. `helpers/__init__.py` - Export string functions
6. `questionnaire/schema.py` - Add response types (imports artifact + dto)
7. `questionnaire/__init__.py` - Export types
8. Tests for string utilities
9. Tests for artifact types
10. Tests for questionnaire schema
11. Run `mypy`, `ruff`, full test suite

---

## Key References

- **Design document**: `.agents/claude/dev/active/follow_up_questionnaire/research/shared_types_brainstorm/analysis.md`
- **Evidence hierarchy pattern**: `ai_services/shared/schema/evidence/schema.py` (VellumDocExcerpt)
- **SOC2 generated content pattern**: `ai_services/shared/schema/artifact/documents/soc2/schema.py` (VellumSOC2SummaryTrack)
- **VectorDbSearchResult**: `ai_services/shared/vectordb/vectordb_search_result.py`

---

## Notes

- `Ext.JSON` already exists in the codebase
- `Tabular` class exists but is UNUSED - can be modified freely
- `QuestionnaireAnswer` in evidence/schema.py is UNUSED - will be superseded by `QuestionnaireResponse`
- The union type `Questionnaire = TabularQuestionnaire | JsonQuestionnaire` enables polymorphic handling
- Factory method `from_vector_db_search_result()` follows established pattern from `VellumDocExcerpt`
