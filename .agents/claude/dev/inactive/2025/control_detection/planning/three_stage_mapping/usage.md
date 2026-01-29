uv run python ai_services/scripts/experiments/control_detection/run_stage3_standalone.py \
      --stage2-dir ai_services/scripts/experiments/control_detection/files/llm_outputs/control_centric/20260101_150123 \
      --policy Shared_Responsibility_Policy \
      --experiment template_policies_v2


# Stage 3 Standalone Runner - Usage Guide

This document describes how to use `run_stage3_standalone.py` to run Stage 3 verification on existing Stage 2 outputs.

## Overview

The standalone Stage 3 runner allows you to:
- Run Stage 3 verification independently of Stage 2
- Process existing Stage 2 outputs from disk
- Resume interrupted runs (skips already-verified controls)
- Test different verification prompts without re-running Stage 2

## Prerequisites

1. **Stage 2 outputs** - A completed Stage 2 run with batch JSON files
2. **Policy PDFs** - The original policy PDFs used in Stage 2
3. **GCP credentials** - For Vertex AI / Gemini access

## Basic Invocation

```bash
# Run Stage 3 on all policies from a Stage 2 run
uv run python ai_services/scripts/experiments/control_detection/run_stage3_standalone.py \
  --stage2-dir ai_services/scripts/experiments/control_detection/files/llm_outputs/control_centric/20260101_150123
```

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--stage2-dir` | (required) | Path to Stage 2 output directory |
| `--output-dir` | `<stage2-dir>/stage3_<timestamp>` | Where to write Stage 3 results |
| `--experiment` | `template_policies` | Experiment name for loading policy PDFs |
| `--prompts-dir` | `control_centric_false_negatives_take3` | Which system prompt to use |
| `--gcp-project` | `ai-team-gemini-dev` | GCP project for Vertex AI |
| `--model` | `gemini-3-flash-preview` | Gemini model to use |
| `--policy` | (all) | Process only this policy (by directory name) |
| `--max-concurrent` | `5` | Max concurrent Stage 3 LLM calls |

## Example Commands

### Process all policies

```bash
uv run python ai_services/scripts/experiments/control_detection/run_stage3_standalone.py \
  --stage2-dir ai_services/scripts/experiments/control_detection/files/llm_outputs/control_centric/20260101_150123
```

### Process a single policy (for testing)

```bash
uv run python ai_services/scripts/experiments/control_detection/run_stage3_standalone.py \
  --stage2-dir ai_services/scripts/experiments/control_detection/files/llm_outputs/control_centric/20260101_150123 \
  --policy Acceptable_Use_Policy
```

### Use a different prompts directory

```bash
uv run python ai_services/scripts/experiments/control_detection/run_stage3_standalone.py \
  --stage2-dir ai_services/scripts/experiments/control_detection/files/llm_outputs/control_centric/20260101_150123 \
  --prompts-dir control_centric_false_negatives_take4
```

### Specify custom output directory

```bash
uv run python ai_services/scripts/experiments/control_detection/run_stage3_standalone.py \
  --stage2-dir ai_services/scripts/experiments/control_detection/files/llm_outputs/control_centric/20260101_150123 \
  --output-dir ai_services/scripts/experiments/control_detection/files/llm_outputs/stage3_experiment_v2
```

### Higher concurrency for faster processing

```bash
uv run python ai_services/scripts/experiments/control_detection/run_stage3_standalone.py \
  --stage2-dir ai_services/scripts/experiments/control_detection/files/llm_outputs/control_centric/20260101_150123 \
  --max-concurrent 10
```

---

## Example Log Output

### Successful Run (Fresh Start)

```
2026-01-01 17:00:00,123 - INFO - __main__ - Loading Stage 2 outputs from ai_services/scripts/experiments/control_detection/files/llm_outputs/control_centric/20260101_150123
2026-01-01 17:00:00,234 - INFO - __main__ - Loaded 5 MAPPED controls for Acceptable_Use_Policy
2026-01-01 17:00:00,345 - INFO - __main__ - Loaded 12 MAPPED controls for AI_Governance_Policy
2026-01-01 17:00:00,456 - INFO - __main__ - Loaded 8 MAPPED controls for Asset_Management_Policy
2026-01-01 17:00:00,567 - INFO - __main__ - Output directory: ai_services/scripts/experiments/control_detection/files/llm_outputs/control_centric/20260101_150123/stage3_20260101_170000
2026-01-01 17:00:00,678 - INFO - __main__ - Loading DCF controls...
2026-01-01 17:00:00,789 - INFO - __main__ - Loaded 779 DCF controls

