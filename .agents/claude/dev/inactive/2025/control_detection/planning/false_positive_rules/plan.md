# Plan: False Positive Rule Generation

## Overview

Generate "Failure Avoidance Rules" from FP Judge outputs using batched summarization. The FP Judge has already categorized 1,870 false positives into 14 root causes with structured reasoning—we leverage this pre-structuring for a 97.8% reduction in LLM calls (41 vs 1,869).

**Key Insight:** Binary tree MapReduce is designed for unstructured data. Our data is already structured by root_cause, so we use batched summarization instead.

## Changes from ChatGPT Review

| Change | Rationale |
|--------|-----------|
| **Stratified round-robin batching** | Prevents policy-specific rules that don't generalize |
| **`supporting_fp_indices` per rule** | Fixes bug where `example_count=len(fps)` for all rules |
| **`DecisionEffect` enum expanded** | Add `requires_more_evidence`, `downgrade_confidence` |
| **Discriminator fields** | `danger_example_pattern`, `safe_example_pattern`, `allow_condition` |
| **Grounding fields** | `evidence_triggers`, `required_evidence` |
| **`conflicts_with` for Phase 3** | Make rule collisions explicit |
| **Run metadata** | Prompt hashes, git SHA for reproducibility |
| **Rule linter** | Reject vague conditions ("unless relevant", etc.) |
| **Coverage analysis** | Measure which FPs are addressed by which rules |

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     False Positive Rule Generation                        │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. LOAD: fp_judge_*.json files → filter UNCERTAIN → 1,868 FPs           │
│                                                                          │
│  2. GROUP: By root_cause (14 categories)                                 │
│     └─ Stratified round-robin by policy for high-volume categories       │
│                                                                          │
│  3. BATCH: Create ~50-75 item batches per root_cause                     │
│     └─ Each FP gets a stable index for provenance tracking               │
│                                                                          │
│  4. PHASE 1: Per-batch summarization (34 LLM calls, parallelizable)      │
│     └─ Extract failure avoidance rules with boundary conditions          │
│                                                                          │
│  5. PHASE 2: Per-root-cause consolidation (5 LLM calls for multi-batch)  │
│     └─ Merge within-category rules, preserve provenance                  │
│                                                                          │
│  6. PHASE 3: Cross-root-cause synthesis (1-2 LLM calls)                  │
│     └─ De-conflict rules, final universal/rare classification            │
│                                                                          │
│  7. OUTPUT: failure_avoidance_rules.json + .md files                     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

Estimated: ~41 LLM calls total (down from 1,869 for binary tree)
```

## Module Structure

```
ai_services/scripts/experiments/control_detection/
└── fp_rule_aggregator/
    ├── __init__.py
    ├── config.py              # FPRuleConfig dataclass
    ├── models.py              # FailureAvoidanceRule, BatchSummary, etc.
    ├── fp_loader.py           # Load fp_judge_*.json, group by root_cause
    ├── batcher.py             # Stratified round-robin batching
    ├── aggregator.py          # LLM calls: summarize, consolidate, synthesize
    ├── rule_linter.py         # Validate rule quality (no vague conditions)
    ├── output_writer.py       # Atomic JSON/MD output
    ├── run.py                 # CLI entry point
    └── prompts/
        ├── batch_summarize/   # Phase 1: Extract rules from batch
        │   ├── system
        │   ├── user
        │   └── response.json
        ├── consolidate_rules/ # Phase 2: Merge within root_cause
        │   ├── system
        │   ├── user
        │   └── response.json
        └── synthesize_rules/  # Phase 3: Cross-root-cause synthesis
            ├── system
            ├── user
            └── response.json
```

## Test-Driven Development Approach

This implementation follows **strict TDD**: write tests first, see them fail, then implement.

### Test Directory Structure

```
tests/scripts/experiments/control_detection/fp_rule_aggregator/
├── __init__.py
├── conftest.py                    # Shared fixtures
├── test_models.py                 # Data model tests
├── test_config.py                 # Config validation tests
├── test_fp_loader.py              # FP loading tests
├── test_batcher.py                # Stratified batching tests
├── test_rule_linter.py            # Rule quality validation tests
├── test_output_writer.py          # Output formatting tests
├── test_aggregator.py             # Integration tests (mocked LLM)
└── fixtures/
    ├── sample_fp_judge_outputs/   # Real FP judge JSON samples
    │   ├── Acceptable_Use_Policy/
    │   │   └── fp_judge_DCF-741.json
    │   └── Asset_Management_Policy/
    │       └── fp_judge_DCF-107.json
    └── expected_outputs/          # Golden outputs for comparison
```

### TDD Cycle for Each Component

```
┌─────────────────────────────────────────────────────────────────┐
│                    TDD Implementation Order                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: models.py        ← Test dataclass creation, serialize  │
│       ↓                                                         │
│  Step 2: config.py        ← Test validation, defaults           │
│       ↓                                                         │
│  Step 3: fp_loader.py     ← Test JSON parsing, grouping         │
│       ↓                                                         │
│  Step 4: batcher.py       ← Test stratified round-robin         │
│       ↓                                                         │
│  Step 5: rule_linter.py   ← Test lint checks, coverage          │
│       ↓                                                         │
│  Step 6: aggregator.py    ← Test with mocked LLM responses      │
│       ↓                                                         │
│  Step 7: prompts/         ← Static files, no tests needed       │
│       ↓                                                         │
│  Step 8: output_writer.py ← Test atomic writes, formatting      │
│       ↓                                                         │
│  Step 9: run.py           ← Test CLI arg parsing                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Shared Test Fixtures (`conftest.py`)

```python
import pytest
from pathlib import Path

@pytest.fixture
def sample_fp_judge_output() -> dict:
    """Single FP judge output as raw dict."""
    return {
        "control_id": "DCF-741",
        "policy_name": "Acceptable Use Policy",
        "verdict": "CONFIRMED_FP",
        "confidence": "high",
        "reasoning": "The control requires audit logging policy...",
        "misapplied_rules": ["IR-3", "IR-4"],
        "root_cause": "SEMANTIC_STRETCH",
        "evidence_critique": "The quote 'subject to monitoring' is about privacy...",
        "original_fp": {
            "llm_evidence_quote": "Use of computing systems is subject to monitoring",
            "llm_reasoning": "Mapped via IR-4: Policy establishes monitoring mandate",
            "llm_evidence_location": "Page 5 - Procedures",
            "batch_file": "batch_024.json"
        }
    }

@pytest.fixture
def sample_fp_judge_output_obj(sample_fp_judge_output) -> FPJudgeOutput:
    """Single FP judge output as dataclass."""
    return FPJudgeOutput(
        control_id=sample_fp_judge_output["control_id"],
        policy_name=sample_fp_judge_output["policy_name"],
        verdict=sample_fp_judge_output["verdict"],
        confidence=sample_fp_judge_output["confidence"],
        reasoning=sample_fp_judge_output["reasoning"],
        misapplied_rules=tuple(sample_fp_judge_output["misapplied_rules"]),
        root_cause=sample_fp_judge_output["root_cause"],
        evidence_critique=sample_fp_judge_output["evidence_critique"],
        original_evidence_quote=sample_fp_judge_output["original_fp"]["llm_evidence_quote"],
        original_llm_reasoning=sample_fp_judge_output["original_fp"]["llm_reasoning"],
        original_evidence_location=sample_fp_judge_output["original_fp"]["llm_evidence_location"],
    )

@pytest.fixture
def sample_fps_by_root_cause() -> dict[str, list[FPJudgeOutput]]:
    """Multiple FPs grouped by root_cause for batcher tests."""
    # Generate diverse FPs across policies
    fps = {
        "SEMANTIC_STRETCH": [
            _make_fp(f"DCF-{i}", f"Policy_{i % 5}") for i in range(250)
        ],
        "SCOPE_OVERREACH": [
            _make_fp(f"DCF-{i}", f"Policy_{i % 3}") for i in range(50)
        ],
    }
    return fps

@pytest.fixture
def sample_failure_avoidance_rule() -> FailureAvoidanceRule:
    """Valid rule for linter tests."""
    return FailureAvoidanceRule(
        rule_id="rule_abc123",
        rule_name="Monitoring vs Logging Distinction",
        failure_pattern="LLM confuses user monitoring with system logging",
        trigger_words=("monitoring", "subject to", "tracking"),
        control_contexts=("audit logging", "log retention"),
        evidence_triggers=("subject to monitoring", "may be monitored"),
        danger_example_pattern="'Users are subject to monitoring' for audit log control",
        safe_example_pattern="'System events are logged and retained' for audit log control",
        blocking_condition="Block when 'monitoring' refers to user surveillance",
        boundary_condition="Allow when monitoring explicitly references system events or logs",
        recovery_check="Verify if surrounding context mentions log files, retention, or SIEM",
        allow_condition="ALLOW if evidence mentions log files, retention periods, or audit trails",
        required_evidence=("log", "retention", "audit trail"),
        root_causes_addressed=("SEMANTIC_STRETCH",),
        ir_rules_involved=("IR-3", "IR-4"),
        decision_effect=DecisionEffect.BLOCKS_MAPPING,
        derived_from=("SEMANTIC_STRETCH_batch_00",),
        supporting_fp_indices=(0, 3, 7, 12),
        example_count=4,
        frequency="common",
    )

@pytest.fixture
def tmp_fp_validation_dir(tmp_path, sample_fp_judge_output) -> Path:
    """Temporary directory mimicking FP validation output structure."""
    policy_dir = tmp_path / "Acceptable_Use_Policy"
    policy_dir.mkdir()
    fp_file = policy_dir / "fp_judge_DCF-741.json"
    fp_file.write_text(json.dumps(sample_fp_judge_output))
    return tmp_path
```

## Data Models

