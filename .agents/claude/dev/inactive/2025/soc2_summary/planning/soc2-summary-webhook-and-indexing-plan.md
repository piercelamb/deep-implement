# SOC2 Summary Webhook and Indexing Plan

## Overview

This document outlines the plan for completing the SOC2 summary workflow with two key capabilities:
1. **Webhook notifications** - Two-stage notification to the caller
2. **Summary indexing** - Index each summary track into a Vellum document index for semantic search

### Two-Webhook Flow

The workflow sends **two webhooks** to provide immediate results while also notifying when indexing completes:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SOC2 Summary Workflow                          │
├─────────────────────────────────────────────────────────────────────┤
│  1. Execute summary_soc2_activity (Vellum processing)               │
│                         ↓                                           │
│  2. Upload JSON to S3 (for drata runs)                              │
│                         ↓                                           │
│  3. ══════════════════════════════════════════════════════════════  │
│     WEBHOOK #1: status=SUMMARIZED, includes full summary payload    │
│     ══════════════════════════════════════════════════════════════  │
│                         ↓                                           │
│  4. Index summary tracks to Vellum (5 documents)                    │
│                         ↓                                           │
│  5. ══════════════════════════════════════════════════════════════  │
│     WEBHOOK #2: status=INDEXED (no payload, just notification)      │
│     ══════════════════════════════════════════════════════════════  │
└─────────────────────────────────────────────────────────────────────┘
```

**Benefits:**
- Caller receives summary immediately without waiting for indexing
- Caller is notified when document is searchable
- If indexing fails, caller still has the summary
- Clear separation of concerns (processing vs. indexing)

## Current State

### Completed Work

1. **Naming refactor** - Reverted `SOCType2` → `SOC2` naming across codebase
2. **Schema updates** - `SOC2ProcessingResult` and related types in `ai_services/shared/schema/artifact/documents/soc2/schema.py`
3. **Webhook activity logging** - Updated `send_soc2_summary_webhook_activity.py` to log at ERROR level for failures, INFO for success (matching `send_document_created_webhook_activity.py` pattern)
4. **Unused imports cleanup** - Removed 27 unused imports from workflow/support files

### Key Files

| File | Purpose |
|------|---------|
| `ai_services/temporal_workers/workflows/vrm/summary_soc2_workflow_v1.py` | Main workflow orchestration |
| `ai_services/temporal_workers/activities/vellum/summary_soc2_activity.py` | Calls Vellum SOC2 summary workflow |
| `ai_services/temporal_workers/activities/vrm/send_soc2_summary_webhook_activity.py` | Sends webhook to Drata API |
| `ai_services/shared/schema/artifact/documents/soc2/schema.py` | Domain models for SOC2 processing |
| `ai_services/shared/schema/dto.py` | DTO types for serialization |

## Part 1: Webhook Flow


### Webhook #1: SUMMARIZED

Sent immediately after summary processing completes, before indexing begins.

**Payload:**
```python
{
    "status": "SUCCESS",
    "jobId": "...",
    "tenantId": "...",
    "tenantName": "...",
    "summary": { ... }  # Full summary from to_webhook_dto()
}
```

### Webhook #2: INDEXED

Sent after all 5 summary tracks are successfully indexed to Vellum.

**Payload:**
```python
{
    "status": "SUCCESS",
    "jobId": "...",
    "tenantId": "...",
    "tenantName": "...",
    # No summary payload - caller already has it from SUMMARIZED webhook
}
```

### Webhook #3: FAILURE (on error)

Sent if any step fails. Includes error details.

**Payload:**
```python
{
    "status": "FAILURE",
    "jobId": "...",
    "tenantId": "...",
    "tenantName": "...",
    "error": {"message": "..."}
}
```

### Webhook Activity (Existing)

The existing `send_soc2_summary_webhook_activity.py` already supports all these cases:

```python
# send_soc2_summary_webhook_activity.py
if input.error_message:
    payload["error"] = {"message": input.error_message}
    activity.logger.error(
        "Sending VRM SOC2 summary webhook with error information",
        extra={...}
    )
else:
    activity.logger.info(
        "Sending VRM SOC2 summary webhook",
        extra={...}
    )