2026-01-01 17:00:01,000 - INFO - __main__ - Policy 'Acceptable_Use_Policy': 5 MAPPED, 0 already verified
2026-01-01 17:00:01,100 - INFO - __main__ - Creating Gemini cache for Stage 3: 'Acceptable_Use_Policy'...
2026-01-01 17:00:05,200 - INFO - __main__ - Created cache: projects/ai-team-gemini-dev/locations/global/cachedContents/abc123xyz
2026-01-01 17:00:08,300 - INFO - __main__ - VERIFIED: DCF-37
2026-01-01 17:00:11,400 - INFO - __main__ - REJECTED: DCF-195 - Control requires Business Associate Agreement, document is Acceptable Use Policy
2026-01-01 17:00:14,500 - INFO - __main__ - REJECTED: DCF-94 - G-15 violated: Document is not a Physical Security Policy
2026-01-01 17:00:17,600 - INFO - __main__ - VERIFIED: DCF-800
2026-01-01 17:00:20,700 - INFO - __main__ - REJECTED: DCF-167 - Evidence not found for Business Impact Analysis requirement
2026-01-01 17:00:20,800 - INFO - __main__ - Deleted cache: projects/ai-team-gemini-dev/locations/global/cachedContents/abc123xyz

2026-01-01 17:00:21,000 - INFO - __main__ - Policy 'AI_Governance_Policy': 12 MAPPED, 0 already verified
2026-01-01 17:00:21,100 - INFO - __main__ - Creating Gemini cache for Stage 3: 'AI_Governance_Policy'...
...
```

### Resume Run (Partially Completed)

```
2026-01-01 18:30:00,123 - INFO - __main__ - Loading Stage 2 outputs from ai_services/scripts/experiments/control_detection/files/llm_outputs/control_centric/20260101_150123
2026-01-01 18:30:00,234 - INFO - __main__ - Loaded 5 MAPPED controls for Acceptable_Use_Policy
2026-01-01 18:30:00,345 - INFO - __main__ - Loaded 12 MAPPED controls for AI_Governance_Policy
2026-01-01 18:30:00,456 - INFO - __main__ - Output directory: ai_services/scripts/experiments/control_detection/files/llm_outputs/control_centric/20260101_150123/stage3_20260101_170000
2026-01-01 18:30:00,567 - INFO - __main__ - Loading DCF controls...
2026-01-01 18:30:00,678 - INFO - __main__ - Loaded 779 DCF controls

2026-01-01 18:30:01,000 - INFO - __main__ - Policy 'Acceptable_Use_Policy': 5 MAPPED, 5 already verified
2026-01-01 18:30:01,100 - INFO - __main__ - All controls already verified for 'Acceptable_Use_Policy'

2026-01-01 18:30:01,200 - INFO - __main__ - Policy 'AI_Governance_Policy': 12 MAPPED, 7 already verified
2026-01-01 18:30:01,300 - INFO - __main__ - Creating Gemini cache for Stage 3: 'AI_Governance_Policy'...
2026-01-01 18:30:05,400 - INFO - __main__ - Created cache: projects/ai-team-gemini-dev/locations/global/cachedContents/def456uvw
2026-01-01 18:30:08,500 - INFO - __main__ - VERIFIED: DCF-512
2026-01-01 18:30:11,600 - INFO - __main__ - REJECTED: DCF-623 - Quote hallucinated: claimed evidence not found in document
2026-01-01 18:30:14,700 - INFO - __main__ - VERIFIED: DCF-789
2026-01-01 18:30:17,800 - INFO - __main__ - REJECTED: DCF-845 - Binding language missing for mandate control
2026-01-01 18:30:20,900 - INFO - __main__ - VERIFIED: DCF-901
2026-01-01 18:30:21,000 - INFO - __main__ - Deleted cache: projects/ai-team-gemini-dev/locations/global/cachedContents/def456uvw
...
```

### Error Handling - PDF Not Found

```
2026-01-01 19:00:00,123 - INFO - __main__ - Loading Stage 2 outputs from ai_services/scripts/experiments/control_detection/files/llm_outputs/control_centric/20260101_150123
2026-01-01 19:00:00,234 - INFO - __main__ - Loaded 3 MAPPED controls for Custom_Policy_Name
2026-01-01 19:00:00,345 - INFO - __main__ - Output directory: ai_services/scripts/experiments/control_detection/files/llm_outputs/control_centric/20260101_150123/stage3_20260101_190000
2026-01-01 19:00:00,456 - INFO - __main__ - Loading DCF controls...
2026-01-01 19:00:00,567 - INFO - __main__ - Loaded 779 DCF controls

