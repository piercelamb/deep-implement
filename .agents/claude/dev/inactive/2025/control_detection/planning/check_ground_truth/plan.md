# Ground Truth Validation Pipeline

## Background: Control Detection Experiment

### What is this experiment?

The **Control Detection Experiment** is a machine learning pipeline that automatically maps security controls to policy documents. It's part of Drata's GRC (Governance, Risk, and Compliance) automation efforts.

**The problem it solves:** Organizations have hundreds of security controls (requirements like "encrypt data at rest") and dozens of policy documents. Manually mapping which policies address which controls is tedious and error-prone. This experiment automates that mapping.

### Key Concepts

| Term | Definition |
|------|------------|
| **DCF Control** | A specific security requirement from Drata's Control Framework (e.g., "DCF-37: Acceptable Use Policy exists"). There are ~779 controls in our dataset. |
| **Policy Document** | A PDF document describing organizational security policies (e.g., "Acceptable_Use_Policy.pdf") |
| **Control-to-Policy Mapping** | The assertion that a policy document "addresses" a control - meaning it contains binding language mandating the control's requirements |
| **Ground Truth (GT)** | Human-annotated labels in `eval.csv` that say "this policy SHOULD map to these controls" |

### How the experiment works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CONTROL DETECTION PIPELINE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. RETRIEVAL (ColModernVBERT embeddings)                                   │
│     - Score all 779 controls against each page of the policy PDF            │
│     - Keep controls scoring above threshold (default: 0.5)                  │
│     - Typically yields 100-500 candidate controls per document              │
│                                                                              │
│  2. BATCHING                                                                │
│     - Group candidate controls into batches of ~10                          │
│     - Uses page-aware clustering to batch semantically similar controls     │
│     - Limited to MAX_CALLS (50) LLM calls per document                      │
│                                                                              │
│  3. LLM DECISION (Gemini with PDF context caching)                          │
│     - For each batch: "Does the policy contain binding language for these   │
│       controls?"                                                            │
│     - Returns one of three decisions per control:                           │
│         • MAPPED - Policy fully addresses the control                       │
│         • PARTIAL - Policy partially addresses it (has gaps)                │
│         • NO_MATCH - Policy doesn't address this control                    │
│                                                                              │
│  4. EVALUATION                                                              │
│     - Compare LLM predictions against ground truth                          │
│     - Calculate precision, recall, F1                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### The ground truth problem

Our ground truth labels come from `files/eval.csv`. Each row maps a policy to its expected controls:

```csv
_Name,_Controls
Acceptable Use Policy,"DCF-1, DCF-37, DCF-106, DCF-32, ..."
Data Protection Policy,"DCF-45, DCF-67, DCF-89, ..."
```

**The issue:** These ground truth labels may not be perfect. When the LLM says "NO_MATCH" but ground truth says "should match", there are two possibilities:
1. **LLM is wrong** - The policy DOES address the control, LLM missed it
2. **Ground truth is wrong** - The policy does NOT address the control, human annotator made an error

This pipeline helps us distinguish between these two cases by having a second LLM "judge" review disputed mappings.

### Key files in the experiment

| File | Purpose |
|------|---------|
| `run_experiment.py` | Main CLI entry point for running experiments |
| `control_centric_decider.py` | LLM decision logic, PDF caching, batch processing |
| `analyze_ground_truth.py` | Script to analyze GT control decisions post-experiment |
| `files/eval.csv` | Ground truth mappings (policy → controls) |
| `files/dcf_controls.csv` | All 779 DCF control definitions |
| `files/llm_outputs/control_centric/{timestamp}/` | Saved LLM outputs from experiments |
| `prompts/control_centric_expanded/` | System/user prompts for control mapping |

### LLM output structure

Each experiment run saves outputs to `files/llm_outputs/control_centric/{timestamp}/{policy_name}/`:

```
batch_000.json      # LLM response for first batch of controls
batch_000_prompt.txt  # The prompt sent to LLM
batch_001.json
...
```

Each batch JSON contains:
```json
{
  "batch_id": 0,
  "control_ids": ["DCF-37", "DCF-195", ...],
  "response": {
    "batch_results": [
      {
        "control_id": "DCF-37",
        "decision": "MAPPED",
        "confidence": "high",
        "evidence_quote": "This policy specifies...",
        "reasoning": "The document explicitly mandates..."
      },
      ...
    ]
  }
}
```

---

## Overview

This pipeline validates ground truth labels by having a second LLM "judge" review cases where the original LLM disagreed with ground truth.

For any GT control that was NOT classified as `MAPPED`, run a "judge" prompt to determine:
1. **LLM_WRONG**: The ground truth is correct, but the LLM missed it (or was too strict)
2. **GT_WRONG**: The ground truth label is incorrect (policy is **irrelevant** to this control)

---

## Critical Design Decisions

These decisions address potential "footguns" identified during plan review:

### 1. The "PARTIAL" Trap

**Problem:** When GT says "MAPPED" but LLM says "PARTIAL", what should the judge decide?

**Decision:** In GRC, partial coverage is usually "good enough" to keep the GT label. A policy that addresses the *core intent* of a control—even with minor gaps—should keep its GT mapping.

| Original Decision | Judge Should Rule | Rationale |
|-------------------|-------------------|-----------|
| `NO_MATCH` | Could be either | Truly disputed - needs full review |
| `PARTIAL` | Lean toward `LLM_WRONG` | Partial coverage = keep GT unless policy is irrelevant |

**Prompt guidance:** "If the policy addresses the core intent of the control, even with gaps, rule `LLM_WRONG` (keep GT). Only rule `GT_WRONG` if the policy is **irrelevant** to the control."

### 2. NOT_EVALUATED Controls

**Problem:** GT controls that never appeared in any batch (filtered out by retrieval threshold or MAX_CALLS truncation) won't be in `batch_*.json` files. These are potentially the most important errors to catch!

**Decision:** Add a third category: `NOT_SENT_TO_LLM`. These controls also need judge review.

```python
class DisputeReason(StrEnum):
    PARTIAL = "PARTIAL"           # LLM said PARTIAL, not MAPPED
    NO_MATCH = "NO_MATCH"         # LLM said NO_MATCH
    NOT_SENT_TO_LLM = "NOT_SENT"  # GT control never reached LLM (retrieval filtered it out)
```

