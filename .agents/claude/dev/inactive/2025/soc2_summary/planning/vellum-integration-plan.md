# SOC2 Summary Vellum Workflow Integration Plan

## Context

We need to replace the dummy data in `summary_soc2_activity.py` with actual calls to the Vellum workflow `"soc-1-2-type-ii-summary"`. This document outlines the research, decisions, and implementation plan based on the provided Vellum example code and our established best practices.

## Data Flow Analysis

### API Request → Workflow → Activity → Vellum

**1. API Endpoint:** `POST /api/v1/vrm/summary/soc2`

**Request Model:** `Soc2SummaryWorkflowRequest`
```python
class Soc2SummaryWorkflowRequest(BaseInput):
    # From BaseInput:
    job_id: str
    tenant_id: str
    tenant_name: str
    callback_host: str | None

    # SOC2-specific:
    vendor_id: str
    vendor_name: str
    vendor_document_index_id: str
    vendor_document_id: str
    filename: str  # ✅ NOW AVAILABLE (merged from main)
```

**2. API → Workflow Mapping:** `start_soc2_summary_workflow()`
```python
workflow_input = Soc2SummaryWorkflowInputV1(
    job_id=body.job_id,
    tenant_id=body.tenant_id,
    tenant_name=body.tenant_name,
    callback_host=body.callback_host,
    vendor_id=body.vendor_id,
    vendor_name=body.vendor_name,
    source=ExecutionSource.from_env(settings.environment),  # Generated
    filename=body.filename,                                 # ✅ NOW INCLUDED
    document_index_id=body.vendor_document_index_id,       # Renamed
    document_id=body.vendor_document_id,                   # Renamed
)
```

**3. Current Workflow → Activity Mapping:**
```python
Soc2SummaryActivityInput(
    job_id=input.job_id,
    tenant_id=input.tenant_id,
    tenant_name=input.tenant_name,
    vendor_id=input.vendor_id,
    vendor_name=input.vendor_name,
    source=input.source,
    filename=input.filename,                  # ✅ NOW INCLUDED
    document_index_id=input.document_index_id,
    document_id=input.document_id,
)
```

**4. Activity → Vellum Workflow:**

Currently passes dummy data. Need to call Vellum with **9 inputs** (not 7, not 10):

✅ **Available from API request (7 direct inputs):**
1. `tenant_id` (STRING)
2. `tenant_name` (STRING)
3. `vendor_id` (STRING)
4. `vendor_name` (STRING)
5. `source` (STRING) - ExecutionSource
6. `document_index_id` (STRING) - Vector DB index
7. `document_id` (STRING) - Document in vector DB

✅ **Constructed in workflow/activity (2 additional inputs):**
8. `remote_key` (STRING) - Constructed using `get_ai_artifact_remote_key()` utility
9. `bucket` (STRING) - From `settings.aws_s3_bucket`

❌ **Omitted (treat as None):**
- `artifact_type` - Always None (omit from inputs list)

**Key Insight:** We CAN construct `remote_key` and get `bucket` because we now have all required fields (tenant_id, document_index_id, document_id, filename). The document is stored in S3 and Vellum needs these fields to access it.

## Vellum Workflow Specification

**From Vellum Example Code:**
- **Deployment Name:** `"soc-1-2-type-ii-summary"`
- **Release Tag:** ~~`"LATEST"`~~ → Use `get_vellum_workflow_release_tag()` (our best practice)
- **Client:** ~~Direct Vellum client~~ → Use `vellum_execute_workflow()` helper (our best practice)

**Vellum Example Listed 10 Inputs, We'll Use 9:**

The Vellum example showed all 10 inputs. We'll use 9:
- **`artifact_type`**: Always None for this use case → **Omit from inputs list**
- **`remote_key`**: ✅ Can construct using new shared utility `get_ai_artifact_remote_key()`
- **`bucket`**: ✅ Available from `settings.aws_s3_bucket`

**How to Handle None in Vellum:**
> In Vellum, `None` is expressed by leaving that input OFF the list of inputs when you invoke.

So we omit `artifact_type` from the inputs array.

## Our Best Practices vs Vellum Example