2026-01-01 19:00:01,000 - INFO - __main__ - Policy 'Custom_Policy_Name': 3 MAPPED, 0 already verified
2026-01-01 19:00:01,100 - ERROR - __main__ - Failed to load PDF for 'Custom_Policy_Name': PDF not found: ai_services/scripts/experiments/control_detection/files/policies/template_policies/Custom Policy Name.pdf
```

### Error Handling - LLM Errors

```
2026-01-01 19:15:00,123 - INFO - __main__ - Policy 'Encryption_Policy': 8 MAPPED, 0 already verified
2026-01-01 19:15:00,234 - INFO - __main__ - Creating Gemini cache for Stage 3: 'Encryption_Policy'...
2026-01-01 19:15:04,345 - INFO - __main__ - Created cache: projects/ai-team-gemini-dev/locations/global/cachedContents/ghi789abc
2026-01-01 19:15:07,456 - INFO - __main__ - VERIFIED: DCF-123
2026-01-01 19:15:10,567 - ERROR - __main__ - Gemini call failed for DCF-456: ResourceExhausted: 429 Quota exceeded
2026-01-01 19:15:13,678 - INFO - __main__ - VERIFIED: DCF-789
2026-01-01 19:15:16,789 - ERROR - __main__ - JSON parse error for DCF-321: Expecting ',' delimiter: line 15 column 3
2026-01-01 19:15:19,890 - INFO - __main__ - REJECTED: DCF-654 - Domain mismatch: evidence addresses network security, control requires physical security
...
```

### Final Summary Output

```
============================================================
STAGE 3 VERIFICATION SUMMARY
============================================================
Total MAPPED from Stage 2:  127
Total VERIFIED:             34
Total REJECTED:             93
Verification rate:          26.8%