For `NOT_SENT_TO_LLM` cases, there's no original LLM reasoning—the judge must evaluate fresh.

### 3. Anchoring Bias

**Problem:** Showing the original LLM's decision and reasoning could bias the judge toward agreeing with it.

**Decision:** Accept the bias trade-off for now. The original reasoning provides valuable context about *what was already checked*. However, the prompt explicitly instructs: "Be critical of both the LLM and the ground truth - neither is assumed correct."

**Future enhancement:** Could implement "blind judge" mode where original decision is hidden, then revealed for comparison.

### 4. Concurrency & Rate Limits

**Problem:** Evaluating controls one-at-a-time sequentially could take 60-100+ seconds per document with many disputes.

**Decision:** Use `asyncio.Semaphore` to limit parallel judge calls (default: 5 concurrent). This balances speed with Vertex AI rate limits.

```python
self._semaphore = asyncio.Semaphore(config.max_concurrent_judges)  # Default: 5
```

### 5. Resumability

**Problem:** If a run dies midway, we don't want to re-judge everything.

**Decision:** Write individual `judge_{control_id}.json` files. On restart, skip controls that already have output files (unless `--force` flag is set).

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         CLI: run_validation.py                            │
│  --experiment NAME           (run experiment first, then validate)        │
│  --row N                     (single doc mode)                            │
│  --experiment-timestamp TS   (reuse existing experiment, skip Phase 1)    │
│  --max-rows N                (multi doc mode)                             │
│  --force                     (re-judge even if output exists)             │
│  --max-judges N              (limit judges for testing, default: all)     │
└────────────────────────────────────────────┬─────────────────────────────┘
                                             │
                    ┌────────────────────────┴────────────────────────┐
                    ▼                                                 ▼
         ┌──────────────────────┐                        ┌────────────────────────┐
         │ PHASE 1: Experiment  │                        │ SKIP: Load From        │
         │ (if no --exp-ts)     │                        │ Existing Results       │
         │                      │                        │ (if --exp-ts)          │
         │ Calls run_experiment │                        │                        │
         │ with control_centric │                        │ Parses batch_*.json    │
         │ mode                 │                        │ from timestamp dir     │
         └──────────┬───────────┘                        └──────────┬─────────────┘
                    │                                               │
                    └────────────────────┬──────────────────────────┘
                                         ▼
              ┌──────────────────────────────────────────────────────┐
              │ PHASE 2: Collect Disputed GT Controls                │
              │                                                       │
              │ For each policy:                                      │
              │   - Load GT from eval.csv                             │
              │   - Find GT in batch_*.json outputs                   │
              │   - Collect THREE categories:                         │
              │     * PARTIAL - LLM found partial match               │
              │     * NO_MATCH - LLM found no match                   │
              │     * NOT_SENT - GT never reached LLM (filtered out)  │
              └──────────────────────────┬───────────────────────────┘
                                         ▼
              ┌──────────────────────────────────────────────────────┐
              │ PHASE 3: Run Judge Prompts (with concurrency limit)  │
              │                                                       │
              │ For each disputed GT control:                         │
              │   - Skip if output file exists (unless --force)       │
              │   - Upload PDF to Gemini cache (per document)         │
              │   - Send judge prompt with control + context          │
              │   - Write judge_{control_id}.json immediately         │
              │   - Use asyncio.Semaphore(5) for rate limiting        │
              └──────────────────────────┬───────────────────────────┘
                                         ▼
              ┌──────────────────────────────────────────────────────┐
              │ PHASE 4: Output Results                              │
              │                                                       │
              │ Save to: files/llm_outputs/gt_validation/{ts}/       │
              │   - run_metadata.json      (config for reproducibility)│
              │   - validation_summary.json                          │
              │   - detailed_results.json                            │
              │   - grc_review_llm_wrong.csv                         │
              │   - grc_review_gt_wrong.csv                          │
              │   - grc_review_uncertain.csv                         │
              │   - grc_review_not_sent.csv  (controls never evaluated)│
              └──────────────────────────────────────────────────────┘
```

---

## File Structure

```
ai_services/scripts/experiments/control_detection/
├── ground_truth_validation/              # NEW FOLDER
│   ├── __init__.py
│   ├── run_validation.py                 # CLI entry point
│   ├── gt_collector.py                   # Phase 2: Collect non-MAPPED GT
│   ├── judge_decider.py                  # Phase 3: Judge LLM logic
│   └── models.py                         # Judge-specific data models
│
├── prompts/
│   └── judge/                            # NEW FOLDER
│       ├── system                        # Judge system prompt
│       ├── user                          # Judge user prompt template
│       └── response.json                 # Judge response schema
│
└── files/llm_outputs/
    └── gt_validation/                    # NEW OUTPUT FOLDER
        └── {timestamp}/
            └── {policy_name}/
                ├── judge_results.json
                └── judge_{control_id}.json
```

---

## CLI Interface

```bash
# Run full pipeline: experiment + validation (single doc)
python -m ai_services.scripts.experiments.control_detection.ground_truth_validation.run_validation \
    --experiment original \
    --row 0 \
    --gcp-project PROJECT_ID

# Run full pipeline: multi-doc
python -m ai_services.scripts.experiments.control_detection.ground_truth_validation.run_validation \
    --experiment original \
    --max-rows 5 \
    --gcp-project PROJECT_ID

# Validate existing experiment results (skip Phase 1)
python -m ai_services.scripts.experiments.control_detection.ground_truth_validation.run_validation \
    --experiment-timestamp 20251226_150103 \
    --gcp-project PROJECT_ID

# Dry run: limit to 5 judges for testing (prevent bill shock)
python -m ai_services.scripts.experiments.control_detection.ground_truth_validation.run_validation \
    --experiment-timestamp 20251226_150103 \
    --gcp-project PROJECT_ID \
    --max-judges 5

# Force re-evaluation (ignore existing judge_*.json files)
python -m ai_services.scripts.experiments.control_detection.ground_truth_validation.run_validation \
    --experiment-timestamp 20251226_150103 \
    --gcp-project PROJECT_ID \
    --force
```

---

## Data Models

### Dispute Categories

```python
class DisputeReason(StrEnum):
    """Why this GT control needs judge review."""
    PARTIAL = "PARTIAL"           # LLM said PARTIAL, not MAPPED
    NO_MATCH = "NO_MATCH"         # LLM said NO_MATCH
    NOT_SENT_TO_LLM = "NOT_SENT"  # GT control never reached LLM (retrieval filtered it out)
