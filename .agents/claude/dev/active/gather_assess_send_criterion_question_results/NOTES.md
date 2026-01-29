# Notes: Send Criterion Question Results in Webhook

## 2025-01-27

- Researched workflow: gather/assess → criteria_review → ReviewedCriterion → webhook
- Current webhook (`AssessmentWebhookDTO`) only sends aggregate: status, criteriaName, analysisSummary, flattened sources
- Individual `CriterionEvidence` (testable criteria) data exists but not sent: question text, per-question status, explanation, summary, reason
- Proposed: Add `TestableCriteriaWebhookDTO` and `testableCriteria` field to webhook DTO
- Add `CriterionEvidence.to_assessment_webhook_dto()` method for serialization
- Use camelCase for webhook DTOs to match existing pattern
- Plan written to planning/PLAN.md
