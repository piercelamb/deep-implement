# Research: MapReduce for LLM False Negative Analysis

## Objective

Investigate whether the existing MapReduce approach in `reason_aggregator/` can be reused to distill "failure avoidance rules" from LLM_WRONG entries in `detailed_results.json`.

## Key Finding: High Reusability (85%+)

The existing MapReduce framework is **domain-agnostic** and can be reused with minimal changes. The core aggregation loop, binary tree reduction, parallelism, and resume logic remain unchanged.

## What Changes Are Needed

| Component | Reuse | Change Needed |
|-----------|-------|---------------|
| `aggregator.py` core loop | 100% | None |
| `models.py` data structures | 95% | Minor field additions |
| `config.py` | 90% | New paths/config |
| `output_writer.py` | 80% | Formatting tweaks |
| `input_loader.py` | **0%** | New loader for LLM_WRONG data |
| `prompts/` | **0%** | All new prompts |
| `run.py` | 80% | CLI flags for mode selection |

## Approach Options

### Option A: Branch in Existing Code (Minimal Changes)

Add a `--mode` flag to `run.py` that switches between:
- `mapping-reasons` (current behavior)
- `false-negatives` (new behavior)

The mode would control:
1. Which input loader to use
2. Which prompt directory to use
3. Output formatting

**Pros:** Single codebase, shared improvements
**Cons:** Complexity in run.py

### Option B: Parallel Module (Copy + Modify)

Create `false_negative_aggregator/` as sibling to `reason_aggregator/`:
- Copy aggregator.py (unchanged)
- New input_loader.py
- New prompts/
- New run.py

**Pros:** Clean separation, no risk to existing code
**Cons:** Code duplication, parallel maintenance

### Recommendation: Option A (Branch)

The existing code is well-structured for extension. Key reasons:
1. `PromptBuilder` already routes based on input type
2. `ReasonAggregator` accepts config for all paths
3. Input loaders share the same interface (`list[PolicyReasons]`)

---

## Data Structure Mapping

### Input: LLM_WRONG Entry

```json
{
  "policy_name": "Asset Management Policy",
  "control_id": "DCF-149",
  "control_name": "Removable Media Device Encryption",
  "control_description": "The Organization encrypts removable media...",
  "verdict": "LLM_WRONG",
  "confidence": "high",
  "reasoning": "The policy contains a binding mandate on Page 1...",
  "evidence_for_gt": "Temporary or permanent copies of information will be...",
  "dispute_reason": "NO_MATCH",
  "original_decision": "NO_MATCH",
  "original_reasoning": "The policy uses non-binding language ('should')..."
}
```

### Transformed to PolicyReasons-like Structure

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class FalseNegativeReasons:
    """Failure analysis extracted from LLM_WRONG entries."""

    policy_name: str
    control_id: str
    control_name: str

    # Core fields for aggregation (analogous to generalized_reasons)
    failure_analysis: str           # The `reasoning` field
    evidence_missed: str            # The `evidence_for_gt` field
    original_error: str             # The `original_reasoning` field
    dispute_category: str           # NOT_SENT | NO_MATCH | PARTIAL
```

---

## LLM_WRONG Data Statistics

From `detailed_results.json`:
- **Total LLM_WRONG entries:** 146 (out of 247)
- **Confidence distribution:** 144 high, 2 medium
- **Unique policies:** 29
- **Unique controls:** 122

### Dispute Reason Breakdown

| Category | Count | Meaning | Has Original Decision |
|----------|-------|---------|----------------------|
| NOT_SENT | 77 | Control never evaluated | No (null) |
| NO_MATCH | 32 | LLM said NO_MATCH but GT valid | Yes |
| PARTIAL | 37 | LLM said PARTIAL, GT reasoning differs | Yes |

**Key Insight:** NOT_SENT entries (53%) have no original reasoning to compare against. These represent blind spots where the retrieval system didn't even send the control to the LLM.

---

## Prompt Design for False Negative Analysis

### Round 1: Extract Failure Patterns

**Goal:** Transform failure analyses into generalizable "anti-patterns" (what causes LLM misses)

**System Prompt Sketch:**
```
You are a GRC Auditor analyzing LLM false negatives in control-to-policy mapping.