### Input: FPJudgeOutput (loaded from fp_judge_*.json)

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class FPJudgeOutput:
    """Loaded from fp_judge_*.json files."""
    control_id: str
    policy_name: str
    verdict: Literal["CONFIRMED_FP", "UNCERTAIN"]
    confidence: Literal["high", "medium", "low"]
    reasoning: str
    misapplied_rules: tuple[str, ...]  # e.g., ("IR-3", "IR-4")
    root_cause: str  # e.g., "SEMANTIC_STRETCH"
    evidence_critique: str

    # From original_fp nested object
    original_evidence_quote: str
    original_llm_reasoning: str
    original_evidence_location: str
```

### Output: FailureAvoidanceRule

```python
class DecisionEffect(str, Enum):
    """What action the rule prescribes."""
    BLOCKS_MAPPING = "blocks_mapping"
    REQUIRES_MORE_EVIDENCE = "requires_more_evidence"
    DOWNGRADE_CONFIDENCE = "downgrade_confidence"

@dataclass(frozen=True, slots=True, kw_only=True)
class FailureAvoidanceRule:
    """A rule teaching the LLM what patterns to avoid."""
    rule_id: str  # Auto-generated hash
    rule_name: str

    # What triggers this failure
    failure_pattern: str  # Describes the LLM error pattern
    trigger_words: tuple[str, ...]  # Keywords that often cause this error
    control_contexts: tuple[str, ...]  # Control types prone to this error

    # Grounding (from original evidence)
    evidence_triggers: tuple[str, ...]  # Quoted spans that caused FPs
    danger_example_pattern: str  # What the FP "bait" looks like
    safe_example_pattern: str  # What a valid mapping looks like (discriminator)

    # How to avoid (blocking)
    blocking_condition: str  # When to reject a mapping
    boundary_condition: str  # When this rule does NOT apply (safe exception)
    recovery_check: str  # Verification step before rejecting

    # How to allow (positive case)
    allow_condition: str  # "ALLOW if evidence includes X"
    required_evidence: tuple[str, ...]  # What must be present for valid mapping

    # Categorization
    root_causes_addressed: tuple[str, ...]  # Which root causes this handles
    ir_rules_involved: tuple[str, ...]  # Which IR rules are commonly misapplied
    decision_effect: DecisionEffect  # blocks_mapping | requires_more_evidence | downgrade_confidence

    # Provenance
    derived_from: tuple[str, ...]  # Batch/source IDs
    supporting_fp_indices: tuple[int, ...]  # Which FPs in the batch support this rule
    example_count: int  # len(supporting_fp_indices) - computed, not from LLM
    frequency: Literal["very_common", "common", "uncommon", "rare"]

    # Conflicts (Phase 3 only)
    conflicts_with: tuple[str, ...] = ()  # Rule IDs that conflict with this one
```

### Intermediate: BatchSummary

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class IndexedFP:
    """FP with stable index for provenance tracking."""
    index: int  # Position in batch (0-based)
    fp: FPJudgeOutput

@dataclass(frozen=True, slots=True, kw_only=True)
class BatchSummary:
    """Output from Phase 1 batch summarization."""
    batch_id: str  # e.g., "SEMANTIC_STRETCH_batch_03"
    root_cause: str
    fp_count: int
    fp_index_map: dict[int, str]  # index -> control_id (for provenance)
    rules: tuple[FailureAvoidanceRule, ...]
```

### Intermediate: RootCauseRuleSet

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class RootCauseRuleSet:
    """Output from Phase 2 consolidation (per root_cause)."""
    root_cause: str
    universal_rules: tuple[FailureAvoidanceRule, ...]  # Multi-batch
    rare_rules: tuple[FailureAvoidanceRule, ...]  # Single-batch
    source_batches: tuple[str, ...]
```

## Implementation Steps

Each step follows TDD: **write tests first**, see them fail, then implement.

---

### Step 1: Models (`models.py`)

#### 1a. Write Tests First (`test_models.py`)

```python
class TestDecisionEffect:
    def test_enum_values(self):
        assert DecisionEffect.BLOCKS_MAPPING.value == "blocks_mapping"
        assert DecisionEffect.REQUIRES_MORE_EVIDENCE.value == "requires_more_evidence"
        assert DecisionEffect.DOWNGRADE_CONFIDENCE.value == "downgrade_confidence"

    def test_enum_from_string(self):
        assert DecisionEffect("blocks_mapping") == DecisionEffect.BLOCKS_MAPPING


class TestFPJudgeOutput:
    def test_creation_from_valid_data(self, sample_fp_judge_output):
        fp = FPJudgeOutput(
            control_id=sample_fp_judge_output["control_id"],
            # ... all fields
        )
        assert fp.control_id == "DCF-741"
        assert fp.root_cause == "SEMANTIC_STRETCH"

    def test_immutability(self, sample_fp_judge_output_obj):
        with pytest.raises(FrozenInstanceError):
            sample_fp_judge_output_obj.control_id = "NEW_ID"

    def test_misapplied_rules_is_tuple(self, sample_fp_judge_output_obj):
        assert isinstance(sample_fp_judge_output_obj.misapplied_rules, tuple)


class TestFailureAvoidanceRule:
    def test_creation_with_all_fields(self, sample_failure_avoidance_rule):
        assert sample_failure_avoidance_rule.rule_id == "rule_abc123"
        assert sample_failure_avoidance_rule.example_count == 4

    def test_to_dict_serialization(self, sample_failure_avoidance_rule):
        d = sample_failure_avoidance_rule.to_dict()
        assert d["rule_id"] == "rule_abc123"
        assert d["decision_effect"] == "blocks_mapping"

    def test_conflicts_with_default_empty(self):
        rule = FailureAvoidanceRule(
            # ... required fields without conflicts_with
        )
        assert rule.conflicts_with == ()


class TestIndexedFP:
    def test_creation(self, sample_fp_judge_output_obj):
        indexed = IndexedFP(index=5, fp=sample_fp_judge_output_obj)
        assert indexed.index == 5
        assert indexed.fp.control_id == "DCF-741"


class TestBatchSummary:
    def test_creation(self, sample_failure_avoidance_rule):
        summary = BatchSummary(
            batch_id="SEMANTIC_STRETCH_batch_00",
            root_cause="SEMANTIC_STRETCH",
            fp_count=60,
            fp_index_map={0: "DCF-741", 1: "DCF-107"},
            rules=(sample_failure_avoidance_rule,),
        )
        assert summary.batch_id == "SEMANTIC_STRETCH_batch_00"
        assert len(summary.rules) == 1
```

#### 1b. Implement (`models.py`)

Then implement the dataclasses to make tests pass.

---

### Step 2: Config (`config.py`)

#### 2a. Write Tests First (`test_config.py`)

```python
class TestFPRuleConfig:
    def test_default_values(self, tmp_path):
        config = FPRuleConfig(
            fp_validation_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
        )
        assert config.gcp_project == "ai-team-gemini-dev"
        assert config.model_name == "gemini-3-pro-preview"
        assert config.batch_size == 60
        assert config.pilot_mode is False

    def test_custom_temperatures(self, tmp_path):
        config = FPRuleConfig(
            fp_validation_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            batch_summarize_temp=0.5,
        )
        assert config.batch_summarize_temp == 0.5

    def test_immutability(self, tmp_path):
        config = FPRuleConfig(
            fp_validation_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
        )
        with pytest.raises(FrozenInstanceError):
            config.batch_size = 100

    def test_parallelism_bounds(self, tmp_path):
        # Should validate max_parallel_batches is reasonable
        with pytest.raises(ValueError):
            FPRuleConfig(
                fp_validation_dir=tmp_path / "input",
                output_dir=tmp_path / "output",
                max_parallel_batches=0,  # Invalid
            )
```

#### 2b. Implement (`config.py`)

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class FPRuleConfig:
    # GCP/Model
    gcp_project: str = "ai-team-gemini-dev"
    vertex_location: str = "global"
    model_name: str = "gemini-3-pro-preview"

    # Temperatures
    batch_summarize_temp: float = 0.7  # Exploratory extraction
    consolidate_temp: float = 0.5  # Focused merging
    synthesize_temp: float = 0.3  # Final synthesis

    # Batching
    batch_size: int = 60  # Items per batch (< 75 for token headroom)
    max_parallel_batches: int = 5  # Concurrent LLM calls

    # Paths
    fp_validation_dir: Path  # Input: fp_validation/{timestamp}
    output_dir: Path  # Output: fp_rule_aggregator/{timestamp}
    prompts_dir: Path = field(default_factory=lambda: SCRIPT_DIR / "prompts")

    # Options
    pilot_mode: bool = False  # Only process 1 batch per root_cause
    skip_synthesis: bool = False  # Stop after consolidation
```

### Step 3: FP Loader (`fp_loader.py`)

#### 3a. Write Tests First (`test_fp_loader.py`)