| Aspect | Vellum Example | Our Best Practice | Why |
|--------|----------------|-------------------|-----|
| Client | `Vellum(api_key=...)` | `vellum_execute_workflow()` | Centralized error handling, tracing, logging |
| Release Tag | `"LATEST"` | `get_vellum_workflow_release_tag()` | LaunchDarkly-based release management |
| Error Handling | Manual REJECTED check | Handled automatically | Retry logic, ApplicationError conversion |
| Input Types | `types.WorkflowRequestStringInputRequest` | `WorkflowRequestStringInputRequest` | Same, just imported directly |
| Deployment Name | Hardcoded string | Enum `VellumWorkflowDeploymentName` | Type safety, centralized management |
| None Values | Not shown | Omit from inputs list | Vellum's way of handling optional inputs |

## Research Findings

### 1. Helper Function: `vellum_execute_workflow()`

**Location:** `ai_services/temporal_workers/activities/vellum/vellum_execute_workflow.py`

**Signature:**
```python
def vellum_execute_workflow(
    workflow_deployment_name: VellumWorkflowDeploymentName,
    inputs: list[WorkflowRequestInputRequest],
    tenant_id: str,
) -> list[WorkflowOutput]
```

**What it does for us:**
- ✅ Gets Vellum client with API key from settings
- ✅ Resolves release tag via `get_vellum_workflow_release_tag(workflow_deployment_name, tenant_id)`
- ✅ Wraps execution in OpenTelemetry span with attributes
- ✅ Handles REJECTED state and raises `ApplicationError`
- ✅ Distinguishes retryable vs non-retryable errors (ValueError = non-retryable)
- ✅ Logs execution start and completion with structured data
- ✅ Already decorated with `@vellum_error_handler` for SDK exceptions

**We should NOT:**
- ❌ Create our own Vellum client
- ❌ Handle REJECTED state ourselves
- ❌ Use hardcoded "LATEST" release tag
- ❌ Duplicate error handling logic

### 2. Current Activity Implementation

**File:** `ai_services/temporal_workers/activities/vellum/summary_soc2_activity.py`

**Current Input Dataclass (Need to add filename!):**
```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Soc2SummaryActivityInput:
    job_id: str          # ✅ Have (for logging, not passed to Vellum)
    tenant_id: str       # ✅ Pass to Vellum
    tenant_name: str     # ✅ Pass to Vellum
    vendor_id: str       # ✅ Pass to Vellum
    vendor_name: str     # ✅ Pass to Vellum
    source: ExecutionSource  # ✅ Pass to Vellum
    filename: str        # ✅ Need to ADD - used to construct remote_key
    document_index_id: str   # ✅ Pass to Vellum (vector DB)
    document_id: str     # ✅ Pass to Vellum (vector DB)
```

**Current Implementation:**
- Returns dummy data dict with structure:
  - `summary` dict with `overview`, `exception`, `management_response`, `complementary_user_entity_controls`
  - `validation` dict with `success`, `message`

### 3. Pattern from Similar Activities

**Reference:** `ai_services/temporal_workers/activities/vellum/gather_and_assess_activity.py`

**Pattern:**
```python
from vellum import WorkflowRequestJsonInputRequest, WorkflowRequestStringInputRequest

@dataclass(frozen=True, slots=True, kw_only=True)
class ActivityInput:
    # ... fields

FINAL_OUTPUT_SPEC: VellumWorkflowOutputSpec = {"name": "final_output", "type": "JSON"}

@activity.defn
def activity_function(params: ActivityInput) -> ReturnType:
    try:
        outputs = vellum_execute_workflow(
            tenant_id=params.tenant_id,
            workflow_deployment_name=VellumWorkflowDeploymentName.SOME_WORKFLOW,
            inputs=[
                WorkflowRequestStringInputRequest(
                    name="field_name",
                    type="STRING",
                    value=params.field_value,
                ),
                # ... more inputs
            ],
        )

        final_output = get_vellum_workflow_output_value(FINAL_OUTPUT_SPEC, outputs)
        return process_output(final_output)

    except ApplicationError:
        raise  # Re-raise Vellum errors (already have retry behavior)
    except Exception as exc:
        activity.logger.error({"msg": "activity failed", "error": str(exc)})
        raise ApplicationError(f"activity failed: {exc}", non_retryable=True) from exc
```