```

### Remaining Webhook Work

- [ ] Verify `to_webhook_dto()` output format matches Drata API expectations
- [ ] Coordinate with Drata API team on new status values
- [ ] Integration testing with Drata API

## Part 2: Summary Indexing Flow

### Goal

Index each SOC2 summary track as a separate searchable document in the Vellum document index, enabling semantic search over:
- Overview information (company name, auditor, scope, time period, etc.)
- Exceptions and their details
- Management responses
- Auditor opinion
- CUECs (Complementary User Entity Controls)

### Architecture Decision: Upload Method

**Chosen approach: In-memory file upload to Vellum**

Rather than:
- ❌ Calling our own API endpoint (unnecessary HTTP hop)
- ❌ Using `CreateVellumDocumentWorkflowV1` (designed for PDF files, sends webhooks)
- ❌ Uploading to S3 first then indexing (extra round-trip)

We will:
- ✅ Create text content in-memory
- ✅ Upload directly to Vellum using `io.BytesIO` wrapper
- ✅ Reuse existing activities where applicable
- ✅ If there are activities i cannot use, I will abstract/generalize code that can be reused between them and this activity

### Architecture Decision: Search Result Type for Indexed Summaries

**Problem:** When searching the indexed summary tracks, the results cannot use `VellumDocExcerpt` because:

1. **External ID format incompatibility:**
   - `VellumDocExcerpt.external_id_re` expects: `{uuid}--{TYPE}--{integer}` (double-dash separators)
   - Summary tracks use: `{tenant_id}-{doc_id}-{track_name}` (single-dash, different structure)

2. **Metadata structure mismatch:**
   - `VellumDocExcerpt` expects: `FILENAME`, `MIME_TYPE`, `S3_BUCKET`, `S3_OBJECT_KEY`
   - Summary tracks have: `type`, `track`, `tenant_id`, `vendor_id`, `source_document_id`, `refs`

3. **Source concept differs:**
   - `VellumDocExcerpt`: chunk extracted directly from an uploaded document (PDF)
   - Summary track: AI-generated summary text derived from document analysis

4. **Page numbers don't apply:**
   - `VellumDocExcerpt.page_num`: references specific page in source document
   - Summary tracks: generated content with no meaningful page reference

**Chosen approach: Parallel type hierarchies with shared `Excerpt` base**

Rather than:
- ❌ Forcing summary data into `VellumDocExcerpt` (would require faking metadata, breaking regex parsing)
- ❌ Making `VellumDocExcerpt` polymorphic (adds complexity, confuses intent)
- ❌ Inheriting from `RankedDocExcerpt` (forces `source: Document` and `page_num` which don't fit)

We will:
- ✅ Create a new `Excerpt` base class that captures shared fields (`content`, `content_hash`)
- ✅ Create parallel branches: `DocExcerpt` (direct extraction) and `GeneratedExcerpt` (AI-synthesized)
- ✅ Both branches inherit from `Excerpt`, making the shared structure explicit
- ✅ Keep ranking scores in separate classes (acceptable duplication for semantic clarity)
- ✅ Existing code unchanged - `DocExcerpt` just inherits `content`/`content_hash` from parent instead of defining directly

**Conceptual model - two types of evidence:**

| Aspect | Extracted (DocExcerpt) | Generated (GeneratedExcerpt) |
|--------|------------------------|------------------------------|
| Relationship | "This text exists at page 47" | "This text was synthesized from pages 5, 12, 47" |
| Location | Single, specific | Multiple, aggregated |
| Fidelity | Verbatim from source | Interpreted/summarized |
| Provenance | Direct pointer (`source`, `page_num`) | Chain of references (`source_refs`) |

**Type hierarchy:**
```
Reference (source: Artifact)
    │
    └── SourcedContent (content, content_hash)  ← shared base
            │
            ├── DocExcerpt (source: Document, page_num)
            │       └── RankedDocExcerpt (scores)
            │               └── VellumDocExcerpt
            │
            └── GeneratedContent (source_refs)
                    └── RankedGeneratedContent (scores)
                            └── VellumGeneratedContent (tenant_id, metadata)  ← generic base for Vellum
                                    │
                                    └── VellumSOC2SummaryContent (track, vendor_id, source_document_external_id)
                                            ↑ Lives in soc2/schema.py, uses SOC2SummaryTracks enum
```

**Type definitions:**

```python
# ai_services/shared/schema/evidence/schema.py