```python
import json
import pytest
from pathlib import Path

from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.fp_loader import (
    load_fp_judge_outputs,
)
from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.models import (
    FPJudgeOutput,
)


class TestLoadFPJudgeOutputs:
    def test_loads_single_fp_file(self, tmp_fp_validation_dir):
        """Should load a single FP judge output file."""
        result = load_fp_judge_outputs(tmp_fp_validation_dir)

        assert "SEMANTIC_STRETCH" in result
        assert len(result["SEMANTIC_STRETCH"]) == 1
        assert result["SEMANTIC_STRETCH"][0].control_id == "DCF-741"

    def test_groups_by_root_cause(self, tmp_path, sample_fp_judge_output):
        """Should group FPs by root_cause."""
        # Create multiple FPs with different root causes
        for i, root_cause in enumerate(["SEMANTIC_STRETCH", "SCOPE_OVERREACH", "SEMANTIC_STRETCH"]):
            policy_dir = tmp_path / f"Policy_{i}"
            policy_dir.mkdir()
            fp = {**sample_fp_judge_output, "root_cause": root_cause, "control_id": f"DCF-{i}"}
            (policy_dir / f"fp_judge_DCF-{i}.json").write_text(json.dumps(fp))

        result = load_fp_judge_outputs(tmp_path)

        assert len(result["SEMANTIC_STRETCH"]) == 2
        assert len(result["SCOPE_OVERREACH"]) == 1

    def test_filters_uncertain_by_default(self, tmp_path, sample_fp_judge_output):
        """Should exclude UNCERTAIN verdicts by default."""
        policy_dir = tmp_path / "Policy_A"
        policy_dir.mkdir()

        # CONFIRMED_FP should be included
        fp1 = {**sample_fp_judge_output, "control_id": "DCF-1", "verdict": "CONFIRMED_FP"}
        (policy_dir / "fp_judge_DCF-1.json").write_text(json.dumps(fp1))

        # UNCERTAIN should be excluded
        fp2 = {**sample_fp_judge_output, "control_id": "DCF-2", "verdict": "UNCERTAIN"}
        (policy_dir / "fp_judge_DCF-2.json").write_text(json.dumps(fp2))

        result = load_fp_judge_outputs(tmp_path)

        assert len(result["SEMANTIC_STRETCH"]) == 1
        assert result["SEMANTIC_STRETCH"][0].control_id == "DCF-1"

    def test_includes_uncertain_when_disabled(self, tmp_path, sample_fp_judge_output):
        """Should include UNCERTAIN when exclude_uncertain=False."""
        policy_dir = tmp_path / "Policy_A"
        policy_dir.mkdir()

        fp = {**sample_fp_judge_output, "verdict": "UNCERTAIN"}
        (policy_dir / "fp_judge_DCF-1.json").write_text(json.dumps(fp))

        result = load_fp_judge_outputs(tmp_path, exclude_uncertain=False)

        assert len(result["SEMANTIC_STRETCH"]) == 1

    def test_extracts_nested_original_fp_fields(self, tmp_fp_validation_dir):
        """Should extract fields from nested original_fp object."""
        result = load_fp_judge_outputs(tmp_fp_validation_dir)
        fp = result["SEMANTIC_STRETCH"][0]

        assert fp.original_evidence_quote == "Use of computing systems is subject to monitoring"
        assert fp.original_llm_reasoning == "Mapped via IR-4: Policy establishes monitoring mandate"
        assert fp.original_evidence_location == "Page 5 - Procedures"

    def test_returns_fpjudgeoutput_instances(self, tmp_fp_validation_dir):
        """Should return FPJudgeOutput dataclass instances."""
        result = load_fp_judge_outputs(tmp_fp_validation_dir)

        assert all(isinstance(fp, FPJudgeOutput) for fp in result["SEMANTIC_STRETCH"])

    def test_empty_directory_returns_empty_dict(self, tmp_path):
        """Should return empty dict for empty directory."""
        result = load_fp_judge_outputs(tmp_path)

        assert result == {}

    def test_skips_non_directory_files(self, tmp_path, sample_fp_judge_output):
        """Should skip files in the root directory."""
        # Create a file (not directory) in root
        (tmp_path / "random_file.json").write_text("{}")

        # Create valid structure
        policy_dir = tmp_path / "Policy_A"
        policy_dir.mkdir()
        (policy_dir / "fp_judge_DCF-1.json").write_text(json.dumps(sample_fp_judge_output))

        result = load_fp_judge_outputs(tmp_path)

        assert len(result["SEMANTIC_STRETCH"]) == 1
```

#### 3b. Implement (`fp_loader.py`)

Load all `fp_judge_*.json` files from the FP validation output directory.

```python
def load_fp_judge_outputs(
    fp_validation_dir: Path,
    exclude_uncertain: bool = True,
) -> dict[str, list[FPJudgeOutput]]:
    """
    Load FP judge outputs grouped by root_cause.

    Returns:
        Dict mapping root_cause -> list of FPJudgeOutput
        Example: {"SEMANTIC_STRETCH": [...926 items...], ...}
    """
    result: dict[str, list[FPJudgeOutput]] = defaultdict(list)

    for policy_dir in sorted(fp_validation_dir.iterdir()):
        if not policy_dir.is_dir():
            continue
        for fp_file in sorted(policy_dir.glob("fp_judge_*.json")):
            data = json.loads(fp_file.read_text())

            if exclude_uncertain and data["verdict"] == "UNCERTAIN":
                continue

            fp = FPJudgeOutput(
                control_id=data["control_id"],
                policy_name=data["policy_name"],
                verdict=data["verdict"],
                confidence=data["confidence"],
                reasoning=data["reasoning"],
                misapplied_rules=tuple(data["misapplied_rules"]),
                root_cause=data["root_cause"],
                evidence_critique=data["evidence_critique"],
                original_evidence_quote=data["original_fp"]["llm_evidence_quote"],
                original_llm_reasoning=data["original_fp"]["llm_reasoning"],
                original_evidence_location=data["original_fp"]["llm_evidence_location"],
            )
            result[fp.root_cause].append(fp)

    return dict(result)
```

### Step 4: Stratified Batcher (`batcher.py`)

Key enhancement: Use **stratified round-robin** for high-volume categories instead of sorted-then-chunked.
This prevents policy-specific rules that don't generalize while maintaining coherent clusters.

#### 4a. Write Tests First (`test_batcher.py`)

```python
import pytest
from collections import Counter

from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.batcher import (
    create_batches,
    _stratified_round_robin,
    _simple_batch,
    HIGH_VOLUME_THRESHOLD,
)
from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.models import (
    FPJudgeOutput,
    IndexedFP,
)


def _make_fp(control_id: str, policy_name: str, root_cause: str = "SEMANTIC_STRETCH") -> FPJudgeOutput:
    """Helper to create FPJudgeOutput for testing."""
    return FPJudgeOutput(
        control_id=control_id,
        policy_name=policy_name,
        verdict="CONFIRMED_FP",
        confidence="high",
        reasoning="Test reasoning",
        misapplied_rules=("IR-3",),
        root_cause=root_cause,
        evidence_critique="Test critique",
        original_evidence_quote="Test quote",
        original_llm_reasoning="Test LLM reasoning",
        original_evidence_location="Page 1",
    )


class TestCreateBatches:
    def test_uses_stratified_for_high_volume(self):
        """Should use stratified round-robin for categories > HIGH_VOLUME_THRESHOLD."""
        fps = {
            "HIGH_VOLUME": [_make_fp(f"DCF-{i}", f"Policy_{i % 5}") for i in range(HIGH_VOLUME_THRESHOLD + 50)],
            "LOW_VOLUME": [_make_fp(f"DCF-{i}", f"Policy_{i % 3}") for i in range(50)],
        }

        result = create_batches(fps, batch_size=50)

        # Both should produce batches
        assert "HIGH_VOLUME" in result
        assert "LOW_VOLUME" in result
        # High volume should have more batches (5 batches for 250 items at size 50)
        assert len(result["HIGH_VOLUME"]) == 5

    def test_returns_indexed_fps(self):
        """Each FP should be wrapped in IndexedFP with stable index."""
        fps = {"TEST": [_make_fp(f"DCF-{i}", "Policy_A") for i in range(100)]}

        result = create_batches(fps, batch_size=30)

        # Check all items are IndexedFP
        for batch in result["TEST"]:
            for item in batch:
                assert isinstance(item, IndexedFP)
                assert isinstance(item.index, int)
                assert isinstance(item.fp, FPJudgeOutput)


class TestStratifiedRoundRobin:
    def test_round_robin_distributes_policies(self):
        """Each batch should contain FPs from multiple policies."""
        fps = []
        # 100 FPs each from 4 policies
        for i in range(100):
            for policy in ["Policy_A", "Policy_B", "Policy_C", "Policy_D"]:
                fps.append(_make_fp(f"DCF-{policy}-{i}", policy))

        batches = _stratified_round_robin(fps, batch_size=60)

        # Each batch should have FPs from all 4 policies
        for batch in batches[:-1]:  # Exclude last partial batch
            policies_in_batch = {ifp.fp.policy_name for ifp in batch}
            assert len(policies_in_batch) == 4, f"Expected 4 policies, got {policies_in_batch}"

    def test_no_policy_dominates_batch(self):
        """No single policy should dominate any batch."""
        fps = []
        # Uneven distribution: Policy_A has 200, others have 50 each
        for i in range(200):
            fps.append(_make_fp(f"DCF-A-{i}", "Policy_A"))
        for i in range(50):
            fps.append(_make_fp(f"DCF-B-{i}", "Policy_B"))
        for i in range(50):
            fps.append(_make_fp(f"DCF-C-{i}", "Policy_C"))

        batches = _stratified_round_robin(fps, batch_size=60)

        # Check first few batches for balance
        for batch in batches[:3]:
            policy_counts = Counter(ifp.fp.policy_name for ifp in batch)
            # Policy_A should not have more than 50% of batch
            assert policy_counts["Policy_A"] <= len(batch) * 0.6

    def test_indices_are_unique_and_sequential(self):
        """Indices should be unique and cover 0 to N-1."""
        fps = [_make_fp(f"DCF-{i}", f"Policy_{i % 3}") for i in range(250)]

        batches = _stratified_round_robin(fps, batch_size=60)

        all_indices = []
        for batch in batches:
            all_indices.extend(ifp.index for ifp in batch)

        assert len(all_indices) == 250
        assert set(all_indices) == set(range(250))

    def test_handles_single_policy(self):
        """Should work with all FPs from one policy."""
        fps = [_make_fp(f"DCF-{i}", "Only_Policy") for i in range(100)]

        batches = _stratified_round_robin(fps, batch_size=30)

        assert len(batches) == 4  # 100/30 = 3.33, rounds up to 4
        total_fps = sum(len(b) for b in batches)
        assert total_fps == 100


class TestSimpleBatch:
    def test_creates_sequential_batches(self):
        """Should create batches in order with sequential indices."""
        fps = [_make_fp(f"DCF-{i}", "Policy_A") for i in range(100)]

        batches = _simple_batch(fps, batch_size=30)

        assert len(batches) == 4
        assert len(batches[0]) == 30
        assert len(batches[1]) == 30
        assert len(batches[2]) == 30
        assert len(batches[3]) == 10  # Remainder

    def test_indices_match_position(self):
        """Each FP should have index matching its position in original list."""
        fps = [_make_fp(f"DCF-{i}", "Policy_A") for i in range(50)]

        batches = _simple_batch(fps, batch_size=20)

        # First batch: indices 0-19
        assert [ifp.index for ifp in batches[0]] == list(range(20))
        # Second batch: indices 20-39
        assert [ifp.index for ifp in batches[1]] == list(range(20, 40))
        # Third batch: indices 40-49
        assert [ifp.index for ifp in batches[2]] == list(range(40, 50))

    def test_preserves_fp_data(self):
        """FP data should be preserved in IndexedFP wrapper."""
        fps = [_make_fp("DCF-123", "Test_Policy")]

        batches = _simple_batch(fps, batch_size=10)

        assert batches[0][0].fp.control_id == "DCF-123"
        assert batches[0][0].fp.policy_name == "Test_Policy"
```

