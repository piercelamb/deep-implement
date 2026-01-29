# Three-Stage Pipeline Implementation Splits

This document breaks the three-stage control mapping pipeline implementation into sequential, isolated units of work. Each split has clear entry/exit criteria, deliverables, and can be verified independently before moving to the next.

## Overview

```
Split 1: Data Models
    ↓
Split 2: Prompt Templates
    ↓
Split 3: Response Parsing
    ↓
Split 4: Gemini Integration (Thinking + Retry)
    ↓
Split 5: Output Persistence
    ↓
Split 6: Three-Stage Orchestrator
    ↓
Split 7: CLI Integration
    ↓
Split 8: E2E Validation
```

---

## Split 1: Data Models

**Purpose**: Define the core data structures for Stage 3 verification results.

### Scope

Create immutable dataclasses and enums that represent:
- Verification verdicts (VERIFIED/REJECTED)
- Individual verification results
- Document-level three-stage decisions

### Entry Criteria
- None (first split)

### Exit Criteria
- All tests pass
- Types are importable from `control_centric_models.py`
- Dataclasses are frozen, slotted, keyword-only
- `from_response()` and `from_file()` class methods work

### Files to Create/Modify

| Action | File |
|--------|------|
| Modify | `ai_services/scripts/experiments/control_detection/control_centric_models.py` |
| Create | `tests/scripts/experiments/control_detection/test_control_centric_models.py` |

### Deliverables

```python
# New types to add to control_centric_models.py

class VerificationVerdict(StrEnum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"

@dataclass(frozen=True, slots=True, kw_only=True)
class VerificationResult:
    control_id: str
    control_type_determined: str  # "ARTIFACT" or "MANDATE"
    verified_evidence_quote: str
    verified_location: str
    stage2_quote_validated: bool
    reasoning: str
    verdict: VerificationVerdict
    rejection_reason: str
    guardrails_violated: list[str]
    original_evidence: str
    original_location: str
    original_reasoning: str

    @classmethod
    def from_response(cls, response: dict, original: ControlResult) -> Self: ...

    @classmethod
    def from_file(cls, path: Path) -> Self: ...

@dataclass(frozen=True, slots=True, kw_only=True)
class ThreeStageDecision:
    policy_name: str
    stage2_mapped_count: int
    stage2_partial_count: int
    stage2_no_match_count: int
    verified_controls: list[VerificationResult]
    rejected_controls: list[VerificationResult]
    time_to_first_verified_seconds: float | None
    stage2_call_count: int
    stage3_call_count: int
    stage2_quotes_hallucinated: int
    rejection_reasons: dict[str, int]
    guardrails_violated_counts: dict[str, int]

    @property
    def verification_rate(self) -> float: ...

    @property
    def stage2_hallucination_rate(self) -> float: ...

    def get_final_controls(self) -> list[VerificationResult]: ...
```

### Tests to Write

1. `test_verification_verdict_enum()` - enum values and string conversion
2. `test_verification_result_creation()` - dataclass instantiation
3. `test_verification_result_from_response()` - parsing LLM response dict
4. `test_verification_result_from_file()` - loading from JSON file
5. `test_verification_result_immutability()` - frozen dataclass
6. `test_three_stage_decision_verification_rate()` - property calculation
7. `test_three_stage_decision_hallucination_rate()` - property calculation
8. `test_three_stage_decision_get_final_controls()` - returns only verified

### Isolation Notes

- No external dependencies (pure Python)
- Can be tested without Gemini, file I/O (except `from_file` test)
- Mock data used for all tests

---

## Split 2: Prompt Templates

**Purpose**: Create Stage 3 verification prompt template and JSON schema.

### Scope

- Write the adversarial verification prompt
- Define the response JSON schema
- Implement prompt building function that fills template

### Entry Criteria
- Split 1 complete (need `VerificationResult` structure to inform schema)

### Exit Criteria
- Prompt files exist and are valid
- `build_verification_prompt()` produces correct output
- Schema matches `VerificationResult` fields

### Files to Create/Modify

| Action | File |
|--------|------|
| Create | `ai_services/scripts/experiments/control_detection/prompts/control_verifier/user` |
| Create | `ai_services/scripts/experiments/control_detection/prompts/control_verifier/response.json` |
| Create | `tests/scripts/experiments/control_detection/test_verification_prompt.py` |
| Modify | (optional) prompt_loader.py if adding new loading logic |

