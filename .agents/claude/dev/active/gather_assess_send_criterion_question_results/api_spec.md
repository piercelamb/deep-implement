# Assessment Webhook API Change Specification

## Summary

**Breaking change** to the assessment webhook payload. The flat `source` array is being replaced with a structured `testableCriteria` array that provides individual question-level results with their specific evidence sources.

## Change Overview

| Field | Before | After |
|-------|--------|-------|
| `status` | No change | No change |
| `criteriaName` | No change | No change |
| `analysisSummary` | No change | No change |
| `source` | Flat array of all evidence | **REMOVED** |
| `testableCriteria` | N/A | **NEW** - Array of question results with nested sources |

## Schema Definitions

### AssessmentWebhookDTO (Updated)

```typescript
interface AssessmentWebhookDTO {
  status: "MET" | "NOT_MET" | "INCONCLUSIVE";
  criteriaName: string;
  analysisSummary: string;
  testableCriteria: TestableCriteriaWebhookDTO[];  // NEW - replaces source
}
```

### TestableCriteriaWebhookDTO (New)

```typescript
interface TestableCriteriaWebhookDTO {
  question: string;                      // The testable criterion question text
  status: "MET" | "NOT_MET" | "INCONCLUSIVE";  // Assessment result for this question
  explanation: string;                   // LLM reasoning for the assessment
  source: AssessmentSourceWebhookDTO[];  // Evidence supporting this specific question
}
```

### AssessmentSourceWebhookDTO (Unchanged)

```typescript
interface AssessmentSourceWebhookDTO {
  docExcerpt: string;     // Relevant text excerpt from the document
  documentName: string;   // Human-readable document name
  fileId: string;         // Document identifier
  referencedOn: string;   // ISO 8601 timestamp when the evidence was referenced
}
```

## Example Payloads

### Before (Current)

```json
{
  "status": "MET",
  "criteriaName": "Access Control",
  "analysisSummary": "The organization demonstrates strong access control practices...",
  "source": [
    {
      "docExcerpt": "All users must authenticate via SSO...",
      "documentName": "Security Policy v2.pdf",
      "fileId": "12345",
      "referencedOn": "2025-01-15T14:30:00+00:00"
    },
    {
      "docExcerpt": "Access reviews are conducted quarterly...",
      "documentName": "Security Policy v2.pdf",
      "fileId": "12345",
      "referencedOn": "2025-01-15T14:30:00+00:00"
    },
    {
      "docExcerpt": "MFA is required for all privileged accounts...",
      "documentName": "IT Controls Handbook.pdf",
      "fileId": "67890",
      "referencedOn": "2025-01-15T14:30:01+00:00"
    }
  ]
}
```

### After (New)

```json
{
  "status": "MET",
  "criteriaName": "Access Control",
  "analysisSummary": "The organization demonstrates strong access control practices...",
  "testableCriteria": [
    {
      "question": "Does the organization require authentication for all users?",
      "status": "MET",
      "explanation": "The security policy explicitly requires SSO authentication for all users accessing company systems.",
      "source": [
        {
          "docExcerpt": "All users must authenticate via SSO...",
          "documentName": "Security Policy v2.pdf",
          "fileId": "12345",
          "referencedOn": "2025-01-15T14:30:00+00:00"
        }
      ]
    },
    {
      "question": "Are access reviews performed periodically?",
      "status": "MET",
      "explanation": "Documentation confirms quarterly access reviews are conducted as part of the organization's security controls.",
      "source": [
        {
          "docExcerpt": "Access reviews are conducted quarterly...",
          "documentName": "Security Policy v2.pdf",
          "fileId": "12345",
          "referencedOn": "2025-01-15T14:30:00+00:00"
        }
      ]
    },
    {
      "question": "Is multi-factor authentication enforced for privileged access?",
      "status": "MET",
      "explanation": "The IT Controls Handbook mandates MFA for all privileged accounts.",
      "source": [
        {
          "docExcerpt": "MFA is required for all privileged accounts...",
          "documentName": "IT Controls Handbook.pdf",
          "fileId": "67890",
          "referencedOn": "2025-01-15T14:30:01+00:00"
        }
      ]
    }
  ]
}
```

## Migration Notes

1. **Remove usage of top-level `source` array** - This field will no longer be present
2. **Iterate over `testableCriteria`** to access individual question assessments
3. **Access sources per question** via `testableCriteria[].source` instead of the top-level array
4. **New data available**: Each question now includes its own `status` and `explanation` fields

## Data Mapping

To reconstruct the old flat source list (if needed for backwards compatibility in your code):

```typescript
const allSources = payload.testableCriteria.flatMap(tc => tc.source);
```
