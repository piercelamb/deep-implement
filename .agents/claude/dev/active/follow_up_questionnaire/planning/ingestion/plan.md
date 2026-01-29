# Follow-up Questionnaire Ingestion - Implementation Plan

## Overview

Implement bulk ingestion of vendor follow-up questionnaire responses into the Vellum vector DB, enabling retrieval during re-assessment with proper precedence.

---

## Data Flow Visualization

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              INGESTION DATA FLOW                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────┐       ┌──────────────────────────────────────────────────────────────────┐
│  DRATA  │       │                         AI-SERVICES                              │
│   API   │       │                                                                  │
└────┬────┘       │  ┌─────────────────────────────────────────────────────────────┐ │
     │            │  │                    FastAPI Endpoint                         │ │
     │ POST       │  │         /v1/vrm/followup-questionnaire/index                │ │
     │            │  ├─────────────────────────────────────────────────────────────┤ │
     ▼            │  │                                                             │ │
┌─────────────┐   │  │  IndexFollowupQuestionnaireRequest                          │ │
│ Request     │   │  │  ├── vendor_id, vendor_name                                 │ │
│ Body (JSON) │───┼──┼─▶│  ├── vendor_document_index_id                            │ │
│             │   │  │  │  ├── round_number                                        │ │
│ responses[] │   │  │  │  └── responses[]                                         │ │
└─────────────┘   │  │         ├── criterion_question_text                                  │ │
                  │  │         ├── question_text                                   │ │
                  │  │         └── answer_text                                     │ │
                  │  │                                                             │ │
                  │  │  ┌─────────────────────────────────────────────────────┐    │ │
                  │  │  │ Pre-processing (per response):                      │    │ │
                  │  │  │  • criterion_hash = normalize_and_hash(criterion)   │    │ │
                  │  │  │  • external_id = FollowupResponse.build_external_id │    │ │
                  │  │  │  • item = QuestionnaireItem(...).to_dto()           │    │ │
                  │  │  └─────────────────────────────────────────────────────┘    │ │
                  │  │                           │                                 │ │
                  │  │                           ▼                                 │ │
                  │  │  ┌─────────────────────────────────────────────────────┐    │ │
                  │  │  │ temporal_client.start_workflow(                     │    │ │
                  │  │  │   IndexFollowupQuestionnaireWorkflowV1,             │    │ │
                  │  │  │   id="followup-questionnaire-index-{tenant}-{job}"  │    │ │
                  │  │  │ )                                                   │    │ │
                  │  │  └─────────────────────────────────────────────────────┘    │ │
                  │  │                           │                                 │ │
                  │  └───────────────────────────┼─────────────────────────────────┘ │
                  │                              │                                   │
                  │            ┌─────────────────┴─────────────────┐                 │
                  │            ▼                                   │                 │
                  │  ┌─────────────────────────────────────────────┼───────────────┐ │
                  │  │           TEMPORAL WORKFLOW                 │               │ │
                  │  │    IndexFollowupQuestionnaireWorkflowV1     │               │ │
                  │  ├─────────────────────────────────────────────┼───────────────┤ │
                  │  │                                             │               │ │
                  │  │  Input:                                     │               │ │
                  │  │  ├── job_id, tenant_id, vendor_id           │               │ │
                  │  │  ├── document_index_id, round_number        │               │ │
                  │  │  ├── callback_host                          │               │ │
                  │  │  └── responses: Sequence[FollowupResponseItemV1]            │ │
                  │  │                                             │               │ │
                  │  │  ┌───────────────────────────────────────┐  │               │ │
                  │  │  │     FOR EACH response IN responses:   │◀─┘               │ │
                  │  │  │                                       │                  │ │
                  │  │  │  ┌─────────────────────────────────┐  │                  │ │
                  │  │  │  │ 1. get_vellum_document_activity │  │    ┌───────────┐ │ │
                  │  │  │  │    (check if exists)            │──┼───▶│  Vellum   │ │ │
                  │  │  │  └─────────────────────────────────┘  │    │   API     │ │ │
                  │  │  │              │                        │    └───────────┘ │ │
                  │  │  │              ▼                        │          │       │ │
                  │  │  │     ┌────────────────┐                │          │       │ │
                  │  │  │     │ exists? ─────▶ SKIP (success)   │          │       │ │
                  │  │  │     └───────┬────────┘                │          │       │ │
                  │  │  │             │ no                      │          │       │ │
                  │  │  │             ▼                         │          │       │ │
                  │  │  │  ┌─────────────────────────────────┐  │          │       │ │
                  │  │  │  │ 2. Build content & metadata:    │  │          │       │ │
                  │  │  │  │    • item.embedding_content     │  │          │       │ │
                  │  │  │  │    • FollowupResponse           │  │          │       │ │
                  │  │  │  │        .build_vellum_metadata() │  │          │       │ │
                  │  │  │  └─────────────────────────────────┘  │          │       │ │
                  │  │  │              │                        │          │       │ │
                  │  │  │              ▼                        │          │       │ │
                  │  │  │  ┌─────────────────────────────────┐  │          │       │ │
                  │  │  │  │ 3. upload_text_content_activity │──┼──────────┼──────▶│ │
                  │  │  │  └─────────────────────────────────┘  │          │       │ │
                  │  │  │              │                        │          │       │ │
                  │  │  │              ▼                        │          │       │ │
                  │  │  │  ┌─────────────────────────────────┐  │          │       │ │
                  │  │  │  │ 4. poll_document_until_indexed  │──┼──────────┼──────▶│ │
                  │  │  │  │    (retry until INDEXED)        │  │          │       │ │
                  │  │  │  └─────────────────────────────────┘  │          │       │ │
                  │  │  │              │                        │          │       │ │
                  │  │  │              ▼                        │          │       │ │
                  │  │  │     Track success/failure             │          │       │ │
                  │  │  │              │                        │          │       │ │
                  │  │  └──────────────┼────────────────────────┘          │       │ │
                  │  │                 │                                   │       │ │
                  │  │                 ▼                                   │       │ │
                  │  │  ┌─────────────────────────────────────┐            │       │ │
                  │  │  │ Build result:                       │            │       │ │
                  │  │  │  • total_count                      │            │       │ │
                  │  │  │  • success_count                    │            │       │ │
                  │  │  │  • failure_count                    │            │       │ │
                  │  │  │  • failed_external_ids              │            │       │ │
                  │  │  └─────────────────────────────────────┘            │       │ │
                  │  │                 │                                   │       │ │
                  │  │                 ▼                                   │       │ │
                  │  │  ┌─────────────────────────────────────┐            │       │ │
                  │  │  │ send_followup_questionnaire_webhook │            │       │ │
                  │  │  │  • status: SUCCESS | FAILURE        │            │       │ │
                  │  │  │  • counts + failed_external_ids     │            │       │ │
                  │  │  └──────────────────┬──────────────────┘            │       │ │
                  │  │                     │                               │       │ │
                  │  └─────────────────────┼───────────────────────────────┼───────┘ │
                  │                        │                               │         │
                  └────────────────────────┼───────────────────────────────┼─────────┘
                                           │                               │
                                           ▼                               │
                  ┌─────────────────────────────────────────┐              │
                  │              DRATA API                   │              │
                  │  /ai-agent/vrm/webhook/followup-questionnaire          │
                  │                                         │              │
                  │  Payload:                               │              │
                  │  ├── job_id                             │              │
                  │  ├── tenant_id, vendor_id               │              │
                  │  ├── round_number                       │              │
                  │  ├── status                             │              │
                  │  ├── total_count, success_count         │              │
                  │  ├── failure_count                      │              │
                  │  └── failed_external_ids[]              │              │
                  └─────────────────────────────────────────┘              │
                                                                          │
                                                           ┌──────────────┴──────────┐
                                                           │     VELLUM VECTOR DB    │
                                                           │                         │
                                                           │  vendor_document_index  │
                                                           │  ├── SOC2 docs          │
                                                           │  ├── Policies           │
                                                           │  └── Followup responses │
                                                           │      (NEW)              │
                                                           └─────────────────────────┘