**Key Points:**
1. Use `vellum_execute_workflow()` helper, not direct client
2. Define `FINAL_OUTPUT_SPEC` as module constant
3. Pass deployment name as enum, not string
4. Use `WorkflowRequestStringInputRequest` for string inputs
5. Extract output with `get_vellum_workflow_output_value()`
6. Re-raise `ApplicationError` directly (preserves retry behavior)
7. Wrap other exceptions in `ApplicationError(non_retryable=True)`

### 4. Enum Update Required

**Current Enum:** `ai_services/temporal_workers/activities/vellum/enums.py`

```python
class VellumWorkflowDeploymentName(StrEnum):
    # ... other workflows
    SOC2_SUMMARY = "vendor-soc2-summary-development"  # ❌ WRONG
```

**Should be:**
```python
class VellumWorkflowDeploymentName(StrEnum):
    # ... other workflows
    SOC2_SUMMARY = "soc-1-2-type-ii-summary"  # ✅ CORRECT (from Vellum example)
```

### 5. New Shared Utility for S3 Remote Key Construction

**Need to create:** `ai_services/shared/cloud/file_handling.py`

**Function:**
```python
def get_ai_artifact_remote_key(
    *, tenant_id: str, index_id: str, external_id: str, filename: str
) -> str:
    """Defines the remote key path structure uploaded artifacts will take."""
    return f"{tenant_id}/{index_id}/{external_id}_{filename}"
```

**Rationale:**
- Centralizes S3 key construction logic
- Ensures consistency across all workflows that upload/access documents
- Pattern verified in `create_vellum_document_workflow_v1.py:63`

**Usage in SOC2 Summary:**
```python
from ai_services.shared.cloud.file_handling import get_ai_artifact_remote_key

remote_key = get_ai_artifact_remote_key(
    tenant_id=params.tenant_id,
    index_id=params.document_index_id,
    external_id=params.document_id,
    filename=params.filename,
)
```

**Also update:** `create_vellum_document_workflow_v1.py:63` to use this utility instead of inline string construction

## Implementation Decisions

### Decision 1: Add `filename` to Dataclasses

**Need to add `filename` field:**
- ✅ `Soc2SummaryWorkflowRequest` - Already has it (merged from main)
- ✅ API endpoint - Already passes it (line 184)
- ❌ `Soc2SummaryWorkflowInputV1` - Need to add
- ❌ `Soc2SummaryActivityInput` - Need to add

**Rationale:**
- Need `filename` to construct `remote_key` for S3 document access
- Pattern: `{tenant_id}/{index_id}/{external_id}_{filename}`
- Vellum workflow needs `remote_key` and `bucket` to access document from S3

### Decision 2: Update Enum Only

**Action:** Update existing `SOC2_SUMMARY` enum value to match Vellum deployment

**File:** `ai_services/temporal_workers/activities/vellum/enums.py`

**Change:**
```python
SOC2_SUMMARY = "soc-1-2-type-ii-summary"
```

**Rationale:**
- Matches actual Vellum deployment name from example
- Existing enum constant can be reused
- No breaking changes (activity not yet calling real workflow)

### Decision 3: Output Specification

**Need to determine actual output name from Vellum workflow**

**Action:** Add to `VellumWorkflowOutputName` class (if output name is confirmed)

**Likely:**
```python
@staticmethod
def soc2_summary() -> VellumWorkflowOutputSpec:
    """SOC2 summary output spec."""
    return {"name": "final-output", "type": "JSON"}
```

**Note:** Can verify output name by testing or checking Vellum deployment UI

### Decision 4: Pass 9 Inputs to Vellum (Omit Only artifact_type)

**Inputs to include (9 total):**
1. `tenant_id` ✅
2. `tenant_name` ✅
3. `vendor_id` ✅
4. `vendor_name` ✅
5. `source` ✅
6. `document_index_id` ✅
7. `document_id` ✅
8. `remote_key` ✅ - Constructed using `get_ai_artifact_remote_key()`
9. `bucket` ✅ - From `settings.aws_s3_bucket`

**Inputs to OMIT (treat as None by excluding):**
- `artifact_type` - Always None for this use case

### Decision 5: Return Type

**Keep as `dict`:**
- No domain object exists for SOC2 summary
- Webhook expects dict directly
- Output structure is complex and dynamic

**Return:**
```python
return final_output  # dict with summary structure
```

## Implementation Plan

### Phase 0: Create Shared Utility for S3 Remote Key

**File:** `ai_services/shared/cloud/file_handling.py` (NEW FILE)

