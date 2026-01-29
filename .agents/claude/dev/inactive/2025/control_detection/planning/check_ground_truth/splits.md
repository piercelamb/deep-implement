# Ground Truth Validation Pipeline - Implementation Splits

This document breaks the main plan into sequential, isolated units of work. Each split can be implemented, tested, and verified independently before moving to the next.

---

## Split Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         IMPLEMENTATION SPLITS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Split 1: Foundation          ──┐                                           │
│  (models + test infrastructure) │                                           │
│                                 ├──► Split 4: Judge Decider                 │
│  Split 2: GT Collector      ────┤    (LLM logic)                            │
│  (collect disputed controls)    │         │                                 │
│                                 │         ▼                                 │
│  Split 3: Judge Prompts     ────┘    Split 6: CLI + Integration             │
│  (system/user/schema)                (wire everything together)             │
│                                           │                                 │
│  Split 5: Output Generation  ────────────►│                                 │
│  (CSV/JSON generation)                    │                                 │
│                                           ▼                                 │
│                                  Split 7: E2E Validation                    │
│                                  (real LLM testing)                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Split 1: Foundation (Models + Test Infrastructure)

### Goal
Establish the foundation: data models, enums, and test infrastructure.

### Scope
- Create directory structure for source and tests
- Implement all data models in `models.py`
- Create `conftest.py` with shared fixtures
- Implement and pass all model tests

### Files to Create

| File | Purpose |
|------|---------|
| `ground_truth_validation/__init__.py` | Package init |
| `ground_truth_validation/models.py` | Data models |
| `tests/.../ground_truth_validation/__init__.py` | Test package |
| `tests/.../ground_truth_validation/conftest.py` | Shared fixtures |
| `tests/.../ground_truth_validation/test_models.py` | Model tests |

### TDD Sequence

1. **RED**: Write `test_models.py` with tests for:
   - `Verdict` enum values
   - `DisputeReason` enum values
   - `DisputedGTControl` creation (all fields)
   - `DisputedGTControl` with None fields (NOT_SENT case)
   - `JudgeResult` creation
   - `JudgeConfig` creation and defaults

2. **GREEN**: Implement `models.py` to pass tests

3. **REFACTOR**: Ensure frozen dataclasses, proper typing

### Verification Criteria

```bash
uv run pytest tests/scripts/experiments/control_detection/ground_truth_validation/test_models.py -v
# All tests pass
```

### Dependencies
- None (first split)

### Estimated Complexity
- **Low** - Straightforward dataclass definitions

---

## Split 2: GT Collector

### Goal
Collect disputed GT controls from existing experiment outputs.

### Scope
- Implement `gt_collector.py`
- Parse batch_*.json files
- Detect all three dispute reasons: PARTIAL, NO_MATCH, NOT_SENT_TO_LLM
- Load control metadata from dcf_controls.csv

### Files to Create/Modify

| File | Purpose |
|------|---------|
| `ground_truth_validation/gt_collector.py` | Collection logic |
| `tests/.../ground_truth_validation/test_gt_collector.py` | Collector tests |

### TDD Sequence

1. **RED**: Write `test_gt_collector.py` with tests for:
   - `collect_disputed_gt()` finds NO_MATCH controls
   - `collect_disputed_gt()` finds PARTIAL controls
   - `collect_disputed_gt()` finds NOT_SENT controls (never in batch files)
   - `collect_disputed_gt()` excludes MAPPED controls
   - `collect_disputed_gt()` handles empty GT
   - `collect_disputed_gt()` handles missing policy directory
   - `load_control_metadata()` returns name/description

2. **GREEN**: Implement `gt_collector.py` to pass tests

3. **REFACTOR**: Extract helpers, improve error handling

### Key Functions

```python
def collect_disputed_gt(
    timestamp: str,
    policy_name: str,
    gt_control_ids: set[str],
    llm_output_dir: Path,
    control_metadata: dict[str, DCFControl],
) -> list[DisputedGTControl]:
    """Collect all non-MAPPED GT controls from experiment outputs."""

def load_batch_results(policy_dir: Path) -> dict[str, BatchResult]:
    """Load all batch_*.json files and index by control_id."""
```