```

### Input: Disputed GT Control

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class DisputedGTControl:
    """A ground truth control that needs judge review."""

    policy_name: str
    control_id: str
    control_name: str
    control_description: str

    # Why this control is disputed
    dispute_reason: DisputeReason

    # Original LLM decision (None if NOT_SENT_TO_LLM)
    original_decision: Decision | None
    original_confidence: Confidence | None
    original_reasoning: str | None
    original_evidence_quote: str | None
    original_gaps: tuple[IdentifiedGap, ...] | None

    # Source info
    batch_file: str | None  # None if NOT_SENT_TO_LLM
    experiment_timestamp: str
```

### Output: Judge Verdict

```python
class Verdict(StrEnum):
    LLM_WRONG = "LLM_WRONG"  # GT is correct - keep label (LLM missed it or was too strict)
    GT_WRONG = "GT_WRONG"    # GT is incorrect - remove label (policy is irrelevant)
    UNCERTAIN = "UNCERTAIN"  # Cannot determine - needs human review


@dataclass(frozen=True, slots=True, kw_only=True)
class JudgeResult:
    """Result from the judge LLM."""

    control_id: str
    policy_name: str
    verdict: Verdict
    confidence: Confidence
    reasoning: str

    # Evidence supporting verdict
    evidence_for_gt: str        # Quote if GT IS correct (binding mandate found)
    evidence_against_gt: str    # Explanation if GT is NOT correct
    evidence_page: str | None   # Page number/section where evidence found

    # Original context (preserved for GRC review)
    dispute_reason: DisputeReason
    original_decision: Decision | None
    original_reasoning: str | None
```

### Config

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class JudgeConfig:
    """Configuration for the judge decider."""
    gcp_project: str
    vertex_location: str = "us-central1"
    model_name: str = "gemini-2.0-flash"
    max_concurrent_judges: int = 5       # Concurrency limit (rate limiting)
    save_outputs: bool = True            # Save individual judge_*.json files
```

---

## Judge Prompt Design

### System Prompt (`prompts/judge/system`)

```markdown
**Role:** You are an expert Security Compliance Auditor performing a quality review
of ground truth labels in a control-to-policy mapping dataset.

**Context:** You are reviewing a control that is labeled as "ground truth" for a
policy document, but a previous evaluation flagged it as disputed. Your job is to
determine if the ground truth label is valid.

**Your Task:** Determine if the ground truth (GT) label should be KEPT or REMOVED:

- **LLM_WRONG**: The GT label IS VALID. The policy addresses the core intent of this
  control. Keep the label. (The prior evaluation was too strict or missed something.)
- **GT_WRONG**: The GT label is INVALID. The policy is IRRELEVANT to this control.
  Remove the label. (The human annotator made an error.)
- **UNCERTAIN**: Cannot determine with confidence. Requires human review.

**Critical Guidance on "Partial" Coverage:**

In GRC (Governance, Risk, Compliance), a policy that addresses the CORE INTENT of a
control—even with gaps—is considered a valid mapping. Only mark GT_WRONG if the
policy is truly IRRELEVANT to the control.

- If the policy mandates the behavior but lacks technical details → **LLM_WRONG** (keep GT)
- If the policy mentions the topic only in passing or definitions → **GT_WRONG** (remove GT)
- If the policy is completely unrelated to the control → **GT_WRONG** (remove GT)

**Guidelines for Your Decision:**

1. **Review the Policy Document Thoroughly**
   - Search the ENTIRE document, not just specific pages
   - Look for binding language: "shall", "must", "required", "will ensure"
   - Consider semantic equivalence: different words but same mandate

2. **Apply Policy-Level Evaluation Standards**
   - Policies establish MANDATES, not implementation details
   - A policy saying "data must be encrypted" DOES address an encryption control
   - Missing technical specs (AES-256, etc.) is NOT a valid reason to remove GT

3. **If Original LLM Reasoning is Provided:**
   - Was the LLM too strict? (e.g., penalizing for missing procedures)
   - Did the LLM miss relevant language elsewhere in the document?
   - Be critical of the LLM's reasoning—it may have been wrong

4. **If No Original LLM Reasoning (NOT_SENT case):**
   - The control was filtered out before LLM evaluation (retrieval stage)
   - You must evaluate from scratch: Does this policy address this control?

**Output Requirements:**
- Provide the page number or section where you found evidence
- Provide specific evidence quotes for your decision
- Be critical of both prior evaluations AND the ground truth—neither is assumed correct
```

### User Prompt (`prompts/judge/user`)

Two variants depending on whether there's original LLM context:

**Variant A: With Original LLM Evaluation**
```markdown
Review this disputed ground truth label.

<control>
  <id>{control_id}</id>
  <name>{control_name}</name>
  <description>{control_description}</description>
</control>

<dispute_reason>{dispute_reason}</dispute_reason>

<original_llm_evaluation>
  <decision>{original_decision}</decision>
  <confidence>{original_confidence}</confidence>
  <reasoning>{original_reasoning}</reasoning>
  <evidence_quote>{original_evidence_quote}</evidence_quote>
  <gaps_identified>{original_gaps}</gaps_identified>
</original_llm_evaluation>

<instructions>
This control is labeled as "ground truth" for this policy, but a prior evaluation
decided it was {original_decision} (not MAPPED).

Determine if the ground truth label is VALID (policy addresses core intent) or
INVALID (policy is irrelevant to this control).

Remember: Partial coverage with gaps is usually VALID. Only mark INVALID if the
policy is truly irrelevant.
</instructions>
```

**Variant B: NOT_SENT_TO_LLM (No Original Evaluation)**
```markdown
Review this disputed ground truth label.

<control>
  <id>{control_id}</id>
  <name>{control_name}</name>
  <description>{control_description}</description>
</control>

<dispute_reason>NOT_SENT_TO_LLM</dispute_reason>

<context>
This control is labeled as "ground truth" for this policy, but it was never
evaluated by the LLM. The retrieval stage filtered it out (low embedding score
or capacity limits).

You must evaluate from scratch: Does this policy document address this control?
</context>

<instructions>
Search the ENTIRE policy document and determine:
1. Is there binding language that addresses this control's requirements?
2. Should this ground truth label be kept or removed?