**Create file with function:**
```python
"""File handling utilities for cloud storage operations."""


def get_ai_artifact_remote_key(
    *, tenant_id: str, index_id: str, external_id: str, filename: str
) -> str:
    """Defines the remote key path structure uploaded artifacts will take.

    Args:
        tenant_id: The tenant identifier
        index_id: The vector database index ID
        external_id: The external document identifier
        filename: The original filename

    Returns:
        S3 remote key path following the pattern: {tenant_id}/{index_id}/{external_id}_{filename}
    """
    return f"{tenant_id}/{index_id}/{external_id}_{filename}"
```

**Also update:** `ai_services/temporal_workers/workflows/vellum/create_vellum_document_workflow_v1.py`

**Line 63, change from:**
```python
remote_key = f"{input.tenant_id}/{input.index_id}/{input.external_id}_{input.filename}"
```

**To:**
```python
from ai_services.shared.cloud.file_handling import get_ai_artifact_remote_key

remote_key = get_ai_artifact_remote_key(
    tenant_id=input.tenant_id,
    index_id=input.index_id,
    external_id=input.external_id,
    filename=input.filename,
)
```

### Phase 1: Update Enum

**File:** `ai_services/temporal_workers/activities/vellum/enums.py`

**Change:**
```python
class VellumWorkflowDeploymentName(StrEnum):
    # ...
    SOC2_SUMMARY = "soc-1-2-type-ii-summary"  # Updated from "vendor-soc2-summary-development"
```

### Phase 2: Add Output Spec Method (Optional)

**File:** `ai_services/temporal_workers/activities/vellum/enums.py`

**Add to `VellumWorkflowOutputName` class:**
```python
@staticmethod
def soc2_summary() -> VellumWorkflowOutputSpec:
    """SOC2 summary output spec."""
    return {"name": "final-output", "type": "JSON"}  # TODO: Verify output name
```

**Note:** Can define `FINAL_OUTPUT_SPEC` directly in activity instead if preferred

### Phase 3: Add `filename` to Dataclasses

**File:** `ai_services/temporal_workers/workflows/vrm/summary_soc2_workflow_v1.py`

**Change 1: Add to workflow input dataclass:**
```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Soc2SummaryWorkflowInputV1:
    job_id: str
    tenant_id: str
    tenant_name: str
    callback_host: str | None = None
    vendor_id: str
    vendor_name: str
    source: ExecutionSource
    filename: str  # ADD THIS
    document_index_id: str
    document_id: str
```

**Change 2: Pass to activity:**
```python
# In workflow.run(), update activity invocation:
Soc2SummaryActivityInput(
    job_id=input.job_id,
    tenant_id=input.tenant_id,
    tenant_name=input.tenant_name,
    vendor_id=input.vendor_id,
    vendor_name=input.vendor_name,
    source=input.source,
    filename=input.filename,  # ADD THIS
    document_index_id=input.document_index_id,
    document_id=input.document_id,
)
```

**File:** `ai_services/temporal_workers/activities/vellum/summary_soc2_activity.py`

**Change: Add to activity input dataclass:**
```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Soc2SummaryActivityInput:
    job_id: str
    tenant_id: str
    tenant_name: str
    vendor_id: str
    vendor_name: str
    source: ExecutionSource
    filename: str  # ADD THIS
    document_index_id: str
    document_id: str
```

### Phase 4: Implement Vellum Workflow Call

**File:** `ai_services/temporal_workers/activities/vellum/summary_soc2_activity.py`

**Changes:**

1. Add imports:
```python
from vellum import WorkflowRequestStringInputRequest
from ai_services.shared.cloud.file_handling import get_ai_artifact_remote_key
from ai_services.temporal_workers.activities.vellum.enums import VellumWorkflowDeploymentName
from ai_services.temporal_workers.activities.vellum.vellum_execute_workflow import vellum_execute_workflow
from ai_services.temporal_workers.config import settings
from ai_services.temporal_workers.vellum.shared import VellumWorkflowOutputSpec
from ai_services.temporal_workers.vellum.utils import get_vellum_workflow_output_value
```

2. Define output spec:
```python
FINAL_OUTPUT_SPEC: VellumWorkflowOutputSpec = {"name": "final-output", "type": "JSON"}
```