Your task: Extract FAILURE AVOIDANCE RULES - patterns an LLM can learn to avoid
making these same mistakes.

For each false negative case:
1. What did the LLM MISS in the policy text?
2. What linguistic/structural pattern led to the miss?
3. What heuristic would have prevented this error?

Focus on GENERALIZABLE patterns, not specific policy/control pairs.
```

**Output Schema (Round 1):**
```json
{
  "failure_avoidance_rules": [
    {
      "rule_name": "Binding Preamble Inheritance",
      "failure_pattern": "LLM treats 'should' as non-binding when it follows a binding preamble",
      "recovery_heuristic": "Check if soft language appears under a binding header like 'the following steps will be taken'",
      "evidence_types": ["explicit_mandate"],
      "dispute_categories": ["NO_MATCH"],
      "observed_in": ["source_1"]
    }
  ]
}
```

### Round 2+: Consolidate Failure Patterns

Same merge logic as existing consolidation:
- Merge patterns with same failure_pattern concept
- Track which dispute categories each pattern addresses
- Preserve specificity over generality

---

## Implementation Plan (TDD Approach)

### TDD Cycle 1: FalseNegativeLoader

**Test**: `tests/scripts/experiments/control_detection/reason_aggregator/test_false_negative_loader.py`

```python
import json
import pytest
from pathlib import Path

from ai_services.scripts.experiments.control_detection.reason_aggregator.false_negative_loader import (
    FalseNegativeLoader,
)
from ai_services.scripts.experiments.control_detection.reason_aggregator.input_loader import (
    PolicyReasons,
)


