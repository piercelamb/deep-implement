# SOC2 Summary Webhook Implementation Plan

## Research Summary

### Analyzed Files
- `ai_services/temporal_workers/activities/vrm/post_vendor_assessment_webhook_activity.py`
- `ai_services/temporal_workers/activities/vrm/send_criteria_created_webhook_activity.py`
- `ai_services/temporal_workers/activities/vrm/send_criterion_questions_created_webhook_activity.py`
- `ai_services/temporal_workers/workflows/vrm/criteria_creation_workflow_v1.py`
- `ai_services/temporal_workers/workflows/vrm/criterion_to_questions_workflow_v1.py`
- `ai_services/temporal_workers/workflows/vrm/summary_soc2_workflow_v1.py`
- `ai_services/temporal_workers/activities/vellum/summary_soc2_activity.py`
- `ai_services/temporal_workers/helpers/http_client.py`
- `ai_services/temporal_workers/helpers/http_errors.py`
- `ai_services/temporal_workers/workflows/vrm/shared.py`

## Identified Best Practices

### 1. Webhook Activity Structure
**Pattern:** All webhook activities follow a consistent dataclass-based structure

**Key Elements:**
- Use `@dataclass(frozen=True, slots=True, kw_only=True)` for immutable input
- Standard fields across all webhooks:
  - `job_id: str`
  - `tenant_id: str`
  - `tenant_name: str`
  - `callback_host: str | None`
  - `status: WebhookStatus` (SUCCESS or FAILURE enum)
  - `error_message: str | None = None`
- Domain-specific data fields (e.g., `vendor_id`, `document_id`, etc.)
- Use `@activity.defn` decorator for Temporal activity registration
- Use `@temporal_http_error_handler("<description>")` decorator for standardized error handling

**Benefits:**
- Automatic retry logic based on HTTP status codes (4xx = non-retryable, 5xx/429 = retryable)
- Consistent error propagation to Temporal
- Proper logging of HTTP failures

### 2. HTTP Client Configuration
**Pattern:** Centralized HTTP client with connection pooling

**Implementation:**
```python
client = get_drata_api_http_client(host=input.callback_host)
```

**Features:**
- Reuses connections across requests (performance optimization)
- Supports mTLS for production environments
- Configurable timeouts from settings
- Custom callback_host support for non-production environments
- Standard headers (Accept: application/json, Content-Type: application/json)

### 3. Webhook Payload Structure
**Pattern:** Consistent payload format with conditional fields

**Standard Structure:**
```python
payload: dict[str, webhook_payload_value] = {
    "status": input.status,
    "jobId": input.job_id,
    "tenantId": input.tenant_id,
    "tenantName": input.tenant_name,
    # Domain-specific fields...
}

# Add success data only on SUCCESS status
if input.status == WebhookStatus.SUCCESS:
    payload["resultData"] = {...}

# Add error info if present
if input.error_message:
    payload["error"] = {"message": input.error_message}
```

**Key Conventions:**
- Use camelCase for API payload keys (not snake_case)
- Conditionally include result data only on success
- Always include error object with message on failure
- Type hints for payload values: `str | dict | list | None`

### 4. Workflow Integration Pattern
**Pattern:** Private helper method with try/except wrapper

**Structure:**
```python
@workflow.defn
class MyWorkflowV1:
    async def _send_webhook(
        self,
        input: WorkflowInput,
        status: WebhookStatus,
        result_data: DataDTO | None,
        error_message: str | None = None,
    ) -> None:
        """Send webhook to Drata API."""
        await workflow.execute_activity(
            send_webhook_activity,
            args=[WebhookActivityInput(...)],
            task_queue=settings.task_queue,  # NOT task_queue_vellum!
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=get_retry_policy(RetryKind.DRATA_API),
        )

    @workflow.run
    async def run(self, input: WorkflowInput) -> WorkflowOutput:
        try:
            result = await workflow.execute_activity(...)

            await self._send_webhook(
                input,
                status=WebhookStatus.SUCCESS,
                result_data=result,
            )

            return WorkflowOutput(result=result)
        except (ActivityError, ApplicationError, ChildWorkflowError) as exc:
            error_message = str(exc)
            await self._send_webhook(
                input,
                status=WebhookStatus.FAILURE,
                result_data=None,
                error_message=error_message,
            )
            raise  # Re-raise to mark workflow as failed
```

**Key Points:**
- Use private `_send_webhook` helper method for reusability
- Webhook uses regular task queue, not Vellum task queue
- 30-second timeout for webhook calls (quick operation)
- DRATA_API retry policy (not VELLUM_WORKFLOW)
- Always re-raise exception after sending failure webhook
- Catch specific Temporal exceptions: `ActivityError`, `ApplicationError`, `ChildWorkflowError`

### 5. Configuration Management
**Pattern:** Centralized settings with descriptive names

**Location:** `ai_services/temporal_workers/config.py`

**Naming Convention:**
```python
drata_api_{domain}_{operation}_webhook_endpoint: str = "/ai-agent/{domain}/webhook/{operation}"
```

**Examples:**
- `drata_api_vrm_agent_criteria_created_webhook_endpoint`
- `drata_api_vrm_agent_criterion_questions_created_webhook_endpoint`
- `drata_api_vrm_agent_vendor_assessment_endpoint`

### 6. Logging Patterns
**Pattern:** Structured logging with extra fields

