# Plan: Guard S3 Upload in Create Vellum Document Workflow

## Problem

Current flow downloads file twice:
1. `download_file_and_upload_to_s3_activity`: presigned URL → S3
2. `create_vellum_document_activity`: S3 → Vellum

This prevents proper guarding of S3 uploads based on `ExecutionSource`.

## Solution

Create a combined activity that downloads once and uploads to both destinations, with S3 upload conditional on `source.drata_run`.

## Design Decisions

### Activity Organization: Single Combined Activity

**Rationale:**
- Both existing activities are ONLY used in `create_vellum_document_workflow_v1.py`
- Temporal payload limits prevent passing large binary data between activities
- Single activity = single download, simpler orchestration

### Sequential Uploads (S3 first, then Vellum)

**Rationale:**
- S3 upload is conditional (`drata_run`), so parallelism doesn't always help
- If S3 fails in production, fail fast before consuming Vellum API quota
- Simpler error handling and retry semantics
- BytesIO seeking is straightforward between sequential operations

### Error Handling

- Use existing `raise_temporal_http_error()` for download/S3 errors
- Use existing `_raise_vellum_error()` for Vellum errors
- Both preserve retry semantics (4xx except 429 = non-retryable)

### Idempotency

- S3 PUT to same key is naturally idempotent
- Vellum uses `external_id` - workflow already checks for existing docs
- On retry: re-downloads, re-uploads to S3 (safe), retries Vellum

## Files to Modify

### 1. NEW: `ai_services/temporal_workers/activities/vellum/download_and_upload_document_activity.py`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class DownloadAndUploadDocumentActivityInput:
    source_url: str
    source: ExecutionSource
    bucket: str
    remote_key: str
    external_id: str
    filename: str
    tenant_id: str
    tenant_name: str
    index_id: str
    content_type: str | None = None
    metadata: dict[str, str] | None = None

@dataclass(frozen=True, slots=True, kw_only=True)
class DownloadAndUploadDocumentActivityOutput:
    document_id: str
    bucket: str
    remote_key: str
```

Logic:
1. Download file to `BytesIO` using `requests.get(stream=True)`
2. If `source.drata_run`: upload to S3, then `buffer.seek(0)`
3. Else: log skip message
4. Always: `buffer.seek(0)`, upload to Vellum
5. Metadata always includes `S3_BUCKET` and `S3_OBJECT_KEY`

### 2. MODIFY: `ai_services/temporal_workers/workflows/vellum/create_vellum_document_workflow_v1.py`

Replace lines 127-152 (two activity calls) with single call:

```python
# Before: download_file_and_upload_to_s3 + create_vellum_document_activity
# After:
document = await workflow.execute_activity(
    download_and_upload_document_activity,
    DownloadAndUploadDocumentActivityInput(
        source_url=input.s3_url,
        source=input.source,
        bucket=settings.aws_s3_bucket,
        remote_key=remote_key,
        external_id=input.external_id,
        filename=input.filename,
        tenant_id=input.tenant_id,
        tenant_name=input.tenant_name,
        index_id=input.index_id,
        metadata=input.metadata,
    ),
    start_to_close_timeout=timedelta(minutes=5),
    retry_policy=get_retry_policy(RetryKind.S3),  # Most restrictive
)
```

Update imports accordingly.

### 3. MODIFY: `ai_services/temporal_workers/workers/main_worker.py`

- Add import for `download_and_upload_document_activity`
- Add to `activities=[]` list
- Keep old activities for now (in-flight workflow compatibility)

## Implementation Steps

1. Create new activity file with input/output dataclasses and implementation
2. Update workflow to use new activity (single call replaces two)
3. Update worker registration
4. Add unit tests for new activity
5. Update workflow integration tests
6. Verify with local test run (`ExecutionSource.LOCAL` should skip S3)
7. After deployment + no in-flight old workflows: remove old activities

## Testing

### New Activity Tests

| Scenario | Expected |
|----------|----------|
| `drata_run=True` | Downloads, uploads S3, uploads Vellum |
| `drata_run=False` | Downloads, skips S3 (logs), uploads Vellum |
| Download HTTP 4xx | non-retryable ApplicationError |
| Download HTTP 5xx/429 | retryable ApplicationError |
| S3 failure | retryable ApplicationError |
| Vellum 4xx | non-retryable ApplicationError |
| Vellum 5xx/429 | retryable ApplicationError |
| Metadata always has S3 keys | Even when S3 upload skipped |

### Workflow Tests

- Update mocks to use new activity
- Verify `ExecutionSource.LOCAL` path
- Verify `ExecutionSource.DRATA_WEBAPP_PROD` path

## Critical Files Reference

- `ai_services/temporal_workers/helpers/http_errors.py:27` - `raise_temporal_http_error()`
- `ai_services/temporal_workers/helpers/http_errors.py:50` - `_extract_status_and_body_from_exception()`
- `ai_services/temporal_workers/helpers/vellum_errors.py:63` - `_raise_vellum_error()`
- `ai_services/shared/runtime/context.py` - `ExecutionSource` enum with `.drata_run` property