class TestFalseNegativeLoader:
    @pytest.fixture
    def sample_results(self, tmp_path: Path) -> Path:
        """Create a sample detailed_results.json file."""
        data = {
            "results": [
                {
                    "policy_name": "Asset Management Policy",
                    "control_id": "DCF-149",
                    "control_name": "Removable Media Encryption",
                    "verdict": "LLM_WRONG",
                    "confidence": "high",
                    "reasoning": "The policy contains binding mandate...",
                    "evidence_for_gt": "Copies will be protected...",
                    "dispute_reason": "NO_MATCH",
                    "original_decision": "NO_MATCH",
                    "original_reasoning": "Non-binding language used...",
                },
                {
                    "policy_name": "Asset Management Policy",
                    "control_id": "DCF-821",
                    "control_name": "Media Ownership",
                    "verdict": "LLM_WRONG",
                    "confidence": "high",
                    "reasoning": "Policy mandates owner assignment...",
                    "evidence_for_gt": "Owner will be assigned...",
                    "dispute_reason": "PARTIAL",
                    "original_decision": "PARTIAL",
                    "original_reasoning": "Missing explicit prohibition...",
                },
                {
                    "policy_name": "Data Protection Policy",
                    "control_id": "DCF-107",
                    "control_name": "Data Classification",
                    "verdict": "LLM_WRONG",
                    "confidence": "high",
                    "reasoning": "Classification levels defined...",
                    "evidence_for_gt": "Data shall be classified...",
                    "dispute_reason": "NO_MATCH",
                    "original_decision": "NO_MATCH",
                    "original_reasoning": "No explicit classification...",
                },
                {
                    "policy_name": "Access Control Policy",
                    "control_id": "DCF-51",
                    "control_name": "Automated Updates",
                    "verdict": "LLM_WRONG",
                    "confidence": "high",
                    "reasoning": "Never sent to LLM...",
                    "evidence_for_gt": "Updates will be automated...",
                    "dispute_reason": "NOT_SENT",
                    "original_decision": None,
                    "original_reasoning": None,
                },
                {
                    "policy_name": "Access Control Policy",
                    "control_id": "DCF-606",
                    "control_name": "Device Auth",
                    "verdict": "GT_WRONG",  # Should be filtered out
                    "confidence": "high",
                    "reasoning": "GT is incorrect...",
                    "evidence_for_gt": "",
                    "dispute_reason": "NO_MATCH",
                    "original_decision": "NO_MATCH",
                    "original_reasoning": "Correctly rejected...",
                },
            ]
        }
        results_file = tmp_path / "detailed_results.json"
        results_file.write_text(json.dumps(data))
        return results_file

    def test_filters_to_llm_wrong_only(self, sample_results: Path):
        """Should only load entries with verdict='LLM_WRONG'."""
        loader = FalseNegativeLoader(results_file=sample_results)
        policies = loader.load_all()

        # GT_WRONG entry should be excluded
        all_reasons = []
        for p in policies:
            all_reasons.extend(p.generalized_reasons)

        assert "GT is incorrect" not in str(all_reasons)
        assert "Correctly rejected" not in str(all_reasons)

    def test_filters_out_not_sent(self, sample_results: Path):
        """Should exclude NOT_SENT entries (no original reasoning)."""
        loader = FalseNegativeLoader(results_file=sample_results)
        policies = loader.load_all()

        all_reasons = []
        for p in policies:
            all_reasons.extend(p.generalized_reasons)

        # NOT_SENT entry should be excluded
        assert "Never sent to LLM" not in str(all_reasons)
        # Access Control Policy should not appear (only had NOT_SENT + GT_WRONG)
        policy_names = [p.policy_name for p in policies]
        assert "Access Control Policy" not in policy_names

    def test_groups_by_policy(self, sample_results: Path):
        """Should group entries by policy_name."""
        loader = FalseNegativeLoader(results_file=sample_results)
        policies = loader.load_all()

        policy_names = [p.policy_name for p in policies]
        assert "Asset Management Policy" in policy_names
        assert "Data Protection Policy" in policy_names

        # Asset Management should have 2 entries (NO_MATCH + PARTIAL)
        asset_policy = next(p for p in policies if p.policy_name == "Asset Management Policy")
        assert len(asset_policy.generalized_reasons) == 2

    def test_returns_policy_reasons_type(self, sample_results: Path):
        """Should return list of PolicyReasons for compatibility."""
        loader = FalseNegativeLoader(results_file=sample_results)
        policies = loader.load_all()

        assert all(isinstance(p, PolicyReasons) for p in policies)

    def test_formats_failure_text_with_all_fields(self, sample_results: Path):
        """Should include dispute reason, control info, reasoning, and evidence."""
        loader = FalseNegativeLoader(results_file=sample_results)
        policies = loader.load_all()

        asset_policy = next(p for p in policies if p.policy_name == "Asset Management Policy")
        first_reason = asset_policy.generalized_reasons[0]

        assert "Dispute:" in first_reason
        assert "Control:" in first_reason
        assert "Failure Analysis:" in first_reason
        assert "Original LLM Error:" in first_reason
        assert "Missed Evidence:" in first_reason

    def test_shuffle_with_seed_is_reproducible(self, sample_results: Path):
        """Same seed should produce same order."""
        loader = FalseNegativeLoader(results_file=sample_results)

        policies1 = loader.load_all(shuffle=True, seed=42)
        policies2 = loader.load_all(shuffle=True, seed=42)
        policies3 = loader.load_all(shuffle=True, seed=123)

        names1 = [p.policy_name for p in policies1]
        names2 = [p.policy_name for p in policies2]
        names3 = [p.policy_name for p in policies3]

        assert names1 == names2  # Same seed = same order
        # Different seed may produce different order (if >1 policy)

    def test_handles_missing_optional_fields(self, tmp_path: Path):
        """Should handle entries without original_reasoning or evidence_for_gt."""
        data = {
            "results": [
                {
                    "policy_name": "Test Policy",
                    "control_id": "DCF-1",
                    "control_name": "Test Control",
                    "verdict": "LLM_WRONG",
                    "confidence": "high",
                    "reasoning": "Some analysis...",
                    "evidence_for_gt": "",  # Empty
                    "dispute_reason": "NO_MATCH",
                    "original_decision": "NO_MATCH",
                    "original_reasoning": "",  # Empty
                },
            ]
        }
        results_file = tmp_path / "results.json"
        results_file.write_text(json.dumps(data))

        loader = FalseNegativeLoader(results_file=results_file)
        policies = loader.load_all()

        assert len(policies) == 1
        # Should not crash, empty fields just omitted from text

    def test_load_count(self, sample_results: Path):
        """Should return correct count statistics."""
        loader = FalseNegativeLoader(results_file=sample_results)
        stats = loader.get_statistics()

        assert stats["total_llm_wrong"] == 4  # All LLM_WRONG entries
        assert stats["filtered_count"] == 3  # NO_MATCH + PARTIAL only
        assert stats["no_match_count"] == 2
        assert stats["partial_count"] == 1
        assert stats["not_sent_excluded"] == 1
        assert stats["unique_policies"] == 2
