# FP Rule Aggregator: Implementation Splits

This document breaks the plan into sequential, isolated units of work. Each split:
- Is self-contained and independently verifiable
- Has clear success criteria (tests pass, can run)
- Builds on previous splits

## Split Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Implementation Splits                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Split 1: Foundation           ← Models, Config, Test Fixtures      │
│       ↓                                                             │
│  Split 2: Data Loading         ← FP Loader (loads fp_judge_*.json)  │
│       ↓                                                             │
│  Split 3: Batching             ← Stratified round-robin batcher     │
│       ↓                                                             │
│  Split 4: Rule Validation      ← Rule linter + coverage analysis    │
│       ↓                                                             │
│  Split 5: Output               ← Output writer (atomic writes)      │
│       ↓                                                             │
│  Split 6: Prompts              ← Phase 1/2/3 prompt files           │
│       ↓                                                             │
│  Split 7: Phase 1 Aggregation  ← Batch summarization (LLM)          │
│       ↓                                                             │
│  Split 8: Phase 2+3 Aggregation← Consolidation + Synthesis (LLM)    │
│       ↓                                                             │
│  Split 9: CLI Integration      ← run.py + end-to-end pilot          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Split 1: Foundation

**Goal:** Create all data models, configuration, and shared test fixtures.

### Files to Create

| File | Type |
|------|------|
| `fp_rule_aggregator/__init__.py` | Module init |
| `fp_rule_aggregator/models.py` | Data models |
| `fp_rule_aggregator/config.py` | Configuration |
| `tests/.../fp_rule_aggregator/__init__.py` | Test module init |
| `tests/.../fp_rule_aggregator/conftest.py` | Shared fixtures |
| `tests/.../fp_rule_aggregator/test_models.py` | Model tests |
| `tests/.../fp_rule_aggregator/test_config.py` | Config tests |

### Models to Implement

```python
# Enums
class DecisionEffect(str, Enum)

# Input models
class FPJudgeOutput

# Intermediate models
class IndexedFP
class BatchSummary
class RootCauseRuleSet

# Output models
class FailureAvoidanceRule
class FinalRuleSet
class LintError
class CoverageReport
```

### Success Criteria

- [ ] All model dataclasses are frozen, slotted, kw_only
- [ ] `to_dict()` serialization works for all output models
- [ ] Config validates `max_parallel_batches > 0`
- [ ] All tests pass: `uv run pytest tests/.../fp_rule_aggregator/test_models.py tests/.../fp_rule_aggregator/test_config.py`

### Dependencies

- None (foundational)

### Estimated Effort

Low-Medium - Straightforward dataclass definitions

---

## Split 2: Data Loading

**Goal:** Implement FP loader that reads `fp_judge_*.json` files and groups by root_cause.

### Files to Create

| File | Type |
|------|------|
| `fp_rule_aggregator/fp_loader.py` | Implementation |
| `tests/.../fp_rule_aggregator/test_fp_loader.py` | Tests |
| `tests/.../fp_rule_aggregator/fixtures/sample_fp_judge_outputs/` | Test fixtures |

### Functions to Implement

```python
def load_fp_judge_outputs(
    fp_validation_dir: Path,
    exclude_uncertain: bool = True,
) -> dict[str, list[FPJudgeOutput]]
```

### Success Criteria

- [ ] Loads real FP validation outputs from `files/llm_outputs/fp_validation/20251229_221006/`
- [ ] Groups FPs by `root_cause` correctly (14 categories)
- [ ] Filters `UNCERTAIN` by default
- [ ] Extracts nested `original_fp` fields
- [ ] All tests pass: `uv run pytest tests/.../fp_rule_aggregator/test_fp_loader.py`

### Verification Command

```bash
# Quick verification: should print root_cause counts
uv run python -c "
from pathlib import Path
from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.fp_loader import load_fp_judge_outputs
fps = load_fp_judge_outputs(Path('files/llm_outputs/fp_validation/20251229_221006'))
for rc, items in sorted(fps.items(), key=lambda x: -len(x[1])):
    print(f'{rc}: {len(items)}')"
```

### Dependencies

- Split 1 (models.py)

### Estimated Effort

Low - Simple file reading and parsing

---

## Split 3: Batching

**Goal:** Implement stratified round-robin batching for high-volume categories.

### Files to Create

| File | Type |
|------|------|
| `fp_rule_aggregator/batcher.py` | Implementation |
| `tests/.../fp_rule_aggregator/test_batcher.py` | Tests |