3. Replace dummy implementation with **9 inputs** (omit only artifact_type):
```python
@activity.defn
def summary_soc2_activity(params: Soc2SummaryActivityInput) -> dict:
    """Run the Vellum SOC2 Summary workflow and return a summary dict."""
    try:
        activity.logger.info(
            "Starting SOC2 summary activity",
            extra={
                "tenant_id": params.tenant_id,
                "vendor_id": params.vendor_id,
                "job_id": params.job_id,
                "execution_source": params.source,
                "doc_index_id": params.document_index_id,
                "doc_id": params.document_id,
                "filename": params.filename,
            },
        )

        # Construct remote_key and bucket for S3 document access
        remote_key = get_ai_artifact_remote_key(
            tenant_id=params.tenant_id,
            index_id=params.document_index_id,
            external_id=params.document_id,
            filename=params.filename,
        )
        bucket = settings.aws_s3_bucket

        # Call Vellum workflow using our helper
        # Pass 9 inputs - omit only artifact_type (treat as None)
        outputs = vellum_execute_workflow(
            tenant_id=params.tenant_id,
            workflow_deployment_name=VellumWorkflowDeploymentName.SOC2_SUMMARY,
            inputs=[
                WorkflowRequestStringInputRequest(
                    name="tenant_id",
                    type="STRING",
                    value=params.tenant_id,
                ),
                WorkflowRequestStringInputRequest(
                    name="tenant_name",
                    type="STRING",
                    value=params.tenant_name,
                ),
                WorkflowRequestStringInputRequest(
                    name="vendor_id",
                    type="STRING",
                    value=params.vendor_id,
                ),
                WorkflowRequestStringInputRequest(
                    name="vendor_name",
                    type="STRING",
                    value=params.vendor_name,
                ),
                WorkflowRequestStringInputRequest(
                    name="source",
                    type="STRING",
                    value=params.source,
                ),
                WorkflowRequestStringInputRequest(
                    name="document_index_id",
                    type="STRING",
                    value=params.document_index_id,
                ),
                WorkflowRequestStringInputRequest(
                    name="document_id",
                    type="STRING",
                    value=params.document_id,
                ),
                WorkflowRequestStringInputRequest(
                    name="remote_key",
                    type="STRING",
                    value=remote_key,
                ),
                WorkflowRequestStringInputRequest(
                    name="bucket",
                    type="STRING",
                    value=bucket,
                ),
                # NOTE: Omitting artifact_type only
                # In Vellum, None is expressed by leaving inputs off the list
            ],
        )

        # Extract final output
        final_output = get_vellum_workflow_output_value(FINAL_OUTPUT_SPEC, outputs)

        activity.logger.info(
            "Completed SOC2 summary activity",
            extra={
                "tenant_id": params.tenant_id,
                "vendor_id": params.vendor_id,
                "job_id": params.job_id,
            },
        )

        return final_output  # Return dict directly

    except ApplicationError:
        raise  # Re-raise Vellum errors (already have retry behavior)
    except Exception as exc:
        activity.logger.error(
            {"msg": "summary_soc2_activity failed", "error": str(exc)}
        )
        raise ApplicationError(f"summary_soc2_activity failed: {exc}", non_retryable=True) from exc
```

### Phase 5: Update Tests

**File:** `tests/temporal_workers/test_summary_soc2_workflow_v1.py`

**Changes:**

1. Update fixtures to include `filename` field:
```python
@pytest.fixture
def sample_workflow_input(self) -> Soc2SummaryWorkflowInputV1:
    return Soc2SummaryWorkflowInputV1(
        job_id="job_123456789",
        tenant_id="tenant_456",
        tenant_name="Test Company",
        callback_host="https://api.drata.com",
        vendor_id="vendor_789",
        vendor_name="Test Vendor Inc",
        source=ExecutionSource.DRATA_WEBAPP_DEV,
        filename="soc2_report.pdf",  # ADD THIS
        document_index_id="index_abc123",
        document_id="doc_xyz789",
    )

@pytest.fixture
def sample_activity_input(self) -> Soc2SummaryActivityInput:
    return Soc2SummaryActivityInput(
        job_id="job_123456789",
        tenant_id="tenant_456",
        tenant_name="Test Company",
        vendor_id="vendor_789",
        vendor_name="Test Vendor Inc",
        source=ExecutionSource.DRATA_WEBAPP_DEV,
        filename="soc2_report.pdf",  # ADD THIS
        document_index_id="index_abc123",
        document_id="doc_xyz789",
    )
```