@dataclass(frozen=True, slots=True, kw_only=True)
class SourcedContent(Reference):
    """Base class for text content with provenance back to source documents."""
    content: str
    content_hash: str

@dataclass(frozen=True, slots=True, kw_only=True)
class GeneratedContent(SourcedContent):
    """Content generated/synthesized from analyzing a document."""
    source_refs: Sequence[DocExcerpt]

@dataclass(frozen=True, slots=True, kw_only=True)
class RankedGeneratedContent(GeneratedContent):
    """GeneratedContent with search ranking scores."""
    first_stage_score: float
    second_stage_score: float | None = None
    third_stage_score: float | None = None

@dataclass(frozen=True, slots=True, kw_only=True)
class VellumGeneratedContent(RankedGeneratedContent):
    """Generic base for AI-generated content indexed in Vellum."""
    tenant_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


# ai_services/shared/schema/artifact/documents/soc2/schema.py

class SOC2SummaryTracks(StrEnum):
    """Tracks for SOC2 summary workflow - single source of truth."""
    OVERVIEW = "overview"
    EXCEPTIONS = "exceptions"
    MANAGEMENT_RESPONSES = "management_responses"
    OPINION = "opinion"
    CUEC = "cuec"

@dataclass(frozen=True, slots=True, kw_only=True)
class VellumSOC2SummaryContent(VellumGeneratedContent):
    """Generated SOC2 summary track retrieved from Vellum search.

    External ID format: {source_document_external_id}--{TRACK_SUFFIX}
    Example: 27969e48-...-5c1c95f6c758--VENDORASSESSMENTDOCUMENT--22--SOC2SUMMARYOVERVIEW
    """
    track: SOC2SummaryTracks  # Uses the enum, not string
    vendor_id: str
    source_document_external_id: str

    # Maps between enum and external ID suffix
    ENUM_TO_TRACK_SUFFIX: ClassVar[dict[SOC2SummaryTracks, str]] = {
        SOC2SummaryTracks.OVERVIEW: "SOC2SUMMARYOVERVIEW",
        SOC2SummaryTracks.EXCEPTIONS: "SOC2SUMMARYEXCEPTIONS",
        # ... etc
    }

    @classmethod
    def build_external_id(cls, source_document_external_id: str, track: SOC2SummaryTracks) -> str:
        """Build external ID for indexing a SOC2 summary track."""
        return f"{source_document_external_id}--{cls.ENUM_TO_TRACK_SUFFIX[track]}"

    @classmethod
    def build_metadata_type(cls, track: SOC2SummaryTracks) -> str:
        """Build metadata type field value."""
        return f"soc2_summary:{track.value}"
```

**Key design decisions:**

1. **`VellumGeneratedContent` is generic** - contains only Vellum-specific fields (`tenant_id`, `metadata`)
2. **`VellumSOC2SummaryContent` is SOC2-specific** - lives in `soc2/schema.py` with other SOC2 types
3. **`SOC2SummaryTracks` enum is the single source of truth** - used for track values everywhere
4. **Helper methods for external ID and metadata type** - `build_external_id()` and `build_metadata_type()` ensure consistent formatting

**Benefits:**
- **Shared structure is explicit**: `SourcedContent` base makes it clear what extracted and generated content have in common
- **Semantic clarity**: readers immediately understand which track they're in
- **Backward compatible**: existing `DocExcerpt` code unchanged (fields just inherited now)
- **Future-proof**: pattern scales to other generated content types (control assessments, Q&A, etc.)
- **Type safety**: can't accidentally mix extracted and generated content

**Files modified:**
- `ai_services/shared/schema/evidence/schema.py`:
  - ✅ Added `SourcedContent` base class with shared `content` and `content_hash`
  - ✅ Modified `DocExcerpt` to inherit from `SourcedContent` (backward compatible)
  - ✅ Added `GeneratedContent`, `RankedGeneratedContent`, `VellumGeneratedContent` classes
- `ai_services/shared/schema/artifact/documents/soc2/schema.py`:
  - ✅ Added `VellumSOC2SummaryContent` inheriting from `VellumGeneratedContent`
  - ✅ Uses `SOC2SummaryTracks` enum for track values
  - ✅ Helper methods: `build_external_id()` and `build_metadata_type()`
- `ai_services/shared/schema/dto.py`:
  - ✅ Added `SOC2SummaryExcerptDTO` TypedDict

### Vellum Upload Document API

**Endpoint:** `POST https://documents.vellum.ai/v1/upload-document`