### Deliverables

**`prompts/control_verifier/user`** - Adversarial prompt template with placeholders:
- `{control_id}`, `{control_name}`, `{control_description}`, `{control_type}`
- `{evidence_quote}`, `{location_reference}`, `{reasoning}`
- Contains "TREAT AS UNTRUSTED" framing
- Contains ARTIFACT vs MANDATE differentiation
- Contains rejection criteria checklist

**`prompts/control_verifier/response.json`** - JSON schema with:
- `reasoning` before `verdict` (forces chain-of-thought)
- `verified_evidence_quote` and `verified_location` for fresh extraction
- `stage2_quote_validated` boolean
- `guardrails_violated` as array

**`build_verification_prompt()`** function that:
- Loads template from prompts directory
- Substitutes placeholders with actual values
- Returns complete user prompt string

### Tests to Write

1. `test_verification_prompt_template_exists()` - file exists and readable
2. `test_verification_prompt_template_has_placeholders()` - all required placeholders present
3. `test_verification_prompt_has_adversarial_framing()` - contains "REJECT" and "UNTRUSTED"
4. `test_verification_response_schema_valid()` - valid JSON schema
5. `test_verification_response_schema_has_required_fields()` - all fields present
6. `test_build_verification_prompt_substitution()` - placeholders filled correctly
7. `test_build_verification_prompt_with_special_chars()` - handles quotes, newlines

### Isolation Notes

- File I/O only (no Gemini calls)
- Tests can use sample control data
- Template validation is pure string operations

---

## Split 3: Response Parsing

**Purpose**: Parse Stage 3 LLM responses into structured `VerificationResult` objects.

### Scope

- Parse JSON response from Gemini
- Extract thought summary from thinking mode response
- Handle malformed responses
- Auto-reject VERIFIED without evidence

### Entry Criteria
- Split 1 complete (need `VerificationResult`)
- Split 2 complete (need response schema to know expected structure)

### Exit Criteria
- Can parse valid VERIFIED responses
- Can parse valid REJECTED responses
- Auto-rejects VERIFIED with empty evidence
- Extracts thought summary correctly
- Raises appropriate errors for malformed JSON

### Files to Create/Modify

| Action | File |
|--------|------|
| Create | `ai_services/scripts/experiments/control_detection/verification_parser.py` (or add to existing) |
| Create | `tests/scripts/experiments/control_detection/test_verification_parsing.py` |

### Deliverables

```python
def parse_verification_response(
    raw_json: str,
    control_id: str,
    enforce_evidence: bool = True
) -> dict:
    """
    Parse raw JSON response into verification result dict.

    Args:
        raw_json: JSON string from Gemini
        control_id: Expected control ID (for validation)
        enforce_evidence: If True, auto-reject VERIFIED with empty evidence

    Returns:
        Dict matching response schema

    Raises:
        json.JSONDecodeError: Invalid JSON
        KeyError: Missing required field
        ValueError: Control ID mismatch
    """

def extract_thought_and_answer(response) -> tuple[str, str]:
    """
    Extract thought summary and answer from Gemini thinking mode response.

    Args:
        response: Gemini response object with parts

    Returns:
        (thought_summary, answer_text) tuple
    """
```

### Tests to Write

1. `test_parse_verification_response_verified()` - valid VERIFIED response
2. `test_parse_verification_response_rejected()` - valid REJECTED response
3. `test_parse_verification_response_with_guardrails()` - multiple guardrails violated
4. `test_parse_verification_response_invalid_json()` - raises JSONDecodeError
5. `test_parse_verification_response_missing_field()` - raises KeyError
6. `test_parse_verification_response_control_id_mismatch()` - raises ValueError
7. `test_verified_without_evidence_auto_rejects()` - VERIFIED + empty quote → REJECTED
8. `test_extract_thought_and_answer_with_thoughts()` - thought parts extracted
9. `test_extract_thought_and_answer_no_thoughts()` - handles response without thinking

### Isolation Notes

- Pure functions (no I/O, no Gemini)
- Mock Gemini response objects for thought extraction tests
- Uses sample JSON strings for parsing tests

---

## Split 4: Gemini Integration (Thinking + Retry)

**Purpose**: Implement the Stage 3 verification call with thinking mode and retry logic.

### Scope

- Enable Gemini thinking mode for Stage 3 calls
- Implement retry logic (same as Stage 2)
- Create `_make_rejected_result()` helper for fail-closed behavior