**Implementation:**
```python
activity.logger.info(
    "Sending {operation} webhook",
    extra={
        "endpoint": url,
        "status": input.status,
        "job_id": input.job_id,
        "tenant_id": input.tenant_id,
        # ... other relevant fields
    },
)
```

**Best Practices:**
- Log before making HTTP request
- Include endpoint URL, status, and all identifying fields
- Use snake_case for extra field keys (internal logging convention)
- Don't log sensitive data or full payloads

### 7. Shared Types and Enums
**Pattern:** Reusable types in shared module

**Location:** `ai_services/temporal_workers/workflows/vrm/shared.py`

**Key Types:**
```python
class WebhookStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
```

**Usage:**
- Import from shared module to ensure consistency
- Used in both activities and workflows
- Provides type safety and autocomplete

## Implementation Plan for SOC2 Summary Webhook

### Phase 1: Create Webhook Activity
**File:** `ai_services/temporal_workers/activities/vrm/send_soc2_summary_webhook_activity.py`

**Components:**
1. Input dataclass with fields:
   - Standard: `job_id`, `tenant_id`, `tenant_name`, `callback_host`, `status`, `error_message`
   - SOC2-specific: `vendor_id`, `vendor_name`, `document_index_id`, `document_id`
   - Result data: `summary: dict | None` (dummy data structure TBD)

2. Activity function:
   - Use `@activity.defn` and `@temporal_http_error_handler` decorators
   - Build payload with camelCase keys
   - Conditionally include summary on SUCCESS
   - Log structured info
   - Make HTTP POST call
   - Raise for status

### Phase 2: Add Endpoint Configuration
**File:** `ai_services/temporal_workers/config.py`

**Addition:**
```python
drata_api_vrm_agent_soc2_summary_webhook_endpoint: str = "/ai-agent/vrm/webhook/soc2-summary"
```

### Phase 3: Update Workflow
**File:** `ai_services/temporal_workers/workflows/vrm/summary_soc2_workflow_v1.py`

**Changes:**
1. Import webhook activity and `WebhookStatus`
2. Add private `_send_webhook` helper method
3. Wrap existing workflow logic in try/except
4. Send SUCCESS webhook after activity completes
5. Send FAILURE webhook on exception and re-raise
6. Update workflow to return summary result (currently returns None)

### Phase 4: Register Activity
**File:** `ai_services/temporal_workers/workers/main_worker.py`

**Changes:**
- Import `send_soc2_summary_webhook` activity
- Add to activities list in worker registration

### Phase 5: Dummy Data Structure
**Format:** For initial implementation, use simple dummy summary data:
```python
{
    "summary": {
        "overallRiskScore": "MEDIUM",
        "findings": [
            {
                "category": "Access Control",
                "status": "COMPLIANT",
                "description": "Access controls are properly implemented"
            },
            {
                "category": "Data Encryption",
                "status": "NEEDS_REVIEW",
                "description": "Encryption at rest requires verification"
            }
        ],
        "recommendations": [
            "Review encryption policies",
            "Update access control documentation"
        ],
        "completedAt": "<ISO timestamp>"
    }
}
```

## Success Criteria

1. ✅ Webhook activity follows established patterns
2. ✅ Workflow sends SUCCESS webhook with dummy summary data
3. ✅ Workflow sends FAILURE webhook with error message on exception
4. ✅ HTTP errors are properly handled with retry logic
5. ✅ All logging includes structured extra fields
6. ✅ Activity is registered in main worker
7. ✅ Configuration follows naming conventions
8. ✅ Code matches style of existing webhook implementations

## Testing Strategy

1. **Unit Test - Webhook Activity:**
   - Test successful webhook call
   - Test HTTP error handling
   - Test payload structure

2. **Integration Test - Workflow:**
   - Test workflow with successful summary activity (mock)
   - Test workflow with failing summary activity
   - Verify webhook sent in both cases
   - Verify correct status and payload

3. **Manual Testing:**
   - Run workflow locally against callback server
   - Verify webhook payload structure
   - Check Temporal UI for activity execution

## Risks and Considerations

1. **Dummy Data Structure:** The summary data structure is tentative and may need adjustment based on actual Vellum workflow output
2. **Endpoint Path:** Confirm with team that `/ai-agent/vrm/webhook/soc2-summary` is the correct endpoint path
3. **Return Value:** Currently workflow returns `None`, may need to return summary data for consistency
4. **Webhook Timing:** Webhook is sent after activity completes, before workflow ends - confirm this is desired behavior

## Dependencies

- No new dependencies required
- Uses existing infrastructure:
  - `get_drata_api_http_client` for HTTP requests
  - `temporal_http_error_handler` for error handling
  - `WebhookStatus` enum from shared module
  - `RetryKind.DRATA_API` retry policy

## Follow-up Work

1. Replace dummy summary data with actual Vellum workflow output
2. Add S3 storage of summary results (similar to `TODO: Save to s3` in criteria_creation_workflow_v1.py)
3. Create tests for webhook activity and updated workflow
4. Update API endpoint documentation if needed
5. Add webhook endpoint to Drata API backend

## References

**Similar Implementations:**
- `criteria_creation_workflow_v1.py` - Best reference for workflow pattern
- `criterion_to_questions_workflow_v1.py` - Alternative workflow pattern example
- `send_criteria_created_webhook_activity.py` - Complex payload structure example
- `send_criterion_questions_created_webhook_activity.py` - Simple payload structure example
