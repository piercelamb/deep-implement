# Three-Stage Control Mapping Pipeline

## Background: What This Experiment Is About

### The Business Problem

Drata helps companies achieve and maintain compliance with security frameworks (SOC 2, ISO 27001, HIPAA, PCI-DSS, etc.). Each framework requires organizations to implement hundreds of **controls**—specific security requirements like "encrypt data at rest" or "conduct annual access reviews."

Organizations document how they meet these controls in **policy documents** (e.g., "Acceptable Use Policy," "Encryption Policy," "Vendor Management Policy"). A critical compliance task is **mapping policies to controls**: determining which policy statements satisfy which control requirements.

**Today, this mapping is largely manual.** Compliance teams read through policies and match them to controls by hand—a tedious, error-prone process that doesn't scale.

### What We're Building

This experiment develops an **automated policy-to-control mapping pipeline** that:
1. Takes a policy document (PDF) as input
2. Evaluates it against ~779 DCF (Drata Common Framework) controls
3. Outputs which controls the policy addresses, with evidence quotes

### Why Precision Matters

The pipeline must balance two competing goals:
- **Recall**: Don't miss controls that the policy actually addresses (false negatives are bad—compliance gaps go undetected)
- **Precision**: Don't claim the policy addresses controls it doesn't (false positives are bad—creates false confidence, audit failures)

**For production use, precision is critical.** A system that says "yes, this policy addresses that control" when it doesn't is worse than useless—it creates compliance risk. We need ~80%+ precision to be production-viable.

### The Current Two-Stage Architecture

```
Stage 1: Embedding-based retrieval (ColModernVBERT)
├── Scores all 779 controls against each page of the document
├── Filters to candidates scoring above threshold (0.48)
└── Output: ~100-300 candidate controls per document

Stage 2: LLM-based classification (Gemini Flash)
├── Evaluates candidates in batches of ~10 controls
├── Full document + system prompt cached in Gemini
├── Output: MAPPED / PARTIAL / NO_MATCH for each control
└── ~50 LLM calls per document
```

**Current performance:** ~85% recall, but only **~17-20% precision**. For every 5 controls we predict, only 1 is actually correct.

### Why Precision Is So Low

Our hypothesis: **Gemini Flash is overwhelmed by context.**

Each Stage 2 LLM call receives:
- The entire policy document (10-30 pages)
- A detailed system prompt with 17 guardrails
- 10 controls to evaluate simultaneously

When uncertain, the model defaults to permissive "MAPPED" decisions. It's finding *reasons to map* rather than *proving mappings exist*.

### The Three-Stage Solution

Add a **verification stage** that re-examines each MAPPED control individually:

```
Stage 3: Per-control verification (NEW)
├── Input: Single MAPPED control + Stage 2's evidence/reasoning
├── Task: "Try to REJECT this mapping"
├── Reuses the same Gemini cache (cheap)
└── Output: VERIFIED / REJECTED
```

By isolating one control at a time and framing the task adversarially ("prove this is wrong"), we expect the LLM to catch its own false positives.

**Expected impact:** If Stage 3 rejects 80% of false positives, precision jumps from 20% to 60%+.

---

## Technical Plan

## Problem Statement

Current precision: ~17-20%. Target: ~80%. Prompt engineering has hit diminishing returns.

**Root Cause Hypothesis**: Gemini Flash is overwhelmed by context (full document + 10 controls per batch) and defaults to permissive MAPPED decisions when uncertain.

**Solution**: Add a verification stage (Stage 3) that judges each MAPPED control individually, reusing the same context cache.

## Architecture Overview

```
Stage 1: ColModernVBERT Scoring (existing)
├── Input: PDF pages
├── Output: Control candidates with scores
└── No changes needed

Stage 2: Control-Centric Mapping (existing, minor modifications)
├── Input: Batches of ~10 controls
├── Output: MAPPED/PARTIAL/NO_MATCH decisions
├── Modification: Immediately queue MAPPED controls for Stage 3
└── Reuses: Gemini cache (document + system prompt)

Stage 3: Per-Control Verification (NEW)
├── Input: Single MAPPED control + Stage 2 evidence/reasoning
├── Output: VERIFIED/REJECTED
├── Priority: Higher than Stage 2 (for time-to-first-verified)
└── Reuses: SAME Gemini cache as Stage 2
```

## Key Design Decisions

### 1. Cache Reuse Strategy

The Gemini cache includes both the PDF document AND the system prompt (baked in at creation time). Stage 3 MUST work with the same system prompt.

**This is actually ideal because:**
- The system prompt contains all 17 guardrails (G-1 through G-17)
- Stage 3 should apply the SAME rules, just more carefully to one control
- The verification logic lives entirely in the Stage 3 user prompt

### 2. Immediate Stage 3 Dispatch

**Requirement**: "The moment we get a MAPPED control out of Stage 2, immediately kick off Stage 3"

**Implementation**: Use `asyncio.as_completed()` to process Stage 2 batches as they complete, spawning Stage 3 tasks for each MAPPED control immediately.

```python
pending = set(stage2_tasks)
while pending:
    done, pending = await asyncio.wait(pending, return_when=FIRST_COMPLETED)
    for task in done:
        if is_stage2_task(task):
            for result in task.result().results:
                if result.addresses_control:  # MAPPED + HIGH
                    stage3_task = create_task(_verify_control(result, cache_name))
                    pending.add(stage3_task)
```

### 3. Priority Handling (Experiment vs Production)

**For Experiment**: Simple concurrent execution. Stage 3 tasks are spawned immediately and compete fairly for semaphore slots. This is sufficient because:
- We want to measure Stage 3's effectiveness, not optimize latency
- Call count is what matters, not ordering

**For Production** (noted, not implemented):
- Priority queue with Stage 3 > Stage 2
- Dedicated semaphore slots for Stage 3 (e.g., 3 of 10 reserved)
- Early termination when enough VERIFIED controls found

### 4. Stage 3 Scope

**MAPPED+HIGH only**: Stage 3 verifies controls where `addresses_control == True` (MAPPED decision with HIGH confidence). PARTIAL controls are not verified.

### 5. Call Budget

**No hard cap for experiment**: "Make as many Stage 3 calls as needed"

Each MAPPED+HIGH control from Stage 2 gets one Stage 3 verification call. If Stage 2 produces 30 such controls, that's 30 Stage 3 calls.