### Entry Criteria
- Split 1 complete (need `VerificationResult`, `VerificationVerdict`)
- Split 3 complete (need parsing functions)

### Exit Criteria
- Thinking mode enabled for Stage 3 calls
- Retries once on None response
- Retries once on parse error
- Fails to REJECTED after retry exhaustion
- `_make_rejected_result()` creates valid result

### Files to Create/Modify

| Action | File |
|--------|------|
| Create | `ai_services/scripts/experiments/control_detection/verification_caller.py` (or add to three_stage_decider.py) |
| Create | `tests/scripts/experiments/control_detection/test_verification_retry.py` |

### Deliverables

```python
from google.generativeai import types

STAGE3_THINKING_CONFIG = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(include_thoughts=True)
)

async def call_stage3_verification(
    gemini_client,
    prompt: str,
    cache_name: str,
    control_id: str,
    max_attempts: int = 2
) -> tuple[VerificationResult | None, str]:
    """
    Call Gemini for Stage 3 verification with retry logic.

    Returns:
        (verification_result, thought_summary) tuple
        result is None if all retries failed (caller should use _make_rejected_result)
    """

def _make_rejected_result(
    original: ControlResult,
    reason: str
) -> VerificationResult:
    """Create a REJECTED result for fail-closed scenarios."""
```

### Tests to Write

1. `test_call_stage3_thinking_mode_enabled()` - config includes thinking
2. `test_call_stage3_retries_on_none()` - retries once when response is None
3. `test_call_stage3_fails_after_max_retries_none()` - returns None after 2 None responses
4. `test_call_stage3_retries_on_parse_error()` - retries once on JSONDecodeError
5. `test_call_stage3_fails_after_max_retries_parse()` - returns None after 2 parse errors
6. `test_call_stage3_success_first_try()` - returns result without retry
7. `test_call_stage3_success_second_try()` - returns result after one retry
8. `test_make_rejected_result_fields()` - all fields populated correctly
9. `test_make_rejected_result_preserves_original()` - original evidence/location kept

### Isolation Notes

- Mock Gemini client for all tests
- No actual API calls
- Uses AsyncMock for async client methods

---

## Split 5: Output Persistence

**Purpose**: Write Stage 3 results to disk for analysis and resume capability.

### Scope

- Write verification JSON files (`verification_{control_id}.json`)
- Include thought summaries in output
- Implement resume detection (skip already-verified controls)

### Entry Criteria
- Split 1 complete (need `VerificationResult`)

### Exit Criteria
- Verification results written to correct file path
- Output includes stage2_input, stage3_response, thought_summary, timestamp
- `get_existing_verifications()` returns correct control IDs
- Can skip already-processed controls on resume

### Files to Create/Modify

| Action | File |
|--------|------|
| Create | `ai_services/scripts/experiments/control_detection/verification_persistence.py` |
| Create | `tests/scripts/experiments/control_detection/test_verification_persistence.py` |

### Deliverables

```python
def write_verification_output(
    output_dir: Path,
    control_id: str,
    stage2_input: dict,
    stage3_response: dict,
    thought_summary: str,
    attempt_count: int = 1
) -> Path:
    """
    Write Stage 3 verification result to JSON file.

    Returns:
        Path to written file
    """

def get_existing_verifications(output_dir: Path) -> set[str]:
    """
    Return control IDs that have already been verified.

    Scans for verification_*.json files in output_dir.
    """

def load_verification_result(file_path: Path) -> VerificationResult:
    """
    Load a VerificationResult from a saved JSON file.
    """
```