### Functions to Implement

```python
HIGH_VOLUME_THRESHOLD = 200

def create_batches(
    fps_by_root_cause: dict[str, list[FPJudgeOutput]],
    batch_size: int = 60,
) -> dict[str, list[list[IndexedFP]]]

def _stratified_round_robin(
    fps: list[FPJudgeOutput],
    batch_size: int,
) -> list[list[IndexedFP]]

def _simple_batch(
    fps: list[FPJudgeOutput],
    batch_size: int,
) -> list[list[IndexedFP]]
```

### Success Criteria

- [ ] High-volume categories (>200) use stratified round-robin
- [ ] Each batch has diverse policies (no policy > 60% of batch)
- [ ] All indices are unique and sequential (0 to N-1)
- [ ] Low-volume categories use simple sequential batching
- [ ] All tests pass: `uv run pytest tests/.../fp_rule_aggregator/test_batcher.py`

### Verification Command

```bash
# Verify batch distribution for SEMANTIC_STRETCH
uv run python -c "
from pathlib import Path
from collections import Counter
from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.fp_loader import load_fp_judge_outputs
from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.batcher import create_batches

fps = load_fp_judge_outputs(Path('files/llm_outputs/fp_validation/20251229_221006'))
batches = create_batches(fps, batch_size=60)

# Check first batch of SEMANTIC_STRETCH
batch = batches['SEMANTIC_STRETCH'][0]
policy_counts = Counter(ifp.fp.policy_name for ifp in batch)
print(f'Batch size: {len(batch)}')
print(f'Unique policies: {len(policy_counts)}')
print(f'Top 3 policies: {policy_counts.most_common(3)}')"
```

### Dependencies

- Split 1 (models.py)

### Estimated Effort

Medium - Round-robin logic requires careful testing

---

## Split 4: Rule Validation

**Goal:** Implement rule linter and coverage analysis.

### Files to Create

| File | Type |
|------|------|
| `fp_rule_aggregator/rule_linter.py` | Implementation |
| `tests/.../fp_rule_aggregator/test_rule_linter.py` | Tests |

### Functions to Implement

```python
def lint_rules(rules: list[FailureAvoidanceRule]) -> list[LintError]

def compute_coverage(
    rules: list[FailureAvoidanceRule],
    total_fps: int
) -> CoverageReport
```

### Lint Checks

1. Absolute terms in `blocking_condition` require concrete `boundary_condition`
2. `boundary_condition` must not be vague ("unless relevant", etc.)
3. `allow_condition` must be present and non-trivial (>20 chars)
4. `supporting_fp_indices` must be non-empty (provenance required)

### Success Criteria

- [ ] Valid rules pass lint with no errors
- [ ] Each lint rule catches the specific violation
- [ ] Coverage correctly calculates `coverage_pct` and `multi_covered_fps`
- [ ] All tests pass: `uv run pytest tests/.../fp_rule_aggregator/test_rule_linter.py`

### Dependencies

- Split 1 (models.py)

### Estimated Effort

Low - Straightforward validation logic

---

## Split 5: Output

**Goal:** Implement atomic file writer for JSON and Markdown outputs.

### Files to Create

| File | Type |
|------|------|
| `fp_rule_aggregator/output_writer.py` | Implementation |
| `tests/.../fp_rule_aggregator/test_output_writer.py` | Tests |

### Class to Implement

```python
class FPRuleOutputWriter:
    def __init__(self, output_dir: Path)
    def write_final_output(self, rules: FinalRuleSet) -> None
    def write_batch_summary(self, summary: BatchSummary) -> None
    def write_run_metadata(self, ...) -> None
    def _atomic_write(self, path: Path, content: str) -> None
    def _format_rules_md(self, rules: tuple[FailureAvoidanceRule, ...], title: str) -> str
```

### Output Files

```
{output_dir}/
├── failure_avoidance_rules.json
├── universal_rules.md
├── rare_rules.md
├── run_metadata.json
├── lint_report.json
├── coverage_report.json
└── batches/
    └── {batch_id}.json
```

### Success Criteria

- [ ] Creates output directory if not exists
- [ ] Writes valid JSON (parseable)
- [ ] Writes readable Markdown with headers
- [ ] Uses atomic writes (temp file + rename)
- [ ] No temp files remain after write
- [ ] All tests pass: `uv run pytest tests/.../fp_rule_aggregator/test_output_writer.py`

### Dependencies

- Split 1 (models.py)