#### 4b. Implement (`batcher.py`)

```python
HIGH_VOLUME_THRESHOLD = 200  # Categories above this get stratified batching

def create_batches(
    fps_by_root_cause: dict[str, list[FPJudgeOutput]],
    batch_size: int = 60,
) -> dict[str, list[list[IndexedFP]]]:
    """
    Create batches grouped by root_cause with stratified round-robin.

    High-volume categories (>200 items) use round-robin by policy_name
    to ensure each batch has diversity while maintaining coherent clusters.
    Low-volume categories are batched as-is.

    Each FP gets a stable index for provenance tracking.
    """
    batches: dict[str, list[list[IndexedFP]]] = {}

    for root_cause, fps in fps_by_root_cause.items():
        if len(fps) > HIGH_VOLUME_THRESHOLD:
            indexed_fps = _stratified_round_robin(fps, batch_size)
        else:
            # Simple sequential batching for low-volume
            indexed_fps = _simple_batch(fps, batch_size)

        batches[root_cause] = indexed_fps

    return batches

def _stratified_round_robin(
    fps: list[FPJudgeOutput],
    batch_size: int,
) -> list[list[IndexedFP]]:
    """
    Round-robin by policy to ensure diversity in each batch.

    Groups FPs by policy_name, then deals them round-robin into batches.
    This prevents any single policy from dominating a batch while keeping
    related FPs close together within the round-robin cycle.
    """
    # Group by policy
    by_policy: dict[str, list[FPJudgeOutput]] = defaultdict(list)
    for fp in fps:
        by_policy[fp.policy_name].append(fp)

    # Sort policies by count (largest first for better distribution)
    sorted_policies = sorted(by_policy.keys(), key=lambda p: -len(by_policy[p]))

    # Round-robin into batches
    batches: list[list[IndexedFP]] = []
    current_batch: list[IndexedFP] = []
    global_index = 0

    # Create iterators for each policy
    iterators = {p: iter(by_policy[p]) for p in sorted_policies}
    active_policies = set(sorted_policies)

    while active_policies:
        for policy in sorted_policies:
            if policy not in active_policies:
                continue
            try:
                fp = next(iterators[policy])
                current_batch.append(IndexedFP(index=global_index, fp=fp))
                global_index += 1

                if len(current_batch) >= batch_size:
                    batches.append(current_batch)
                    current_batch = []
            except StopIteration:
                active_policies.remove(policy)

    # Don't forget the last partial batch
    if current_batch:
        batches.append(current_batch)

    return batches

def _simple_batch(
    fps: list[FPJudgeOutput],
    batch_size: int,
) -> list[list[IndexedFP]]:
    """Simple sequential batching with index assignment."""
    batches = []
    for i in range(0, len(fps), batch_size):
        batch = [
            IndexedFP(index=i + j, fp=fp)
            for j, fp in enumerate(fps[i:i + batch_size])
        ]
        batches.append(batch)
    return batches
```

### Step 5: Rule Linter (`rule_linter.py`)

Automated quality checks on generated rules to prevent vague or overly-broad rules.

#### 5a. Write Tests First (`test_rule_linter.py`)

```python
import pytest

from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.rule_linter import (
    lint_rules,
    compute_coverage,
    LintError,
    CoverageReport,
)
from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.models import (
    FailureAvoidanceRule,
    DecisionEffect,
)


class TestLintRules:
    def test_valid_rule_passes(self, sample_failure_avoidance_rule):
        """Valid rule should produce no lint errors."""
        errors = lint_rules([sample_failure_avoidance_rule])

        assert errors == []

    def test_absolute_blocking_without_boundary_fails(self):
        """Rule with 'always/never' in blocking_condition needs concrete boundary."""
        rule = FailureAvoidanceRule(
            rule_id="test_rule",
            rule_name="Test Rule",
            failure_pattern="Test pattern",
            trigger_words=("test",),
            control_contexts=("test",),
            evidence_triggers=("test",),
            danger_example_pattern="Danger pattern",
            safe_example_pattern="Safe pattern",
            blocking_condition="ALWAYS block when monitoring is mentioned",
            boundary_condition="",  # Empty - should fail
            recovery_check="Check context",
            allow_condition="ALLOW if audit logs are explicitly mentioned",
            required_evidence=("audit", "log"),
            root_causes_addressed=("SEMANTIC_STRETCH",),
            ir_rules_involved=("IR-3",),
            decision_effect=DecisionEffect.BLOCKS_MAPPING,
            derived_from=("batch_01",),
            supporting_fp_indices=(0, 1),
            example_count=2,
            frequency="common",
        )

        errors = lint_rules([rule])

        assert len(errors) == 1
        assert "Absolute blocking_condition without concrete boundary" in errors[0].error

    def test_vague_boundary_condition_fails(self):
        """Rule with vague boundary condition should fail."""
        rule = FailureAvoidanceRule(
            rule_id="test_rule",
            rule_name="Test Rule",
            failure_pattern="Test pattern",
            trigger_words=("test",),
            control_contexts=("test",),
            evidence_triggers=("test",),
            danger_example_pattern="Danger pattern",
            safe_example_pattern="Safe pattern",
            blocking_condition="Block when monitoring mentioned",
            boundary_condition="Unless it's relevant to the context",  # Vague
            recovery_check="Check context",
            allow_condition="ALLOW if audit logs are explicitly mentioned",
            required_evidence=("audit", "log"),
            root_causes_addressed=("SEMANTIC_STRETCH",),
            ir_rules_involved=("IR-3",),
            decision_effect=DecisionEffect.BLOCKS_MAPPING,
            derived_from=("batch_01",),
            supporting_fp_indices=(0, 1),
            example_count=2,
            frequency="common",
        )

        errors = lint_rules([rule])

        assert len(errors) == 1
        assert "Vague boundary_condition" in errors[0].error

    def test_missing_allow_condition_fails(self):
        """Rule without allow_condition should fail."""
        rule = FailureAvoidanceRule(
            rule_id="test_rule",
            rule_name="Test Rule",
            failure_pattern="Test pattern",
            trigger_words=("test",),
            control_contexts=("test",),
            evidence_triggers=("test",),
            danger_example_pattern="Danger pattern",
            safe_example_pattern="Safe pattern",
            blocking_condition="Block when monitoring mentioned",
            boundary_condition="When audit logs are explicitly referenced",
            recovery_check="Check context",
            allow_condition="",  # Missing
            required_evidence=("audit", "log"),
            root_causes_addressed=("SEMANTIC_STRETCH",),
            ir_rules_involved=("IR-3",),
            decision_effect=DecisionEffect.BLOCKS_MAPPING,
            derived_from=("batch_01",),
            supporting_fp_indices=(0, 1),
            example_count=2,
            frequency="common",
        )

        errors = lint_rules([rule])

        assert len(errors) == 1
        assert "Missing or trivial allow_condition" in errors[0].error

    def test_empty_supporting_fp_indices_fails(self):
        """Rule without provenance should fail."""
        rule = FailureAvoidanceRule(
            rule_id="test_rule",
            rule_name="Test Rule",
            failure_pattern="Test pattern",
            trigger_words=("test",),
            control_contexts=("test",),
            evidence_triggers=("test",),
            danger_example_pattern="Danger pattern",
            safe_example_pattern="Safe pattern",
            blocking_condition="Block when monitoring mentioned",
            boundary_condition="When audit logs are explicitly referenced",
            recovery_check="Check context",
            allow_condition="ALLOW if audit logs are explicitly mentioned",
            required_evidence=("audit", "log"),
            root_causes_addressed=("SEMANTIC_STRETCH",),
            ir_rules_involved=("IR-3",),
            decision_effect=DecisionEffect.BLOCKS_MAPPING,
            derived_from=("batch_01",),
            supporting_fp_indices=(),  # Empty
            example_count=0,
            frequency="common",
        )

        errors = lint_rules([rule])

        assert len(errors) == 1
        assert "No supporting_fp_indices" in errors[0].error

    def test_multiple_errors_for_same_rule(self):
        """Rule with multiple issues should have multiple errors."""
        rule = FailureAvoidanceRule(
            rule_id="bad_rule",
            rule_name="Bad Rule",
            failure_pattern="Test pattern",
            trigger_words=("test",),
            control_contexts=("test",),
            evidence_triggers=("test",),
            danger_example_pattern="Danger pattern",
            safe_example_pattern="Safe pattern",
            blocking_condition="NEVER allow this",
            boundary_condition="",  # Empty
            recovery_check="Check context",
            allow_condition="",  # Empty
            required_evidence=("audit",),
            root_causes_addressed=("SEMANTIC_STRETCH",),
            ir_rules_involved=("IR-3",),
            decision_effect=DecisionEffect.BLOCKS_MAPPING,
            derived_from=("batch_01",),
            supporting_fp_indices=(),  # Empty
            example_count=0,
            frequency="common",
        )

        errors = lint_rules([rule])

        # Should have 3 errors: absolute without boundary, missing allow, no provenance
        assert len(errors) == 3
        rule_ids = [e.rule_id for e in errors]
        assert all(rid == "bad_rule" for rid in rule_ids)


class TestComputeCoverage:
    def test_full_coverage(self):
        """All FPs covered by rules should give 100% coverage."""
        rules = [
            _make_rule("rule_1", supporting_indices=(0, 1, 2)),
            _make_rule("rule_2", supporting_indices=(3, 4)),
        ]

        report = compute_coverage(rules, total_fps=5)

        assert report.total_fps == 5
        assert report.covered_fps == 5
        assert report.coverage_pct == 100.0

    def test_partial_coverage(self):
        """Only some FPs covered should give partial coverage."""
        rules = [
            _make_rule("rule_1", supporting_indices=(0, 2, 4)),
        ]

        report = compute_coverage(rules, total_fps=10)

        assert report.coverage_pct == 30.0
        assert report.covered_fps == 3

    def test_overlapping_coverage(self):
        """Same FP in multiple rules should count multi_covered."""
        rules = [
            _make_rule("rule_1", supporting_indices=(0, 1, 2)),
            _make_rule("rule_2", supporting_indices=(1, 2, 3)),  # 1, 2 overlap
        ]

        report = compute_coverage(rules, total_fps=5)

        assert report.covered_fps == 4  # 0, 1, 2, 3
        assert report.multi_covered_fps == 2  # 1, 2 are in both rules

    def test_empty_rules(self):
        """No rules should give 0% coverage."""
        report = compute_coverage([], total_fps=100)

        assert report.coverage_pct == 0.0
        assert report.covered_fps == 0


def _make_rule(rule_id: str, supporting_indices: tuple[int, ...]) -> FailureAvoidanceRule:
    """Helper to create minimal rule for coverage tests."""
    return FailureAvoidanceRule(
        rule_id=rule_id,
        rule_name="Test Rule",
        failure_pattern="Test pattern",
        trigger_words=("test",),
        control_contexts=("test",),
        evidence_triggers=("test",),
        danger_example_pattern="Danger",
        safe_example_pattern="Safe",
        blocking_condition="Block condition",
        boundary_condition="When X is present",
        recovery_check="Check Y",
        allow_condition="ALLOW when Z is present",
        required_evidence=("z",),
        root_causes_addressed=("SEMANTIC_STRETCH",),
        ir_rules_involved=("IR-3",),
        decision_effect=DecisionEffect.BLOCKS_MAPPING,
        derived_from=("batch_01",),
        supporting_fp_indices=supporting_indices,
        example_count=len(supporting_indices),
        frequency="common",
    )
```