```

**Implementation**: `reason_aggregator/false_negative_loader.py`

```python
"""Loader for LLM false negative entries from ground truth validation results."""

import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .input_loader import PolicyReasons


@dataclass(frozen=True, slots=True, kw_only=True)
class FalseNegativeStats:
    """Statistics about loaded false negative data."""

    total_llm_wrong: int
    filtered_count: int
    no_match_count: int
    partial_count: int
    not_sent_excluded: int
    unique_policies: int


class FalseNegativeLoader:
    """Loads LLM_WRONG entries from detailed_results.json for aggregation."""

    # Only include entries where we have original reasoning to analyze
    INCLUDED_DISPUTE_REASONS: frozenset[str] = frozenset({"NO_MATCH", "PARTIAL"})

    def __init__(self, results_file: Path) -> None:
        """
        Initialize the loader.

        Args:
            results_file: Path to detailed_results.json from GT validation

        """
        self.results_file = results_file
        self._cached_data: dict[str, Any] | None = None

    def _load_data(self) -> dict[str, Any]:
        """Load and cache JSON data."""
        if self._cached_data is None:
            self._cached_data = json.loads(self.results_file.read_text())
        return self._cached_data

    def _get_filtered_entries(self) -> list[dict[str, Any]]:
        """Get LLM_WRONG entries with NO_MATCH or PARTIAL dispute reasons."""
        data = self._load_data()
        return [
            r
            for r in data["results"]
            if r["verdict"] == "LLM_WRONG"
            and r.get("dispute_reason") in self.INCLUDED_DISPUTE_REASONS
        ]

    def load_all(
        self, shuffle: bool = False, seed: int | None = None
    ) -> list[PolicyReasons]:
        """
        Load all LLM_WRONG entries, grouped by policy.

        Args:
            shuffle: Whether to randomize the order of policies
            seed: Random seed for reproducible shuffling (None = random)

        Returns:
            List of PolicyReasons, one per policy with false negatives

        """
        entries = self._get_filtered_entries()

        # Group by policy
        by_policy: dict[str, list[str]] = defaultdict(list)
        for entry in entries:
            failure_text = self._format_failure_text(entry)
            by_policy[entry["policy_name"]].append(failure_text)

        # Convert to PolicyReasons (reuse existing type for compatibility)
        policies = [
            PolicyReasons(
                policy_name=name,
                policy_dir=Path(),  # Not used for this mode
                generalized_reasons=tuple(reasons),
            )
            for name, reasons in sorted(by_policy.items())
        ]

        if shuffle:
            rng = random.Random(seed)
            rng.shuffle(policies)

        return policies

    def _format_failure_text(self, entry: dict[str, Any]) -> str:
        """
        Format a single LLM_WRONG entry as text for aggregation.

        Includes all relevant context for the LLM to identify failure patterns.
        """
        parts = [
            f"Dispute: {entry['dispute_reason']}",
            f"Control: {entry['control_name']} ({entry['control_id']})",
            f"Failure Analysis: {entry['reasoning']}",
        ]

        if entry.get("original_reasoning"):
            parts.append(f"Original LLM Error: {entry['original_reasoning']}")

        if entry.get("evidence_for_gt"):
            parts.append(f"Missed Evidence: {entry['evidence_for_gt']}")

        return "\n".join(parts)

    def get_statistics(self) -> dict[str, int]:
        """Get statistics about the loaded data."""
        data = self._load_data()
        all_wrong = [r for r in data["results"] if r["verdict"] == "LLM_WRONG"]
        filtered = self._get_filtered_entries()

        no_match = sum(1 for e in filtered if e["dispute_reason"] == "NO_MATCH")
        partial = sum(1 for e in filtered if e["dispute_reason"] == "PARTIAL")
        not_sent = sum(
            1 for e in all_wrong if e.get("dispute_reason") == "NOT_SENT"
        )

        unique_policies = len({e["policy_name"] for e in filtered})

        return {
            "total_llm_wrong": len(all_wrong),
            "filtered_count": len(filtered),
            "no_match_count": no_match,
            "partial_count": partial,
            "not_sent_excluded": not_sent,
            "unique_policies": unique_policies,
        }