Remember: Partial coverage with gaps is usually VALID. Only mark INVALID if the
policy is truly irrelevant.
</instructions>
```

### Response Schema (`prompts/judge/response.json`)

```json
{
  "type": "object",
  "properties": {
    "control_id": {
      "type": "string",
      "description": "The control ID being evaluated"
    },
    "verdict": {
      "type": "string",
      "enum": ["LLM_WRONG", "GT_WRONG", "UNCERTAIN"],
      "description": "LLM_WRONG: GT is valid (keep). GT_WRONG: GT is invalid (remove). UNCERTAIN: needs human."
    },
    "confidence": {
      "type": "string",
      "enum": ["high", "medium", "low"]
    },
    "reasoning": {
      "type": "string",
      "description": "2-3 sentence explanation of your verdict"
    },
    "evidence_for_gt": {
      "type": "string",
      "description": "Quote supporting that GT IS valid (binding mandate found). Empty if none."
    },
    "evidence_against_gt": {
      "type": "string",
      "description": "Explanation of why GT is NOT valid (policy irrelevant). Empty if none."
    },
    "evidence_page": {
      "type": "string",
      "description": "Page number or section reference where evidence was found. E.g., 'Page 5' or 'Section 3.2'"
    }
  },
  "required": ["control_id", "verdict", "confidence", "reasoning", "evidence_for_gt", "evidence_against_gt", "evidence_page"]
}
```

---

## Implementation Details

### Phase 2: GT Collector (`gt_collector.py`)

Reuses code from `analyze_ground_truth.py`:

```python
def collect_non_mapped_gt(
    timestamp: str,
    eval_rows: list[EvalRow],
) -> dict[str, list[NonMappedGTControl]]:
    """
    Collect all non-MAPPED ground truth controls from experiment outputs.

    Returns:
        Dict mapping policy_name -> list of NonMappedGTControl
    """
    # For each policy:
    #   1. Load GT controls from eval_row.ground_truth_controls
    #   2. Find batch_*.json files in llm_outputs/control_centric/{timestamp}/{policy_name}/
    #   3. Search for GT control IDs in batch results
    #   4. Collect those with decision != MAPPED
```

### Phase 3: Judge Decider (`judge_decider.py`)

Follows patterns from `control_centric_decider.py`:

```python
class JudgeDecider:
    """LLM-based judge for ground truth validation."""

    def __init__(self, config: JudgeConfig):
        self.config = config
        self._client: Client | None = None

    async def judge_control(
        self,
        cache_name: str,  # Reuse PDF cache
        gt_control: NonMappedGTControl,
    ) -> JudgeResult:
        """Judge a single non-MAPPED ground truth control."""
        # Build prompt with control context + original LLM decision
        # Call Gemini with cached PDF
        # Parse response into JudgeResult

    async def judge_document(
        self,
        policy_name: str,
        pdf_bytes: bytes,
        gt_controls: list[NonMappedGTControl],
    ) -> list[JudgeResult]:
        """Judge all non-MAPPED GT controls for a document."""
        # Upload PDF to cache once
        # Judge each control (can batch if multiple)
        # Return all results
```

### Phase 4: Output Generation

```python
def generate_grc_review_files(
    results: list[JudgeResult],
    output_dir: Path,
):
    """Generate CSV files for GRC expert review."""

    llm_wrong = [r for r in results if r.verdict == Verdict.LLM_WRONG]
    gt_wrong = [r for r in results if r.verdict == Verdict.GT_WRONG]
    uncertain = [r for r in results if r.verdict == Verdict.UNCERTAIN]

    # grc_review_llm_wrong.csv - Controls where LLM was too strict
    # grc_review_gt_wrong.csv - Controls where GT should be removed
    # grc_review_uncertain.csv - Controls needing human review
```

---

## Code Reuse Strategy

| Component | Reuse From | How |
|-----------|------------|-----|
| Gemini client | `control_centric_decider.py` | Same `Client(vertexai=True, ...)` pattern |
| PDF caching | `control_centric_decider.py` | `client.caches.create()` pattern |
| Retry logic | `control_centric_decider.py` | `@retry` decorator with same config |
| Prompt loading | `prompt_loader.py` | `load_response_schema()` |
| Control loading | `dcf_controls.py` | `load_dcf_controls()` |
| Eval row loading | `run_experiment.py` | `load_eval_rows()` |
| GT analysis | `analyze_ground_truth.py` | `find_llm_outputs()` pattern |
| Data models | `control_centric_models.py` | Import `Decision`, `Confidence`, etc. |

---

## Output Files

### run_metadata.json (Config Capture for Reproducibility)

```json
{
  "validation_timestamp": "20251226_160000",
  "experiment_timestamp": "20251226_150103",
  "config": {
    "model_name": "gemini-2.0-flash",
    "max_concurrent_judges": 5,
    "gcp_project": "project-id",
    "vertex_location": "us-central1"
  },
  "experiment_config": {
    "score_threshold": 0.5,
    "max_calls_per_document": 50,
    "max_batch_size": 10
  },
  "prompt_versions": {
    "system_hash": "abc123...",
    "user_hash": "def456..."
  },
  "git_commit": "84c1fde1"
}
```

### validation_summary.json

```json
{
  "validation_timestamp": "20251226_160000",
  "experiment_timestamp": "20251226_150103",
  "totals": {
    "gt_controls": 24,
    "disputed": 15,
    "judged": 15
  },
  "by_dispute_reason": {
    "PARTIAL": 5,
    "NO_MATCH": 7,
    "NOT_SENT": 3
  },
  "verdicts": {
    "LLM_WRONG": 6,
    "GT_WRONG": 7,
    "UNCERTAIN": 2
  },
  "by_policy": [
    {
      "policy_name": "Acceptable Use Policy",
      "total_gt": 8,
      "disputed": 3,
      "by_dispute_reason": {"PARTIAL": 1, "NO_MATCH": 1, "NOT_SENT": 1},
      "verdicts": {"LLM_WRONG": 1, "GT_WRONG": 2, "UNCERTAIN": 0}
    }
  ]
}
```

### grc_review_gt_wrong.csv

```csv
policy_name,control_id,control_name,dispute_reason,original_decision,judge_confidence,judge_reasoning,evidence_page,evidence_against_gt
Acceptable Use Policy,DCF-51,Network Segmentation,NO_MATCH,NO_MATCH,high,"The policy only addresses...",N/A,""
Data Protection Policy,DCF-123,Encryption Standard,PARTIAL,PARTIAL,medium,"...","Page 3",""
```

### grc_review_not_sent.csv (Controls Never Evaluated)

```csv
policy_name,control_id,control_name,judge_verdict,judge_confidence,judge_reasoning,evidence_page,evidence_for_gt
Acceptable Use Policy,DCF-789,Audit Logging,LLM_WRONG,high,"Found mandate on page 5...","Page 5","All system access shall be logged..."
```

This CSV helps identify retrieval stage issues—GT controls that should have been sent to the LLM but were filtered out.

---

## Success Criteria

1. Single CLI command runs full workflow
2. Can reuse existing experiment results (`--experiment-timestamp`)
3. Handles all three dispute categories: PARTIAL, NO_MATCH, NOT_SENT_TO_LLM
4. Judge prompt correctly identifies LLM strictness vs GT errors
5. Resumable: skips controls with existing outputs (unless `--force`)
6. Rate-limited: uses semaphore for concurrent judge calls
7. Config captured: `run_metadata.json` for reproducibility
8. Output CSV files are actionable by GRC experts
9. All infrastructure reused from existing experiment code
10. New code isolated in `ground_truth_validation/` subfolder
11. **All code has unit tests written BEFORE implementation (TDD)**

---

## Test-Driven Development Approach

This implementation follows **Test-Driven Development (TDD)** methodology:

### TDD Cycle: RED → GREEN → REFACTOR

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TDD CYCLE                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. RED: Write a failing test                                               │
│     - Test describes the behavior we want                                   │
│     - Test MUST fail initially (proves test is valid)                       │
│     - Test should be specific and focused                                   │
│                                                                              │
│  2. GREEN: Write minimal code to pass the test                              │
│     - Only write enough code to make the test pass                          │
│     - Don't optimize or add features yet                                    │
│     - Ugly code is fine at this stage                                       │
│                                                                              │
│  3. REFACTOR: Clean up while keeping tests green                            │
│     - Improve code structure, naming, patterns                              │
│     - Run tests after each change to ensure they still pass                 │
│     - Apply DRY, extract functions, improve readability                     │
│                                                                              │
│  Repeat for each piece of functionality                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Test File Structure

```
tests/scripts/experiments/control_detection/
└── ground_truth_validation/
    ├── __init__.py
    ├── test_models.py           # Test data models and enums
    ├── test_gt_collector.py     # Test GT collection logic
    ├── test_judge_decider.py    # Test judge LLM logic (mocked)
    ├── test_output_generation.py # Test CSV/JSON output
    └── conftest.py              # Shared fixtures