```

### Sequence Summary

```
1. Drata API  ──POST──▶  FastAPI /followup-questionnaire/index
2. FastAPI    ──────────▶  Pre-compute hashes, external_ids
3. FastAPI    ──start───▶  Temporal Workflow (fire-and-forget)
4. FastAPI    ◀─200 OK──   Return immediately
5. Workflow   ──loop────▶  For each response:
                             a. Check if document exists (idempotency)
                             b. Upload to Vellum if new
                             c. Poll until INDEXED
6. Workflow   ──webhook─▶  POST to Drata with results
```

## User Requirements

- **Index Target**: Same `vendor_document_index_id` as SOC2/policies
- **Async Model**: Fire-and-forget Temporal workflow with webhook callback
- **Failure Mode**: Retry failed items with backoff, report failures
- **Status Polling**: Poll each document until INDEXED status

## Design Requirements (from type_hierarchy.md)

- **Content-based hashing**: Use `normalize_and_hash()` from `shared/helpers/strings.py` (SHA256, first 16 hex chars)
- **Embedded content format**: Use `QuestionnaireItem.embedding_content` property → `"Question: {q} Answer: {a}"`
- **External ID format**: `followup-{vendor_id}-{content_hash}-round{round_number}`
  - `content_hash = hash(criterion_question_text || question_text)` ensures uniqueness for:
    - Same criterion with different questions (user copy-paste scenario)
    - Ad-hoc questions (criterion_question_text is empty)
- **Two hash fields**:
  - `content_hash`: for external_id uniqueness (criterion + question)
  - `criterion_question_hash`: for retrieval filtering (criterion only, None for ad-hoc)
- **Ad-hoc questions**: `criterion_question_text` is optional (can be null/empty for user-added questions not tied to a criterion)
- **Metadata building**: Use `FollowupResponse.build_vellum_metadata()` method

---

## Implementation Steps

### Step 1: Request/Response Models

**File**: `ai_services/api/models/vrm.py` (add to existing)

```python
from ai_services.shared.schema.dto import QuestionnaireItemDTO