```

---

### TDD Cycle 2: Config Extension

**Test**: `tests/scripts/experiments/control_detection/reason_aggregator/test_config.py` (additions)

```python
class TestAggregatorConfigFalseNegativeMode:
    def test_default_mode_is_mapping_reasons(self):
        config = AggregatorConfig()
        assert config.mode == "mapping-reasons"

    def test_mode_can_be_set_to_false_negatives(self):
        config = AggregatorConfig(mode="false-negatives")
        assert config.mode == "false-negatives"

    def test_false_negative_paths_exist_in_config(self):
        config = AggregatorConfig(mode="false-negatives")
        # Paths should be defined (existence checked at runtime)
        assert config.false_negative_results_file is not None
        assert config.false_negative_prompts_dir is not None
        assert config.false_negative_consolidation_prompts_dir is not None

    def test_invalid_mode_raises_error(self):
        with pytest.raises((ValueError, TypeError)):
            AggregatorConfig(mode="invalid-mode")
```

**Implementation**: Add to `reason_aggregator/config.py`

```python
from typing import Literal

@dataclass(frozen=True, slots=True, kw_only=True)
class AggregatorConfig:
    # ... existing fields ...

    # Mode selection
    mode: Literal["mapping-reasons", "false-negatives"] = "mapping-reasons"

    # False negative mode paths
    false_negative_results_file: Path = (
        FILES_DIR / "llm_outputs" / "gt_validation" / "20251227_145838" / "detailed_results.json"
    )
    false_negative_prompts_dir: Path = SCRIPT_DIR / "prompts" / "false_negative_analysis"
    false_negative_consolidation_prompts_dir: Path = (
        SCRIPT_DIR / "prompts" / "consolidate_failure_patterns"
    )
    false_negative_output_dir: Path = EXPERIMENTS_DIR / "failure_patterns"
```

---

### TDD Cycle 3: Aggregator Mode Branching

**Test**: `tests/scripts/experiments/control_detection/reason_aggregator/test_aggregator_mode.py`

```python
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_services.scripts.experiments.control_detection.reason_aggregator.aggregator import (
    ReasonAggregator,
)
from ai_services.scripts.experiments.control_detection.reason_aggregator.config import (
    AggregatorConfig,
)
from ai_services.scripts.experiments.control_detection.reason_aggregator.input_loader import (
    ReasonFileLoader,
)
from ai_services.scripts.experiments.control_detection.reason_aggregator.false_negative_loader import (
    FalseNegativeLoader,
)