```

### Test Categories

| Category | Description | Mocking Strategy |
|----------|-------------|------------------|
| **Unit Tests** | Test individual functions in isolation | Mock all external dependencies |
| **Integration Tests** | Test module interactions | Mock only LLM calls |
| **E2E Tests** | Full pipeline with real LLM | Mark with `@pytest.mark.integration` |

### Key Testing Principles

1. **Mock LLM calls** - Never call real LLM in unit tests (cost, flakiness)
2. **Use fixtures** - Create reusable test data (controls, decisions, etc.)
3. **Test edge cases** - Empty inputs, None values, malformed data
4. **Test all dispute reasons** - PARTIAL, NO_MATCH, NOT_SENT_TO_LLM

---

## Implementation Order (TDD)

Each step follows RED → GREEN → REFACTOR. Tests are written FIRST.

### Cycle 1: Data Models (`models.py`)

**1.1 RED: Write failing tests for enums and dataclasses**

```python
# tests/scripts/experiments/control_detection/ground_truth_validation/test_models.py

def test_verdict_enum_has_expected_values():
    """Verdict enum should have LLM_WRONG, GT_WRONG, UNCERTAIN."""
    assert Verdict.LLM_WRONG == "LLM_WRONG"
    assert Verdict.GT_WRONG == "GT_WRONG"
    assert Verdict.UNCERTAIN == "UNCERTAIN"

def test_dispute_reason_enum_has_expected_values():
    """DisputeReason enum should have PARTIAL, NO_MATCH, NOT_SENT."""
    assert DisputeReason.PARTIAL == "PARTIAL"
    assert DisputeReason.NO_MATCH == "NO_MATCH"
    assert DisputeReason.NOT_SENT_TO_LLM == "NOT_SENT"

def test_disputed_gt_control_creation():
    """DisputedGTControl should be creatable with required fields."""
    control = DisputedGTControl(
        policy_name="Test Policy",
        control_id="DCF-123",
        control_name="Test Control",
        control_description="Test description",
        dispute_reason=DisputeReason.NO_MATCH,
        original_decision=Decision.NO_MATCH,
        original_confidence=Confidence.HIGH,
        original_reasoning="No relevant content found",
        original_evidence_quote="",
        original_gaps=None,
        batch_file="batch_001.json",
        experiment_timestamp="20251226_150103",
    )
    assert control.control_id == "DCF-123"
    assert control.dispute_reason == DisputeReason.NO_MATCH

def test_disputed_gt_control_not_sent_has_none_original_fields():
    """NOT_SENT controls should allow None for original_* fields."""
    control = DisputedGTControl(
        policy_name="Test Policy",
        control_id="DCF-456",
        control_name="Test Control",
        control_description="Test description",
        dispute_reason=DisputeReason.NOT_SENT_TO_LLM,
        original_decision=None,  # Not evaluated
        original_confidence=None,
        original_reasoning=None,
        original_evidence_quote=None,
        original_gaps=None,
        batch_file=None,  # No batch file
        experiment_timestamp="20251226_150103",
    )
    assert control.original_decision is None
    assert control.batch_file is None

def test_judge_result_creation():
    """JudgeResult should be creatable with all fields."""
    result = JudgeResult(
        control_id="DCF-123",
        policy_name="Test Policy",
        verdict=Verdict.LLM_WRONG,
        confidence=Confidence.HIGH,
        reasoning="Policy clearly mandates this requirement",
        evidence_for_gt="All data must be encrypted at rest",
        evidence_against_gt="",
        evidence_page="Page 5",
        dispute_reason=DisputeReason.NO_MATCH,
        original_decision=Decision.NO_MATCH,
        original_reasoning="No content found",
    )
    assert result.verdict == Verdict.LLM_WRONG