#### 5b. Implement (`rule_linter.py`)

The implementation is already in the Testing Strategy section - move it here as the canonical implementation.

---

### Step 6: Aggregator (`aggregator.py`)

Three-phase aggregation following existing patterns.

#### 6a. Write Tests First (`test_aggregator.py`)

```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.aggregator import (
    FPRuleAggregator,
)
from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.config import (
    FPRuleConfig,
)
from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.models import (
    FPJudgeOutput,
    IndexedFP,
    BatchSummary,
    FailureAvoidanceRule,
    DecisionEffect,
)


@pytest.fixture
def mock_genai_client():
    """Mock Google GenAI client."""
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock()
    return client


@pytest.fixture
def sample_config(tmp_path):
    """Sample configuration for tests."""
    return FPRuleConfig(
        fp_validation_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        batch_size=10,
        max_parallel_batches=2,
    )


def _mock_llm_response(rules: list[dict]) -> MagicMock:
    """Create a mock LLM response with given rules."""
    response = MagicMock()
    response.text = json.dumps({"failure_avoidance_rules": rules})
    return response


class TestFPRuleAggregator:
    @pytest.mark.asyncio
    async def test_phase1_creates_batch_summaries(
        self, mock_genai_client, sample_config
    ):
        """Phase 1 should create BatchSummary for each batch."""
        # Setup mock LLM response
        mock_rule = {
            "rule_name": "Test Rule",
            "failure_pattern": "Test pattern",
            "trigger_words": ["monitoring"],
            "control_contexts": ["audit logging"],
            "evidence_triggers": ["subject to monitoring"],
            "danger_example_pattern": "Danger",
            "safe_example_pattern": "Safe",
            "blocking_condition": "Block when X",
            "boundary_condition": "Unless Y",
            "recovery_check": "Check Z",
            "allow_condition": "ALLOW when W",
            "required_evidence": ["evidence"],
            "root_causes_addressed": ["SEMANTIC_STRETCH"],
            "ir_rules_involved": ["IR-3"],
            "decision_effect": "blocks_mapping",
            "frequency": "common",
            "supporting_fp_indices": [0, 1, 2],
        }
        mock_genai_client.aio.models.generate_content.return_value = _mock_llm_response(
            [mock_rule]
        )

        aggregator = FPRuleAggregator(sample_config, mock_genai_client)

        # Create sample batches
        fps = [_make_test_fp(f"DCF-{i}", "Policy_A") for i in range(10)]
        batches = {"SEMANTIC_STRETCH": [[IndexedFP(index=i, fp=fp) for i, fp in enumerate(fps)]]}

        summaries = await aggregator._phase1_batch_summarize(batches)

        assert len(summaries) == 1
        assert summaries[0].batch_id == "SEMANTIC_STRETCH_batch_00"
        assert len(summaries[0].rules) == 1
        assert summaries[0].rules[0].example_count == 3  # len(supporting_fp_indices)

    @pytest.mark.asyncio
    async def test_phase1_respects_pilot_mode(
        self, mock_genai_client, sample_config, tmp_path
    ):
        """Pilot mode should only process 1 batch per root cause."""
        pilot_config = FPRuleConfig(
            fp_validation_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            pilot_mode=True,
            batch_size=5,
        )

        mock_genai_client.aio.models.generate_content.return_value = _mock_llm_response([])

        aggregator = FPRuleAggregator(pilot_config, mock_genai_client)

        # Create 3 batches worth of FPs
        fps = [_make_test_fp(f"DCF-{i}", "Policy_A") for i in range(15)]
        indexed_fps = [IndexedFP(index=i, fp=fp) for i, fp in enumerate(fps)]
        batches = {
            "SEMANTIC_STRETCH": [
                indexed_fps[:5],
                indexed_fps[5:10],
                indexed_fps[10:15],
            ]
        }

        summaries = await aggregator._phase1_batch_summarize(batches)

        # Should only process 1 batch in pilot mode
        assert len(summaries) == 1
        assert mock_genai_client.aio.models.generate_content.call_count == 1

    @pytest.mark.asyncio
    async def test_phase1_parallel_execution(
        self, mock_genai_client, sample_config
    ):
        """Phase 1 should process batches in parallel up to limit."""
        mock_genai_client.aio.models.generate_content.return_value = _mock_llm_response([])

        aggregator = FPRuleAggregator(sample_config, mock_genai_client)

        # Create multiple batches
        fps = [_make_test_fp(f"DCF-{i}", f"Policy_{i % 3}") for i in range(30)]
        indexed_fps = [IndexedFP(index=i, fp=fp) for i, fp in enumerate(fps)]
        batches = {
            "ROOT_A": [indexed_fps[:10], indexed_fps[10:20]],
            "ROOT_B": [indexed_fps[20:30]],
        }

        summaries = await aggregator._phase1_batch_summarize(batches)

        # All batches should be processed
        assert len(summaries) == 3
        assert mock_genai_client.aio.models.generate_content.call_count == 3

    @pytest.mark.asyncio
    async def test_computes_example_count_from_indices(
        self, mock_genai_client, sample_config
    ):
        """example_count should be computed from len(supporting_fp_indices)."""
        mock_rule = {
            "rule_name": "Test Rule",
            "failure_pattern": "Test pattern",
            "trigger_words": ["test"],
            "control_contexts": ["test"],
            "evidence_triggers": ["test"],
            "danger_example_pattern": "Danger",
            "safe_example_pattern": "Safe",
            "blocking_condition": "Block",
            "boundary_condition": "Unless",
            "recovery_check": "Check",
            "allow_condition": "ALLOW",
            "required_evidence": ["evidence"],
            "root_causes_addressed": ["SEMANTIC_STRETCH"],
            "ir_rules_involved": ["IR-3"],
            "decision_effect": "blocks_mapping",
            "frequency": "common",
            "supporting_fp_indices": [0, 5, 10, 15, 20],  # 5 indices
        }
        mock_genai_client.aio.models.generate_content.return_value = _mock_llm_response(
            [mock_rule]
        )

        aggregator = FPRuleAggregator(sample_config, mock_genai_client)
        fps = [_make_test_fp(f"DCF-{i}", "Policy_A") for i in range(10)]
        batches = {"SEMANTIC_STRETCH": [[IndexedFP(index=i, fp=fp) for i, fp in enumerate(fps)]]}

        summaries = await aggregator._phase1_batch_summarize(batches)

        rule = summaries[0].rules[0]
        assert rule.supporting_fp_indices == (0, 5, 10, 15, 20)
        assert rule.example_count == 5  # Computed, not from LLM

    @pytest.mark.asyncio
    async def test_builds_fp_index_map(self, mock_genai_client, sample_config):
        """BatchSummary should include fp_index_map for provenance."""
        mock_genai_client.aio.models.generate_content.return_value = _mock_llm_response([])

        aggregator = FPRuleAggregator(sample_config, mock_genai_client)

        # Create FPs with specific control IDs
        fps = [
            _make_test_fp("DCF-100", "Policy_A"),
            _make_test_fp("DCF-200", "Policy_B"),
            _make_test_fp("DCF-300", "Policy_C"),
        ]
        indexed_fps = [IndexedFP(index=i, fp=fp) for i, fp in enumerate(fps)]
        batches = {"SEMANTIC_STRETCH": [indexed_fps]}

        summaries = await aggregator._phase1_batch_summarize(batches)

        assert summaries[0].fp_index_map == {
            0: "DCF-100",
            1: "DCF-200",
            2: "DCF-300",
        }


def _make_test_fp(control_id: str, policy_name: str) -> FPJudgeOutput:
    """Helper to create FPJudgeOutput for testing."""
    return FPJudgeOutput(
        control_id=control_id,
        policy_name=policy_name,
        verdict="CONFIRMED_FP",
        confidence="high",
        reasoning="Test reasoning",
        misapplied_rules=("IR-3",),
        root_cause="SEMANTIC_STRETCH",
        evidence_critique="Test critique",
        original_evidence_quote="Test quote",
        original_llm_reasoning="Test LLM reasoning",
        original_evidence_location="Page 1",
    )
```