### Verification Criteria

```bash
uv run pytest tests/scripts/experiments/control_detection/ground_truth_validation/test_gt_collector.py -v
# All tests pass

# Manual verification with real data:
# Can parse an existing experiment's batch_*.json files
```

### Dependencies
- Split 1 (uses `DisputedGTControl`, `DisputeReason`)

### Estimated Complexity
- **Medium** - File parsing, edge case handling

---

## Split 3: Judge Prompts

### Goal
Create and manually test the judge prompts.

### Scope
- Create `prompts/judge/` directory
- Write system prompt
- Write user prompt template (handles both variants)
- Write response.json schema
- Manual testing in Vertex AI Studio

### Files to Create

| File | Purpose |
|------|---------|
| `prompts/judge/system` | System prompt |
| `prompts/judge/user` | User prompt template |
| `prompts/judge/response.json` | Response schema |

### Implementation Sequence

1. **Create system prompt** with:
   - Role definition (Security Compliance Auditor)
   - Task description (validate GT labels)
   - Verdict definitions (LLM_WRONG, GT_WRONG, UNCERTAIN)
   - PARTIAL coverage guidance
   - Policy-level evaluation standards

2. **Create user prompt template** with:
   - Control details section (id, name, description)
   - Dispute reason section
   - Conditional original_llm_evaluation section (only if not NOT_SENT)
   - Instructions section

3. **Create response schema** with:
   - control_id, verdict, confidence, reasoning
   - evidence_for_gt, evidence_against_gt, evidence_page

4. **Manual testing in Vertex AI Studio**:
   - Upload a sample policy PDF
   - Test with a NO_MATCH disputed control
   - Test with a NOT_SENT disputed control
   - Verify response format matches schema
   - Iterate on wording if needed

### Verification Criteria

- [ ] System prompt conveys correct evaluation standards
- [ ] User prompt template renders correctly for both variants
- [ ] Response schema parses valid JSON
- [ ] Manual testing produces sensible verdicts

### Dependencies
- None (can be done in parallel with Split 2)

### Estimated Complexity
- **Medium** - Prompt engineering, manual iteration

---

## Split 4: Judge Decider

### Goal
Implement the LLM judge that evaluates disputed controls.

### Scope
- Implement `judge_decider.py`
- Gemini client setup (reuse patterns from control_centric_decider.py)
- PDF caching
- Retry logic
- Semaphore for rate limiting
- Prompt building (both variants)
- Response parsing

### Files to Create/Modify

| File | Purpose |
|------|---------|
| `ground_truth_validation/judge_decider.py` | Judge LLM logic |
| `tests/.../ground_truth_validation/test_judge_decider.py` | Judge tests |

### TDD Sequence

1. **RED**: Write `test_judge_decider.py` with tests for:
   - `judge_control()` returns JudgeResult from LLM response
   - `judge_control()` builds correct prompt for NO_MATCH
   - `judge_control()` builds correct prompt for PARTIAL
   - `judge_control()` builds correct prompt for NOT_SENT (no original reasoning)
   - `judge_document()` respects semaphore limit
   - `judge_document()` skips existing outputs (resumability)
   - `judge_document()` processes all when --force
   - `_build_user_prompt()` handles None original_* fields
   - Response parsing handles missing fields gracefully

2. **GREEN**: Implement `judge_decider.py` to pass tests

3. **REFACTOR**: Extract prompt building, improve error handling

### Key Classes/Functions