class FollowupQuestionnaireResponseInput(BaseModel):
    """Single Q&A response from follow-up questionnaire.

    Supports two types:
    - Criterion-linked: criterion_question_text is set (auto-generated from NOT_MET/INCONCLUSIVE)
    - Ad-hoc: criterion_question_text is None/empty (user-added questions)
    """
    criterion_question_text: str | None = Field(None, alias="criterionText")  # Optional for ad-hoc
    question_text: str = Field(..., alias="questionText")
    answer_text: str = Field(..., alias="answerText")
    notes: str | None = Field(None)

class IndexFollowupQuestionnaireRequest(BaseInput):
    """Request to index a batch of follow-up questionnaire responses."""
    vendor_id: str = Field(..., alias="vendorId")
    vendor_name: str = Field(..., alias="vendorName")
    vendor_document_index_id: str = Field(..., alias="vendorDocumentIndexId")
    round_number: int = Field(..., alias="roundNumber", ge=1)
    responses: list[FollowupQuestionnaireResponseInput] = Field(..., min_length=1)
    timestamp: datetime | None = Field(None)

    @model_validator(mode="after")
    def check_unique_responses(self) -> Self:
        """Ensure no duplicate (criterion_question_text, question_text) pairs.

        Uses (criterion, question) tuple because:
        - Same criterion can have different questions (user copy-paste)
        - Different ad-hoc questions (both with criterion=None) are distinct
        """
        pairs = [(r.criterion_question_text or "", r.question_text) for r in self.responses]
        if len(pairs) != len(set(pairs)):
            raise ValueError("Duplicate (criterion_question_text, question_text) pairs in responses")
        return self