2. Add test to verify Vellum integration:
```python
from unittest.mock import patch
from vellum import WorkflowOutput

def test_soc2_summary_activity_calls_vellum(
    sample_activity_input: Soc2SummaryActivityInput,
) -> None:
    """Test activity calls Vellum workflow correctly."""
    with patch(
        "ai_services.temporal_workers.activities.vellum.summary_soc2_activity.vellum_execute_workflow"
    ) as mock_vellum:
        # Mock return value
        mock_vellum.return_value = [
            WorkflowOutput(
                name="final-output",
                type="JSON",
                value={
                    "summary": {
                        "overview": "Test overview",
                        "exception": "No exceptions",
                        "management_response": "Test response",
                        "complementary_user_entity_controls": {},
                    },
                    "validation": {
                        "success": True,
                        "message": "Valid SOC2 report",
                    },
                },
            )
        ]

        # Execute activity
        result = summary_soc2_activity(sample_activity_input)

        # Verify vellum_execute_workflow was called
        assert mock_vellum.called
        call_kwargs = mock_vellum.call_args

        # Verify deployment name
        assert call_kwargs.kwargs["workflow_deployment_name"] == VellumWorkflowDeploymentName.SOC2_SUMMARY

        # Verify tenant_id
        assert call_kwargs.kwargs["tenant_id"] == sample_activity_input.tenant_id

        # Verify inputs include exactly 9 fields (not 7, not 10)
        inputs = call_kwargs.kwargs["inputs"]
        input_names = {inp.name for inp in inputs}
        assert input_names == {
            "tenant_id", "tenant_name", "vendor_id", "vendor_name",
            "source", "document_index_id", "document_id",
            "remote_key", "bucket"  # These ARE included now
        }

        # Verify artifact_type is NOT included (only omitted field)
        assert "artifact_type" not in input_names

        # Verify remote_key and bucket ARE included
        assert "remote_key" in input_names
        assert "bucket" in input_names

        # Verify result structure
        assert isinstance(result, dict)
        assert "summary" in result
        assert "validation" in result
```

3. Existing workflow tests should continue to pass (no changes needed to workflow logic)

## Questions Resolved ✅

### Q1: Vellum Output Name
**Status:** Need to verify, but likely `"final-output"` (with dash)

**Can verify by:**
- Testing with sandbox environment
- Checking Vellum deployment UI
- Easy to fix if wrong (just update `FINAL_OUTPUT_SPEC`)

### Q2: Artifact Type ✅
**Answer:** Always None - omit from inputs list

**Source:** User confirmation

### Q3: Remote Key & Bucket ✅
**Answer:** Not provided - document accessed via vector DB using `document_index_id` and `document_id`

**Source:** Analyzed API request model and data flow

### Q4: Default Bucket ✅
**Answer:** Not applicable - no bucket field needed

### Q5: API Endpoint Status ✅
**Answer:** Exists and is correct - no changes needed

**Endpoint:** `POST /api/v1/vrm/summary/soc2`
**File:** `ai_services/api/routers/vrm_router.py:166`

## Testing Strategy

### 1. Unit Tests - Activity

**Test Cases:**
- ✅ Successfully calls `vellum_execute_workflow` with correct inputs
- ✅ Passes exactly 7 inputs (not 10) to Vellum
- ✅ Omits artifact_type, remote_key, bucket from inputs
- ✅ Extracts output correctly
- ✅ Handles Vellum REJECTED state (via mocked ApplicationError)
- ✅ Wraps non-Vellum exceptions correctly
- ✅ Logs structured data

**Approach:**
- Mock `vellum_execute_workflow` to return test outputs
- Verify inputs passed to helper function
- Verify input names match expected 7 fields
- Test error paths

### 2. Integration Tests - Workflow

**Test Cases:**
- ✅ Workflow passes all inputs to activity correctly
- ✅ Webhook receives real summary data (not dummy)
- ✅ Error handling still works (FAILURE webhook sent)

**Approach:**
- Use Temporal test environment
- Mock Vellum at activity level
- Verify webhook payloads
- Existing tests should continue to pass

### 3. Manual/E2E Tests