**Anomaly detection (warning only)**: If Stage 2 returns >50 MAPPED controls, log a warning—this likely indicates a prompt breakdown. But proceed with all verifications anyway (for experiment purposes, we want to see the full picture).

```python
if len(mapped_controls) > 50:
    logger.warning(f"Stage 2 returned {len(mapped_controls)} MAPPED - possible prompt breakdown. Proceeding anyway.")
```

**Production consideration**: Cap at N verifications per document, prioritize by confidence/score.

## File Changes

### New Files

#### 1. `prompts/control_verifier/user`
Stage 3 user prompt template. Adversarial framing ("try to reject this") with fresh evidence extraction requirement.

**Key Design Principle**: Stage 3 must independently re-locate and extract evidence. Stage 2's quote is treated as an *untrusted hint*, not as ground truth. This prevents anchoring bias and catches hallucinated quotes.

```markdown
## Task: Verify or Reject a Control Mapping

A previous analysis determined that control {control_id} is MAPPED to this document.

**Your task: Attempt to REJECT this mapping.**

Only return VERIFIED if you cannot find a valid reason to reject. You must independently verify the evidence exists.

### Control Being Verified
- **ID**: {control_id}
- **Name**: {control_name}
- **Description**: {control_description}
- **Control Type**: {control_type}

### Previous Analysis (TREAT AS UNTRUSTED)
The previous analysis claimed:
- **Claimed Evidence**: "{evidence_quote}"
- **Claimed Location**: {location_reference}
- **Claimed Reasoning**: {reasoning}

**WARNING**: Do NOT assume the claimed evidence is accurate. You must independently locate it.

### Verification Steps

**Step 1: Classify the control requirement**
- Is this an ARTIFACT control (existence of a document/policy satisfies it)?
- Or a MANDATE control (requires specific binding requirements)?

**Step 2: Search for evidence independently**
- Scan the document for text that could satisfy this control
- Do NOT assume the "Claimed Evidence" above is correct or exists
- If you find supporting evidence, extract it verbatim

**Step 3: Validate the evidence**
For ARTIFACT controls:
- Document title, purpose statement, or applicability section may be valid evidence
- Binding language (must/shall/will) is NOT required for artifact existence

For MANDATE controls (administrative/technical):
- Evidence MUST contain binding language (must/shall/required/will)
- Evidence must directly address the control's specific requirements
- Aspirational or descriptive language is insufficient

**Step 4: Apply guardrails (G-1 through G-17)**
Check the evidence against all applicable guardrails from the system prompt.

**Step 5: Determine verdict**
VERIFIED only if all checks pass. REJECTED if any check fails.

### Rejection Criteria
REJECT if ANY of these apply:
□ **Evidence not found**: You cannot locate valid evidence in the document
□ **Quote is hallucinated**: The claimed evidence does not exist verbatim
□ **Quote is stitched**: Evidence combines text from different locations
□ **Evidence locality violated**: Evidence assembled from multiple sections
□ **Binding language missing**: MANDATE control but no must/shall/will (N/A for ARTIFACT)
□ **Domain mismatch**: Evidence addresses different domain than control requires
□ **Guardrail violated**: Any G-1 through G-17 rule is violated
□ **Artifact type mismatch**: Control requires specific document type this isn't
□ **Inference required**: Mapping relies on interpretation rather than explicit mandate

### Output Requirements
You MUST output:
1. The verbatim evidence quote you found (or empty if none)
2. The exact location where you found it
3. Your step-by-step reasoning
4. The verdict (VERIFIED/REJECTED)
5. If REJECTED: the specific reason and any guardrails violated
```

#### 2. `prompts/control_verifier/response.json`

**Design Notes:**
- `reasoning` comes BEFORE `verdict` in the schema—LLMs generate JSON sequentially, so this forces chain-of-thought reasoning before committing to a decision.
- `verified_evidence_quote` and `verified_location` are the FRESH extraction by Stage 3, independent of Stage 2's claims.
- `guardrails_violated` is an array since multiple guardrails may apply to a single rejection.
- Conditional requirements: If `verdict=REJECTED`, `rejection_reason` should be populated. If `verdict=VERIFIED`, `verified_evidence_quote` should be non-empty.

```json
{
  "type": "object",
  "properties": {
    "control_id": {
      "type": "string",
      "const": "{CONTROL_ID}",
      "description": "The control ID being verified (injected at runtime)"
    },
    "control_type_determined": {
      "type": "string",
      "enum": ["ARTIFACT", "MANDATE"],
      "description": "Whether Stage 3 classified this as an artifact or mandate control"
    },
    "verified_evidence_quote": {
      "type": "string",
      "description": "The verbatim evidence quote Stage 3 independently found. Empty if no valid evidence located."
    },
    "verified_location": {
      "type": "string",
      "description": "Where Stage 3 found the evidence (page/section). Empty if no evidence."
    },
    "stage2_quote_validated": {
      "type": "boolean",
      "description": "Did Stage 2's claimed quote exist verbatim in the document?"
    },
    "reasoning": {
      "type": "string",
      "description": "Step-by-step analysis: (1) control type classification, (2) evidence search, (3) evidence validation, (4) guardrail check."
    },
    "verdict": {
      "type": "string",
      "enum": ["VERIFIED", "REJECTED"]
    },
    "rejection_reason": {
      "type": "string",
      "description": "Specific reason for rejection. Empty string if VERIFIED."
    },
    "guardrails_violated": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of guardrails violated (e.g., ['G-15', 'G-17']). Empty array if VERIFIED or no guardrail violations."
    }
  },
  "required": ["control_id", "control_type_determined", "verified_evidence_quote", "verified_location", "stage2_quote_validated", "reasoning", "verdict"]
}
```

**Implementation Note**: The code should enforce conditional requirements:
- If `verdict == "REJECTED"` and `rejection_reason` is empty, log a warning but treat as valid rejection.
- If `verdict == "VERIFIED"` and `verified_evidence_quote` is empty, auto-downgrade to REJECTED (no evidence = no verification).

#### 3. `control_centric_models.py` additions
```python
class VerificationVerdict(StrEnum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
```

#### 4. `three_stage_decider.py` (NEW)
Main orchestrator that coordinates Stage 2 and Stage 3.

### Modified Files

#### 1. `control_centric_decider.py`
- Extract `_call_gemini` and cache methods to be reusable
- Add method to verify a single control: `_verify_control(result, cache_name)`
- Or: Keep Stage 3 logic in separate class that accepts cache_name