**Key fields:**
- `label` (required) - Document identifier
- `contents` (required) - File content (can use `io.BytesIO` for text)
- `add_to_index_names` - Index to add document to
- `external_id` - External reference ID
- `metadata` - Additional searchable metadata

**Python SDK usage:**
```python
import io
from vellum import Vellum

client = Vellum(api_key="...")
file_content = io.BytesIO(text_content.encode('utf-8'))

response = client.documents.upload(
    label="soc2-summary-overview-{doc_id}",
    contents=file_content,
    add_to_index_names=[index_id],
    # doc_external_id is the source document's external ID
    # e.g., "27969e48-...-5c1c95f6c758--VENDORASSESSMENTDOCUMENT--22"
    external_id=f"{doc_external_id}--SOC2SUMMARYOVERVIEW",
    metadata={"type": "soc2_summary:overview", "tenant_id": tenant_id},
)
```

### Component Design

#### Reusable from Existing Workflows

| Component | Location | Reuse Strategy |
|-----------|----------|----------------|
| `assert_index_exists_activity` | `activities/vellum/` | Direct reuse - validates index exists |
| `get_vellum_document_activity` | `activities/vellum/` | Direct reuse - checks document existence, polls status |
| `VellumVectorDb` client setup | `shared/vectordb/vellum/` | Reference for Vellum client patterns |

#### New Components Needed

**1. `upload_text_content_activity`**

```python
# ai_services/temporal_workers/activities/vellum/upload_text_content_activity.py

from ai_services.shared.schema.dto import EvidenceRefDTO

@dataclass(frozen=True, slots=True, kw_only=True)
class UploadTextContentActivityInput:
    """Input for uploading text content to Vellum."""
    index_id: str
    external_id: str
    label: str
    content: str  # The text to index
    metadata: dict[str, Any] | None = None
    # Source references - serialized EvidenceRefDTO list
    refs: Sequence[EvidenceRefDTO] | None = None
    tenant_id: str
    tenant_name: str

@dataclass(frozen=True, slots=True, kw_only=True)
class UploadTextContentActivityOutput:
    """Output from uploading text content."""
    document_id: str

@activity.defn
def upload_text_content_activity(
    input: UploadTextContentActivityInput,
) -> UploadTextContentActivityOutput:
    """Upload text content to Vellum document index."""
    client = get_vellum_client()

    file_content = io.BytesIO(input.content.encode('utf-8'))

    # Build metadata with refs
    metadata = dict(input.metadata) if input.metadata else {}
    if input.refs:
        # Serialize refs as JSON string if Vellum doesn't support nested objects
        metadata["refs"] = json.dumps(input.refs)

    response = client.documents.upload(
        label=input.label,
        contents=file_content,
        add_to_index_names=[input.index_id],
        external_id=input.external_id,
        metadata=metadata,
    )

    return UploadTextContentActivityOutput(document_id=response.document_id)
```

**2. Summary Track Text Formatters**

Functions to convert each summary track to searchable text:

```python
# ai_services/temporal_workers/helpers/soc2_summary_formatters.py

def format_overview_for_indexing(overview: OverviewSOC2Evidence) -> str:
    """Format overview track for semantic indexing."""
    parts = []
    if overview.company_name:
        parts.append(f"Company: {overview.company_name}")
    if overview.auditor_name:
        parts.append(f"Auditor: {overview.auditor_name}")
    if overview.scope:
        parts.append(f"Scope: {overview.scope}")
    # ... etc
    return "\n".join(parts)

def format_exceptions_for_indexing(exceptions: ExceptionsSOC2Evidence) -> str:
    """Format exceptions track for semantic indexing."""
    ...

def format_opinion_for_indexing(opinion: OpinionSOC2Evidence) -> str:
    """Format opinion track for semantic indexing."""
    ...

def format_cuec_for_indexing(cuec: CUECEvidenceSOC2) -> str:
    """Format CUECs for semantic indexing."""
    ...

def format_management_responses_for_indexing(
    responses: ManagementResponsesSOC2Evidence
) -> str:
    """Format management responses for semantic indexing."""
    ...
```

### Document Structure

Each SOC2 summary will be indexed as **5 separate documents** (one per track):