### Output File Format

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
  "thought_summary": "...",
  "timestamp": "2025-01-01T12:34:56Z",
  "attempt_count": 1
}
```

### Tests to Write

1. `test_write_verification_output_creates_file()` - file created at correct path
2. `test_write_verification_output_format()` - JSON structure matches spec
3. `test_write_verification_output_timestamp()` - timestamp included
4. `test_write_verification_output_special_chars()` - handles quotes in evidence
5. `test_get_existing_verifications_empty()` - returns empty set for empty dir
6. `test_get_existing_verifications_finds_files()` - finds all verification files
7. `test_get_existing_verifications_ignores_other_files()` - ignores batch_*.json
8. `test_load_verification_result()` - loads and reconstructs VerificationResult
9. `test_resume_skips_existing()` - integration test showing skip behavior

### Isolation Notes

- Uses `tmp_path` fixture for all file tests
- No Gemini calls
- No network I/O

---

## Split 6: Three-Stage Orchestrator

**Purpose**: Implement the main `ThreeStageDecider` class that coordinates Stage 2 and Stage 3.

### Scope

- Create `ThreeStageDecider` class
- Implement immediate Stage 3 dispatch on MAPPED results
- Track `time_to_first_verified`
- Task naming for Stage 2 vs Stage 3 identification
- Cache lifecycle management

### Entry Criteria
- Splits 1-5 complete
- Existing `ControlCentricDecider` available for Stage 2 calls

### Exit Criteria
- `ThreeStageDecider.process_document()` runs full pipeline
- Stage 3 tasks spawned immediately on MAPPED
- `time_to_first_verified` tracked correctly
- Tasks identifiable by name prefix
- Returns `ThreeStageDecision` with all metrics

### Files to Create/Modify

| Action | File |
|--------|------|
| Create | `ai_services/scripts/experiments/control_detection/three_stage_decider.py` |
| Create | `tests/scripts/experiments/control_detection/test_three_stage_decider.py` |
| Modify | `ai_services/scripts/experiments/control_detection/control_centric_decider.py` (extract reusable methods if needed) |

### Deliverables

```python
class ThreeStageDecider:
    """Orchestrates Stage 2 and Stage 3 of control mapping pipeline."""

    def __init__(
        self,
        stage2_decider: ControlCentricDecider,
        gemini_client,
        output_dir: Path,
        dcf_controls: dict[str, DCFControl],
    ): ...

    async def process_document(
        self,
        pdf_bytes: bytes,
        batches: list[Batch],
    ) -> ThreeStageDecision:
        """
        Run full three-stage pipeline on a document.

        1. Upload PDF to Gemini cache
        2. Run Stage 2 batches (from existing decider)
        3. Immediately dispatch Stage 3 for each MAPPED
        4. Collect results and compute metrics
        5. Return ThreeStageDecision
        """

    def _is_stage2_task(self, task: asyncio.Task) -> bool: ...
    def _is_stage3_task(self, task: asyncio.Task) -> bool: ...
```

### Tests to Write

1. `test_is_stage2_task()` - identifies stage2 tasks by name
2. `test_is_stage3_task()` - identifies stage3 tasks by name
3. `test_stage3_dispatched_immediately_on_mapped()` - Stage 3 created right after Stage 2 MAPPED
4. `test_stage3_not_dispatched_for_no_match()` - NO_MATCH doesn't trigger Stage 3
5. `test_time_to_first_verified_tracked()` - metric computed correctly
6. `test_time_to_first_verified_none_if_all_rejected()` - None when no VERIFIED
7. `test_process_document_returns_decision()` - full pipeline returns ThreeStageDecision
8. `test_process_document_counts_correct()` - stage2_mapped_count etc. correct
9. `test_process_document_resumes_from_existing()` - skips already-verified controls

### Isolation Notes

- Mock Stage 2 decider (return predetermined results)
- Mock Gemini client
- Use `tmp_path` for output directory
- Time tracking tests may need to mock `time.time()`

---

## Split 7: CLI Integration

**Purpose**: Wire up `--mode three_stage` to `run_experiment.py` and add metrics computation.

### Scope

- Add `--mode three_stage` CLI argument
- Instantiate `ThreeStageDecider` when mode selected
- Compute comparison metrics (Stage 2 vs final)
- Update output/reporting

### Entry Criteria
- Split 6 complete (`ThreeStageDecider` exists)

### Exit Criteria
- `python run_experiment.py --mode three_stage --policy "..."` works
- Metrics output includes precision/recall for both stages
- Output directory structure matches spec

### Files to Create/Modify

| Action | File |
|--------|------|
| Modify | `ai_services/scripts/experiments/control_detection/run_experiment.py` |
| Modify | `ai_services/scripts/experiments/control_detection/experiment_config.py` |
| Create | `tests/scripts/experiments/control_detection/test_three_stage_integration.py` |

### Deliverables

```python
# In run_experiment.py
parser.add_argument("--mode", choices=["control_centric", "three_stage"], default="control_centric")