```

**Example JSON Request Body**:

```json
POST /v1/vrm/followup-questionnaire/index

{
  "jobId": "job-uuid-789",
  "tenantId": "tenant-uuid-abc",
  "tenantName": "Customer Inc",
  "callbackHost": "https://api.drata.com",
  "vendorId": "vendor-uuid-123",
  "vendorName": "Acme Corp",
  "vendorDocumentIndexId": "vellum-index-uuid-456",
  "roundNumber": 2,
  "timestamp": "2024-01-15T10:30:00Z",
  "responses": [
    {
      "criterionText": "CC6.1: The entity implements logical access security software...",
      "questionText": "How does Acme Corp restrict logical access to sensitive systems?",
      "answerText": "We use role-based access control (RBAC) with quarterly access reviews...",
      "notes": "See attached access control policy document"
    },
    {
      "criterionText": "CC7.2: The entity monitors system components...",
      "questionText": "What monitoring tools does Acme Corp use for security events?",
      "answerText": "We use Datadog for infrastructure monitoring and Splunk for SIEM...",
      "notes": null
    },
    {
      "criterionText": null,
      "questionText": "Do you have a business continuity plan?",
      "answerText": "Yes, we have a BCP that is reviewed annually and tested quarterly.",
      "notes": "Ad-hoc question added by user"
    }
  ]
}
```

**Field Descriptions**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `jobId` | string | Yes | Unique job identifier (from BaseInput) |
| `tenantId` | string | Yes | Tenant UUID (from BaseInput) |
| `tenantName` | string | Yes | Tenant display name (from BaseInput) |
| `callbackHost` | string | No | Webhook callback host URL (from BaseInput) |
| `vendorId` | string | Yes | UUID of the vendor being assessed |
| `vendorName` | string | Yes | Display name of the vendor |
| `vendorDocumentIndexId` | string | Yes | Vellum document index ID (same as SOC2/policies) |
| `roundNumber` | integer | Yes | Follow-up round number (≥1) |
| `timestamp` | string | No | ISO 8601 timestamp of when responses were collected |
| `responses` | array | Yes | Array of Q&A responses (min 1 item) |
| `responses[].criterionText` | string | **No** | Original criterion text (null/omitted for ad-hoc questions) |
| `responses[].questionText` | string | Yes | Follow-up question asked to vendor |
| `responses[].answerText` | string | Yes | Vendor's response to the question |
| `responses[].notes` | string | No | Optional notes or context |

**Validation Rules**:
- `roundNumber` must be ≥ 1
- `responses` must contain at least 1 item
- `(criterionText, questionText)` pairs must be unique within a single request

### Step 2: Workflow Dataclasses

**File**: `ai_services/temporal_workers/workflows/vrm/index_followup_questionnaire_workflow_v1.py` (new)

```python
from collections.abc import Sequence
from ai_services.shared.schema.dto import QuestionnaireItemDTO

@dataclass(frozen=True, slots=True, kw_only=True)
class FollowupResponseItemV1:
    """Single response item for workflow processing.

    Supports both criterion-linked and ad-hoc questions:
    - Criterion-linked: criterion_question_text is set, criterion_question_hash computed
    - Ad-hoc: criterion_question_text is empty, criterion_question_hash is None
    """
    criterion_question_text: str           # Original criterion text (empty for ad-hoc)
    content_hash: str             # hash(criterion_question_text || question_text) - for external_id
    criterion_question_hash: str | None  # hash(criterion_question_text) - for retrieval, None for ad-hoc
    item: QuestionnaireItemDTO    # Q&A content (question, answer, notes)
    external_id: str              # Pre-computed: followup-{vendor_id}-{content_hash}-round{round}