**External ID Format:**
```
{source_document_external_id}--{TRACK}
```

Where `source_document_external_id` follows the VellumDocExcerpt format:
```
{tenant_id}--{DOC_TYPE}--{primary_key}
```

Full example:
```
27969e48-000d-4a31-8673-5c1c95f6c758--VENDORASSESSMENTDOCUMENT--22--SOC2SUMMARYOVERVIEW
```

| Track | External ID Suffix | Metadata Type | Content |
|-------|-------------------|---------------|---------|
| Overview | `SOC2SUMMARYOVERVIEW` | `soc2_summary:overview` | Company, auditor, scope, time period, criteria |
| Exceptions | `SOC2SUMMARYEXCEPTIONS` | `soc2_summary:exceptions` | Exception details, control IDs, test results |
| Management Responses | `SOC2SUMMARYMANAGEMENTRESPONSES` | `soc2_summary:management_responses` | Response text, related criteria |
| Opinion | `SOC2SUMMARYOPINION` | `soc2_summary:opinion` | Opinion type, text, qualifications |
| CUECs | `SOC2SUMMARYCUEC` | `soc2_summary:cuec` | Control text, related criteria |

### Source References (refs)

**Critical requirement:** Each Evidence type contains a `refs: Sequence[VellumDocExcerpt]` field that tracks the source excerpts used to generate that track. This provenance information must be included in the indexed document metadata.

**Evidence types and their refs:**
- `OverviewSOC2Evidence.refs` → sources for overview extraction
- `ExceptionsSOC2Evidence.refs` → sources for exception identification
- `ManagementResponsesSOC2Evidence.refs` → sources for management responses
- `OpinionSOC2Evidence.refs` → sources for auditor opinion
- `CUECEvidenceSOC2.refs` → sources for CUEC extraction

**VellumDocExcerpt structure:**
```python
@dataclass
class VellumDocExcerpt:
    source: Document           # The source document
    page_num: int | None       # Page number in source
    content: str               # The excerpt text
    content_hash: str          # For deduplication
    first_stage_score: float   # Retrieval relevance score
    account_id: UUID
    primary_key: int
    doc_type: str
    metadata: Mapping[str, Any]  # Source document metadata
```

**Metadata for each indexed document:**
```python
{
    "type": "soc2_summary",
    "track": "overview|exceptions|management_responses|opinion|cuec",
    "tenant_id": "<tenant_id>",
    "vendor_id": "<vendor_id>",
    "source_document_id": "<original_doc_id>",
    # Source references for this track (uses existing EvidenceRefDTO structure)
    "refs": [
        {
            "source": {
                "artifact_id": "...",
                "remote_key": "...",
                "bucket": "...",
                "ext": "pdf",
                "pages": [5, 6, 7]
            },
            "page_num": 5,
            "content": "excerpt text...",
            "content_hash": "abc123...",
            "first_stage_score": 0.95,
            "second_stage_score": null,
            "third_stage_score": null,
            "account_id": "...",
            "primary_key": 123,
            "doc_type": "soc2_report",
            "metadata": {
                "type": "soc2_report",
                "FILENAME": "vendor_soc2.pdf",
                "MIME_TYPE": "application/pdf",
                "S3_BUCKET": "...",
                "S3_OBJECT_KEY": "..."
            }
        },
        # ... more refs
    ]
}
```

**Note:** The `refs` field is a list of VellumDocExcerpt and may need to be serialized as JSON string if Vellum metadata doesn't support nested objects. We'll need to test this.

### Workflow Integration

Update `summary_soc2_workflow_v1.py` with the two-webhook flow:

```python
@workflow.run
async def run(self, input: Soc2SummaryWorkflowInputV1) -> None:
    try:
        # 1. Execute Vellum summary processing
        summary_dto = await workflow.execute_activity(
            summary_soc2_activity,
            args=[Soc2SummaryActivityInput(...)],
            ...
        )

        processing_result = SOC2ProcessingResult.from_dto(summary_dto)

        # 2. Upload to S3 (for drata runs)
        if input.source.drata_run:
            await workflow.execute_activity(upload_to_s3, ...)
            workflow.logger.info(f"[{input.tenant_name}] Stored SOC2 summary outputs to S3")

        # 3. WEBHOOK #1: SUMMARIZED - Send summary immediately
        await self._send_webhook(
            input,
            status=WebhookStatus.SUMMARIZED,
            summary=processing_result.to_webhook_dto(),
        )

        # 4. Index summary tracks (only if summary exists)
        if processing_result.summary is not None:
            await self._index_summary_tracks(
                input=input,
                summary=processing_result.summary,
            )

            # 5. WEBHOOK #2: INDEXED - Notify indexing complete
            await self._send_webhook(
                input,
                status=WebhookStatus.INDEXED,
                summary=None,  # No payload needed
            )

        workflow.logger.info(f"[{input.tenant_name}] Completed SOC2 Summary workflow")

    except TEMPORAL_ERRORS as exc:
        # WEBHOOK: FAILURE
        await self._send_webhook(
            input,
            status=WebhookStatus.FAILURE,
            summary=None,
            error_message=str(exc),
        )
        raise

async def _index_summary_tracks(
    self,
    input: Soc2SummaryWorkflowInputV1,
    summary: SummarizedSOC2,
) -> None:
    """Index each summary track into the document index."""

    # Validate index exists
    await workflow.execute_activity(
        assert_index_exists_activity,
        AssertIndexExistsActivityInput(index_id=input.document_index_id),
        start_to_close_timeout=timedelta(seconds=30),
        retry_policy=get_retry_policy(RetryKind.VELLUM_API),
    )

    # Use SOC2SummaryTracks enum and VellumSOC2SummaryContent helpers
    from ai_services.shared.schema.artifact.documents.soc2.schema import (
        SOC2SummaryTracks,
        VellumSOC2SummaryContent,
    )

    # Build track tuples: (track, content, refs)
    # Each Evidence type has a refs field with source excerpts
    tracks: list[tuple[SOC2SummaryTracks, str | None, list[EvidenceRefDTO] | None]] = [
        (
            SOC2SummaryTracks.OVERVIEW,
            format_overview_for_indexing(summary.overview),
            _convert_refs_to_dto(summary.overview.refs) if summary.overview else None,
        ),
        (
            SOC2SummaryTracks.EXCEPTIONS,
            format_exceptions_for_indexing(summary.exceptions),
            _convert_refs_to_dto(summary.exceptions.refs) if summary.exceptions else None,
        ),
        (
            SOC2SummaryTracks.MANAGEMENT_RESPONSES,
            format_management_responses_for_indexing(summary.management_responses),
            _convert_refs_to_dto(summary.management_responses.refs) if summary.management_responses else None,
        ),
        (
            SOC2SummaryTracks.OPINION,
            format_opinion_for_indexing(summary.opinion),
            _convert_refs_to_dto(summary.opinion.refs) if summary.opinion else None,
        ),
        (
            SOC2SummaryTracks.CUEC,
            format_cuec_for_indexing(summary.cuec),
            _convert_refs_to_dto(summary.cuec.refs) if summary.cuec else None,
        ),
    ]

    for track, content, refs in tracks:
        if content:  # Only index non-empty tracks
            # Use helper methods for consistent external ID and metadata type
            # input.document_id IS the source document's external ID
            # e.g., "27969e48-...-5c1c95f6c758--VENDORASSESSMENTDOCUMENT--22"
            external_id = VellumSOC2SummaryContent.build_external_id(input.document_id, track)
            metadata_type = VellumSOC2SummaryContent.build_metadata_type(track)

            await workflow.execute_activity(
                upload_text_content_activity,
                UploadTextContentActivityInput(
                    index_id=input.document_index_id,
                    external_id=external_id,
                    label=f"soc2-{track.value}-{input.document_id}",
                    content=content,
                    metadata={
                        "type": metadata_type,
                        "tenant_id": input.tenant_id,
                        "vendorId": input.vendor_id,
                    },
                    refs=refs,  # Pass source references for this track
                    tenant_id=input.tenant_id,
                    tenant_name=input.tenant_name,
                ),
                task_queue=settings.task_queue_vellum,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=get_retry_policy(RetryKind.VELLUM_API),
            )


def _convert_refs_to_dto(refs: Sequence[VellumDocExcerpt] | None) -> list[EvidenceRefDTO] | None:
    """Convert VellumDocExcerpt sequence to serializable DTOs.

    Note: EvidenceRefDTO and EvidenceSourceDTO already exist in
    ai_services/shared/schema/dto.py - we reuse those types.
    """
    if not refs:
        return None
    return [ref.to_dto() for ref in refs]  # VellumDocExcerpt.to_dto() returns EvidenceRefDTO
```