```python
class JudgeDecider:
    def __init__(self, config: JudgeConfig): ...

    async def judge_control(
        self,
        cache_name: str,
        disputed_control: DisputedGTControl,
        output_dir: Path | None = None,
    ) -> JudgeResult: ...

    async def judge_document(
        self,
        policy_name: str,
        pdf_bytes: bytes,
        disputed_controls: list[DisputedGTControl],
        output_dir: Path,
        force: bool = False,
    ) -> list[JudgeResult]: ...

    def _build_user_prompt(self, control: DisputedGTControl) -> str: ...

    async def _upload_document_cache(self, pdf_bytes: bytes, name: str) -> str: ...

    async def _delete_cache(self, cache_name: str) -> None: ...
```

### Verification Criteria

```bash
uv run pytest tests/scripts/experiments/control_detection/ground_truth_validation/test_judge_decider.py -v
# All tests pass (with mocked LLM)
```

### Dependencies
- Split 1 (models)
- Split 3 (prompts)

### Estimated Complexity
- **High** - Async code, LLM integration, error handling

---

## Split 5: Output Generation

### Goal
Generate CSV and JSON output files from judge results.

### Scope
- Implement output generation functions
- Create CSV files for GRC review (by verdict)
- Create validation_summary.json
- Create run_metadata.json
- Create detailed_results.json

### Files to Create/Modify

| File | Purpose |
|------|---------|
| `ground_truth_validation/output_generator.py` | Output generation |
| `tests/.../ground_truth_validation/test_output_generation.py` | Output tests |

### TDD Sequence

1. **RED**: Write `test_output_generation.py` with tests for:
   - `generate_grc_review_files()` creates all CSV files
   - `grc_review_llm_wrong.csv` has correct columns and content
   - `grc_review_gt_wrong.csv` has correct columns and content
   - `grc_review_uncertain.csv` has correct columns and content
   - `generate_validation_summary()` has correct totals
   - `generate_validation_summary()` has correct by_dispute_reason counts
   - `generate_validation_summary()` has correct by_policy breakdown
   - `generate_run_metadata()` captures config correctly
   - `generate_detailed_results()` includes all judge results
   - Handle empty results gracefully

2. **GREEN**: Implement `output_generator.py` to pass tests

3. **REFACTOR**: Improve CSV formatting, add docstrings

### Key Functions

```python
def generate_grc_review_files(
    results: list[JudgeResult],
    output_dir: Path,
) -> None:
    """Generate CSV files for GRC expert review."""

def generate_validation_summary(
    results: list[JudgeResult],
    output_dir: Path,
    validation_timestamp: str,
    experiment_timestamp: str,
) -> None:
    """Generate validation_summary.json."""

def generate_run_metadata(
    output_dir: Path,
    config: JudgeConfig,
    experiment_timestamp: str,
    validation_timestamp: str,
) -> None:
    """Generate run_metadata.json for reproducibility."""

def generate_detailed_results(
    results: list[JudgeResult],
    output_dir: Path,
) -> None:
    """Generate detailed_results.json with all judge results."""
```

### Verification Criteria

```bash
uv run pytest tests/scripts/experiments/control_detection/ground_truth_validation/test_output_generation.py -v
# All tests pass
```

### Dependencies
- Split 1 (models)

### Estimated Complexity
- **Low-Medium** - File I/O, data aggregation

---

## Split 6: CLI + Integration

### Goal
Wire everything together into a working CLI.

### Scope
- Implement `run_validation.py` CLI
- Argument parsing
- Phase orchestration (collect → judge → output)
- Integration testing with mocked LLM

### Files to Create/Modify

| File | Purpose |
|------|---------|
| `ground_truth_validation/run_validation.py` | CLI entry point |
| `tests/.../ground_truth_validation/test_run_validation.py` | CLI tests |
| `tests/.../ground_truth_validation/test_integration.py` | Integration tests |

### TDD Sequence

1. **RED**: Write CLI argument tests:
   - Requires --experiment-timestamp OR --experiment
   - Parses --gcp-project correctly
   - Parses --max-judges correctly
   - Parses --force flag correctly
   - Parses --row and --max-rows correctly

2. **GREEN**: Implement argument parsing

3. **RED**: Write integration tests:
   - Full pipeline with mocked LLM produces correct outputs
   - Resumability works (skips existing outputs)
   - --force re-judges everything
   - --max-judges limits judge calls