### Estimated Effort

Low - File I/O with formatting

---

## Split 6: Prompts

**Goal:** Create all Phase 1, 2, 3 prompt files.

### Files to Create

| File | Type |
|------|------|
| `fp_rule_aggregator/prompts/batch_summarize/system` | Phase 1 system |
| `fp_rule_aggregator/prompts/batch_summarize/user` | Phase 1 user |
| `fp_rule_aggregator/prompts/batch_summarize/response.json` | Phase 1 schema |
| `fp_rule_aggregator/prompts/consolidate_rules/system` | Phase 2 system |
| `fp_rule_aggregator/prompts/consolidate_rules/user` | Phase 2 user |
| `fp_rule_aggregator/prompts/consolidate_rules/response.json` | Phase 2 schema |
| `fp_rule_aggregator/prompts/synthesize_rules/system` | Phase 3 system |
| `fp_rule_aggregator/prompts/synthesize_rules/user` | Phase 3 user |
| `fp_rule_aggregator/prompts/synthesize_rules/response.json` | Phase 3 schema |

### Phase 1 (Batch Summarize)

- Input: Batch of FPs with same root_cause
- Output: 2-5 `FailureAvoidanceRule` with provenance
- Key fields: `supporting_fp_indices`, `evidence_triggers`, discriminators

### Phase 2 (Consolidate Rules)

- Input: Rules from multiple batches of same root_cause
- Output: Merged rules, preserving provenance
- Key: Don't merge rules that address different patterns

### Phase 3 (Synthesize Rules)

- Input: All rules from all root_causes
- Output: Final rules with `conflicts_with` field
- Key: De-conflict rules, classify as universal/rare

### Success Criteria

- [ ] All JSON schemas are valid and complete
- [ ] Prompts emphasize discriminator fields
- [ ] Prompts require `supporting_fp_indices` per rule
- [ ] Phase 3 prompt requires `conflicts_with` field

### Dependencies

- None (static files)

### Estimated Effort

Medium - Prompt engineering requires iteration

---

## Split 7: Phase 1 Aggregation

**Goal:** Implement Phase 1 batch summarization with LLM integration.

### Files to Create/Modify

| File | Type |
|------|------|
| `fp_rule_aggregator/aggregator.py` | Implementation (partial) |
| `tests/.../fp_rule_aggregator/test_aggregator.py` | Tests |

### Methods to Implement

```python
class FPRuleAggregator:
    def __init__(self, config: FPRuleConfig, client: genai.Client)

    async def _phase1_batch_summarize(
        self,
        batches: dict[str, list[list[IndexedFP]]],
    ) -> list[BatchSummary]

    async def _summarize_batch(
        self,
        batch_id: str,
        root_cause: str,
        indexed_fps: list[IndexedFP],
    ) -> BatchSummary

    def _build_batch_prompt(self, root_cause: str, indexed_fps: list[IndexedFP]) -> Prompt
    def _generate_rule_id(self, rule_data: dict) -> str
```

### Success Criteria

- [ ] LLM calls work with mocked responses in tests
- [ ] `example_count` is computed from `len(supporting_fp_indices)`
- [ ] `fp_index_map` is built for provenance
- [ ] Pilot mode processes only 1 batch per root_cause
- [ ] Parallelism is limited by semaphore
- [ ] All tests pass: `uv run pytest tests/.../fp_rule_aggregator/test_aggregator.py`

### Pilot Verification

```bash
# Run pilot mode with real LLM (1 batch per root_cause)
# This validates prompts produce usable output
uv run python -c "
import asyncio
from pathlib import Path
from google import genai
from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.config import FPRuleConfig
from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.fp_loader import load_fp_judge_outputs
from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.batcher import create_batches
from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.aggregator import FPRuleAggregator

config = FPRuleConfig(
    fp_validation_dir=Path('files/llm_outputs/fp_validation/20251229_221006'),
    output_dir=Path('files/llm_outputs/fp_rule_aggregator/pilot_test'),
    pilot_mode=True,
)
fps = load_fp_judge_outputs(config.fp_validation_dir)
batches = create_batches(fps, config.batch_size)

client = genai.Client(vertexai=True, project=config.gcp_project, location=config.vertex_location)
aggregator = FPRuleAggregator(config, client)
summaries = asyncio.run(aggregator._phase1_batch_summarize(batches))

for s in summaries:
    print(f'{s.batch_id}: {len(s.rules)} rules')
"
```

### Dependencies

- Splits 1-6