### Polling for Indexing Completion (Required for INDEXED webhook)

Since we send an INDEXED webhook after indexing completes, we need to wait for all documents to be indexed before sending it. We can reuse `get_vellum_document_activity` to poll each document's status. This follows the pattern in `create_vellum_document_workflow_v1.py`.

**Flow for each track:**
1. Upload text content via `upload_text_content_activity` → returns `document_id`
2. Poll via `get_vellum_document_activity` until status is `ACTIVE`
3. After all 5 tracks are `ACTIVE`, send INDEXED webhook

```python
async def _index_summary_tracks(self, input, summary) -> bool:
    """Index each summary track. Returns True if all tracks indexed successfully."""

    # ... upload tracks ...

    # Poll for each document to be indexed
    for doc_id in uploaded_doc_ids:
        document = await workflow.execute_activity(
            get_vellum_document_activity,
            GetVellumDocumentActivityInput(document_id=doc_id),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=get_retry_policy(RetryKind.VELLUM_API),
        )
        if document.status != "ACTIVE":
            workflow.logger.error(f"Document {doc_id} failed to index: {document.status}")
            return False

    return True  # All tracks indexed successfully
```

## Implementation Phases

### Phase 0: Webhook Status Update (Priority: Highest)

1. Add `SUMMARIZED` and `INDEXED` to `WebhookStatus` enum
2. Coordinate with Drata API team on new status values
3. Ensure backwards compatibility (keep `SUCCESS` for now)

**Files to modify:**
- `ai_services/temporal_workers/workflows/vrm/shared.py`

### Phase 1: Schema Types for Summary Search Results (Priority: High) ✅ COMPLETED

1. ✅ Add `SourcedContent` base class (shared `content`, `content_hash`)
2. ✅ Refactor `DocExcerpt` to inherit from `SourcedContent` (backward compatible)
3. ✅ Add `GeneratedContent`, `RankedGeneratedContent`, `VellumGeneratedContent` classes in `evidence/schema.py`
4. ✅ Add `VellumSOC2SummaryContent` in `soc2/schema.py` (uses `SOC2SummaryTracks` enum)
5. ✅ Add `SOC2SummaryExcerptDTO` TypedDict in `dto.py`
6. ✅ Verify existing tests still pass (867 passed)

**Files modified:**
- `ai_services/shared/schema/evidence/schema.py`:
  - Added `SourcedContent` base class
  - Modified `DocExcerpt` to inherit from `SourcedContent`
  - Added `GeneratedContent`, `RankedGeneratedContent`, `VellumGeneratedContent`
- `ai_services/shared/schema/artifact/documents/soc2/schema.py`:
  - Added `VellumSOC2SummaryContent` (inherits `VellumGeneratedContent`)
  - Uses existing `SOC2SummaryTracks` enum for track values
  - Includes `build_external_id()` and `build_metadata_type()` helper methods
- `ai_services/shared/schema/dto.py` - Added `SOC2SummaryExcerptDTO` TypedDict

### Phase 2: Core Indexing Activity (Priority: High)

1. Create `upload_text_content_activity.py`
2. Create `soc2_summary_formatters.py` with track formatters
3. Write unit tests for formatters
4. Write unit tests for activity

**Files to create:**
- `ai_services/temporal_workers/activities/vellum/upload_text_content_activity.py`
- `ai_services/temporal_workers/helpers/soc2_summary_formatters.py`
- `tests/temporal_workers/activities/vellum/test_upload_text_content_activity.py`
- `tests/temporal_workers/helpers/test_soc2_summary_formatters.py`

### Phase 3: Workflow Integration (Priority: High)

1. Update workflow to use two-webhook flow:
   - Send SUMMARIZED webhook after processing
   - Index tracks
   - Send INDEXED webhook after indexing
2. Add `_index_summary_tracks` method to workflow
3. Import and register new activity in worker
4. Write workflow integration tests

**Files to modify:**
- `ai_services/temporal_workers/workflows/vrm/summary_soc2_workflow_v1.py`
- `ai_services/temporal_workers/workers/vellum_worker.py` (register activity)

### Phase 4: Error Handling & Observability (Priority: Medium)