4. **GREEN**: Implement pipeline orchestration

5. **REFACTOR**: Improve logging, error messages

### Key Functions

```python
def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

async def run_validation(args: argparse.Namespace) -> None:
    """Main validation pipeline."""

def main() -> None:
    """Entry point."""
```

### Verification Criteria

```bash
# Unit tests
uv run pytest tests/scripts/experiments/control_detection/ground_truth_validation/test_run_validation.py -v

# Integration tests (mocked LLM)
uv run pytest tests/scripts/experiments/control_detection/ground_truth_validation/test_integration.py -v

# CLI help works
python -m ai_services.scripts.experiments.control_detection.ground_truth_validation.run_validation --help
```

### Dependencies
- All previous splits

### Estimated Complexity
- **Medium-High** - Orchestration, error handling, async coordination

---

## Split 7: E2E Validation

### Goal
Validate the pipeline works end-to-end with real LLM.

### Scope
- Run on real experiment data
- Use real Gemini LLM
- Verify outputs are sensible
- Tune prompts if needed

### Execution Steps

1. **Select test data**:
   - Pick an existing experiment timestamp with known disputed controls
   - Choose a policy with a mix of PARTIAL, NO_MATCH, and NOT_SENT

2. **Dry run with --max-judges**:
   ```bash
   python -m ai_services.scripts.experiments.control_detection.ground_truth_validation.run_validation \
       --experiment-timestamp 20251226_150103 \
       --gcp-project PROJECT_ID \
       --max-judges 3
   ```

3. **Review outputs**:
   - Are verdicts sensible?
   - Are evidence quotes relevant?
   - Are page numbers accurate?

4. **Prompt iteration** (if needed):
   - Adjust system prompt for better results
   - Adjust user prompt template
   - Re-run and compare

5. **Full run**:
   ```bash
   python -m ai_services.scripts.experiments.control_detection.ground_truth_validation.run_validation \
       --experiment-timestamp 20251226_150103 \
       --gcp-project PROJECT_ID
   ```

6. **GRC review**:
   - Share CSV files with GRC expert
   - Collect feedback on verdict quality
   - Document any systematic issues

### Verification Criteria

- [ ] Pipeline completes without errors
- [ ] Verdicts are reasonable (spot-check 10 results)
- [ ] Evidence quotes are relevant to the control
- [ ] CSV files are usable by GRC experts
- [ ] Resumability works (can restart after interruption)

### Dependencies
- All previous splits complete

### Estimated Complexity
- **Medium** - Debugging, prompt tuning, validation

---

## Implementation Schedule

| Split | Estimated Effort | Can Parallelize With |
|-------|------------------|----------------------|
| Split 1: Foundation | 1-2 hours | - |
| Split 2: GT Collector | 2-3 hours | Split 3 |
| Split 3: Judge Prompts | 2-3 hours | Split 2 |
| Split 4: Judge Decider | 3-4 hours | Split 5 (partial) |
| Split 5: Output Generation | 2-3 hours | Split 4 (partial) |
| Split 6: CLI + Integration | 3-4 hours | - |
| Split 7: E2E Validation | 2-3 hours | - |

**Total estimated effort: 15-22 hours**

---

## Handoff Checklist

Before moving to the next split, verify:

- [ ] All tests pass for current split
- [ ] Code follows project patterns (frozen dataclasses, etc.)
- [ ] No linting errors (`uv run ruff check .`)
- [ ] No type errors (`uv run mypy ai_services/`)
- [ ] Code is committed (if appropriate)

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM rate limits | Semaphore limits concurrent calls; --max-judges for testing |
| Prompt doesn't work well | Manual testing in Split 3; iteration in Split 7 |
| Existing experiment data missing | Verify timestamp exists before Split 2 |
| Test flakiness with mocks | Use deterministic mock responses |
| Async complexity | Follow patterns from control_centric_decider.py |
