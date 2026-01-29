# SOC2 Summary Track Indexing

This document explains how SOC2 summary outputs are indexed to Vellum for semantic search retrieval.

## Overview

The SOC2 Summary workflow extracts structured information from SOC2 reports across 5 tracks:
- **Overview** - Company name, auditor, scope, time period, trust criteria, subservicers
- **Exceptions** - Control exceptions/deviations noted by auditor
- **Management Responses** - Management's responses to exceptions or findings
- **Opinion** - Auditor's opinion (unqualified, qualified, adverse, disclaimer)
- **CUECs** - Complementary User Entity Controls

After extraction, each track can optionally be indexed to Vellum for future semantic search.

## Vellum Workflow Output (What the LLM Returns)

| Track | Schema | When Empty |
|-------|--------|------------|
| **Overview** | All fields nullable (`string \| null`) | Individual fields are `null` |
| **Exceptions** | `exceptions: array` with `"empty if none are found"` | `{"exceptions": [], "relevant_excerpts_indices": []}` |
| **Management Responses** | `management_responses: array` with `"empty if none are found"` | `{"management_responses": [], "relevant_excerpts_indices": []}` |
| **Opinion** | All fields nullable | `{"opinion_type": null, "opinion_text": null, ...}` |
| **CUECs** | `cuecs: array` with `"empty if none are found"` | `{"cuecs": [], "relevant_excerpts_indices": []}` |

## Domain Objects After Conversion

The `to_summarized_soc2()` function in `run.py` converts LLM outputs to domain objects:

| Track | Domain Class | When Empty |
|-------|--------------|------------|
| Overview | `OverviewSOC2Evidence` | All fields `None` |
| Exceptions | `ExceptionsSOC2Evidence` | `excepted_controls=[]` |
| Management Responses | `ManagementResponsesSOC2Evidence` | `responses=[]` |
| Opinion | `OpinionSOC2Evidence` | All fields `None` |
| CUECs | `CUECEvidenceSOC2` | `user_controls=[]` |

## Indexable Content Generation

Each domain class has a `to_indexable_text()` method that generates content for indexing:

| Track | Method | When Empty Returns | Example |
|-------|--------|-------------------|---------|
| Overview | `OverviewSOC2Evidence.to_indexable_text()` | `""` (empty string) | - |
| Exceptions | `ExceptionsSOC2Evidence.to_indexable_text()` | `"SOC2 Exceptions\nNo exceptions noted in the audit report."` | Placeholder text |
| Management Responses | `ManagementResponsesSOC2Evidence.to_indexable_text()` | `"SOC2 Management Responses\nNo management responses included in the report."` | Placeholder text |
| Opinion | `OpinionSOC2Evidence.to_indexable_text()` | `""` (empty string) | - |
| CUECs | `CUECEvidenceSOC2.to_indexable_text()` | `"SOC2 Complementary User Entity Controls\nNo CUECs specified in the report."` | Placeholder text |

## Workflow Indexing Behavior

The workflow checks `if not indexable_track.content:` before indexing:

| Track | When Empty | Gets Indexed? | Webhook |
|-------|------------|---------------|---------|
| **Overview** | `""` | No - skipped | FAILURE: "Track has no content to index" |
| **Exceptions** | `"SOC2 Exceptions\nNo exceptions noted..."` | **Yes** | SUCCESS |
| **Management Responses** | `"SOC2 Management Responses\nNo..."` | **Yes** | SUCCESS |
| **Opinion** | `""` | No - skipped | FAILURE: "Track has no content to index" |
| **CUECs** | `"SOC2 Complementary User Entity Controls\nNo..."` | **Yes** | SUCCESS |

## Design Rationale

### Why Exceptions/Management Responses/CUECs index placeholder text:

These sections are **optional** in a SOC2 report. Their absence is semantically meaningful:
- "No exceptions" = clean audit, vendor passed all controls
- "No management responses" = no issues required management response
- "No CUECs" = no complementary user controls required

This is valuable information for search queries like "does vendor X have any exceptions?"

### Why Overview/Opinion return empty string:

These sections are **mandatory** in a valid SOC2 report:
- Overview should always contain company name, auditor, scope, etc.
- Opinion should always contain the auditor's opinion type and text

If these are empty, it indicates an extraction failure or an invalid document, not meaningful absence. Skipping indexing for these cases is appropriate.

## File References

- **Domain classes**: `ai_services/shared/schema/artifact/documents/soc2/schema.py`
- **Conversion logic**: `ai_services/vellum/support/artifact_intelligence_q2_fy26/soc2_summary/run.py`
- **Workflow indexing**: `ai_services/temporal_workers/workflows/vrm/summary_soc2_workflow_v1.py`
- **Response schemas**: `ai_services/vellum/support/artifact_intelligence_q2_fy26/soc2_summary/prompts/*/response.json`