#### 6b. Implement (`aggregator.py`)

```python
class FPRuleAggregator:
    def __init__(self, config: FPRuleConfig, client: genai.Client):
        self.config = config
        self.client = client
        self.semaphore = asyncio.Semaphore(config.max_parallel_batches)

    async def run_full_aggregation(
        self,
        fps_by_root_cause: dict[str, list[FPJudgeOutput]],
    ) -> FinalRuleSet:
        """Execute all three phases."""

        # Create batches
        batches = create_batches(fps_by_root_cause, self.config.batch_size)

        # Phase 1: Batch summarization (parallel across all batches)
        batch_summaries = await self._phase1_batch_summarize(batches)

        # Phase 2: Per-root-cause consolidation
        root_cause_rule_sets = await self._phase2_consolidate(batch_summaries)

        # Phase 3: Cross-root-cause synthesis
        if not self.config.skip_synthesis:
            final_rules = await self._phase3_synthesize(root_cause_rule_sets)
        else:
            final_rules = self._flatten_without_synthesis(root_cause_rule_sets)

        return final_rules

    async def _phase1_batch_summarize(
        self,
        batches: dict[str, list[list[FPJudgeOutput]]],
    ) -> list[BatchSummary]:
        """Phase 1: Extract rules from each batch (parallel)."""
        tasks = []
        for root_cause, category_batches in batches.items():
            for i, batch in enumerate(category_batches):
                if self.config.pilot_mode and i > 0:
                    continue  # Only first batch in pilot mode
                batch_id = f"{root_cause}_batch_{i:02d}"
                tasks.append(self._summarize_batch(batch_id, root_cause, batch))

        return await asyncio.gather(*tasks)

    async def _summarize_batch(
        self,
        batch_id: str,
        root_cause: str,
        indexed_fps: list[IndexedFP],
    ) -> BatchSummary:
        """Summarize a single batch into failure avoidance rules."""
        async with self.semaphore:
            prompt = self._build_batch_prompt(root_cause, indexed_fps)

            response = await self.client.aio.models.generate_content(
                model=self.config.model_name,
                contents=[types.Content(role="user", parts=[types.Part(text=prompt.user)])],
                config=types.GenerateContentConfig(
                    system_instruction=prompt.system,
                    temperature=self.config.batch_summarize_temp,
                    response_mime_type="application/json",
                    response_schema=prompt.response_schema,
                ),
            )

            data = json.loads(response.text)

            # Build index map for provenance
            fp_index_map = {ifp.index: ifp.fp.control_id for ifp in indexed_fps}

            rules = tuple(
                FailureAvoidanceRule(
                    rule_id=self._generate_rule_id(r),
                    derived_from=(batch_id,),
                    # LLM outputs supporting_fp_indices; we compute example_count
                    supporting_fp_indices=tuple(r.pop("supporting_fp_indices", [])),
                    example_count=len(r.get("supporting_fp_indices", [])),
                    **r
                )
                for r in data["failure_avoidance_rules"]
            )

            return BatchSummary(
                batch_id=batch_id,
                root_cause=root_cause,
                fp_count=len(indexed_fps),
                fp_index_map=fp_index_map,
                rules=rules,
            )
```

### Step 7: Prompts

#### Phase 1: `prompts/batch_summarize/system`

```
You are a Security Compliance Auditor analyzing patterns in false positive control mappings.

## Context

A mapping LLM incorrectly determined that certain controls MAPPED to policies when they shouldn't have.
You are given a batch of analyzed false positives, all sharing the same ROOT CAUSE category.

Your task: Extract generalizable "Failure Avoidance Rules" that will teach the mapping LLM to avoid these errors.

## Root Cause Categories Reference

| Code | Description |
|------|-------------|
| SEMANTIC_STRETCH | Words seem similar but functional outcome differs |
| SCOPE_OVERREACH | Policy scope doesn't cover control's target assets |
| ABSTRACT_VS_SPECIFIC | LLM confused governance intent with operational mandate |
| EXISTENCE_NOT_IMPLIED | Using X doesn't imply having X documented |
| (... full list ...) |

## Rule Quality Criteria

1. **Actionable**: Rules must be testable (IF condition THEN action)
2. **Discriminating**: Include BOTH when to block AND when to allow
3. **Grounded**: Quote specific evidence spans that triggered the FP
4. **Non-Regressive**: Rules should not block valid mappings
5. **Traceable**: Reference which FPs (by index) support each rule

## Output Format

Generate 2-5 failure avoidance rules per batch. Each rule MUST include:

**Failure Identification:**
- failure_pattern: What error pattern this addresses
- trigger_words: Specific terms that often cause this error
- evidence_triggers: Short quoted spans from original_evidence_quote that caused the FP

**Discriminator Examples (critical for avoiding over-blocking):**
- danger_example_pattern: What the FP "bait" looks like (leads to incorrect mapping)
- safe_example_pattern: What a VALID mapping looks like that might seem similar

**Blocking Logic:**
- blocking_condition: When to reject a mapping
- boundary_condition: When this rule does NOT apply (safe exception)
- recovery_check: Verification step before final rejection

**Allowing Logic:**
- allow_condition: Positive case - "ALLOW if evidence includes X"
- required_evidence: What must be present for a valid mapping

**Provenance:**
- supporting_fp_indices: Which FPs (by index number) support this rule
```

#### Phase 1: `prompts/batch_summarize/user`

```
Analyze these {FP_COUNT} false positives (all root cause: {ROOT_CAUSE}).

Each FP is numbered with an index. When creating rules, reference which FP indices support each rule.

<false_positives>
{FP_DATA}
</false_positives>

For each FP above, the original LLM cited evidence_quote as justification for mapping.
Identify what linguistic patterns or contextual gaps led to the incorrect mapping.

IMPORTANT: For each rule you create:
1. Include supporting_fp_indices listing which FPs (by index) support this rule
2. Include evidence_triggers with short quoted spans from the original evidence
3. Include BOTH danger_example_pattern AND safe_example_pattern to discriminate
4. Include allow_condition describing when mapping IS valid despite trigger words
```

#### Phase 1: `prompts/batch_summarize/response.json`

```json
{
  "type": "object",
  "properties": {
    "failure_avoidance_rules": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "rule_name": {"type": "string"},
          "failure_pattern": {"type": "string"},
          "trigger_words": {"type": "array", "items": {"type": "string"}},
          "control_contexts": {"type": "array", "items": {"type": "string"}},
          "evidence_triggers": {"type": "array", "items": {"type": "string"}},
          "danger_example_pattern": {"type": "string"},
          "safe_example_pattern": {"type": "string"},
          "blocking_condition": {"type": "string"},
          "boundary_condition": {"type": "string"},
          "recovery_check": {"type": "string"},
          "allow_condition": {"type": "string"},
          "required_evidence": {"type": "array", "items": {"type": "string"}},
          "root_causes_addressed": {"type": "array", "items": {"type": "string"}},
          "ir_rules_involved": {"type": "array", "items": {"type": "string"}},
          "decision_effect": {
            "type": "string",
            "enum": ["blocks_mapping", "requires_more_evidence", "downgrade_confidence"]
          },
          "frequency": {"type": "string", "enum": ["very_common", "common", "uncommon", "rare"]},
          "supporting_fp_indices": {"type": "array", "items": {"type": "integer"}}
        },
        "required": [
          "rule_name", "failure_pattern", "trigger_words", "evidence_triggers",
          "danger_example_pattern", "safe_example_pattern",
          "blocking_condition", "boundary_condition", "recovery_check",
          "allow_condition", "required_evidence",
          "root_causes_addressed", "ir_rules_involved", "decision_effect", "frequency",
          "supporting_fp_indices"
        ]
      }
    }
  },
  "required": ["failure_avoidance_rules"]
}
```

### Step 8: Output Writer (`output_writer.py`)

Follow the atomic write pattern from reason_aggregator.

#### 8a. Write Tests First (`test_output_writer.py`)