#### 2. `run_experiment.py`
- Add `--mode three_stage` option
- Wire up `ThreeStageDecider`
- Track new metrics: verification_rate, time_to_first_verified

#### 3. `experiment_config.py`
- Add `MAX_VERIFICATION_CALLS_PER_DOCUMENT` (optional, for future production use)
- Add `VERIFICATION_PROMPTS_DIR` constant

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ThreeStageDecider                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Upload PDF to Gemini cache (once)                              │
│     └── cache_name = await _upload_document_cache(pdf_bytes)       │
│                                                                     │
│  2. Create Stage 2 batch tasks                                      │
│     └── stage2_tasks = [_process_batch(b, cache_name) for b in batches] │
│                                                                     │
│  3. Process with immediate Stage 3 dispatch                         │
│     ┌─────────────────────────────────────────────────────────────┐ │
│     │  pending = set(stage2_tasks)                                │ │
│     │  verified_controls = []                                     │ │
│     │                                                             │ │
│     │  while pending:                                             │ │
│     │      done, pending = await wait(pending, FIRST_COMPLETED)   │ │
│     │      for task in done:                                      │ │
│     │          if is_stage2(task):                                │ │
│     │              for result in task.result():                   │ │
│     │                  if result.addresses_control:               │ │
│     │                      # Spawn Stage 3 immediately            │ │
│     │                      s3 = create_task(_verify(result))      │ │
│     │                      pending.add(s3)                        │ │
│     │          elif is_stage3(task):                              │ │
│     │              verification = task.result()                   │ │
│     │              if verification.verdict == VERIFIED:           │ │
│     │                  verified_controls.append(verification)     │ │
│     │                  track_time_to_first_verified()             │ │
│     └─────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  4. Delete cache (shielded)                                         │
│                                                                     │
│  5. Return ThreeStageDecision(verified_controls, metrics)          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Orchestration Implementation Details

### Task Identification

Use explicit task naming to distinguish Stage 2 vs Stage 3 tasks in the pending set:

```python
# Tag tasks with descriptive names
stage2_task = asyncio.create_task(
    self._process_batch(batch, cache_name),
    name=f"stage2:batch_{batch.batch_id}"
)

stage3_task = asyncio.create_task(
    self._verify_control(result, cache_name),
    name=f"stage3:{result.control_id}"
)

# In the processing loop
def is_stage2_task(task: asyncio.Task) -> bool:
    return task.get_name().startswith("stage2:")

def is_stage3_task(task: asyncio.Task) -> bool:
    return task.get_name().startswith("stage3:")
```

### Retry Semantics (Same as Stage 2)

Stage 3 must use the **same retry behavior as Stage 2**:

1. **Transient errors (quota, network, 5xx)**: Use the same exponential backoff retry policy as Stage 2 LLM calls. These are handled by the underlying `_call_gemini` infrastructure.

2. **None or unparseable response**: Retry exactly **once**. If the retry also fails, then fail-closed (REJECTED).

```python
async def _verify_control(self, result: ControlResult, cache_name: str) -> VerificationResult:
    max_attempts = 2  # Same as Stage 2: initial + 1 retry for parse failures

    for attempt in range(max_attempts):
        try:
            # _call_gemini handles transient errors (quota, network) with its own retry policy
            response = await self._call_gemini(prompt, cache_name)

            if response is None:
                if attempt < max_attempts - 1:
                    logger.warning(f"Stage 3 got None for {result.control_id}, retrying (attempt {attempt + 1})")
                    continue
                else:
                    logger.error(f"Stage 3 got None for {result.control_id} after retry. Treating as REJECTED.")
                    return self._make_rejected_result(result, "LLM returned None after retry")

            parsed = self._parse_verification_response(response)

            # Enforce conditional requirements
            if parsed.verdict == "VERIFIED" and not parsed.verified_evidence_quote:
                logger.warning(f"Stage 3 VERIFIED {result.control_id} but no evidence quote. Auto-rejecting.")
                return self._make_rejected_result(result, "VERIFIED without evidence quote (auto-rejected)")

            return VerificationResult.from_response(parsed, original=result)

        except (json.JSONDecodeError, KeyError, ValidationError) as e:
            if attempt < max_attempts - 1:
                logger.warning(f"Stage 3 parse error for {result.control_id}: {e}. Retrying (attempt {attempt + 1})")
                continue
            else:
                logger.error(f"Stage 3 parse error for {result.control_id} after retry: {e}. Treating as REJECTED.")
                return self._make_rejected_result(result, f"Parse error after retry: {e}")

    # Should not reach here, but fail-closed just in case
    return self._make_rejected_result(result, "Unexpected: exhausted retries")


def _make_rejected_result(self, result: ControlResult, reason: str) -> VerificationResult:
    """Helper to create a REJECTED result with defaults."""
    return VerificationResult(
        control_id=result.control_id,
        control_type_determined="",
        verified_evidence_quote="",
        verified_location="",
        stage2_quote_validated=False,
        reasoning=reason,
        verdict=VerificationVerdict.REJECTED,
        rejection_reason=reason,
        guardrails_violated=[],
        original_evidence=result.evidence_quote,
        original_location=result.location_reference,
        original_reasoning=result.reasoning,
    )
```

### Fail-Closed Principle

After retry exhaustion, Stage 3 always fails to REJECTED (precision-first). Never leave a control in an ambiguous state.

### Cache Lifecycle

Ensure cache deletion doesn't race with outstanding tasks:

```python
async def process_document(self, pdf_bytes: bytes, batches: list[Batch]) -> ThreeStageDecision:
    cache_name = await self._upload_document_cache(pdf_bytes)
    try:
        # ... process all stage 2 and stage 3 tasks ...
        # Wait for ALL tasks to complete before deleting cache
        while pending:
            done, pending = await asyncio.wait(pending, return_when=FIRST_COMPLETED)
            # ... handle results ...

        return ThreeStageDecision(...)

    finally:
        # Shield cache deletion from cancellation
        await asyncio.shield(self._delete_cache(cache_name))
```

### Stage 3 Output Persistence

**Requirement**: Write every Stage 3 LLM response to disk for analysis and resume capability, just like Stage 2 batch outputs.

**File Structure**:
```
files/llm_outputs/three_stage/{timestamp}/{policy_name}/
├── batch_000.json          # Stage 2 output (existing)
├── batch_001.json
├── ...
├── verification_DCF-37.json   # Stage 3 output (NEW)
├── verification_DCF-142.json
├── verification_DCF-298.json
└── ...
```