```

**1.2 GREEN: Implement models.py to pass tests**

**1.3 REFACTOR: Ensure frozen dataclasses, proper typing**

---

### Cycle 2: GT Collector (`gt_collector.py`)

**2.1 RED: Write failing tests for GT collection**

```python
# tests/scripts/experiments/control_detection/ground_truth_validation/test_gt_collector.py

@pytest.fixture
def sample_batch_json():
    """Sample batch_*.json content."""
    return {
        "batch_id": 0,
        "control_ids": ["DCF-37", "DCF-195"],
        "response": {
            "batch_results": [
                {
                    "control_id": "DCF-37",
                    "decision": "MAPPED",
                    "confidence": "high",
                    "evidence_quote": "Policy mandates...",
                    "reasoning": "Direct match",
                    "gaps_identified": [],
                },
                {
                    "control_id": "DCF-195",
                    "decision": "NO_MATCH",
                    "confidence": "high",
                    "evidence_quote": "",
                    "reasoning": "No relevant content",
                    "gaps_identified": [],
                },
            ]
        }
    }

def test_collect_disputed_gt_finds_no_match(tmp_path, sample_batch_json):
    """Should collect GT controls with NO_MATCH decision."""
    # Setup: Create mock batch file
    policy_dir = tmp_path / "llm_outputs" / "control_centric" / "20251226_150103" / "Test_Policy"
    policy_dir.mkdir(parents=True)
    (policy_dir / "batch_000.json").write_text(json.dumps(sample_batch_json))

    # GT includes DCF-195 which got NO_MATCH
    gt_controls = {"DCF-195"}

    disputed = collect_disputed_gt(
        timestamp="20251226_150103",
        policy_name="Test Policy",
        gt_control_ids=gt_controls,
        llm_output_dir=tmp_path / "llm_outputs",
    )

    assert len(disputed) == 1
    assert disputed[0].control_id == "DCF-195"
    assert disputed[0].dispute_reason == DisputeReason.NO_MATCH

def test_collect_disputed_gt_finds_partial(tmp_path):
    """Should collect GT controls with PARTIAL decision."""
    # ... similar test for PARTIAL

def test_collect_disputed_gt_finds_not_sent(tmp_path, sample_batch_json):
    """Should detect GT controls that never appeared in batch files."""
    # Setup: Create mock batch file WITHOUT DCF-999
    policy_dir = tmp_path / "llm_outputs" / "control_centric" / "20251226_150103" / "Test_Policy"
    policy_dir.mkdir(parents=True)
    (policy_dir / "batch_000.json").write_text(json.dumps(sample_batch_json))

    # GT includes DCF-999 which was never sent to LLM
    gt_controls = {"DCF-999"}

    disputed = collect_disputed_gt(
        timestamp="20251226_150103",
        policy_name="Test Policy",
        gt_control_ids=gt_controls,
        llm_output_dir=tmp_path / "llm_outputs",
    )

    assert len(disputed) == 1
    assert disputed[0].control_id == "DCF-999"
    assert disputed[0].dispute_reason == DisputeReason.NOT_SENT_TO_LLM
    assert disputed[0].original_decision is None

def test_collect_disputed_gt_excludes_mapped(tmp_path, sample_batch_json):
    """Should NOT collect GT controls that were MAPPED (not disputed)."""
    # Setup
    policy_dir = tmp_path / "llm_outputs" / "control_centric" / "20251226_150103" / "Test_Policy"
    policy_dir.mkdir(parents=True)
    (policy_dir / "batch_000.json").write_text(json.dumps(sample_batch_json))

    # GT includes DCF-37 which got MAPPED
    gt_controls = {"DCF-37"}

    disputed = collect_disputed_gt(
        timestamp="20251226_150103",
        policy_name="Test Policy",
        gt_control_ids=gt_controls,
        llm_output_dir=tmp_path / "llm_outputs",
    )

    assert len(disputed) == 0  # MAPPED is not disputed

def test_collect_disputed_gt_handles_empty_gt():
    """Should return empty list if no GT controls provided."""
    disputed = collect_disputed_gt(
        timestamp="20251226_150103",
        policy_name="Test Policy",
        gt_control_ids=set(),
        llm_output_dir=Path("/nonexistent"),
    )
    assert disputed == []
```

**2.2 GREEN: Implement gt_collector.py to pass tests**

**2.3 REFACTOR: Extract helper functions, improve error handling**

---

### Cycle 3: Judge Decider (`judge_decider.py`)

**3.1 RED: Write failing tests for judge logic (mocked LLM)**

```python
# tests/scripts/experiments/control_detection/ground_truth_validation/test_judge_decider.py

@pytest.fixture
def mock_gemini_response():
    """Mock response from Gemini judge."""
    return {
        "control_id": "DCF-123",
        "verdict": "LLM_WRONG",
        "confidence": "high",
        "reasoning": "Policy clearly mandates encryption",
        "evidence_for_gt": "All data must be encrypted at rest",
        "evidence_against_gt": "",
        "evidence_page": "Page 5",
    }

@pytest.fixture
def disputed_control():
    """Sample disputed GT control."""
    return DisputedGTControl(
        policy_name="Test Policy",
        control_id="DCF-123",
        control_name="Encryption at Rest",
        control_description="Data must be encrypted at rest",
        dispute_reason=DisputeReason.NO_MATCH,
        original_decision=Decision.NO_MATCH,
        original_confidence=Confidence.HIGH,
        original_reasoning="No encryption mentioned",
        original_evidence_quote="",
        original_gaps=None,
        batch_file="batch_001.json",
        experiment_timestamp="20251226_150103",
    )

@pytest.mark.asyncio
async def test_judge_control_returns_judge_result(
    mocker, mock_gemini_response, disputed_control
):
    """Judge should return JudgeResult from LLM response."""
    # Mock the Gemini client
    mock_client = mocker.MagicMock()
    mock_client.models.generate_content.return_value.text = json.dumps(mock_gemini_response)

    decider = JudgeDecider(JudgeConfig(gcp_project="test-project"))
    decider._client = mock_client

    result = await decider.judge_control(
        cache_name="test-cache",
        disputed_control=disputed_control,
    )

    assert isinstance(result, JudgeResult)
    assert result.verdict == Verdict.LLM_WRONG
    assert result.control_id == "DCF-123"