```python
import json
import pytest
from pathlib import Path

from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.output_writer import (
    FPRuleOutputWriter,
)
from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.models import (
    FailureAvoidanceRule,
    BatchSummary,
    FinalRuleSet,
    DecisionEffect,
)


class TestFPRuleOutputWriter:
    def test_creates_output_directory(self, tmp_path):
        """Should create output directory if it doesn't exist."""
        output_dir = tmp_path / "new_dir" / "nested"

        writer = FPRuleOutputWriter(output_dir)

        assert output_dir.exists()

    def test_write_final_output_creates_json(
        self, tmp_path, sample_failure_avoidance_rule
    ):
        """Should write failure_avoidance_rules.json."""
        writer = FPRuleOutputWriter(tmp_path)
        rule_set = FinalRuleSet(
            universal_rules=(sample_failure_avoidance_rule,),
            rare_rules=(),
        )

        writer.write_final_output(rule_set)

        json_file = tmp_path / "failure_avoidance_rules.json"
        assert json_file.exists()
        data = json.loads(json_file.read_text())
        assert "universal_rules" in data
        assert len(data["universal_rules"]) == 1

    def test_write_final_output_creates_markdown(
        self, tmp_path, sample_failure_avoidance_rule
    ):
        """Should write universal_rules.md and rare_rules.md."""
        writer = FPRuleOutputWriter(tmp_path)
        rule_set = FinalRuleSet(
            universal_rules=(sample_failure_avoidance_rule,),
            rare_rules=(),
        )

        writer.write_final_output(rule_set)

        assert (tmp_path / "universal_rules.md").exists()
        assert (tmp_path / "rare_rules.md").exists()

    def test_write_batch_summary_creates_batch_dir(
        self, tmp_path, sample_failure_avoidance_rule
    ):
        """Should create batches/ subdirectory."""
        writer = FPRuleOutputWriter(tmp_path)
        summary = BatchSummary(
            batch_id="SEMANTIC_STRETCH_batch_00",
            root_cause="SEMANTIC_STRETCH",
            fp_count=50,
            fp_index_map={0: "DCF-741"},
            rules=(sample_failure_avoidance_rule,),
        )

        writer.write_batch_summary(summary)

        batch_file = tmp_path / "batches" / "SEMANTIC_STRETCH_batch_00.json"
        assert batch_file.exists()

    def test_atomic_write_temp_file(self, tmp_path, sample_failure_avoidance_rule):
        """Should use atomic write (write to temp, then rename)."""
        writer = FPRuleOutputWriter(tmp_path)
        rule_set = FinalRuleSet(
            universal_rules=(sample_failure_avoidance_rule,),
            rare_rules=(),
        )

        # Write should complete without partial files
        writer.write_final_output(rule_set)

        # Verify no temp files remain
        temp_files = list(tmp_path.glob("*.tmp"))
        assert temp_files == []

    def test_markdown_formatting(self, tmp_path, sample_failure_avoidance_rule):
        """Should format rules as readable markdown."""
        writer = FPRuleOutputWriter(tmp_path)
        rule_set = FinalRuleSet(
            universal_rules=(sample_failure_avoidance_rule,),
            rare_rules=(),
        )

        writer.write_final_output(rule_set)

        md_content = (tmp_path / "universal_rules.md").read_text()
        assert "# Universal Failure Avoidance Rules" in md_content
        assert sample_failure_avoidance_rule.rule_name in md_content
        assert "## " in md_content  # Has rule headers


class TestWriteRunMetadata:
    def test_writes_metadata_file(self, tmp_path):
        """Should write run_metadata.json with config and stats."""
        writer = FPRuleOutputWriter(tmp_path)

        writer.write_run_metadata(
            config={"batch_size": 60, "model": "gemini-3-pro"},
            input_stats={"total_fps": 1868},
            output_stats={"total_rules": 85},
            git_sha="abc123",
            prompt_hashes={"batch_summarize_system": "sha256:..."},
        )

        metadata_file = tmp_path / "run_metadata.json"
        assert metadata_file.exists()
        data = json.loads(metadata_file.read_text())
        assert data["config"]["batch_size"] == 60
        assert data["reproducibility"]["git_sha"] == "abc123"
```

#### 8b. Implement (`output_writer.py`)

```python
class FPRuleOutputWriter:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_final_output(self, rules: FinalRuleSet) -> None:
        """Write final rules to JSON and Markdown."""
        self._atomic_write(
            self.output_dir / "failure_avoidance_rules.json",
            json.dumps(rules.to_dict(), indent=2)
        )
        self._atomic_write(
            self.output_dir / "universal_rules.md",
            self._format_rules_md(rules.universal_rules, "Universal")
        )
        self._atomic_write(
            self.output_dir / "rare_rules.md",
            self._format_rules_md(rules.rare_rules, "Rare")
        )

    def write_batch_summary(self, summary: BatchSummary) -> None:
        """Write individual batch output for debugging."""
        batch_dir = self.output_dir / "batches"
        batch_dir.mkdir(exist_ok=True)
        self._atomic_write(
            batch_dir / f"{summary.batch_id}.json",
            json.dumps(summary.to_dict(), indent=2)
        )
```

### Step 9: CLI Entry Point (`run.py`)

#### 9a. Write Tests First (`test_run.py`)

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run import (
    main,
    run_aggregation,
    parse_args,
)
from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.config import (
    FPRuleConfig,
)


class TestParseArgs:
    def test_required_fp_validation_timestamp(self):
        """Should require --fp-validation-timestamp."""
        with pytest.raises(SystemExit):
            parse_args([])  # Missing required arg

    def test_parses_timestamp(self):
        """Should parse fp-validation-timestamp."""
        args = parse_args(["--fp-validation-timestamp", "20251229_221006"])

        assert args.fp_validation_timestamp == "20251229_221006"

    def test_default_parallelism(self):
        """Should default to 5 parallel batches."""
        args = parse_args(["--fp-validation-timestamp", "20251229_221006"])

        assert args.parallelism == 5

    def test_pilot_flag(self):
        """Should parse --pilot flag."""
        args = parse_args([
            "--fp-validation-timestamp", "20251229_221006",
            "--pilot"
        ])

        assert args.pilot is True

    def test_skip_synthesis_flag(self):
        """Should parse --skip-synthesis flag."""
        args = parse_args([
            "--fp-validation-timestamp", "20251229_221006",
            "--skip-synthesis"
        ])

        assert args.skip_synthesis is True

    def test_custom_parallelism(self):
        """Should parse -n/--parallelism."""
        args = parse_args([
            "--fp-validation-timestamp", "20251229_221006",
            "-n", "10"
        ])

        assert args.parallelism == 10

    def test_output_timestamp(self):
        """Should parse --output-timestamp."""
        args = parse_args([
            "--fp-validation-timestamp", "20251229_221006",
            "--output-timestamp", "20251230_120000"
        ])

        assert args.output_timestamp == "20251230_120000"


class TestBuildConfig:
    def test_builds_config_from_args(self, tmp_path):
        """Should build FPRuleConfig from parsed args."""
        args = parse_args([
            "--fp-validation-timestamp", "20251229_221006",
            "--pilot",
            "-n", "3"
        ])

        # Mock the base directories
        with patch(
            "ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run.FP_VALIDATION_DIR",
            tmp_path / "fp_validation"
        ), patch(
            "ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run.OUTPUT_DIR",
            tmp_path / "output"
        ):
            from ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run import (
                build_config,
            )

            config = build_config(args)

            assert config.pilot_mode is True
            assert config.max_parallel_batches == 3
            assert "20251229_221006" in str(config.fp_validation_dir)


class TestRunAggregation:
    @pytest.mark.asyncio
    async def test_orchestrates_full_pipeline(self, tmp_path):
        """Should orchestrate loader, aggregator, and writer."""
        config = FPRuleConfig(
            fp_validation_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
        )

        with patch(
            "ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run.genai.Client"
        ) as mock_client_cls, patch(
            "ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run.load_fp_judge_outputs"
        ) as mock_loader, patch(
            "ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run.FPRuleAggregator"
        ) as mock_aggregator_cls, patch(
            "ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run.FPRuleOutputWriter"
        ) as mock_writer_cls:
            # Setup mocks
            mock_loader.return_value = {"SEMANTIC_STRETCH": []}
            mock_aggregator = MagicMock()
            mock_aggregator.run_full_aggregation = AsyncMock(return_value=MagicMock())
            mock_aggregator_cls.return_value = mock_aggregator

            await run_aggregation(config)

            # Verify pipeline was called
            mock_loader.assert_called_once_with(config.fp_validation_dir)
            mock_aggregator.run_full_aggregation.assert_called_once()
            mock_writer_cls.return_value.write_final_output.assert_called_once()