class TestAggregatorModeSelection:
    def test_mapping_reasons_mode_uses_reason_file_loader(self):
        config = AggregatorConfig(mode="mapping-reasons")
        aggregator = ReasonAggregator(config=config, client=MagicMock())

        loader = aggregator._get_input_loader()
        assert isinstance(loader, ReasonFileLoader)

    def test_false_negatives_mode_uses_false_negative_loader(self):
        config = AggregatorConfig(mode="false-negatives")
        aggregator = ReasonAggregator(config=config, client=MagicMock())

        loader = aggregator._get_input_loader()
        assert isinstance(loader, FalseNegativeLoader)

    def test_mapping_reasons_mode_uses_aggregate_reasons_prompts(self):
        config = AggregatorConfig(mode="mapping-reasons")
        aggregator = ReasonAggregator(config=config, client=MagicMock())

        prompts_dir = aggregator._get_round1_prompts_dir()
        assert "aggregate_reasons" in str(prompts_dir)

    def test_false_negatives_mode_uses_false_negative_prompts(self):
        config = AggregatorConfig(mode="false-negatives")
        aggregator = ReasonAggregator(config=config, client=MagicMock())

        prompts_dir = aggregator._get_round1_prompts_dir()
        assert "false_negative_analysis" in str(prompts_dir)

    def test_false_negatives_consolidation_uses_correct_prompts(self):
        config = AggregatorConfig(mode="false-negatives")
        aggregator = ReasonAggregator(config=config, client=MagicMock())

        prompts_dir = aggregator._get_consolidation_prompts_dir()
        assert "consolidate_failure_patterns" in str(prompts_dir)

    def test_false_negatives_uses_correct_output_dir(self):
        config = AggregatorConfig(mode="false-negatives")
        aggregator = ReasonAggregator(config=config, client=MagicMock())

        output_dir = aggregator._get_output_dir()
        assert "failure_patterns" in str(output_dir)
```

**Implementation**: Add to `reason_aggregator/aggregator.py`

```python
def _get_input_loader(self) -> ReasonFileLoader | FalseNegativeLoader:
    """Get the appropriate input loader based on mode."""
    if self.config.mode == "false-negatives":
        from .false_negative_loader import FalseNegativeLoader
        return FalseNegativeLoader(self.config.false_negative_results_file)
    return ReasonFileLoader(self.config.input_dir)

def _get_round1_prompts_dir(self) -> Path:
    """Get prompts directory for round 1 based on mode."""
    if self.config.mode == "false-negatives":
        return self.config.false_negative_prompts_dir
    return self.config.prompts_dir

def _get_consolidation_prompts_dir(self) -> Path:
    """Get prompts directory for consolidation rounds based on mode."""
    if self.config.mode == "false-negatives":
        return self.config.false_negative_consolidation_prompts_dir
    return self.config.consolidation_prompts_dir

def _get_output_dir(self) -> Path:
    """Get output directory based on mode."""
    if self.config.mode == "false-negatives":
        return self.config.false_negative_output_dir
    return self.config.output_dir
```

---

### TDD Cycle 4: CLI Mode Flag

**Test**: `tests/scripts/experiments/control_detection/reason_aggregator/test_cli.py` (additions)

```python
from typer.testing import CliRunner
from ai_services.scripts.experiments.control_detection.reason_aggregator.run import app

runner = CliRunner()