Results saved to: ai_services/scripts/experiments/control_detection/files/llm_outputs/control_centric/20260101_150123/stage3_20260101_170000
```

---

## Output File Structure

```
<stage2-dir>/stage3_<timestamp>/
├── Acceptable_Use_Policy/
│   ├── verification_DCF-37.json
│   ├── verification_DCF-195.json
│   ├── verification_DCF-94.json
│   └── ...
├── AI_Governance_Policy/
│   ├── verification_DCF-512.json
│   ├── verification_DCF-623.json
│   └── ...
├── Asset_Management_Policy/
│   └── ...
└── ...
```

### Verification File Format

Each `verification_*.json` file contains:

```json
{
  "control_id": "DCF-37",
  "stage2_input": {
    "evidence_quote": "This policy specifies acceptable use of end-user computing devices and technology.",
    "location_reference": "Page 1, Purpose",
    "reasoning": "Direct match: The document is an established Acceptable Use Policy..."
  },
  "stage3_response": {
    "control_type_determined": "ARTIFACT",
    "verified_evidence_quote": "This policy specifies acceptable use of end-user computing devices and technology.",
    "verified_location": "Page 1, Purpose section",
    "stage2_quote_validated": true,
    "reasoning": "Step 1: This is an ARTIFACT control requiring existence of an Acceptable Use Policy. Step 2: Located evidence in Purpose section. Step 3: Document title and purpose statement confirm this is an Acceptable Use Policy. Step 4: No guardrails violated. Step 5: VERIFIED.",
    "verdict": "VERIFIED",
    "rejection_reason": "",
    "guardrails_violated": []
  },
  "thought_summary": "",
  "timestamp": "2026-01-01T17:00:08Z",
  "attempt_count": 1
}
```

For rejected controls:

```json
{
  "control_id": "DCF-94",
  "stage2_input": {
    "evidence_quote": "Clean Desk Policy: Employees must secure sensitive documents...",
    "location_reference": "Page 4, Clean Desk section",
    "reasoning": "Policy contains clean desk requirements which relate to physical security..."
  },
  "stage3_response": {
    "control_type_determined": "ARTIFACT",
    "verified_evidence_quote": "",
    "verified_location": "",
    "stage2_quote_validated": true,
    "reasoning": "Step 1: This is an ARTIFACT control requiring a Physical Security Policy. Step 2: Located the claimed clean desk section. Step 3: However, this document is titled 'Acceptable Use Policy', not 'Physical Security Policy'. Step 4: G-15 violated - document type mismatch. Step 5: REJECTED.",
    "verdict": "REJECTED",
    "rejection_reason": "G-15: Document is Acceptable Use Policy, not Physical Security Policy",
    "guardrails_violated": ["G-15"]
  },
  "thought_summary": "",
  "timestamp": "2026-01-01T17:00:14Z",
  "attempt_count": 1
}
```

---

## Code Branches and Flow

```
main()
├── Load Stage 2 outputs from --stage2-dir
│   ├── For each policy directory
│   │   └── Parse batch_*.json files
│   │       └── Extract MAPPED controls (decision == "MAPPED")
│   └── Log: "Loaded N MAPPED controls for <policy>"
│
├── Filter to --policy if specified
│   └── Error if policy not found
│
├── Load DCF controls
│   └── Log: "Loaded 779 DCF controls"
│
└── For each policy with MAPPED controls
    ├── Check existing verifications (resume capability)
    │   ├── If all verified: Log "All controls already verified" → skip
    │   └── If partial: Log "N MAPPED, M already verified" → process remaining
    │
    ├── Load policy PDF
    │   └── Error: "Failed to load PDF" if not found → skip policy
    │
    ├── Create Gemini cache (PDF + system prompt)
    │   └── Log: "Created cache: <cache_name>"
    │
    ├── For each MAPPED control needing verification
    │   ├── Build verification prompt
    │   ├── Call Gemini with thinking mode
    │   │   ├── Success → parse JSON response
    │   │   ├── Empty response → REJECTED
    │   │   ├── JSON parse error → REJECTED
    │   │   └── LLM error (quota, timeout) → REJECTED
    │   │
    │   ├── Write verification_*.json to disk
    │   └── Log: "VERIFIED: <control>" or "REJECTED: <control> - <reason>"
    │
    ├── Delete Gemini cache
    │   └── Log: "Deleted cache: <cache_name>"
    │
    └── Aggregate metrics for summary

Print final summary:
├── Total MAPPED from Stage 2
├── Total VERIFIED
├── Total REJECTED
├── Verification rate
└── Results directory path
```

---

## Troubleshooting

### "PDF not found" error

The script looks up PDF filenames using the experiment config's `policy_name_to_pdf` mapping. If your policy directory name doesn't match, check:

1. The policy directory name in Stage 2 outputs (e.g., `Acceptable_Use_Policy`)
2. The mapping in `experiment_config.py` under `TEMPLATE_POLICY_NAME_TO_PDF`

### Cache creation fails

- Verify GCP credentials are set up: `gcloud auth application-default login`
- Check the `--gcp-project` is correct
- Ensure the PDF file is valid and not corrupted

### High rejection rate

Check the rejection reasons in the verification files:
- **G-15 violations**: Document type mismatch (e.g., control requires "Physical Security Policy" but document is "Acceptable Use Policy")
- **Quote hallucinated**: Stage 2 generated a fake evidence quote
- **Binding language missing**: Control requires must/shall/will but evidence is aspirational

### Resume not working

Ensure the `--output-dir` points to the same directory as the previous run. The script checks for `verification_*.json` files to determine which controls to skip.