```

#### 9b. Implement (`run.py`)

```python
def main():
    parser = argparse.ArgumentParser(
        description="Generate failure avoidance rules from FP validation outputs"
    )
    parser.add_argument(
        "--fp-validation-timestamp",
        required=True,
        help="Timestamp of FP validation run (e.g., 20251229_221006)",
    )
    parser.add_argument(
        "--output-timestamp",
        default=None,
        help="Output timestamp (default: current time)",
    )
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="Pilot mode: only 1 batch per root_cause (~14 LLM calls)",
    )
    parser.add_argument(
        "--skip-synthesis",
        action="store_true",
        help="Skip Phase 3 cross-root-cause synthesis",
    )
    parser.add_argument(
        "-n", "--parallelism",
        type=int,
        default=5,
        help="Max concurrent LLM calls (default: 5)",
    )

    args = parser.parse_args()

    # Build config
    config = FPRuleConfig(
        fp_validation_dir=FP_VALIDATION_DIR / args.fp_validation_timestamp,
        output_dir=OUTPUT_DIR / (args.output_timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")),
        pilot_mode=args.pilot,
        skip_synthesis=args.skip_synthesis,
        max_parallel_batches=args.parallelism,
    )

    # Run
    asyncio.run(run_aggregation(config))

async def run_aggregation(config: FPRuleConfig) -> None:
    client = genai.Client(
        vertexai=True,
        project=config.gcp_project,
        location=config.vertex_location,
    )

    # Load FP judge outputs
    fps_by_root_cause = load_fp_judge_outputs(config.fp_validation_dir)

    # Run aggregation
    aggregator = FPRuleAggregator(config, client)
    final_rules = await aggregator.run_full_aggregation(fps_by_root_cause)

    # Write outputs
    writer = FPRuleOutputWriter(config.output_dir)
    writer.write_final_output(final_rules)
```

## LLM Call Breakdown

| Phase | Root Cause | Items | Batches | Calls |
|-------|------------|-------|---------|-------|
| 1 | SEMANTIC_STRETCH | 926 | 16 | 16 |
| 1 | SCOPE_OVERREACH | 285 | 5 | 5 |
| 1 | ABSTRACT_VS_SPECIFIC | 191 | 4 | 4 |
| 1 | EXISTENCE_NOT_IMPLIED | 155 | 3 | 3 |
| 1 | EVIDENCE_OUT_OF_CONTEXT | 86 | 2 | 2 |
| 1 | STANDARD_NOT_REFERENCED | 66 | 2 | 2 |
| 1 | WRONG_SUBJECT | 54 | 1 | 1 |
| 1 | DISJUNCTION_WRONG | 43 | 1 | 1 |
| 1 | (6 smaller) | ~60 | 6 | 6 |
| **Phase 1 Total** | | **1,868** | **40** | **40** |
| 2 | Consolidation (multi-batch only) | | | ~5 |
| 3 | Synthesis | | | 1-2 |
| **Grand Total** | | | | **~47** |

## Key Design Decisions

### 1. Stratified Round-Robin Batching (from ChatGPT)

High-volume categories use **round-robin by policy** instead of sorted-then-chunked. This ensures:
- Each batch has diversity across policies
- No single policy dominates a batch
- Rules generalize better instead of being policy-specific

### 2. Per-Rule Provenance with `supporting_fp_indices` (from ChatGPT)

**Bug fix:** Original plan set `example_count=len(fps)` for every rule, making them all look equally frequent.

**Fix:** LLM outputs `supporting_fp_indices` per rule, we compute `example_count=len(supporting_fp_indices)`. This enables:
- Accurate frequency classification
- Rule-to-FP traceability for debugging
- Coverage analysis (which FPs are addressed by which rules)

### 3. Discriminator Fields (from ChatGPT)

Every rule must include **both** blocking and allowing logic:
- `danger_example_pattern`: What the FP "bait" looks like
- `safe_example_pattern`: What a VALID mapping looks like
- `allow_condition`: Positive case - "ALLOW if evidence includes X"

This forces discriminator thinking and prevents mushy "block everything similar" rules.

### 4. Evidence Grounding (from ChatGPT)

Rules include:
- `evidence_triggers`: Quoted spans from `original_evidence_quote` that caused FPs
- `required_evidence`: What must be present for valid mapping

This makes rules auditable and enables deterministic checks.

### 5. Expanded `decision_effect` Enum (from ChatGPT)

Not all avoidance requires hard blocking:
- `blocks_mapping` - Reject the mapping
- `requires_more_evidence` - Ask for additional evidence
- `downgrade_confidence` - Map but with lower confidence

### 6. Explicit Conflict Tracking in Phase 3 (from ChatGPT)

Phase 3 synthesis requires `conflicts_with: [rule_id...]` to make rule collisions explicit instead of silently resolved.

### 7. Pilot Mode (from ChatGPT)

`--pilot` flag runs only 1 batch per root_cause (~14 LLM calls) to validate prompts and output quality before full run.

### 8. Boundary Conditions (from Gemini 3)

Every rule must include a `boundary_condition` field describing when the rule does NOT apply. This prevents over-blocking.

## Output Location

```
files/llm_outputs/fp_rule_aggregator/{timestamp}/
├── run_metadata.json             # Config, stats, reproducibility info
├── failure_avoidance_rules.json  # Final rules
├── universal_rules.md            # Multi-source rules (markdown)
├── rare_rules.md                 # Single-source rules (markdown)
├── lint_report.json              # Rule linter output
├── coverage_report.json          # FP coverage analysis
└── batches/                      # Intermediate outputs
    ├── SEMANTIC_STRETCH_batch_00.json
    ├── SEMANTIC_STRETCH_batch_01.json
    └── ...
```

### `run_metadata.json` Schema

For determinism and repeatability:

```json
{
  "timestamp": "20251230_143022",
  "fp_validation_timestamp": "20251229_221006",
  "config": {
    "model_name": "gemini-3-pro-preview",
    "batch_summarize_temp": 0.7,
    "consolidate_temp": 0.5,
    "synthesize_temp": 0.3,
    "batch_size": 60,
    "max_parallel_batches": 5,
    "pilot_mode": false
  },
  "input_stats": {
    "total_fps_loaded": 1868,
    "fps_by_root_cause": {"SEMANTIC_STRETCH": 926, "...": "..."},
    "total_batches": 40
  },
  "output_stats": {
    "total_rules_generated": 85,
    "universal_rules": 42,
    "rare_rules": 43,
    "lint_errors": 3,
    "fp_coverage_pct": 94.2
  },
  "reproducibility": {
    "git_sha": "abc123def456",
    "git_branch": "plamb/DATA-5698/policy-to-control-exp",
    "prompt_hashes": {
      "batch_summarize_system": "sha256:...",
      "batch_summarize_user": "sha256:...",
      "consolidate_rules_system": "sha256:...",
      "synthesize_rules_system": "sha256:..."
    }
  }
}
```

## Testing Strategy

### 1. Unit Tests
- Config validation, loader, batcher
- Stratified round-robin produces balanced batches
- Index assignment is stable and traceable

### 2. Prompt Validation
- Run `--pilot` mode, manually review outputs
- Check rules have concrete (not vague) conditions

### 3. Rule Linter (`rule_linter.py`)

Automated quality checks on generated rules:

```python
def lint_rules(rules: list[FailureAvoidanceRule]) -> list[LintError]:
    """Validate rule quality."""
    errors = []
    for rule in rules:
        # Check blocking_condition doesn't contain absolute terms without boundary
        if re.search(r'\b(always|never|all|none)\b', rule.blocking_condition, re.I):
            if not rule.boundary_condition or rule.boundary_condition.lower() in ("none", "n/a", ""):
                errors.append(LintError(
                    rule_id=rule.rule_id,
                    error="Absolute blocking_condition without concrete boundary_condition"
                ))

        # Check boundary_condition is concrete (not vague)
        vague_patterns = ["unless relevant", "when appropriate", "as needed", "if applicable"]
        if any(p in rule.boundary_condition.lower() for p in vague_patterns):
            errors.append(LintError(
                rule_id=rule.rule_id,
                error="Vague boundary_condition - must reference evidence or scope explicitly"
            ))

        # Check allow_condition is present and non-trivial
        if not rule.allow_condition or len(rule.allow_condition) < 20:
            errors.append(LintError(
                rule_id=rule.rule_id,
                error="Missing or trivial allow_condition"
            ))

        # Check supporting_fp_indices is non-empty
        if not rule.supporting_fp_indices:
            errors.append(LintError(
                rule_id=rule.rule_id,
                error="No supporting_fp_indices - rule has no provenance"
            ))

    return errors
```

### 4. Regression Check (True Positive Backtest)
- After generating rules, dry-run against known True Positives
- Any rule that triggers on a TP is flagged as too aggressive

### 5. Coverage Analysis (FP Backtest)

Measure how well rules cover the original FP set:

```python
def compute_coverage(rules: list[FailureAvoidanceRule], total_fps: int) -> CoverageReport:
    """Measure FP coverage and rule overlap."""
    covered_indices = set()
    rule_overlap = defaultdict(set)  # index -> set of rule_ids

    for rule in rules:
        for idx in rule.supporting_fp_indices:
            covered_indices.add(idx)
            rule_overlap[idx].add(rule.rule_id)

    coverage_pct = len(covered_indices) / total_fps * 100
    multi_covered = sum(1 for indices in rule_overlap.values() if len(indices) > 1)

    return CoverageReport(
        total_fps=total_fps,
        covered_fps=len(covered_indices),
        coverage_pct=coverage_pct,
        multi_covered_fps=multi_covered,  # FPs addressed by multiple rules
    )
```

This prevents generating 200 rules that all describe the same thing.

## Files to Create

| File | Purpose |
|------|---------|
| `fp_rule_aggregator/__init__.py` | Module exports |
| `fp_rule_aggregator/config.py` | FPRuleConfig dataclass |
| `fp_rule_aggregator/models.py` | FPJudgeOutput, FailureAvoidanceRule, BatchSummary, DecisionEffect, etc. |
| `fp_rule_aggregator/fp_loader.py` | Load and group FP judge outputs |
| `fp_rule_aggregator/batcher.py` | Stratified round-robin batching |
| `fp_rule_aggregator/aggregator.py` | Three-phase LLM orchestration |
| `fp_rule_aggregator/rule_linter.py` | Validate rule quality (lint_rules, compute_coverage) |
| `fp_rule_aggregator/output_writer.py` | Atomic file writes |
| `fp_rule_aggregator/run.py` | CLI entry point |
| `fp_rule_aggregator/prompts/batch_summarize/system` | Phase 1 system prompt |
| `fp_rule_aggregator/prompts/batch_summarize/user` | Phase 1 user template |
| `fp_rule_aggregator/prompts/batch_summarize/response.json` | Phase 1 schema |
| `fp_rule_aggregator/prompts/consolidate_rules/system` | Phase 2 system prompt |
| `fp_rule_aggregator/prompts/consolidate_rules/user` | Phase 2 user template |
| `fp_rule_aggregator/prompts/consolidate_rules/response.json` | Phase 2 schema |
| `fp_rule_aggregator/prompts/synthesize_rules/system` | Phase 3 system prompt |
| `fp_rule_aggregator/prompts/synthesize_rules/user` | Phase 3 user template |
| `fp_rule_aggregator/prompts/synthesize_rules/response.json` | Phase 3 schema |

## CLI Usage

```bash
# Full run
uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006

# Pilot mode (validate prompts first)
uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006 \
    --pilot

# Skip synthesis (Phase 1+2 only)
uv run python -m ai_services.scripts.experiments.control_detection.fp_rule_aggregator.run \
    --fp-validation-timestamp 20251229_221006 \
    --skip-synthesis
```