class TestCLIModeFlag:
    def test_default_mode_is_mapping_reasons(self, mock_aggregator):
        result = runner.invoke(app, ["--dry-run"])
        assert result.exit_code == 0
        # Check that mapping-reasons mode was used (via mock inspection)

    def test_mode_flag_accepts_false_negatives(self, mock_aggregator):
        result = runner.invoke(app, ["--mode", "false-negatives", "--dry-run"])
        assert result.exit_code == 0

    def test_short_mode_flag_works(self, mock_aggregator):
        result = runner.invoke(app, ["-m", "false-negatives", "--dry-run"])
        assert result.exit_code == 0

    def test_invalid_mode_shows_error(self):
        result = runner.invoke(app, ["--mode", "invalid"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid" in result.output.lower()

    def test_dry_run_shows_mode_info(self, mock_aggregator):
        result = runner.invoke(app, ["--mode", "false-negatives", "--dry-run"])
        assert "false-negatives" in result.output or "false negatives" in result.output.lower()
```

**Implementation**: Add to `reason_aggregator/run.py`

```python
from typing import Literal

@app.command()
def main(
    # ... existing options ...
    mode: str = typer.Option(
        "mapping-reasons",
        "--mode",
        "-m",
        help="Aggregation mode: 'mapping-reasons' (default) or 'false-negatives'",
        callback=lambda v: v if v in ("mapping-reasons", "false-negatives") else typer.BadParameter(f"Invalid mode: {v}"),
    ),
):
    """Aggregate control mapping reasons or false negative patterns."""
    config = AggregatorConfig(
        mode=mode,
        max_parallel_pairs=parallelism,
        max_rounds=max_rounds,
        shuffle_seed=seed,
    )

    if dry_run:
        _show_dry_run_info(config, mode)
        return

    # ... rest of implementation
```

---

### TDD Cycle 5: Prompts (Integration Test)

**Test**: `tests/scripts/experiments/control_detection/reason_aggregator/test_prompts_false_negative.py`

```python
import json
import pytest
from pathlib import Path


class TestFalseNegativePrompts:
    @pytest.fixture
    def prompts_dir(self) -> Path:
        return Path(__file__).parents[5] / "ai_services" / "scripts" / "experiments" / "control_detection" / "reason_aggregator" / "prompts" / "false_negative_analysis"

    @pytest.fixture
    def consolidation_prompts_dir(self) -> Path:
        return Path(__file__).parents[5] / "ai_services" / "scripts" / "experiments" / "control_detection" / "reason_aggregator" / "prompts" / "consolidate_failure_patterns"

    def test_round1_system_prompt_exists(self, prompts_dir: Path):
        system_file = prompts_dir / "system"
        assert system_file.exists(), f"Missing {system_file}"
        content = system_file.read_text()
        assert len(content) > 100, "System prompt seems too short"
        assert "failure" in content.lower() or "false negative" in content.lower()

    def test_round1_user_prompt_has_placeholders(self, prompts_dir: Path):
        user_file = prompts_dir / "user"
        assert user_file.exists(), f"Missing {user_file}"
        content = user_file.read_text()
        assert "{SOURCE_1_NAME}" in content
        assert "{SOURCE_1_REASONS}" in content
        assert "{SOURCE_2_NAME}" in content
        assert "{SOURCE_2_REASONS}" in content

    def test_round1_response_schema_is_valid_json(self, prompts_dir: Path):
        schema_file = prompts_dir / "response.json"
        assert schema_file.exists(), f"Missing {schema_file}"
        schema = json.loads(schema_file.read_text())
        assert "type" in schema
        assert schema["type"] == "object"
        assert "properties" in schema
        # Should have failure_avoidance_rules array
        assert "failure_avoidance_rules" in schema["properties"] or "decision_rules" in schema["properties"]

    def test_consolidation_system_prompt_exists(self, consolidation_prompts_dir: Path):
        system_file = consolidation_prompts_dir / "system"
        assert system_file.exists(), f"Missing {system_file}"
        content = system_file.read_text()
        assert len(content) > 100

    def test_consolidation_user_prompt_has_indexed_placeholders(self, consolidation_prompts_dir: Path):
        user_file = consolidation_prompts_dir / "user"
        assert user_file.exists(), f"Missing {user_file}"
        content = user_file.read_text()
        # Should reference indexed patterns from previous rounds
        assert "SOURCE_1" in content or "UNIVERSAL" in content or "RARE" in content

    def test_consolidation_response_schema_is_valid_json(self, consolidation_prompts_dir: Path):
        schema_file = consolidation_prompts_dir / "response.json"
        assert schema_file.exists(), f"Missing {schema_file}"
        schema = json.loads(schema_file.read_text())
        assert "type" in schema
```

**Implementation**: Create prompt files (6 files total)

## File Changes Summary

| File | Lines Changed | Description |
|------|---------------|-------------|
| `test_false_negative_loader.py` | ~150 | **NEW** - Tests for loader |
| `false_negative_loader.py` | ~80 | **NEW** - Load LLM_WRONG data |
| `test_config.py` | ~20 | Add tests for mode config |
| `config.py` | ~15 | Add mode and paths |
| `test_aggregator_mode.py` | ~50 | **NEW** - Tests for mode branching |
| `aggregator.py` | ~30 | Mode-aware loader/prompt selection |
| `test_cli.py` | ~30 | Add tests for CLI mode flag |
| `run.py` | ~15 | CLI mode flag |
| `test_prompts_false_negative.py` | ~50 | **NEW** - Prompt validation tests |
| `prompts/false_negative_analysis/*` | 3 files | **NEW** - Round 1 prompts |
| `prompts/consolidate_failure_patterns/*` | 3 files | **NEW** - Round 2+ prompts |

**Total:** ~300 lines of tests + ~140 lines of implementation + 6 prompt files

---

## Expected Output

### Final Output: `failure_avoidance_rules.md`

```markdown
# LLM Failure Avoidance Rules

Distilled from 146 false negative cases across 29 policies.

## Rule 1: Binding Preamble Inheritance

**Failure Pattern:** LLM incorrectly dismisses requirements using soft language
("should", "may") when they appear under a binding preamble ("the following
steps will be taken").

**Recovery Heuristic:** Check section headers for binding language before
evaluating individual bullets. Binding preambles cascade to nested items.

**Evidence Types:** explicit_mandate
**Dispute Categories:** NO_MATCH, PARTIAL
**Frequency:** Very Common

---

## Rule 2: Implicit Scope Inclusion

**Failure Pattern:** LLM requires explicit terminology match (e.g., "removable
media") when the policy uses broader terms (e.g., "assets") that implicitly
include the control's subject.

**Recovery Heuristic:** Identify the semantic category of the control's subject.
Check if policy covers the parent category.

**Evidence Types:** scope_definition
**Dispute Categories:** NO_MATCH
**Frequency:** Common

---
...
```

---

## Confirmed Decisions

1. **Dispute Category Filtering:** Aggregate NO_MATCH + PARTIAL only (69 entries). Ignore NOT_SENT (77 entries) since they lack original reasoning to compare against.

2. **Implementation Approach:** Branch in existing code with `--mode` flag. ~100 lines Python + 6 prompt files.

3. **Prompt Review:** Draft prompts during implementation, iterate after seeing results.

---

## Implementation Order (TDD)

### Cycle 1: FalseNegativeLoader
1. Write `test_false_negative_loader.py` tests
2. Run tests (all fail - RED)
3. Implement `false_negative_loader.py`
4. Run tests (all pass - GREEN)

### Cycle 2: Config Extension
1. Add tests to `test_config.py` for mode handling
2. Run tests (fail - RED)
3. Add mode fields to `config.py`
4. Run tests (pass - GREEN)

### Cycle 3: Aggregator Mode Branching
1. Write `test_aggregator_mode.py` tests
2. Run tests (fail - RED)
3. Add mode branching methods to `aggregator.py`
4. Run tests (pass - GREEN)

### Cycle 4: CLI Mode Flag
1. Add tests to `test_cli.py` for mode flag
2. Run tests (fail - RED)
3. Add `--mode` flag to `run.py`
4. Run tests (pass - GREEN)

### Cycle 5: Prompts
1. Write `test_prompts_false_negative.py` tests
2. Run tests (fail - RED)
3. Create 6 prompt files
4. Run tests (pass - GREEN)

### Integration Testing
1. Run dry-run: `--mode false-negatives --dry-run`
2. Run single pair test
3. Run full aggregation
