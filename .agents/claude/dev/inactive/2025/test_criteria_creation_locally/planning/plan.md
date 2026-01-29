# Plan: Create Script to Invoke VRM Questionnaire Criteria Workflow

## Overview

Create a script at `ai_services/scripts/invoke_questionnaire_criteria.py` that:
1. Accepts a local file path as input
2. Uploads the file to the test S3 bucket
3. Generates a presigned URL for the uploaded file
4. Outputs a curl command to invoke `start_vrm_questionnaire_criteria_workflow`

## Implementation Details

### Script Location
`ai_services/scripts/invoke_questionnaire_criteria.py`

### Dependencies
- `boto3` - for S3 upload and presigned URL generation (already in project)
- `uuid` - for generating job_id, tenant_id, questionnaire_id (stdlib)
- `argparse` - for CLI argument parsing (stdlib)
- `json` - for JSON formatting (stdlib)

### CLI Interface
```bash
uv run python -m ai_services.scripts.invoke_questionnaire_criteria <file_path> [options]

# Options:
#   --api-url     API base URL (default: http://localhost:9000)
#   --bucket      S3 bucket to upload to (default: from temporal config)
```

### Implementation Steps

#### 1. S3 Upload Function
Reuse patterns from `tests/e2e/utils/boto3_utils.py`:
- Use `boto3.client("s3")` to upload file
- Generate S3 key in format: `questionnaire_extraction/questionnaires/{uuid}/{filename}`
- Use the test bucket from `ai_services.temporal_workers.config.settings.test_s3_bucket_name`

#### 2. Presigned URL Generation
Reuse `build_presigned_url()` pattern from `tests/e2e/utils/boto3_utils.py`:
```python
s3_client = boto3.client("s3", config=boto3.session.Config(signature_version="s3v4"))
presigned_url = s3_client.generate_presigned_url(
    "get_object",
    Params={"Bucket": bucket, "Key": key},
    ExpiresIn=3600
)
```

#### 3. Generate Request Body
Following the `VrmQuestionnaireCriteriaWorkflowRequest` model structure:
```python
{
    "jobId": str(uuid.uuid4()),
    "tenantId": str(uuid.uuid4()),
    "tenantName": "Local Test",
    "questionnaires": [
        {
            "questionnaireId": str(uuid.uuid4()),
            "preSignedS3Url": presigned_url,
            "filename": filename
        }
    ]
}
```

#### 4. Output Curl Command
Format and print the curl command:
```bash
curl -X POST http://localhost:9000/api/v1/vrm/questionnaire/criteria \
  -H "Content-Type: application/json" \
  -d '<json_body>'
```

### Script Structure

```python
"""Script to invoke VRM questionnaire criteria workflow with a local file."""

import argparse
import json
import uuid
from pathlib import Path

import boto3

from ai_services.temporal_workers.config import settings


def upload_to_s3(file_path: Path, bucket: str) -> tuple[str, str]:
    """Upload file to S3 and return (key, filename)."""
    ...

def build_presigned_url(bucket: str, key: str, expiration_seconds: int = 3600) -> str:
    """Generate a presigned URL for S3 object access."""
    ...

def build_request_body(presigned_url: str, filename: str) -> dict:
    """Build the API request body with generated UUIDs."""
    ...

def format_curl_command(api_url: str, body: dict) -> str:
    """Format the curl command string."""
    ...

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(...)
    args = parser.parse_args()

    # 1. Upload file to S3
    # 2. Generate presigned URL
    # 3. Build request body
    # 4. Print curl command

if __name__ == "__main__":
    main()
```

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `ai_services/scripts/invoke_questionnaire_criteria.py` | Create | Main script |

## Reference Files

| File | Purpose |
|------|---------|
| `tests/e2e/utils/boto3_utils.py` | Pattern for S3 operations and presigned URLs |
| `ai_services/temporal_workers/config.py` | Test S3 bucket configuration |
| `ai_services/api/models/vrm.py` | Request model structure |
| `ai_services/api/routers/vrm_router.py` | API endpoint reference |

## Example Usage

```bash
# Upload a PDF and get curl command
uv run python -m ai_services.scripts.invoke_questionnaire_criteria \
  ai_services/scripts/files/Drata_AI_Pentest_Summary.pdf

# Output:
# Uploaded file to s3://da-localdev-ai-services-agent-testcases-us-west-2-bucket/questionnaire_extraction/questionnaires/abc123/Drata_AI_Pentest_Summary.pdf
#
# curl -X POST http://localhost:9000/api/v1/vrm/questionnaire/criteria \
#   -H "Content-Type: application/json" \
#   -d '{
#     "jobId": "550e8400-e29b-41d4-a716-446655440000",
#     "tenantId": "550e8400-e29b-41d4-a716-446655440001",
#     "tenantName": "Local Test",
#     "questionnaires": [{
#       "questionnaireId": "550e8400-e29b-41d4-a716-446655440002",
#       "preSignedS3Url": "https://...",
#       "filename": "Drata_AI_Pentest_Summary.pdf"
#     }]
#   }'
```