**Stage 3 Output Format** (`verification_{control_id}.json`):
```json
{
  "control_id": "DCF-37",
  "stage2_input": {
    "evidence_quote": "...",
    "location_reference": "...",
    "reasoning": "..."
  },
  "stage3_response": {
    "control_type_determined": "ARTIFACT",
    "verified_evidence_quote": "...",
    "verified_location": "...",
    "stage2_quote_validated": true,
    "reasoning": "...",
    "verdict": "VERIFIED",
    "rejection_reason": "",
    "guardrails_violated": []
  },
  "thought_summary": "First I need to locate the evidence quote in the document... Found it on page 1 in the Purpose section... Now checking if this is an ARTIFACT or MANDATE control... DCF-37 requires an Acceptable Use Policy to exist, so this is ARTIFACT type... The document title and purpose statement satisfy this...",
  "timestamp": "2025-01-01T12:34:56Z",
  "attempt_count": 1
}
```

### Capturing Gemini Flash Thought Summaries

**Requirement**: Enable thinking mode in Stage 3 calls and capture the thought summaries for debugging.

**Enable thinking in Stage 3 config**:
```python
from google.generativeai import types

config = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(
        include_thoughts=True
    )
)
```

**Extract thought summary from response**:
```python
def _extract_thought_and_answer(self, response) -> tuple[str, str]:
    """Extract thought summary and answer from Gemini response with thinking enabled."""
    thought_parts = []
    answer_parts = []

    for part in response.candidates[0].content.parts:
        if part.thought:
            thought_parts.append(part.text)
        else:
            answer_parts.append(part.text)

    thought_summary = "\n".join(thought_parts)
    answer_text = "\n".join(answer_parts)
    return thought_summary, answer_text
```

**Why capture thoughts**:
1. **Prompt debugging**: See how the model interprets the verification instructions
2. **Failure analysis**: Understand why a control was incorrectly VERIFIED or REJECTED
3. **Guardrail reasoning**: See which guardrails the model considered and why
4. **Evidence search process**: Trace how the model searched for and evaluated evidence

**Resume Capability**:
```python
def _get_existing_verifications(self, output_dir: Path) -> set[str]:
    """Return control IDs that have already been verified."""
    existing = set()
    for f in output_dir.glob("verification_*.json"):
        # Extract control ID from filename: verification_DCF-37.json -> DCF-37
        control_id = f.stem.replace("verification_", "")
        existing.add(control_id)
    return existing

async def _verify_control(self, result: ControlResult, cache_name: str, output_dir: Path) -> VerificationResult:
    # Check if already processed (for resume)
    output_file = output_dir / f"verification_{result.control_id}.json"
    if output_file.exists():
        logger.info(f"Skipping {result.control_id} - already verified")
        return VerificationResult.from_file(output_file)

    # ... do verification ...

    # Write result immediately after getting response
    self._write_verification_output(output_file, result, verification_result)
    return verification_result
```

**Why This Matters**:
1. **Analysis**: Inspect individual Stage 3 decisions to understand rejection patterns
2. **Resume**: If pipeline crashes or is interrupted, skip already-verified controls on restart
3. **Debugging**: Compare Stage 2 input vs Stage 3 output for specific controls
4. **Audit trail**: Full record of what the LLM saw and decided

## New Data Structures

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class VerificationResult:
    """Result of Stage 3 verification for a single control."""
    control_id: str

    # Stage 3's independent analysis
    control_type_determined: str  # "ARTIFACT" or "MANDATE"
    verified_evidence_quote: str  # Fresh quote extracted by Stage 3 (empty if none found)
    verified_location: str  # Where Stage 3 found evidence (empty if none)
    stage2_quote_validated: bool  # Did Stage 2's claimed quote exist verbatim?

    reasoning: str  # Step-by-step analysis (generated BEFORE verdict)
    verdict: VerificationVerdict  # VERIFIED / REJECTED
    rejection_reason: str  # Empty if VERIFIED
    guardrails_violated: list[str]  # e.g., ["G-15", "G-17"] or empty list

    # Original Stage 2 data (for traceability and analysis)
    original_evidence: str
    original_location: str
    original_reasoning: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ThreeStageDecision:
    """Document-level result from three-stage pipeline."""
    policy_name: str

    # Stage 2 outputs
    stage2_mapped_count: int  # How many went to Stage 3
    stage2_partial_count: int
    stage2_no_match_count: int

    # Stage 3 outputs
    verified_controls: list[VerificationResult]  # VERIFIED only
    rejected_controls: list[VerificationResult]  # REJECTED only

    # Core metrics
    time_to_first_verified_seconds: float | None
    stage2_call_count: int
    stage3_call_count: int

    # Diagnostic metrics (computed from results)
    stage2_quotes_hallucinated: int  # Count where stage2_quote_validated=False
    rejection_reasons: dict[str, int]  # e.g., {"Parse error": 2, "Evidence not found": 5}
    guardrails_violated_counts: dict[str, int]  # e.g., {"G-15": 12, "G-17": 5}

    def get_final_controls(self) -> list[VerificationResult]:
        """Returns only VERIFIED controls (final predictions)."""
        return self.verified_controls

    @property
    def verification_rate(self) -> float:
        """Ratio of verified to total (verified + rejected)."""
        total = len(self.verified_controls) + len(self.rejected_controls)
        return len(self.verified_controls) / total if total > 0 else 0.0

    @property
    def stage2_hallucination_rate(self) -> float:
        """Ratio of hallucinated quotes to total Stage 3 calls."""
        total = len(self.verified_controls) + len(self.rejected_controls)
        return self.stage2_quotes_hallucinated / total if total > 0 else 0.0
```

## Implementation Steps (TDD Approach)

This implementation follows **Test-Driven Development**: write failing tests first, then implement the minimum code to pass them, then refactor.

### Phase 1: Data Models (Test → Implement)

**1.1 Test `VerificationVerdict` enum**
```python
# tests/scripts/experiments/control_detection/test_control_centric_models.py
def test_verification_verdict_enum():
    assert VerificationVerdict.VERIFIED == "VERIFIED"
    assert VerificationVerdict.REJECTED == "REJECTED"
    assert VerificationVerdict("VERIFIED") == VerificationVerdict.VERIFIED