### Estimated Effort

High - LLM integration + async + prompt refinement

---

## Split 8: Phase 2+3 Aggregation

**Goal:** Complete aggregator with consolidation and synthesis phases.

### Methods to Implement

```python
class FPRuleAggregator:
    # ... (from Split 7)

    async def run_full_aggregation(
        self,
        fps_by_root_cause: dict[str, list[FPJudgeOutput]],
    ) -> FinalRuleSet

    async def _phase2_consolidate(
        self,
        batch_summaries: list[BatchSummary],
    ) -> list[RootCauseRuleSet]

    async def _phase3_synthesize(
        self,
        root_cause_rule_sets: list[RootCauseRuleSet],
    ) -> FinalRuleSet

    def _flatten_without_synthesis(
        self,
        root_cause_rule_sets: list[RootCauseRuleSet],
    ) -> FinalRuleSet
```

### Success Criteria

- [ ] Phase 2 merges rules within same root_cause
- [ ] Phase 2 preserves `derived_from` provenance
- [ ] Phase 3 adds `conflicts_with` field
- [ ] Phase 3 classifies rules as universal/rare
- [ ] `skip_synthesis` flag works (stops after Phase 2)
- [ ] All tests pass with mocked LLM

### Dependencies

- Split 7

### Estimated Effort

Medium - Similar pattern to Phase 1

---

## Split 9: CLI Integration

**Goal:** Create CLI entry point and run end-to-end pilot.

### Files to Create

| File | Type |
|------|------|
| `fp_rule_aggregator/run.py` | Implementation |
| `tests/.../fp_rule_aggregator/test_run.py` | Tests |

### Functions to Implement

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace
def build_config(args: argparse.Namespace) -> FPRuleConfig
async def run_aggregation(config: FPRuleConfig) -> None
def main() -> None
```

### CLI Arguments

```
--fp-validation-timestamp  (required)
--output-timestamp         (optional, default: now)
--pilot                    (flag)
--skip-synthesis           (flag)
-n/--parallelism           (default: 5)
```

### Success Criteria

- [ ] CLI parses all arguments correctly
- [ ] Config is built from args
- [ ] Full pipeline runs with `--pilot` flag
- [ ] Output files are written correctly
- [ ] Run metadata includes git SHA and prompt hashes
- [ ] All tests pass: `uv run pytest tests/.../fp_rule_aggregator/test_run.py`

### End-to-End Verification

```bash
# Pilot run (~14 LLM calls)
uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006 \
    --pilot

# Check outputs
ls -la files/llm_outputs/fp_rule_aggregator/*/
cat files/llm_outputs/fp_rule_aggregator/*/run_metadata.json | jq .output_stats
```

### Dependencies

- All previous splits

### Estimated Effort

Low - Orchestration only

---

## Split Summary Table

| Split | Name | Files | Tests | Dependencies | Effort |
|-------|------|-------|-------|--------------|--------|
| 1 | Foundation | 4 | 2 | None | Low-Med |
| 2 | Data Loading | 1 | 1 | Split 1 | Low |
| 3 | Batching | 1 | 1 | Split 1 | Medium |
| 4 | Rule Validation | 1 | 1 | Split 1 | Low |
| 5 | Output | 1 | 1 | Split 1 | Low |
| 6 | Prompts | 9 | 0 | None | Medium |
| 7 | Phase 1 Aggregation | 1 | 1 | Splits 1-6 | High |
| 8 | Phase 2+3 Aggregation | 1 | 0 | Split 7 | Medium |
| 9 | CLI Integration | 1 | 1 | All | Low |

## Parallelization Opportunities

Some splits can be worked on in parallel:

```
Split 1 (Foundation)
    ↓
    ├── Split 2 (Data Loading)
    ├── Split 3 (Batching)
    ├── Split 4 (Rule Validation)
    ├── Split 5 (Output)
    └── Split 6 (Prompts)
             ↓
         Split 7 (Phase 1)
             ↓
         Split 8 (Phase 2+3)
             ↓
         Split 9 (CLI)
```

After Split 1, Splits 2-6 can be developed in parallel since they have no dependencies on each other.

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Prompt quality issues | Use `--pilot` mode early, iterate on prompts |
| Rule quality issues | Rule linter catches vague conditions before output |
| Over-blocking rules | Discriminator fields + boundary conditions required |
| LLM rate limits | Semaphore limits concurrent calls |
| Lost provenance | `supporting_fp_indices` required in schema |