@pytest.mark.asyncio
async def test_judge_control_builds_correct_prompt_for_no_match(
    mocker, mock_gemini_response, disputed_control
):
    """Prompt should include original LLM decision for NO_MATCH disputes."""
    mock_client = mocker.MagicMock()
    mock_client.models.generate_content.return_value.text = json.dumps(mock_gemini_response)

    decider = JudgeDecider(JudgeConfig(gcp_project="test-project"))
    decider._client = mock_client

    await decider.judge_control(cache_name="test-cache", disputed_control=disputed_control)

    # Check the prompt that was sent
    call_args = mock_client.models.generate_content.call_args
    prompt = call_args.kwargs.get("contents") or call_args[1].get("contents")

    assert "DCF-123" in prompt
    assert "NO_MATCH" in prompt
    assert "No encryption mentioned" in prompt  # Original reasoning

@pytest.mark.asyncio
async def test_judge_control_handles_not_sent_case(mocker, mock_gemini_response):
    """NOT_SENT disputes should use different prompt (no original reasoning)."""
    not_sent_control = DisputedGTControl(
        policy_name="Test Policy",
        control_id="DCF-456",
        control_name="Audit Logging",
        control_description="System access must be logged",
        dispute_reason=DisputeReason.NOT_SENT_TO_LLM,
        original_decision=None,
        original_confidence=None,
        original_reasoning=None,
        original_evidence_quote=None,
        original_gaps=None,
        batch_file=None,
        experiment_timestamp="20251226_150103",
    )

    mock_client = mocker.MagicMock()
    mock_response = mock_gemini_response.copy()
    mock_response["control_id"] = "DCF-456"
    mock_client.models.generate_content.return_value.text = json.dumps(mock_response)

    decider = JudgeDecider(JudgeConfig(gcp_project="test-project"))
    decider._client = mock_client

    await decider.judge_control(cache_name="test-cache", disputed_control=not_sent_control)

    # Check prompt uses NOT_SENT variant
    call_args = mock_client.models.generate_content.call_args
    prompt = call_args.kwargs.get("contents") or call_args[1].get("contents")

    assert "NOT_SENT_TO_LLM" in prompt
    assert "evaluate from scratch" in prompt.lower()

@pytest.mark.asyncio
async def test_judge_document_respects_semaphore(mocker, mock_gemini_response):
    """Should limit concurrent judge calls via semaphore."""
    # Test that semaphore is properly used
    ...

@pytest.mark.asyncio
async def test_judge_document_skips_existing_outputs(tmp_path, mocker):
    """Should skip controls that already have judge_*.json files."""
    ...
```

**3.2 GREEN: Implement judge_decider.py to pass tests**

**3.3 REFACTOR: Extract prompt building, improve error handling**

---

### Cycle 4: Output Generation

**4.1 RED: Write failing tests for CSV/JSON generation**

```python
# tests/scripts/experiments/control_detection/ground_truth_validation/test_output_generation.py

@pytest.fixture
def sample_judge_results():
    """Sample judge results for output testing."""
    return [
        JudgeResult(
            control_id="DCF-1",
            policy_name="Policy A",
            verdict=Verdict.LLM_WRONG,
            confidence=Confidence.HIGH,
            reasoning="Found mandate",
            evidence_for_gt="Data shall be encrypted",
            evidence_against_gt="",
            evidence_page="Page 5",
            dispute_reason=DisputeReason.NO_MATCH,
            original_decision=Decision.NO_MATCH,
            original_reasoning="Missed it",
        ),
        JudgeResult(
            control_id="DCF-2",
            policy_name="Policy A",
            verdict=Verdict.GT_WRONG,
            confidence=Confidence.HIGH,
            reasoning="Policy irrelevant",
            evidence_for_gt="",
            evidence_against_gt="Only mentions topic in glossary",
            evidence_page="N/A",
            dispute_reason=DisputeReason.PARTIAL,
            original_decision=Decision.PARTIAL,
            original_reasoning="Partial coverage",
        ),
    ]

def test_generate_grc_review_files_creates_csvs(tmp_path, sample_judge_results):
    """Should create separate CSV files for each verdict type."""
    generate_grc_review_files(sample_judge_results, tmp_path)

    assert (tmp_path / "grc_review_llm_wrong.csv").exists()
    assert (tmp_path / "grc_review_gt_wrong.csv").exists()
    assert (tmp_path / "grc_review_uncertain.csv").exists()

def test_grc_review_llm_wrong_csv_has_correct_content(tmp_path, sample_judge_results):
    """LLM_WRONG CSV should contain controls where LLM was too strict."""
    generate_grc_review_files(sample_judge_results, tmp_path)

    df = pd.read_csv(tmp_path / "grc_review_llm_wrong.csv")
    assert len(df) == 1
    assert df.iloc[0]["control_id"] == "DCF-1"
    assert df.iloc[0]["verdict"] == "LLM_WRONG"

def test_validation_summary_json_has_correct_totals(tmp_path, sample_judge_results):
    """Summary JSON should have correct verdict counts."""
    generate_validation_summary(sample_judge_results, tmp_path)

    with open(tmp_path / "validation_summary.json") as f:
        summary = json.load(f)

    assert summary["verdicts"]["LLM_WRONG"] == 1
    assert summary["verdicts"]["GT_WRONG"] == 1
    assert summary["verdicts"]["UNCERTAIN"] == 0
```

**4.2 GREEN: Implement output generation to pass tests**

**4.3 REFACTOR: Improve CSV formatting, add headers**

---

### Cycle 5: CLI (`run_validation.py`)

**5.1 RED: Write failing tests for CLI argument parsing**

```python
# tests/scripts/experiments/control_detection/ground_truth_validation/test_run_validation.py

def test_cli_requires_experiment_or_timestamp():
    """CLI should require either --experiment or --experiment-timestamp."""
    with pytest.raises(SystemExit):
        parse_args([])  # No args should fail

def test_cli_parses_experiment_timestamp():
    """Should parse --experiment-timestamp correctly."""
    args = parse_args(["--experiment-timestamp", "20251226_150103", "--gcp-project", "test"])
    assert args.experiment_timestamp == "20251226_150103"
    assert args.experiment is None

def test_cli_parses_max_judges():
    """Should parse --max-judges for testing."""
    args = parse_args([
        "--experiment-timestamp", "20251226_150103",
        "--gcp-project", "test",
        "--max-judges", "5",
    ])
    assert args.max_judges == 5