```
→ Then implement `VerificationVerdict` in `control_centric_models.py`

**1.2 Test `VerificationResult` dataclass**
```python
def test_verification_result_creation():
    result = VerificationResult(
        control_id="DCF-37",
        control_type_determined="ARTIFACT",
        verified_evidence_quote="This policy specifies...",
        verified_location="Page 1, Purpose",
        stage2_quote_validated=True,
        reasoning="Found evidence on page 1...",
        verdict=VerificationVerdict.VERIFIED,
        rejection_reason="",
        guardrails_violated=[],
        original_evidence="...",
        original_location="...",
        original_reasoning="...",
    )
    assert result.control_id == "DCF-37"
    assert result.verdict == VerificationVerdict.VERIFIED

def test_verification_result_from_response():
    """Test parsing LLM response into VerificationResult."""
    raw_response = {
        "control_id": "DCF-37",
        "control_type_determined": "ARTIFACT",
        "verified_evidence_quote": "...",
        # ... etc
    }
    original = MockControlResult(control_id="DCF-37", ...)
    result = VerificationResult.from_response(raw_response, original=original)
    assert result.control_id == "DCF-37"

def test_verification_result_from_file(tmp_path):
    """Test loading VerificationResult from saved JSON file."""
    output_file = tmp_path / "verification_DCF-37.json"
    output_file.write_text(json.dumps({...}))
    result = VerificationResult.from_file(output_file)
    assert result.control_id == "DCF-37"
```
→ Then implement `VerificationResult` dataclass with `from_response()` and `from_file()` methods

**1.3 Test `ThreeStageDecision` dataclass**
```python
def test_three_stage_decision_verification_rate():
    decision = ThreeStageDecision(
        policy_name="Acceptable Use Policy",
        stage2_mapped_count=10,
        verified_controls=[...],  # 3 items
        rejected_controls=[...],  # 7 items
        # ...
    )
    assert decision.verification_rate == 0.3  # 3/10

def test_three_stage_decision_hallucination_rate():
    # ...

def test_three_stage_decision_get_final_controls():
    # Returns only verified controls
```
→ Then implement `ThreeStageDecision` dataclass

### Phase 2: Prompt Building (Test → Implement)

**2.1 Test prompt template loading**
```python
# tests/scripts/experiments/control_detection/test_three_stage_decider.py
def test_load_verification_prompt_template():
    template = load_prompt_template("control_verifier")
    assert "{control_id}" in template
    assert "{evidence_quote}" in template
    assert "REJECT" in template  # adversarial framing
```
→ Then create `prompts/control_verifier/user` and `response.json`

**2.2 Test prompt building**
```python
def test_build_verification_prompt():
    stage2_result = ControlResult(
        control_id="DCF-37",
        evidence_quote="This policy specifies...",
        location_reference="Page 1",
        reasoning="Direct match...",
    )
    control_info = DCFControl(
        id="DCF-37",
        name="Acceptable Use Policy",
        description="Organization has an acceptable use policy...",
    )
    prompt = build_verification_prompt(stage2_result, control_info)

    assert "DCF-37" in prompt
    assert "This policy specifies..." in prompt
    assert "TREAT AS UNTRUSTED" in prompt
    assert "Attempt to REJECT" in prompt
```
→ Then implement `build_verification_prompt()` function

### Phase 3: Response Parsing (Test → Implement)

**3.1 Test successful response parsing**
```python
def test_parse_verification_response_verified():
    raw = {
        "control_id": "DCF-37",
        "control_type_determined": "ARTIFACT",
        "verified_evidence_quote": "This policy specifies...",
        "verified_location": "Page 1, Purpose",
        "stage2_quote_validated": True,
        "reasoning": "Step 1: This is an ARTIFACT control...",
        "verdict": "VERIFIED",
        "rejection_reason": "",
        "guardrails_violated": []
    }
    result = parse_verification_response(raw)
    assert result["verdict"] == "VERIFIED"
    assert result["verified_evidence_quote"] != ""

def test_parse_verification_response_rejected():
    raw = {
        "verdict": "REJECTED",
        "rejection_reason": "G-15: Document type mismatch",
        "guardrails_violated": ["G-15"],
        # ...
    }
    result = parse_verification_response(raw)
    assert result["verdict"] == "REJECTED"
    assert "G-15" in result["guardrails_violated"]
```

**3.2 Test auto-rejection for VERIFIED without evidence**
```python
def test_verified_without_evidence_auto_rejects():
    """VERIFIED with empty evidence should auto-downgrade to REJECTED."""
    raw = {
        "verdict": "VERIFIED",
        "verified_evidence_quote": "",  # Empty!
        # ...
    }
    result = parse_verification_response(raw, enforce_evidence=True)
    assert result["verdict"] == "REJECTED"
    assert "auto-rejected" in result["rejection_reason"].lower()
```

**3.3 Test thought summary extraction**
```python
def test_extract_thought_and_answer():
    mock_response = MockGeminiResponse(parts=[
        MockPart(text="First I look for evidence...", thought=True),
        MockPart(text="Then I check guardrails...", thought=True),
        MockPart(text='{"verdict": "VERIFIED", ...}', thought=False),
    ])
    thought, answer = extract_thought_and_answer(mock_response)
    assert "First I look for evidence" in thought
    assert "Then I check guardrails" in thought
    assert '{"verdict"' in answer
```
→ Then implement parsing functions

### Phase 4: Retry Logic (Test → Implement)

**4.1 Test retry on None response**
```python
@pytest.mark.asyncio
async def test_verify_control_retries_on_none():
    mock_gemini = AsyncMock(side_effect=[None, valid_response])
    decider = ThreeStageDecider(gemini_client=mock_gemini)

    result = await decider._verify_control(stage2_result, cache_name)

    assert mock_gemini.call_count == 2  # Retried once
    assert result.verdict == VerificationVerdict.VERIFIED

@pytest.mark.asyncio
async def test_verify_control_fails_after_max_retries():
    mock_gemini = AsyncMock(return_value=None)  # Always None
    decider = ThreeStageDecider(gemini_client=mock_gemini)

    result = await decider._verify_control(stage2_result, cache_name)

    assert mock_gemini.call_count == 2  # Initial + 1 retry
    assert result.verdict == VerificationVerdict.REJECTED
    assert "None after retry" in result.rejection_reason