@dataclass(frozen=True, slots=True, kw_only=True)
class IndexFollowupQuestionnaireWorkflowInputV1:
    """Input for the follow-up questionnaire indexing workflow."""
    job_id: str
    tenant_id: str
    tenant_name: str
    vendor_id: str
    vendor_name: str
    document_index_id: str
    round_number: int
    timestamp: str  # ISO format
    callback_host: str | None
    responses: Sequence[FollowupResponseItemV1]

@dataclass(frozen=True, slots=True, kw_only=True)
class IndexFollowupQuestionnaireResultV1:
    """Result of the follow-up questionnaire indexing workflow."""
    total_count: int
    success_count: int
    failure_count: int
    failed_external_ids: Sequence[str]
```

### Step 3: Webhook Activity

**File**: `ai_services/temporal_workers/activities/vrm/send_followup_questionnaire_webhook_activity.py` (new)

Follow pattern from `send_soc2_summary_webhook_activity.py`:

```python
from collections.abc import Sequence

@dataclass(frozen=True, slots=True, kw_only=True)
class SendFollowupQuestionnaireWebhookInputV1:
    job_id: str
    tenant_id: str
    vendor_id: str
    round_number: int
    status: str  # "SUCCESS" | "FAILURE"
    total_count: int
    success_count: int
    failure_count: int
    failed_external_ids: Sequence[str]
    callback_host: str

@activity.defn
@temporal_http_error_handler
async def send_followup_questionnaire_webhook(
    input: SendFollowupQuestionnaireWebhookInputV1,
) -> None:
    # POST to settings.drata_api_vrm_agent_followup_questionnaire_webhook_endpoint
```

### Step 4: Main Workflow

**File**: `ai_services/temporal_workers/workflows/vrm/index_followup_questionnaire_workflow_v1.py` (continued)

Pattern based on `IndexSoc2TrackWorkflowV1`:

1. **Iterate responses sequentially** (not fan-out to simplify retry handling)
2. For each response:
   - Check if document exists via `get_vellum_document_activity` (idempotency)
   - If exists, count as success and skip
   - Build `QuestionnaireItem` from `item` DTO
   - Use `QuestionnaireItem.embedding_content` for content
   - Build metadata via `FollowupResponse.build_vellum_metadata()`
   - Upload via `upload_text_content_activity`
   - Poll via `poll_document_until_indexed()`
   - Track success/failure
3. **Catch errors per-item** - continue to next item on failure
4. **Send webhook** with final counts and failed_external_ids

```python
# In workflow run() method:
from ai_services.shared.schema.questionnaire.schema import (
    QuestionnaireItem,
    FollowupResponse,
)

for response in input.responses:
    # Build QuestionnaireItem from DTO
    item = QuestionnaireItem.from_dto(response.item)

    # Get embedding content via property
    content = item.embedding_content  # "Question: {q} Answer: {a}"

    # Build metadata using FollowupResponse class method
    metadata = FollowupResponse.build_vellum_metadata(
        tenant_id=input.tenant_id,
        vendor_id=input.vendor_id,
        round_number=input.round_number,
        criterion_hash=response.criterion_hash,
        original_criterion_question_text=response.criterion_question_text,
        item=item,
        timestamp=input.timestamp,
    )

    # Upload to Vellum...
```

### Step 5: API Endpoint

**File**: `ai_services/api/routers/vrm_router.py` (add endpoint)

```python
from ai_services.shared.schema.questionnaire.schema import (
    QuestionnaireItem,
    FollowupResponse,
)