**Test Cases:**
- ✅ Real Vellum workflow execution in sandbox
- ✅ Document accessed correctly via vector DB
- ✅ Summary structure matches expectations
- ✅ Webhook delivered successfully

**Prerequisites:**
- Document indexed in vector DB
- Vellum workflow deployed and accessible
- Sandbox environment configured

## Success Criteria

1. ✅ Enum updated to correct deployment name: `"soc-1-2-type-ii-summary"`
2. ✅ Activity successfully calls Vellum workflow
3. ✅ Exactly 7 inputs passed (tenant_id, tenant_name, vendor_id, vendor_name, source, document_index_id, document_id)
4. ✅ artifact_type, remote_key, bucket correctly omitted (None handling)
5. ✅ Output extracted and returned as dict
6. ✅ Error handling follows established patterns
7. ✅ Release tag resolved via LaunchDarkly (not "LATEST")
8. ✅ Tests updated and passing
9. ✅ Webhook receives real summary data
10. ✅ No direct Vellum client usage (uses helper)
11. ✅ No dataclass changes needed (current structure is correct)

## Risks and Mitigations

### Risk 1: Wrong Output Name
**Risk:** Output name doesn't match expectation

**Mitigation:**
- Test with sandbox environment first
- Easy to fix (just update `FINAL_OUTPUT_SPEC`)
- Common names: `"final-output"`, `"final_output"`, `"summary"`

### Risk 2: Vellum Expects More Inputs
**Risk:** Vellum workflow errors because artifact_type/remote_key/bucket are missing

**Mitigation:**
- User confirmed artifact_type is None (omit from list)
- Document access via vector DB (don't need S3 fields)
- Test with sandbox first to verify

### Risk 3: Output Structure Mismatch
**Risk:** Vellum output doesn't match webhook expectations

**Mitigation:**
- Document expected structure in tests
- Current dummy data structure may need adjustment
- Coordinate with Vellum team on output format

## Timeline Estimate

- **Phase 1:** Update enum - 5 minutes
- **Phase 2:** Add output spec (optional) - 5 minutes
- **Phase 3:** Implement Vellum call - 15 minutes
- **Phase 4:** Update tests - 20 minutes
- **Testing & Validation:** 30 minutes

**Total Estimated Time:** 1-1.5 hours (reduced from 2.5 hours - no dataclass changes needed!)

## Summary of Changes

### Files to Modify: 2 (not 5!)

1. **`ai_services/temporal_workers/activities/vellum/enums.py`**
   - Update `SOC2_SUMMARY` enum value
   - Optionally add output spec method

2. **`ai_services/temporal_workers/activities/vellum/summary_soc2_activity.py`**
   - Replace dummy implementation with Vellum workflow call
   - Pass 7 inputs (not 10)

### Files NOT Changing: 5 ✅

- `ai_services/api/models/vrm.py` - Request model is correct
- `ai_services/api/routers/vrm_router.py` - API endpoint is correct
- `ai_services/temporal_workers/workflows/vrm/summary_soc2_workflow_v1.py` - Dataclasses are correct
- Workflow input dataclass - Already has all needed fields
- Activity input dataclass - Already has all needed fields

### Tests to Update: 1

- `tests/temporal_workers/test_summary_soc2_workflow_v1.py`
  - Add Vellum integration test
  - Verify 7 inputs (not 10)
  - Existing tests should continue passing

## References

**Vellum Example Code:** Provided by user (basis for deployment name and inputs)

**Key Files:**
- `ai_services/temporal_workers/activities/vellum/vellum_execute_workflow.py` - Helper we must use
- `ai_services/temporal_workers/activities/vellum/gather_and_assess_activity.py` - Pattern reference
- `ai_services/temporal_workers/activities/vellum/enums.py` - Deployment names and output specs
- `ai_services/temporal_workers/vellum/utils.py` - Output extraction
- `ai_services/temporal_workers/launchdarkly/utils.py` - Release tag resolution
- `ai_services/api/routers/vrm_router.py` - API endpoint (confirmed correct)

**Our Best Practices:**
- Use `vellum_execute_workflow()` helper (not direct client)
- Use `get_vellum_workflow_release_tag()` (not "LATEST")
- Use enum for deployment name (not hardcoded string)
- Follow error handling pattern (re-raise ApplicationError)
- Add structured logging
- Omit None values by leaving inputs off the list