```

**4.2 Test retry on parse error**
```python
@pytest.mark.asyncio
async def test_verify_control_retries_on_parse_error():
    mock_gemini = AsyncMock(side_effect=[
        "invalid json {{{",
        '{"verdict": "VERIFIED", ...}'
    ])
    decider = ThreeStageDecider(gemini_client=mock_gemini)

    result = await decider._verify_control(stage2_result, cache_name)

    assert result.verdict == VerificationVerdict.VERIFIED
```
→ Then implement retry logic in `_verify_control()`

### Phase 5: Output Persistence (Test → Implement)

**5.1 Test writing verification output**
```python
def test_write_verification_output(tmp_path):
    output_file = tmp_path / "verification_DCF-37.json"
    write_verification_output(
        output_file,
        stage2_input={...},
        stage3_response={...},
        thought_summary="...",
    )

    assert output_file.exists()
    data = json.loads(output_file.read_text())
    assert data["control_id"] == "DCF-37"
    assert "thought_summary" in data
    assert "timestamp" in data

def test_resume_skips_existing_verifications(tmp_path):
    # Create existing verification file
    (tmp_path / "verification_DCF-37.json").write_text(json.dumps({...}))

    existing = get_existing_verifications(tmp_path)

    assert "DCF-37" in existing
    assert "DCF-999" not in existing
```
→ Then implement persistence functions

### Phase 6: Orchestration (Test → Implement)

**6.1 Test task identification**
```python
def test_is_stage2_task():
    task = asyncio.create_task(asyncio.sleep(0), name="stage2:batch_003")
    assert is_stage2_task(task) == True
    assert is_stage3_task(task) == False

def test_is_stage3_task():
    task = asyncio.create_task(asyncio.sleep(0), name="stage3:DCF-37")
    assert is_stage2_task(task) == False
    assert is_stage3_task(task) == True
```

**6.2 Test immediate Stage 3 dispatch**
```python
@pytest.mark.asyncio
async def test_stage3_dispatched_immediately_on_mapped():
    """Stage 3 task should be created as soon as Stage 2 returns MAPPED."""
    mock_stage2_result = BatchResult(results=[
        ControlResult(control_id="DCF-37", decision="MAPPED", addresses_control=True),
        ControlResult(control_id="DCF-99", decision="NO_MATCH", addresses_control=False),
    ])

    decider = ThreeStageDecider(...)
    stage3_tasks = []

    # Simulate Stage 2 completion
    await decider._handle_stage2_completion(mock_stage2_result, stage3_tasks)

    assert len(stage3_tasks) == 1  # Only MAPPED control
    assert "DCF-37" in stage3_tasks[0].get_name()
```

**6.3 Test time_to_first_verified tracking**
```python
@pytest.mark.asyncio
async def test_time_to_first_verified_tracked():
    decider = ThreeStageDecider(...)

    # Simulate pipeline
    result = await decider.process_document(pdf_bytes, batches)

    assert result.time_to_first_verified_seconds is not None
    assert result.time_to_first_verified_seconds > 0
```
→ Then implement `ThreeStageDecider` orchestration

### Phase 7: Integration (Test → Implement)

**7.1 Test CLI mode flag**
```python
def test_run_experiment_three_stage_mode():
    """--mode three_stage should use ThreeStageDecider."""
    # Test that argument parsing works
    args = parse_args(["--mode", "three_stage", "--policy", "test.pdf"])
    assert args.mode == "three_stage"
```

**7.2 Test metrics computation**
```python
def test_compute_stage2_vs_stage3_metrics():
    decision = ThreeStageDecision(...)
    ground_truth = {"DCF-37", "DCF-42", "DCF-100"}

    metrics = compute_comparison_metrics(decision, ground_truth)

    assert "stage2_precision" in metrics
    assert "stage2_recall" in metrics
    assert "final_precision" in metrics
    assert "final_recall" in metrics
    assert "precision_lift" in metrics
    assert "tp_loss_rate" in metrics
```
→ Then wire up `--mode three_stage` in `run_experiment.py`

### Phase 8: End-to-End Validation

**8.1 Run on single document with mocked LLM**
```python
@pytest.mark.asyncio
async def test_three_stage_pipeline_e2e_mocked():
    """Full pipeline with mocked Gemini responses."""
    mock_stage2_responses = [...]  # Pre-recorded or synthetic
    mock_stage3_responses = [...]

    decider = ThreeStageDecider(gemini_client=MockGemini(...))
    result = await decider.process_document(pdf_bytes, batches)

    assert result.stage2_mapped_count > 0
    assert len(result.verified_controls) + len(result.rejected_controls) == result.stage2_mapped_count