@router.post("/followup-questionnaire/index", response_model=BaseResponse)
async def start_followup_questionnaire_index_workflow(
    request: Request, body: IndexFollowupQuestionnaireRequest
) -> BaseResponse:
    # Convert each response to workflow format
    workflow_responses = []
    for resp in body.responses:
        criterion_question_text = resp.criterion_question_text or ""  # Normalize None to empty string

        # Compute content_hash (criterion + question) for external_id uniqueness
        content_hash = FollowupResponse.compute_content_hash(
            criterion_question_text=criterion_question_text,
            question_text=resp.question_text,
        )

        # Compute criterion_hash for retrieval filtering (None for ad-hoc)
        criterion_question_hash = FollowupResponse.compute_criterion_question_hash(criterion_question_text)

        # Build QuestionnaireItem and convert to DTO
        item = QuestionnaireItem(
            question=resp.question_text,
            answer=resp.answer_text,
            notes=resp.notes,
        )

        # Build external_id: followup-{vendor_id}-{content_hash}-round{round}
        external_id = f"followup-{body.vendor_id}-{content_hash}-round{body.round_number}"

        workflow_responses.append(FollowupResponseItemV1(
            criterion_question_text=criterion_question_text,
            content_hash=content_hash,
            criterion_question_hash=criterion_question_hash,
            item=item.to_dto(),
            external_id=external_id,
        ))

    # Create workflow input and start...
```

### Step 6: Configuration

**File**: `ai_services/temporal_workers/config.py` (add setting)

```python
drata_api_vrm_agent_followup_questionnaire_webhook_endpoint: str = (
    "/ai-agent/vrm/webhook/followup-questionnaire"
)
```

### Step 7: Worker Registration

**File**: `ai_services/temporal_workers/workers/main_worker.py`

Add imports and register:
- `IndexFollowupQuestionnaireWorkflowV1` to workflows list
- `send_followup_questionnaire_webhook` to activities list

---

## Tests

### Unit Tests (Shared Types)

**File**: `tests/shared/schema/questionnaire/test_schema.py` (if not already covered)

- `test_questionnaire_item_embedding_content` - verify format
- `test_questionnaire_item_to_dto_from_dto_roundtrip`
- `test_followup_response_build_external_id` - verify format
- `test_followup_response_build_vellum_metadata` - verify all fields

**File**: `tests/shared/helpers/test_strings.py` (if not already covered)

- `test_normalize_and_hash_basic` - returns 16 char hex string
- `test_normalize_and_hash_whitespace_normalization` - collapses spaces
- `test_normalize_and_hash_case_insensitive` - lowercase normalization
- `test_normalize_and_hash_unicode_normalization` - NFC normalization

### API Integration Tests

**File**: `tests/api/test_v1_vrm_followup_questionnaire_integration.py` (new)

Pattern from `test_v1_vrm_soc2_summary_integration.py`:
- `test_endpoint_success` - mock Temporal, verify workflow started
- `test_duplicate_criterion_question_texts_rejected` - validation error
- `test_missing_required_fields` - validation error
- `test_workflow_input_correctly_formed` - capture and verify input structure

### Workflow Tests

**File**: `tests/temporal_workers/workflows/vrm/test_index_followup_questionnaire_workflow_v1.py` (new)

Pattern from `test_index_soc2_track_workflow_v1.py`:
- `test_successful_indexing_all_responses` - all succeed, SUCCESS webhook
- `test_partial_failure` - some fail, SUCCESS webhook with failure details
- `test_all_failures` - all fail, FAILURE webhook
- `test_idempotency_existing_document` - skips existing, counts as success
- `test_polling_failure` - document fails to index

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `ai_services/api/models/vrm.py` | Add 2 models |
| `ai_services/temporal_workers/workflows/vrm/index_followup_questionnaire_workflow_v1.py` | **New** |
| `ai_services/temporal_workers/activities/vrm/send_followup_questionnaire_webhook_activity.py` | **New** |
| `ai_services/temporal_workers/config.py` | Add webhook endpoint setting |
| `ai_services/temporal_workers/workers/main_worker.py` | Register workflow + activity |
| `ai_services/api/routers/vrm_router.py` | Add endpoint |
| `tests/api/test_v1_vrm_followup_questionnaire_integration.py` | **New** |
| `tests/temporal_workers/workflows/vrm/test_index_followup_questionnaire_workflow_v1.py` | **New** |

**Note**: Utility functions and shared types are already implemented:
- `ai_services/shared/helpers/strings.py` - `normalize_and_hash()`
- `ai_services/shared/schema/questionnaire/schema.py` - `QuestionnaireItem`, `FollowupResponse`
- `ai_services/shared/schema/dto.py` - `QuestionnaireItemDTO`

---

## Implementation Order

1. Request models (`api/models/vrm.py`)
2. Workflow dataclasses
3. Webhook activity + config setting
4. Main workflow implementation
5. Worker registration
6. API endpoint
7. Integration tests
8. Workflow tests
9. Run `mypy`, `ruff`, full test suite

---

## Key References

- **Shared types**: `ai_services/shared/schema/questionnaire/schema.py`
- **String utilities**: `ai_services/shared/helpers/strings.py`
- **DTOs**: `ai_services/shared/schema/dto.py`
- **Type hierarchy**: `.agents/claude/dev/active/follow_up_questionnaire/planning/shared_types/type_hierarchy.md`
- **Pattern workflow**: `ai_services/temporal_workers/workflows/vrm/index_soc2_track_workflow_v1.py`
- **Pattern webhook**: `ai_services/temporal_workers/activities/vrm/send_soc2_summary_webhook_activity.py`

---

## Key Integration Points with Shared Types

### Using QuestionnaireItem

```python
from ai_services.shared.schema.questionnaire.schema import QuestionnaireItem