# In experiment_config.py
VERIFICATION_PROMPTS_DIR = PROMPTS_DIR / "control_verifier"
MAX_VERIFICATION_CALLS_PER_DOCUMENT = 100  # For production (optional)
```

**Metrics computation:**
```python
def compute_comparison_metrics(
    decision: ThreeStageDecision,
    ground_truth: set[str],
) -> dict:
    """
    Compute Stage 2 vs final precision/recall metrics.

    Returns dict with:
    - stage2_precision, stage2_recall
    - final_precision, final_recall
    - precision_lift, recall_drop
    - tp_loss_rate, fp_rejection_rate
    """
```

### Tests to Write

1. `test_run_experiment_three_stage_mode_arg()` - argument parsing works
2. `test_run_experiment_creates_three_stage_decider()` - correct class instantiated
3. `test_compute_comparison_metrics_basic()` - metrics computed correctly
4. `test_compute_comparison_metrics_precision_lift()` - positive lift calculated
5. `test_compute_comparison_metrics_no_ground_truth()` - handles missing ground truth
6. `test_output_directory_structure()` - files in correct locations

### Isolation Notes

- Mock file I/O and Gemini for integration tests
- Use captured output/mocked print for CLI tests
- May use subprocess for true CLI tests

---

## Split 8: E2E Validation

**Purpose**: Run full pipeline on real data and validate results.

### Scope

- Mocked E2E test (full pipeline with mock Gemini)
- Real E2E test on Acceptable Use Policy
- Manual validation of results
- Document findings

### Entry Criteria
- Splits 1-7 complete

### Exit Criteria
- Mocked E2E test passes
- Real E2E produces output files
- Results analyzed and documented
- Precision lift measured

### Files to Create/Modify

| Action | File |
|--------|------|
| Create | `tests/scripts/experiments/control_detection/test_three_stage_e2e.py` |
| Create | `.agents/claude/dev/active/control_detection/planning/three_stage_mapping/results.md` (manual) |

### Deliverables

**Mocked E2E Test:**
```python
@pytest.mark.asyncio
async def test_three_stage_pipeline_e2e_mocked():
    """Full pipeline with mocked Gemini responses."""
    mock_stage2_responses = load_mock_responses("stage2")
    mock_stage3_responses = load_mock_responses("stage3")

    decider = ThreeStageDecider(gemini_client=MockGemini(...))
    result = await decider.process_document(pdf_bytes, batches)

    assert result.stage2_mapped_count > 0
    assert len(result.verified_controls) + len(result.rejected_controls) == result.stage2_mapped_count
```

**Real E2E Execution:**
```bash
python run_experiment.py --mode three_stage --policy "Acceptable Use Policy"
```

**Validation Checklist:**
- [ ] Stage 2 outputs written to `batch_*.json`
- [ ] Stage 3 outputs written to `verification_*.json`
- [ ] Thought summaries captured
- [ ] Metrics output shows precision/recall
- [ ] Precision lift > 0 (Stage 3 is helping)
- [ ] Recall drop < 10% (not losing too many TPs)

### Isolation Notes

- Mocked test is isolated (no real API calls)
- Real test requires Gemini API key and test PDF
- Real test marked with `@pytest.mark.integration`

---

## Summary Table

| Split | Name | Depends On | Deliverables | Estimated Tests |
|-------|------|------------|--------------|-----------------|
| 1 | Data Models | - | VerificationVerdict, VerificationResult, ThreeStageDecision | 8 |
| 2 | Prompt Templates | 1 | prompts/control_verifier/*, build_verification_prompt() | 7 |
| 3 | Response Parsing | 1, 2 | parse_verification_response(), extract_thought_and_answer() | 9 |
| 4 | Gemini Integration | 1, 3 | call_stage3_verification(), _make_rejected_result() | 9 |
| 5 | Output Persistence | 1 | write_verification_output(), get_existing_verifications() | 9 |
| 6 | Orchestrator | 1-5 | ThreeStageDecider class | 9 |
| 7 | CLI Integration | 6 | --mode three_stage, compute_comparison_metrics() | 6 |
| 8 | E2E Validation | 1-7 | E2E tests, results documentation | 2 |

**Total estimated tests: ~59**

---

## Next Steps

After this document is reviewed, create individual task lists for each split using the structure:

```markdown
## Split N: [Name]

### Tasks
1. [ ] Write test: test_xxx
2. [ ] Write test: test_yyy
3. [ ] Implement: function_name()
4. [ ] Run tests, verify pass
5. [ ] ...

### Verification
- [ ] All tests pass
- [ ] Exit criteria met
- [ ] Ready for next split
```