def test_cli_parses_force_flag():
    """Should parse --force flag."""
    args = parse_args([
        "--experiment-timestamp", "20251226_150103",
        "--gcp-project", "test",
        "--force",
    ])
    assert args.force is True
```

**5.2 GREEN: Implement CLI to pass tests**

**5.3 REFACTOR: Improve help text, add validation**

---

### Cycle 6: Integration Testing

**6.1 RED: Write integration test (marks as slow/integration)**

```python
# tests/scripts/experiments/control_detection/ground_truth_validation/test_integration.py

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline_with_mocked_llm(tmp_path, mocker):
    """Integration test: full pipeline with mocked LLM responses."""
    # Setup: Create mock experiment outputs
    # Run: Execute full validation pipeline
    # Assert: Correct outputs generated
    ...
```

---

### Cycle 7: Manual Prompt Testing (Non-TDD)

**This step is NOT TDD** - prompts need manual testing in Vertex AI Studio:

1. Upload a sample PDF to Vertex AI Studio
2. Test system prompt with sample controls
3. Verify response format matches schema
4. Iterate on prompt wording based on results
5. Document prompt version in `prompts/judge/`

---

## Test Fixtures (`conftest.py`)

```python
# tests/scripts/experiments/control_detection/ground_truth_validation/conftest.py

import pytest
from ai_services.scripts.experiments.control_detection.control_centric_models import (
    Confidence,
    Decision,
)
from ai_services.scripts.experiments.control_detection.ground_truth_validation.models import (
    DisputedGTControl,
    DisputeReason,
    JudgeResult,
    Verdict,
)


@pytest.fixture
def sample_disputed_control_no_match():
    """Disputed control with NO_MATCH decision."""
    return DisputedGTControl(
        policy_name="Acceptable Use Policy",
        control_id="DCF-37",
        control_name="Acceptable Use Policy Exists",
        control_description="Organization maintains an acceptable use policy",
        dispute_reason=DisputeReason.NO_MATCH,
        original_decision=Decision.NO_MATCH,
        original_confidence=Confidence.HIGH,
        original_reasoning="No acceptable use policy found in document",
        original_evidence_quote="",
        original_gaps=None,
        batch_file="batch_001.json",
        experiment_timestamp="20251226_150103",
    )


@pytest.fixture
def sample_disputed_control_not_sent():
    """Disputed control that was never sent to LLM."""
    return DisputedGTControl(
        policy_name="Acceptable Use Policy",
        control_id="DCF-999",
        control_name="Network Segmentation",
        control_description="Network is segmented to isolate sensitive systems",
        dispute_reason=DisputeReason.NOT_SENT_TO_LLM,
        original_decision=None,
        original_confidence=None,
        original_reasoning=None,
        original_evidence_quote=None,
        original_gaps=None,
        batch_file=None,
        experiment_timestamp="20251226_150103",
    )


@pytest.fixture
def sample_judge_result_llm_wrong():
    """Judge result where LLM was wrong (keep GT)."""
    return JudgeResult(
        control_id="DCF-37",
        policy_name="Acceptable Use Policy",
        verdict=Verdict.LLM_WRONG,
        confidence=Confidence.HIGH,
        reasoning="Policy clearly establishes acceptable use requirements",
        evidence_for_gt="All employees must adhere to acceptable use guidelines",
        evidence_against_gt="",
        evidence_page="Page 2",
        dispute_reason=DisputeReason.NO_MATCH,
        original_decision=Decision.NO_MATCH,
        original_reasoning="No acceptable use policy found",
    )
```

---

## Running Tests

```bash
# Run all ground truth validation tests
uv run pytest tests/scripts/experiments/control_detection/ground_truth_validation/ -v

# Run with coverage
uv run pytest tests/scripts/experiments/control_detection/ground_truth_validation/ --cov=ai_services.scripts.experiments.control_detection.ground_truth_validation

# Run only unit tests (fast, no LLM calls)
uv run pytest tests/scripts/experiments/control_detection/ground_truth_validation/ -m "not integration"

# Run integration tests (slow, may cost money)
uv run pytest tests/scripts/experiments/control_detection/ground_truth_validation/ -m integration
```

---

## Future Enhancements

These ideas were identified during plan review but are out of scope for v1:

### 1. Missing GT Labels (False Positives in GT)
**Problem:** We're validating False Negatives (GT has it, LLM missed it), but ignoring potential missing labels (LLM found MAPPED, but GT doesn't have it).

**Future work:** Add a parallel collection phase for "High-Confidence Extras":
- `Original Decision == MAPPED` AND `Control NOT in GT`
- Judge: "Is this a valid mapping that the human annotator missed?"
- Output: `grc_review_missing_gt.csv`

### 2. Blind Judge Mode (Reduce Anchoring Bias)
**Problem:** Showing original LLM decision may bias the judge toward agreeing.

**Future work:** Implement two-pass judging:
1. "Blind" judge (no original decision shown) → verdict + evidence
2. Reveal original decision and ask "did the prior model miss anything?"

### 3. Double-Judge for Low Confidence
**Problem:** UNCERTAIN or low-confidence verdicts may benefit from a second opinion.

**Future work:** For UNCERTAIN verdicts, run a second independent judge pass. Only escalate to human when judges disagree.

### 4. GT Update Mechanism
**Problem:** We output CSVs for review, but no automated way to apply changes.

**Future work:** Create a script that:
- Reads approved changes from reviewed CSVs
- Applies them to `eval.csv`
- Generates a changelog

### 5. Cross-Reference Handling
**Problem:** Policies often say "see Incident Response Plan". Unclear if references count.

**Future work:** Add explicit instruction in prompt about whether cross-references constitute "addressing" a control (usually: no, unless the mandate is in this document).

---

## Decisions Made

| Question | Decision | Rationale |
|----------|----------|-----------|
| Batch vs one-at-a-time | One at a time | Better accuracy, each control is unique |
| Same Gemini model? | Yes, configurable via `--llm-model` | Consistency with experiment |
| Include UNCERTAIN in CSV? | Yes, separate file | GRC experts should review ambiguous cases |
| Handle NOT_SENT controls? | Yes, as third category | These are critical retrieval errors |
| PARTIAL handling | Lean toward LLM_WRONG | Partial coverage = keep GT in GRC |
| Anchoring bias | Accept for v1 | Context is valuable, prompt instructs to be critical |