# Create from API input
item = QuestionnaireItem(
    question=resp.question_text,
    answer=resp.answer_text,
    notes=resp.notes,
)

# Get embedding content (used for Vellum upload)
content = item.embedding_content  # "Question: {q} Answer: {a}"

# Serialize for Temporal workflow
dto = item.to_dto()  # QuestionnaireItemDTO

# Deserialize in workflow
item = QuestionnaireItem.from_dto(dto)
```

### Using FollowupResponse Methods

```python
from ai_services.shared.schema.questionnaire.schema import FollowupResponse

# Compute content_hash for external_id uniqueness (criterion + question)
content_hash = FollowupResponse.compute_content_hash(
    criterion_question_text=criterion_question_text,  # Empty string for ad-hoc
    question_text=question_text,
)
# Result: 16-char hex hash of normalized "criterion_question_text||question_text"

# Compute criterion_hash for retrieval filtering
criterion_question_hash = FollowupResponse.compute_criterion_question_hash(criterion_question_text)
# Result: 16-char hex hash, or None if criterion_question_text is empty (ad-hoc)

# Build external ID manually (or use the property on FollowupResponse instance)
external_id = f"followup-{vendor_id}-{content_hash}-round{round_number}"
# Example: "followup-vendor123-a1b2c3d4e5f6g7h8-round2"

# Using FollowupResponse instance:
response = FollowupResponse(
    source=source_artifact,
    item=item,
    content_hash=content_hash,
    criterion_question_hash=criterion_question_hash,
    original_criterion_question_text=criterion_question_text,
)

# Get external_id from instance
external_id = response.external_id

# Check if ad-hoc question
is_adhoc = response.is_adhoc  # True if original_criterion_question_text is empty

# Build Vellum metadata
metadata = response.build_vellum_metadata()
# Includes: content_hash, criterion_question_hash (None for ad-hoc), question_text, answer_text, etc.
```

### Hash Field Summary

| Field | Purpose | Value for Ad-hoc |
|-------|---------|------------------|
| `content_hash` | External ID uniqueness | `hash("" \|\| question)` |
| `criterion_question_hash` | Retrieval filtering by criterion | `None` |
| `original_criterion_question_text` | Auditability/display | Empty string `""` |