```

**8.2 Run on Acceptable Use Policy (real LLM, manual verification)**
- Execute: `python run_experiment.py --mode three_stage --policy "Acceptable Use Policy"`
- Manually inspect `verification_*.json` files
- Compare Stage 2 vs Stage 3 precision/recall against ground truth
- Analyze rejection reasons and thought summaries

### Test File Structure

```
tests/scripts/experiments/control_detection/
├── __init__.py
├── test_control_centric_models.py      # Phase 1: VerificationVerdict, VerificationResult, ThreeStageDecision
├── test_verification_prompt.py         # Phase 2: Prompt template, building
├── test_verification_parsing.py        # Phase 3: Response parsing, thought extraction
├── test_verification_retry.py          # Phase 4: Retry logic
├── test_verification_persistence.py    # Phase 5: Output files, resume
├── test_three_stage_decider.py         # Phase 6: Orchestration, task management
├── test_three_stage_integration.py     # Phase 7: CLI, metrics
└── conftest.py                         # Shared fixtures (mock responses, sample data)
```

## Metrics to Track

### Stage 2 Metrics (before Stage 3 filtering)

| Metric | Description |
|--------|-------------|
| `stage2_mapped_count` | Controls that passed Stage 2 (sent to Stage 3) |
| `stage2_partial_count` | Controls marked PARTIAL by Stage 2 |
| `stage2_no_match_count` | Controls marked NO_MATCH by Stage 2 |
| `stage2_TP` | Stage 2 MAPPED controls that are true positives (requires ground truth) |
| `stage2_FP` | Stage 2 MAPPED controls that are false positives |
| `stage2_precision` | `stage2_TP / stage2_mapped_count` |
| `stage2_recall` | `stage2_TP / total_ground_truth_positives` |

### Stage 3 Metrics (final output)

| Metric | Description |
|--------|-------------|
| `stage3_verified_count` | Controls that passed Stage 3 (final predictions) |
| `stage3_rejected_count` | Controls rejected by Stage 3 |
| `final_TP` | VERIFIED controls that are true positives |
| `final_FP` | VERIFIED controls that are false positives |
| `final_precision` | `final_TP / stage3_verified_count` |
| `final_recall` | `final_TP / total_ground_truth_positives` |

### Comparison Metrics (Stage 2 → Stage 3)

| Metric | Description |
|--------|-------------|
| `precision_lift` | `final_precision - stage2_precision` (should be positive) |
| `recall_drop` | `stage2_recall - final_recall` (should be minimal) |
| `tp_loss_rate` | `(stage2_TP - final_TP) / stage2_TP` — how many TPs did Stage 3 incorrectly reject? |
| `fp_rejection_rate` | `(stage2_FP - final_FP) / stage2_FP` — how many FPs did Stage 3 correctly reject? |
| `verification_rate` | `verified / (verified + rejected)` |

### Operational Metrics

| Metric | Description |
|--------|-------------|
| `time_to_first_verified` | Latency from pipeline start to first VERIFIED control from Stage 3 (see note below) |
| `stage2_call_count` | Number of Stage 2 LLM calls |
| `stage3_call_count` | Number of Stage 3 LLM calls |
| `total_call_count` | stage2 + stage3 |

**Note on `time_to_first_verified`**: This replaces the old "time to first MAPPED" metric. In a three-stage pipeline, the first *usable* prediction is not when Stage 2 outputs MAPPED (that's just a candidate), but when Stage 3 outputs VERIFIED. This is the first control we're confident enough to show to a user. The immediate dispatch of Stage 3 tasks (as soon as Stage 2 produces MAPPED results) is designed to minimize this latency.

### Diagnostic Metrics

| Metric | Description |
|--------|-------------|
| `stage2_quote_hallucination_rate` | `stage2_quote_validated=false / total Stage 3 calls` |
| `rejection_reason_distribution` | Aggregate counts by rejection_reason (for diagnosis) |
| `guardrail_violation_distribution` | Aggregate counts by guardrail (e.g., "G-15: 12, G-17: 5") |

**Critical Metrics:**
- `tp_loss_rate`: Target < 10%. If Stage 3 rejects too many true positives, we're hurting recall.
- `precision_lift`: Target > 40 percentage points (e.g., 20% → 60%+). This is the whole point.
- `recall_drop`: Target < 5 percentage points. We want precision gains without major recall loss.

## Production Considerations (Not Implemented)

These are noted for future production deployment:

1. **Priority Queue**: Stage 3 tasks should preempt Stage 2 for better latency
2. **Call Budget**: Cap Stage 3 calls per document (e.g., 30 max)
3. **Confidence-Based Prioritization**: Verify highest-confidence MAPPEDs first
4. **Early Termination**: Stop when enough VERIFIED controls found
5. **Separate Semaphore Slots**: Reserve 3 of 10 slots for Stage 3
6. **Deterministic Pre-filters**: Before Stage 3, cheap checks could auto-reject obvious bad mappings:
   - Binding-language check (only for MANDATE controls)
   - Evidence locality check (multiple locations = suspicious)
   - Document-type gating (AUP cannot satisfy Physical Security Policy control)
   - Page alignment check (Stage 1 page hints vs Stage 2 claimed location)
7. **Stage 2 Excerpt-Based Context**: Feed Stage 2 only the top relevant page excerpts from Stage 1, not the full document. This would reduce FP inflow to Stage 3 but changes Stage 2 architecture.

## Design Decisions Incorporated from External Review

The following improvements were incorporated from external analysis (ChatGPT Pro):

### Adopted

1. **Fresh Evidence Extraction**: Stage 3 must independently re-locate and extract evidence rather than just validating Stage 2's quote. This catches hallucinations and enables programmatic validation.

2. **ARTIFACT vs MANDATE Differentiation**: Stage 3 now classifies the control type and applies different evidence standards:
   - ARTIFACT controls: Document existence (title/purpose) is valid evidence; binding language not required
   - MANDATE controls: Binding language required; descriptive statements insufficient

3. **Stage 2 Quote as "Untrusted"**: Stage 3 prompt explicitly treats Stage 2's claimed evidence as a hint, not ground truth, reducing anchoring bias.

4. **Schema Improvements**:
   - `guardrails_violated` is now an array (multiple violations possible)
   - Added `verified_evidence_quote` and `verified_location` for fresh extraction
   - Added `stage2_quote_validated` to track hallucination rate
   - Added `control_type_determined` to capture Stage 3's classification

5. **Fail-Closed Parsing**: Parse errors or missing evidence → auto-reject (precision-first)

6. **Task Tagging**: Explicit task naming for Stage 2 vs Stage 3 task identification

7. **Additional Metrics**:
   - `tp_loss_rate`: Measures if Stage 3 is incorrectly rejecting true positives
   - `stage2_quote_hallucination_rate`: How often Stage 2 quotes don't exist
   - `rejection_reason_distribution` and `guardrail_violation_distribution` for diagnosis

### Deferred

1. **Deterministic pre-filters** (cheap checks before Stage 3) - Production optimization
2. **Stage 2 excerpt-based context** (feed only top pages) - Requires Stage 2 architecture change
3. **Ablation experiments** (Stage 3 with/without Stage 2 reasoning) - Post-initial-experiment analysis

## Expected Impact

If Stage 2 produces 30 MAPPEDs (6 TP, 24 FP) and Stage 3 correctly rejects 20 of the 24 FPs:

| Metric | Before (Stage 2 only) | After (Stage 2 + 3) |
|--------|----------------------|---------------------|
| Predicted | 30 | 10 |
| TP | 6 | 6 |
| FP | 24 | 4 |
| **Precision** | **20%** | **60%** |

## Files to Create/Modify

### Create
- `ai_services/scripts/experiments/control_detection/prompts/control_verifier/user`
- `ai_services/scripts/experiments/control_detection/prompts/control_verifier/response.json`
- `ai_services/scripts/experiments/control_detection/three_stage_decider.py`

### Modify
- `ai_services/scripts/experiments/control_detection/control_centric_models.py` (add enum)
- `ai_services/scripts/experiments/control_detection/control_centric_decider.py` (extract reusable methods)
- `ai_services/scripts/experiments/control_detection/run_experiment.py` (add mode)
- `ai_services/scripts/experiments/control_detection/experiment_config.py` (add constants)

---

## Appendix A: What's in the Gemini Cache

The Gemini cache is created once per document and contains two things:

### 1. The Entire Policy Document (PDF)

The full PDF is uploaded as binary content. For example, "Acceptable Use Policy.pdf" (typically 7-15 pages) is entirely in the cache. The LLM can reference any page.

### 2. The System Prompt (~355 lines)

The system prompt defines the LLM's role, decision framework, and guardrails. It's baked into the cache at creation time and applies to ALL subsequent calls against that cache (both Stage 2 batches and Stage 3 verifications).

**Location:** `ai_services/scripts/experiments/control_detection/prompts/control_centric_false_positive_additions2/system`

**Key Sections:**

```
Role & Golden Rule (lines 1-4)
├── "You are a Strict External Auditor"
├── "Skeptical by default. Default position is NO_MATCH"
└── "Better to return NO_MATCH than falsely credit a control"