1. Add error handling for indexing failures (log, skip INDEXED webhook)
2. Add structured logging for indexing operations
3. Add metrics/traces for indexing duration

### Phase 5: Polling & Verification (Priority: Medium)

1. Add polling to wait for each document's indexing completion
2. Use `get_vellum_document_activity` to check document status
3. Only send INDEXED webhook once all 5 tracks are confirmed indexed

## Success Criteria

1. ✅ Webhook activity logs at appropriate level (ERROR for failures, INFO for success)
2. ⬜ `WebhookStatus` enum includes `SUMMARIZED` and `INDEXED` statuses
3. ⬜ Webhook #1 (SUMMARIZED) sends `to_webhook_dto()` format immediately after processing
4. ⬜ Webhook #2 (INDEXED) sends after all tracks are indexed
5. ⬜ Each summary track is indexed as a separate Vellum document
6. ⬜ Indexed documents have correct metadata for filtering
7. ⬜ Indexed documents are semantically searchable
8. ⬜ Indexing failures don't fail the overall workflow (SUMMARIZED webhook already sent)
9. ⬜ `VellumSummaryExcerpt` type correctly parses search results from indexed summaries
10. ⬜ All new code has unit test coverage

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Vellum rate limiting on bulk uploads | Medium | Sequential uploads with retry policy |
| Large summary text exceeds limits | Low | Truncate/split if needed |
| Drata API not ready for new statuses | High | Coordinate with API team before deploying; keep SUCCESS as fallback |
| Indexing fails after SUMMARIZED sent | Low | Caller already has summary; log failure, skip INDEXED webhook |
| Document ID collisions | Medium | Use deterministic `{tenant}-{doc}-{track}` pattern |
| Partial indexing success | Medium | Only send INDEXED if all 5 tracks succeed |

## Dependencies

- Vellum Python SDK (`vellum-ai`)
- Existing Temporal infrastructure
- Existing Vellum activities (`assert_index_exists_activity`, `get_vellum_document_activity`)

## Testing Strategy

1. **Unit tests** - Formatters, activity logic with mocked Vellum client
2. **Integration tests** - Workflow with mocked activities
3. **E2E tests** - Full flow against Vellum sandbox
4. **Manual verification** - Search indexed content in Vellum UI

## Open Questions

1. ~~Should indexing failures fail the overall workflow, or just log and continue?~~
   - **Resolved:** With two-webhook flow, SUMMARIZED webhook is already sent before indexing.
   - If indexing fails, we can either: (a) skip INDEXED webhook, (b) send FAILURE webhook, or (c) log and don't send INDEXED.
   - **Recommendation:** Log the failure and don't send INDEXED webhook. Caller already has summary.

2. ~~Do we need to poll for indexing completion before sending webhook?~~
   - **Resolved:** Yes, we should wait for indexing to complete before sending INDEXED webhook.
   - Use `get_vellum_document_activity` to poll each document's status.

3. Should we delete existing indexed documents before re-indexing?
   - **Recommendation:** Use deterministic external_ids - Vellum may handle upsert

4. What's the maximum text size Vellum accepts?
   - **Action:** Test with large summaries, add truncation if needed

5. **NEW:** What if indexing partially succeeds (some tracks indexed, some fail)?
   - **Options:** (a) Send INDEXED only if all succeed, (b) Send INDEXED with partial status
   - **Recommendation:** Only send INDEXED if all 5 tracks succeed. Log failures for individual tracks.

6. **NEW:** Should we coordinate the new webhook statuses with Drata API team first?
   - **Recommendation:** Yes - ensure they can handle SUMMARIZED and INDEXED statuses before deploying

7. ~~How should we handle search results from indexed summary tracks?~~
   - **Resolved:** Create parallel type hierarchies with a shared `Excerpt` base class.
   - `VellumDocExcerpt` is incompatible due to: external_id regex format, required metadata fields (`FILENAME`, `S3_*`), and semantic mismatch (document chunk vs generated summary).
   - New hierarchy: `Reference` → `Excerpt` → `GeneratedExcerpt` → `RankedGeneratedExcerpt` → `VellumSummaryExcerpt`
   - `Excerpt` base captures shared fields (`content`, `content_hash`) between extracted and generated content.
   - This models the fundamental concept: evidence from documents comes in two forms (extracted vs generated).