Mapping Standard (lines 7-15)
├── Requires: Mandate + Correct Scope + Type Match + No Critical Mismatch
└── Golden Rule: Don't penalize for missing procedures/parameters

Document Hierarchy Context (lines 18-31)
├── Distinguishes Policy (governance) from Procedure (operations)
└── "Data at rest shall be encrypted" DOES satisfy; "We protect data" does NOT

Phase 0: Document Classification (lines 34-52)
├── CRITICAL: Classify document type before evaluating controls
└── "An Acceptable Use Policy is not an Information Security Policy"

Phase 1: Control Requirement Profile (lines 55-94)
├── Control Type Classification (TECHNICAL/ADMINISTRATIVE/MONITORING/etc.)
└── Mandatory Qualifiers extraction (domain, audience, scope, timing, etc.)

Phase 2: Evidence Retrieval (lines 97-139)
├── Admissibility Filter (reject definitions, disclaimers, aspirational language)
├── Pass A: Direct Binding Evidence (must/shall/required)
├── Pass B: Strict Synonyms Only
└── Pass C: Final Verification

Phase 3: Precision Guardrails G-1 through G-17 (lines 142-202)
├── Category A: Control Type Mismatch (G-1, G-2, G-3, G-17)
├── Category B: Domain & Scope Boundaries (G-4 through G-7, G-15)
├── Category C: Lifecycle & Temporal (G-8, G-9)
├── Category D: Qualifier & Artifact Requirements (G-10, G-11, G-16)
└── Category E: Evidence Quality (G-12, G-13, G-14)

Phase 4: Interpretive Rules IR-1 through IR-7 (lines 205-222)
└── Rules for bridging minor gaps (only if no guardrail violated)

Phase 5: Decision Logic (lines 225-282)
├── MAPPED: All requirements met, single contiguous evidence, high confidence
├── PARTIAL: Real mandate but policy-level gap (scope/third-party/ownership)
├── NO_MATCH: Any guardrail violated, any doubt
└── Anti-patterns: One Quote → Many Controls, Mass Mapping

Output Format (lines 285-313)
└── JSON structure with control_id, decision, evidence_quote, rules_cited, etc.
```

**Why This Matters for Stage 3:**
- Stage 3 reuses this SAME cache (same system prompt + same document)
- The guardrails (G-1 through G-17) are already in context
- Stage 3's user prompt just asks the LLM to re-apply these rules to ONE control
- No need to repeat the guardrails in Stage 3's prompt

---

## Appendix B: Sample Stage 2 Output

Stage 2 processes controls in batches of ~10 and returns JSON for each. Here's a real example from `Acceptable_Use_Policy`:

**Source:** `files/llm_outputs/control_centric/20251231_201430/Acceptable_Use_Policy/batch_000.json`

```json
{
  "batch_id": 0,
  "control_ids": [
    "DCF-37", "DCF-195", "DCF-94", "DCF-10", "DCF-485",
    "DCF-800", "DCF-194", "DCF-914", "DCF-167", "DCF-556"
  ],
  "response": {
    "batch_results": [
      {
        "control_id": "DCF-37",
        "decision": "MAPPED",
        "confidence": "high",
        "control_type": "ARTIFACT",
        "evidence_quote": "This policy specifies acceptable use of end-user computing devices and technology.",
        "location_reference": "Page 1, Purpose",
        "rules_cited": [],
        "gaps_identified": [],
        "reasoning": "Direct match: The document is an established Acceptable Use Policy that outlines requirements for personnel's usage of company IT assets."
      },
      {
        "control_id": "DCF-94",
        "decision": "NO_MATCH",
        "confidence": "high",
        "control_type": "ARTIFACT",
        "evidence_quote": "",
        "location_reference": "",
        "rules_cited": ["G-15"],
        "gaps_identified": [],
        "reasoning": "No match. G-15: The document is an Acceptable Use Policy, not a formal Physical Security Policy, even though it contains a section on clean desks."
      },
      {
        "control_id": "DCF-167",
        "decision": "NO_MATCH",
        "confidence": "high",
        "control_type": "ADMINISTRATIVE",
        "evidence_quote": "",
        "location_reference": "",
        "rules_cited": ["G-17"],
        "gaps_identified": [],
        "reasoning": "No match. G-17: Policy mentions preparing recovery plans for malware attacks but does not mandate the performance or documentation of a Business Impact Analysis (BIA)."
      }
      // ... 7 more results omitted
    ]
  }
}
```

**What Stage 3 Receives:**

For each `MAPPED` control (like DCF-37 above), Stage 3 gets:
- `control_id`: "DCF-37"
- `control_name`: (from DCF controls database)
- `control_description`: (from DCF controls database)
- `evidence_quote`: "This policy specifies acceptable use of end-user computing devices and technology."
- `location_reference`: "Page 1, Purpose"
- `reasoning`: "Direct match: The document is an established Acceptable Use Policy..."

Stage 3's job: Re-examine this evidence against the guardrails and decide VERIFIED or REJECTED.

---

## Appendix C: Stage 2 User Prompt Structure

For completeness, here's what a Stage 2 user prompt looks like (Stage 3 will be much simpler):

**Location:** `ai_services/scripts/experiments/control_detection/prompts/control_centric_false_positive_additions2/user`

The user prompt includes:
1. **Step 0 reminder**: Classify document type first
2. **Decision map**: MAPPED/PARTIAL/NO_MATCH criteria
3. **Hard rules**: Evidence locality, sufficiency test, no mass mapping
4. **Controls XML**: List of ~10 controls with their descriptions and page hints

Stage 3's user prompt will be much shorter—just the single control being verified plus its Stage 2 evidence.
