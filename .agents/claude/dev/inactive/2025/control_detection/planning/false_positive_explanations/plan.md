# Plan: False Positive Analysis (LLM-as-Judge for FPs)

## Background: The Control-to-Policy Mapping Problem

### What We're Building

We're developing an LLM-based system to automatically map **security controls** (DCF controls from Drata's compliance framework) to **policy documents** (customer-uploaded PDFs). The goal is to determine which controls a given policy addresses.

**Example:** A "Data Protection Policy" PDF might address controls like:
- DCF-107: "Organization encrypts data at rest"
- DCF-108: "Organization encrypts data in transit"

But it should NOT map to unrelated controls like:
- DCF-421: "Organization synchronizes system clocks"

### The Recall vs Precision Tradeoff

In **Experiment 4**, our prompts were too strict — the LLM was rejecting valid mappings (false negatives):
- Recall: 86.1% (missing 14% of valid mappings)
- Precision: 18.3%
- False Negatives: 81

To fix this, we created **Experiment 5** with "Interpretive Rules" (IR-1 to IR-10) that tell the LLM when to be more lenient:

| Rule | Name | What It Does |
|------|------|--------------|
| IR-1 | Hierarchical Scope | If control targets "servers" and policy covers "IT systems", accept |
| IR-2 | Tech→Abstract | If control asks for "AES-256" and policy says "encryption", accept |
| IR-3 | Semantic Equivalence | Different words but same functional outcome |
| IR-4 | Governance→Procedure | Policy says What/Who without How/When — still accept |
| IR-8 | Binding Inheritance | Section header has "shall" — applies to all list items below |
| ... | ... | ... |

### The Problem: Precision Collapsed

Experiment 5 achieved its goal — **recall jumped to 94%** (false negatives dropped 57%). But the rules were applied too liberally:

| Metric | Exp 4 | Exp 5 | Change |
|--------|-------|-------|--------|
| Recall | 86.1% | 94.0% | +7.9% ✅ |
| Precision | 18.3% | 9.4% | -8.9% ❌ |
| False Positives | 2,240 | 4,104 | +83% ❌ |

**We now have ~4,104 false positives** — controls the LLM incorrectly said were MAPPED.

### Why We Need False Positive Analysis

To improve the prompts, we need to understand what the LLM is thinking when it produces false positives and try to surface why a false positive is actually a false positive so we can learn rules to avoid surfacing it again

1. For each false positive, show the judge:
   - The control that was incorrectly mapped
   - The LLM's original reasoning (including which IR rules it cited)
   - The policy document
   - The original prompt rules

2. Ask the judge: "Why was this mapping incorrect?"

3. Aggregate patterns to identify:
   - Rules that cause the most FPs
   - Common failure patterns (e.g., "IR-2 is being applied to controls that require specific technical details")
   - How to tighten the rules without losing recall

**This analysis will inform the next iteration of prompts** — adding specificity constraints to the rules that are being over-applied.

Note that the same controls can be a false positive across many documents

---

## Summary

Create a false positive analysis system that mirrors `ground_truth_validation` but for analyzing **MAPPED controls that are NOT in ground truth**. The judge will explain why the LLM incorrectly mapped each control and which Interpretive Rules (IR-1 to IR-10) were misapplied.

**Scope:** Analyze all ~1,878 FP **patterns** (deduplicated from 4,104 instances)

**Key Innovations:**
1. **Pattern deduplication** — Group redundant FPs by `(control_id, IR_rule)` for 2.2x cost reduction
2. **Original prompt in cache** — Include the control mapping system prompt so the judge can see exactly what rules the LLM was following

> **Note (Post-Implementation):** Original plan expected 10-17x reduction using `(control_id, IR_rule, evidence_hash)`.
> Testing on real data showed evidence quotes are unique per policy document, yielding only 1.0x reduction.
> Changed signature to `(control_id, IR_rule)` which achieves 2.2x reduction (4,104 → 1,878 patterns).
> See [deduplication_analysis.md](./deduplication_analysis.md) for full analysis.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  False Positive Analysis Pipeline                                │
├─────────────────────────────────────────────────────────────────┤
│  Phase 0: Distribution Analysis (Zero Cost)                      │
│     - Parse batch files, output distribution CSVs                │
│     - Understand which controls/policies/IR rules dominate       │
│                                                                  │
│  Phase 1: Pattern Deduplication (Critical)                       │
│     - Group 4,104 FP instances → ~1,878 unique patterns          │
│     - Signature: (control_id, IR_rule) — 2.2x reduction          │
│                                                                  │
│  Phase 2: Judge Patterns                                         │
│     - Analyze ALL 1,878 patterns (~$10-20 with Flash-tier model) │
│     - Sampling available if cost is a concern (see sampling_v2)  │
│     - Upload to context cache per policy:                        │
│       • Policy PDF                                               │
│       • Original mapping system prompt (control_centric_*)       │
│       • FP judge system prompt                                   │
│     - Judge asks: "Why was this mapping incorrect?"              │
│                                                                  │
│  Phase 3: Generate Outputs                                       │
│     - detailed_results.json                                      │
│     - fp_analysis_summary.json                                   │
│     - CSVs by error category                                     │
└─────────────────────────────────────────────────────────────────┘
```

> **IMPORTANT**: See [sampling_recommendation_v2.md](./sampling_recommendation_v2.md) for the updated sampling strategy.
> Pattern deduplication by `(control_id, IR_rule)` achieves 2.2x reduction (4,104 → 1,878 patterns).
> At ~$10-20 total cost with Flash-tier models, we recommend analyzing ALL patterns.

## Testing Approach: TDD

This implementation follows **Test-Driven Development (TDD)**:

```
┌─────────────────────────────────────────────────────────────────┐
│  TDD Cycle (Red → Green → Refactor)                             │
├─────────────────────────────────────────────────────────────────┤
│  1. RED:    Write failing tests that define expected behavior   │
│  2. GREEN:  Write minimal code to make tests pass               │
│  3. REFACTOR: Clean up while keeping tests green                │
└─────────────────────────────────────────────────────────────────┘
```

### Test Organization

```
tests/scripts/experiments/control_detection/false_positive_validation/
├── __init__.py
├── conftest.py                    # Shared fixtures (sample FPs, patterns, etc.)
├── test_fp_models.py              # Model validation, serialization
├── test_fp_collector.py           # Collection logic
├── test_analyze_fp_distribution.py # Distribution analysis
├── test_deduplicate_fps.py        # Pattern deduplication
├── test_fp_sampler.py             # Sampling algorithms
├── test_fp_judge_decider.py       # Judge integration (mocked LLM)
├── test_fp_output_generator.py    # Output file generation
└── test_run_fp_validation.py      # CLI integration tests
```

### Test Fixtures (`conftest.py`)

```python
import pytest
from false_positive_validation.fp_models import FalsePositive, FPPattern, FPJudgeResult

@pytest.fixture
def sample_false_positive() -> FalsePositive:
    """A realistic FP for testing."""
    return FalsePositive(
        control_id="DCF-107",
        control_name="Data Encryption at Rest",
        control_description="Organization encrypts data at rest using AES-256",
        policy_name="Information Security Policy",
        llm_decision="MAPPED",
        llm_confidence="high",
        llm_reasoning="IR-2 applies: Policy mentions 'encryption' which covers AES-256",
        llm_evidence_quote="All sensitive data shall be encrypted.",
        llm_evidence_location="Section 4.2",
        llm_gaps=[],
        batch_file="batch_001.json",
        experiment_timestamp="20251228_112332",
    )

@pytest.fixture
def sample_fps_for_dedup(sample_false_positive) -> list[FalsePositive]:
    """Multiple FPs that should deduplicate to fewer patterns."""
    # Same control + IR rule across different policies = 1 pattern
    # ...

@pytest.fixture
def sample_pattern() -> FPPattern:
    """A pattern for testing sampling/output."""
    # ...

@pytest.fixture
def sample_judge_result() -> FPJudgeResult:
    """A judge result for testing output generation."""
    # ...
```

---

## Files to Create

### New Module: `false_positive_validation/`

| File | Purpose | Based On |
|------|---------|----------|
| `__init__.py` | Module exports | gt_validation |
| `fp_models.py` | FalsePositive, FPJudgeResult, FPPattern dataclasses | `models.py` |
| `fp_collector.py` | Collect MAPPED controls not in GT | `gt_collector.py` |
| `analyze_fp_distribution.py` | **Phase 0**: Zero-cost distribution analysis | New |
| `deduplicate_fps.py` | **Phase 1**: Group FPs into patterns by signature | New |
| `fp_sampler.py` | **Phase 2 (optional)**: Pareto + Diversity sampling | New |
| `fp_judge_decider.py` | Judge with original prompt in context | `judge_decider.py` |
| `fp_config.py` | Configuration | `judge_config.py` |
| `fp_output_generator.py` | Generate CSVs, JSONs, summaries | `output_generator.py` |
| `run_fp_validation.py` | CLI orchestrator | `run_validation.py` |

### Test Files (write FIRST)

| Test File | Tests For |
|-----------|-----------|
| `test_fp_models.py` | Dataclass creation, validation, serialization |
| `test_fp_collector.py` | FP collection from batch files |
| `test_analyze_fp_distribution.py` | Distribution CSV generation |
| `test_deduplicate_fps.py` | Pattern signature, deduplication logic |
| `test_fp_sampler.py` | Bucket allocation, coverage guarantees |
| `test_fp_judge_decider.py` | Prompt rendering, response parsing |
| `test_fp_output_generator.py` | JSON/CSV output format |
| `test_run_fp_validation.py` | CLI argument parsing, pipeline orchestration |

### New Prompts: `prompts/fp_judge/`

| File | Purpose |
|------|---------|
| `system` | FP judge system prompt (explains task, references original mapping rules) |
| `user` | User template with FP details and original LLM reasoning |
| `response.json` | Structured output schema for FP analysis |

## Key Data Models

### `FalsePositive` (input)

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class FalsePositive:
    """A control that was MAPPED but is not in ground truth."""
    control_id: str
    control_name: str
    control_description: str
    policy_name: str

    # Original LLM decision
    llm_decision: Literal["MAPPED"]  # Always MAPPED for FPs
    llm_confidence: Confidence
    llm_reasoning: str
    llm_evidence_quote: str
    llm_evidence_location: str
    llm_gaps: list[dict]  # Any gaps identified

    # Metadata
    batch_file: str
    experiment_timestamp: str
```

### `FPPattern` (for deduplication)

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class FPPattern:
    """A unique failure pattern grouping multiple FP instances."""
    signature: str  # Hash of (control_id, ir_rule) — evidence excluded by default
    control_id: str
    primary_ir_rule: str | None  # Extracted from reasoning

    # Statistics
    frequency: int  # How many FP instances match this pattern
    policies: frozenset[str]  # Which policies this pattern appears in

    # Representative instances (2-3 examples)
    representatives: tuple[FalsePositive, ...]
```

### `FPJudgeResult` (output)

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class FPJudgeResult:
    """Result of judging a false positive."""
    control_id: str
    policy_name: str

    # Judge verdict (GT assumed correct, so just confirming FP or uncertain)
    verdict: Literal["CONFIRMED_FP", "UNCERTAIN"]
    confidence: Confidence

    # Analysis
    reasoning: str
    misapplied_rules: list[str]  # e.g., ["IR-2", "IR-8"]
    root_cause: RootCause  # Enum - controlled vocabulary for aggregation

    # Evidence
    why_no_match: str  # Why this shouldn't map
    original_evidence_critique: str  # Why original evidence was wrong
    missing_requirement: str  # What would need to be in policy to make this map

    # Metadata
    fp: FalsePositive  # Original FP data
    pattern_signature: str | None = None  # Link back to pattern if using dedup
```

## Prompt Design

### FP Judge System Prompt (Key Points)

1. **Role**: Security Compliance Auditor reviewing disputed MAPPED decisions
2. **Context**: Include the original mapping prompt so judge can reference IR rules
3. **Task**: Determine if the MAPPED decision was correct or a false positive
4. **Focus Areas**:
   - Did the LLM misapply an Interpretive Rule (IR-1 to IR-10)?
   - Was the evidence quote actually binding?
   - Did scope matching go too far?
   - Was semantic equivalence stretched?

### FP Judge User Prompt Template

```
The LLM mapped this control to the policy, but ground truth says it should NOT map.

<control>
  <id>{control_id}</id>
  <name>{control_name}</name>
  <description>{control_description}</description>
</control>

<original_llm_evaluation>
  <decision>MAPPED</decision>
  <confidence>{confidence}</confidence>
  <reasoning>{reasoning}</reasoning>
  <evidence_quote>{evidence_quote}</evidence_quote>
  <location>{location}</location>
</original_llm_evaluation>

<instructions>
Determine if this is a valid false positive:

1. Review the LLM's reasoning - which Interpretive Rules (IR-1 to IR-10) did it cite?
2. Check if those rules were correctly applied
3. Verify if the evidence quote actually establishes a binding mandate for this control
4. Consider: Does the policy REALLY address this control's requirements?

Verdicts (assume ground truth is correct):
- CONFIRMED_FP: The mapping is incorrect - explain why
- UNCERTAIN: Cannot determine with confidence
</instructions>
```

### Response Schema

```json
{
  "control_id": "string",
  "verdict": "CONFIRMED_FP | UNCERTAIN",
  "confidence": "high | medium | low",
  "reasoning": "2-3 sentence explanation",
  "misapplied_rules": ["IR-X", ...],
  "root_cause": "enum (see below)",
  "why_no_match": "why this control shouldn't map",
  "original_evidence_critique": "why original evidence was insufficient",
  "missing_requirement": "what concrete requirement is absent that would make this map"
}
```

### Root Cause Enum (Controlled Vocabulary)

To enable clean aggregation, constrain `root_cause` to these categories:

| Category | Description | Typically caused by |
|----------|-------------|---------------------|
| `SCOPE_OVERREACH` | Policy scope doesn't actually cover control's target assets | IR-1 misapplied |
| `ABSTRACT_VS_SPECIFIC` | Policy is generic; control requires specific implementation | IR-2 misapplied |
| `SEMANTIC_STRETCH` | Words seem similar but functional outcome differs | IR-3 misapplied |
| `GOVERNANCE_NOT_PROCEDURE` | Policy states intent but control needs actionable procedure | IR-4 misapplied |
| `FREQUENCY_UNSPECIFIED` | Control requires specific timing; policy is silent | IR-5 misapplied |
| `EXISTENCE_NOT_IMPLIED` | Using X doesn't imply having X | IR-6 misapplied |
| `PROHIBITION_NOT_IMPLIED` | Positive mandate doesn't imply prohibition | IR-7 misapplied |
| `BINDING_NOT_INHERITED` | List items don't inherit header's binding language | IR-8 misapplied |
| `STANDARD_NOT_REFERENCED` | Referenced standard doesn't actually cover this control | IR-9 misapplied |
| `DISJUNCTION_WRONG` | Control requires A AND B; policy only has B | IR-10 misapplied |
| `NON_BINDING_LANGUAGE` | Evidence quote uses "should/may/can" not "shall/must/required" | No IR - basic error |
| `WRONG_SUBJECT` | Policy applies to different entity than control requires | No IR - basic error |
| `UNRELATED_DOMAIN` | Policy and control are in completely different domains | No IR - basic error |

## Implementation Steps (TDD)

> **See [sampling_recommendation_v2.md](./sampling_recommendation_v2.md)** for detailed sampling strategy and code examples.

Each step follows the TDD cycle: **RED** (write failing tests) → **GREEN** (implement) → **REFACTOR** (clean up).

---

### Step 1: Create data models (`fp_models.py`)

#### 1a. RED: Write tests first (`test_fp_models.py`)

```python
def test_false_positive_creation():
    """FalsePositive can be created with all required fields."""
    fp = FalsePositive(
        control_id="DCF-107",
        control_name="Data Encryption",
        # ... all fields
    )
    assert fp.control_id == "DCF-107"
    assert fp.llm_decision == "MAPPED"

def test_false_positive_is_frozen():
    """FalsePositive is immutable."""
    fp = FalsePositive(...)
    with pytest.raises(FrozenInstanceError):
        fp.control_id = "DCF-999"

def test_fp_verdict_enum_values():
    """FPVerdict has correct values."""
    assert FPVerdict.CONFIRMED_FP.value == "CONFIRMED_FP"
    assert FPVerdict.UNCERTAIN.value == "UNCERTAIN"

def test_root_cause_enum_has_all_categories():
    """RootCause enum has all 13 categories."""
    assert len(RootCause) == 13
    assert RootCause.SCOPE_OVERREACH in RootCause
    assert RootCause.NON_BINDING_LANGUAGE in RootCause

def test_fp_pattern_creation():
    """FPPattern groups FPs with frequency and representatives."""
    pattern = FPPattern(
        signature="abc123",
        control_id="DCF-107",
        primary_ir_rule="IR-2",
        frequency=45,
        policies=frozenset(["Policy A", "Policy B"]),
        representatives=(fp1, fp2),
    )
    assert pattern.frequency == 45
    assert len(pattern.representatives) == 2
```

#### 1b. GREEN: Implement models

- `FalsePositive` dataclass
- `FPPattern` dataclass (for deduplication)
- `FPJudgeResult` dataclass
- `FPVerdict` enum (CONFIRMED_FP, UNCERTAIN)
- `RootCause` enum (13 categories - see controlled vocabulary above)
- Reuse `Confidence` from existing models

#### 1c. Verify: `uv run pytest tests/.../test_fp_models.py -v`

---

### Step 2: Create collector (`fp_collector.py`)

#### 2a. RED: Write tests first (`test_fp_collector.py`)

```python
@pytest.fixture
def mock_batch_file(tmp_path) -> Path:
    """Create a mock batch file with MAPPED and NOT_MAPPED controls."""
    batch_data = {
        "controls": [
            {"control_id": "DCF-107", "decision": "MAPPED", ...},
            {"control_id": "DCF-108", "decision": "NOT_MAPPED", ...},
            {"control_id": "DCF-421", "decision": "MAPPED", ...},
        ]
    }
    # Write to tmp_path
    return batch_path

@pytest.fixture
def mock_ground_truth() -> set[str]:
    """Ground truth only includes DCF-107."""
    return {"DCF-107"}

def test_collect_finds_mapped_not_in_gt(mock_batch_file, mock_ground_truth):
    """Collector returns MAPPED controls NOT in ground truth."""
    fps = collect_false_positives(
        experiment_timestamp="20251228",
        llm_output_dir=mock_batch_file.parent,
        ground_truth_controls=mock_ground_truth,
    )
    # DCF-107 is MAPPED but IN ground truth → not an FP
    # DCF-421 is MAPPED but NOT in ground truth → is an FP
    assert len(fps) == 1
    assert fps[0].control_id == "DCF-421"

def test_collect_returns_false_positive_objects(mock_batch_file, mock_ground_truth):
    """Collector returns properly typed FalsePositive objects."""
    fps = collect_false_positives(...)
    assert all(isinstance(fp, FalsePositive) for fp in fps)
    assert all(fp.llm_decision == "MAPPED" for fp in fps)

def test_collect_handles_multiple_batch_files(tmp_path):
    """Collector aggregates across multiple batch_*.json files."""
    # Create batch_001.json, batch_002.json
    fps = collect_false_positives(...)
    assert len(fps) == expected_total_across_batches
```

#### 2b. GREEN: Implement collector

```python
def collect_false_positives(
    experiment_timestamp: str,
    llm_output_dir: Path,
    ground_truth_controls: set[str],
) -> list[FalsePositive]:
    """Collect MAPPED controls that are NOT in ground truth."""
    # Load all batch_*.json files
    # Find controls where decision == "MAPPED"
    # Filter to those NOT in ground_truth_controls
    # Return as FalsePositive objects
```

#### 2c. Verify: `uv run pytest tests/.../test_fp_collector.py -v`

---

### Step 3: Distribution Analysis (`analyze_fp_distribution.py`) — Phase 0

**Zero LLM cost.** Run before any judging decisions.

#### 3a. RED: Write tests first (`test_analyze_fp_distribution.py`)

```python
def test_analyze_creates_fps_by_control_csv(sample_fps, tmp_path):
    """Distribution analysis creates fps_by_control.csv."""
    analyze_distribution(sample_fps, output_dir=tmp_path)
    csv_path = tmp_path / "fps_by_control.csv"
    assert csv_path.exists()
    df = pd.read_csv(csv_path)
    assert "control_id" in df.columns
    assert "fp_count" in df.columns

def test_analyze_creates_fps_by_policy_csv(sample_fps, tmp_path):
    """Distribution analysis creates fps_by_policy.csv."""
    analyze_distribution(sample_fps, output_dir=tmp_path)
    assert (tmp_path / "fps_by_policy.csv").exists()

def test_analyze_creates_fps_by_ir_rule_csv(sample_fps, tmp_path):
    """Distribution analysis creates fps_by_ir_rule.csv."""
    analyze_distribution(sample_fps, output_dir=tmp_path)
    assert (tmp_path / "fps_by_ir_rule.csv").exists()

def test_extract_primary_ir_rule_finds_ir2():
    """IR rule extraction finds IR-2 in reasoning."""
    reasoning = "IR-2 applies: Policy mentions 'encryption' which covers AES-256"
    assert extract_primary_ir_rule(reasoning) == "IR-2"

def test_extract_primary_ir_rule_returns_none_when_missing():
    """IR rule extraction returns None when no IR cited."""
    reasoning = "The policy clearly states encryption requirements."
    assert extract_primary_ir_rule(reasoning) is None
```

#### 3b. GREEN: Implement distribution analysis

```python
def extract_primary_ir_rule(reasoning: str) -> str | None:
    """Extract IR-N from reasoning text."""

def analyze_distribution(all_fps: list[FalsePositive], output_dir: Path) -> dict:
    """Output distribution CSVs to understand FP landscape."""
    # fps_by_control.csv   - control_id, fp_count, policies_list
    # fps_by_policy.csv    - policy_name, fp_count, controls_list
    # fps_by_confidence.csv - confidence, fp_count
    # fps_by_ir_rule.csv   - ir_rule_cited, fp_count
```

#### 3c. Verify: `uv run pytest tests/.../test_analyze_fp_distribution.py -v`

---

### Step 4: Pattern Deduplication (`deduplicate_fps.py`) — Phase 1

**Meaningful reduction.** Switch analysis unit from "FP instance" to "FP pattern".

> **Implementation Note:** Original plan expected 10-17x reduction with `(control_id, IR_rule, evidence_hash)`.
> Testing revealed evidence quotes are unique per policy, yielding only 1.0x reduction.
> Changed to `(control_id, IR_rule)` signature which achieves **2.2x reduction** (4,104 → 1,878 patterns).
> See [deduplication_analysis.md](./deduplication_analysis.md) for full analysis.

#### 4a. RED: Write tests first (`test_deduplicate_fps.py`)

```python
def test_same_control_same_ir_is_one_pattern():
    """FPs with same control+IR → single pattern (default, no evidence in signature)."""
    fp1 = FalsePositive(control_id="DCF-107", llm_reasoning="IR-2...", llm_evidence_quote="encrypt A")
    fp2 = FalsePositive(control_id="DCF-107", llm_reasoning="IR-2...", llm_evidence_quote="encrypt B")
    patterns = deduplicate_fps([fp1, fp2])
    assert len(patterns) == 1  # Same pattern despite different evidence
    assert patterns[0].frequency == 2

def test_different_controls_are_different_patterns():
    """FPs with different control IDs → different patterns."""
    fp1 = FalsePositive(control_id="DCF-107", ...)
    fp2 = FalsePositive(control_id="DCF-421", ...)
    patterns = deduplicate_fps([fp1, fp2])
    assert len(patterns) == 2

def test_pattern_has_representative_instances():
    """Each pattern includes 2-3 representative FP instances."""
    fps = [make_fp(control_id="DCF-107") for _ in range(10)]
    patterns = deduplicate_fps(fps)
    assert len(patterns[0].representatives) <= 3

def test_patterns_sorted_by_frequency_descending():
    """Patterns are sorted by frequency (highest first)."""
    # Create FPs such that pattern A has 10 instances, B has 5
    patterns = deduplicate_fps(fps)
    assert patterns[0].frequency >= patterns[1].frequency
```

#### 4b. GREEN: Implement deduplication

```python
def compute_pattern_signature(
    fp: FalsePositive,
    include_evidence: bool = False,  # Default: exclude evidence
) -> str:
    """Group FPs by their failure pattern, not individual instance.

    Default signature: (control_id, IR_rule) — achieves 2.2x reduction.
    With include_evidence=True: adds evidence_hash — achieves ~1.0x (not useful).
    """
    control_id = fp.control_id
    ir_rule = extract_primary_ir_rule(fp.llm_reasoning) or "NONE"

    if include_evidence:
        evidence_hash = normalize_evidence_hash(fp.llm_evidence_quote)
        signature_parts = f"{control_id}|{ir_rule}|{evidence_hash}"
    else:
        signature_parts = f"{control_id}|{ir_rule}"

    return hashlib.md5(signature_parts.encode()).hexdigest()

def normalize_evidence_hash(evidence: str) -> str:
    """Normalize evidence text and return hash (only used if include_evidence=True)."""

def deduplicate_fps(
    all_fps: list[FalsePositive],
    include_evidence: bool = False,
) -> list[FPPattern]:
    """Group 4,104 FP instances → ~1,878 unique patterns (2.2x reduction)."""
```

#### 4c. Verify: `uv run pytest tests/.../test_deduplicate_fps.py -v`

**Actual reduction:** 4,104 → 1,878 patterns (2.2x)

---

### Step 5: Sampler (`fp_sampler.py`) — Phase 2 (SKIPPED)

**Not needed.** With 1,878 patterns at ~$10-20 total cost, we recommend analyzing ALL patterns.

See [sampling_recommendation_v2.md](./sampling_recommendation_v2.md) for a sampling strategy if cost becomes a concern in the future.

#### 5a. RED: Write tests first (`test_fp_sampler.py`)

```python
def test_sampler_respects_target_count():
    """Sampler returns approximately target_count patterns."""
    patterns = [make_pattern() for _ in range(1000)]
    sampled = sample_patterns(patterns, target_count=200)
    assert 180 <= len(sampled) <= 220  # Allow some variance

def test_sampler_covers_all_policies():
    """Sampled set includes patterns from every policy."""
    # Create patterns from 37 different policies
    sampled = sample_patterns(patterns, target_count=200)
    policies_in_sample = {p for pat in sampled for p in pat.policies}
    assert len(policies_in_sample) == 37

def test_sampler_covers_all_ir_rules():
    """Sampled set includes patterns citing each IR rule."""
    sampled = sample_patterns(patterns, target_count=200)
    ir_rules_in_sample = {pat.primary_ir_rule for pat in sampled if pat.primary_ir_rule}
    assert len(ir_rules_in_sample) >= 10

def test_sampler_prioritizes_high_frequency_patterns():
    """High-frequency patterns are more likely to be sampled."""
    patterns = [make_pattern(frequency=100)] + [make_pattern(frequency=1) for _ in range(100)]
    sampled = sample_patterns(patterns, target_count=50)
    # The freq=100 pattern should definitely be included
    assert any(p.frequency == 100 for p in sampled)

def test_sampler_is_reproducible_with_seed():
    """Same seed produces same sample."""
    sample1 = sample_patterns(patterns, seed=42)
    sample2 = sample_patterns(patterns, seed=42)
    assert sample1 == sample2
```

#### 5b. GREEN: Implement sampler

```python
def sample_patterns(
    patterns: list[FPPattern],
    all_fps: list[FalsePositive],
    target_count: int = 200,
    seed: int | None = None,
) -> list[FPPattern]:
    """Pareto + Diversity sampling if pattern count is too high."""
    # Bucket A: Pareto patterns (~70% coverage)
    # Bucket B: Frequent flyer controls
    # Bucket C: Policy coverage
    # Bucket D: IR rule coverage
    # Bucket E: Long tail random
```

#### 5c. Verify: `uv run pytest tests/.../test_fp_sampler.py -v`

---

### Step 6: Create prompts (`prompts/fp_judge/`)

#### 6a. RED: Write tests first (in `test_fp_judge_decider.py`)

```python
def test_user_prompt_renders_control_details(sample_false_positive):
    """User prompt template renders control ID, name, description."""
    prompt = render_user_prompt(sample_false_positive)
    assert "DCF-107" in prompt
    assert "Data Encryption" in prompt

def test_user_prompt_includes_original_reasoning(sample_false_positive):
    """User prompt includes the original LLM reasoning."""
    prompt = render_user_prompt(sample_false_positive)
    assert sample_false_positive.llm_reasoning in prompt

def test_response_schema_is_valid_json():
    """response.json is valid JSON schema."""
    schema = load_response_schema()
    assert "verdict" in schema["properties"]
    assert "root_cause" in schema["properties"]
```

#### 6b. GREEN: Create prompt files

- `system`: Reference original mapping prompt, define FP analysis task
- `user`: Template with placeholders for FP details
- `response.json`: Schema for structured output

#### 6c. Verify: `uv run pytest tests/.../test_fp_judge_decider.py::test_*prompt* -v`

---

### Step 7: Create judge (`fp_judge_decider.py`)

Key difference from `judge_decider.py`: **Include original mapping prompt in cache**

#### 7a. RED: Write tests first (`test_fp_judge_decider.py`)

```python
@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response."""
    return {
        "verdict": "CONFIRMED_FP",
        "confidence": "high",
        "reasoning": "The policy only mentions generic encryption...",
        "misapplied_rules": ["IR-2"],
        "root_cause": "ABSTRACT_VS_SPECIFIC",
        "why_no_match": "Control requires AES-256, policy is generic",
        "original_evidence_critique": "Evidence is non-binding",
        "missing_requirement": "Specific encryption algorithm specification",
    }

def test_judge_returns_fp_judge_result(mock_gemini_response):
    """Judge returns properly typed FPJudgeResult."""
    result = await judge_false_positive(fp, cache_name)
    assert isinstance(result, FPJudgeResult)

def test_judge_parses_verdict_correctly(mock_gemini_response):
    """Judge parses verdict from response."""
    result = await judge_false_positive(fp, cache_name)
    assert result.verdict == FPVerdict.CONFIRMED_FP

def test_judge_parses_root_cause_enum(mock_gemini_response):
    """Judge parses root_cause as RootCause enum."""
    result = await judge_false_positive(fp, cache_name)
    assert result.root_cause == RootCause.ABSTRACT_VS_SPECIFIC

def test_cache_includes_original_mapping_prompt():
    """Context cache includes original control mapping prompt."""
    # Verify that _upload_document_cache includes the original prompt
```

#### 7b. GREEN: Implement judge

```python
class FPJudgeDecider:
    async def _upload_document_cache(
        self,
        pdf_bytes: bytes,
        policy_name: str,
        original_mapping_prompt: str,
    ) -> str:
        """Upload PDF + original mapping prompt + FP judge prompt to cache."""

    async def judge_false_positive(
        self,
        fp: FalsePositive,
        cache_name: str,
    ) -> FPJudgeResult:
        """Judge a single false positive."""
```

#### 7c. Verify: `uv run pytest tests/.../test_fp_judge_decider.py -v`

---

### Step 8: Create output generator (`fp_output_generator.py`)

#### 8a. RED: Write tests first (`test_fp_output_generator.py`)

```python
def test_generates_detailed_results_json(sample_judge_results, tmp_path):
    """Output generator creates detailed_results.json."""
    generate_outputs(sample_judge_results, [], tmp_path)
    assert (tmp_path / "detailed_results.json").exists()

def test_generates_fp_confirmed_csv(sample_judge_results, tmp_path):
    """Output generator creates fp_confirmed.csv for CONFIRMED_FP verdicts."""
    generate_outputs(sample_judge_results, [], tmp_path)
    df = pd.read_csv(tmp_path / "fp_confirmed.csv")
    assert all(df["verdict"] == "CONFIRMED_FP")

def test_generates_fp_uncertain_csv(sample_judge_results, tmp_path):
    """Output generator creates fp_uncertain.csv for UNCERTAIN verdicts."""
    generate_outputs(sample_judge_results, [], tmp_path)
    assert (tmp_path / "fp_uncertain.csv").exists()

def test_summary_aggregates_by_root_cause(sample_judge_results, tmp_path):
    """Summary JSON includes counts by root_cause."""
    generate_outputs(sample_judge_results, [], tmp_path)
    summary = json.loads((tmp_path / "fp_analysis_summary.json").read_text())
    assert "by_root_cause" in summary

def test_summary_aggregates_by_misapplied_rule(sample_judge_results, tmp_path):
    """Summary JSON includes counts by misapplied IR rule."""
    summary = json.loads((tmp_path / "fp_analysis_summary.json").read_text())
    assert "by_misapplied_rule" in summary
```

#### 8b. GREEN: Implement output generator

- `detailed_results.json`: All FP judge results
- `fp_analysis_summary.json`: Aggregate stats by rule, root cause
- `fp_confirmed.csv`: Confirmed false positives with analysis
- `fp_uncertain.csv`: Needs human review

#### 8c. Verify: `uv run pytest tests/.../test_fp_output_generator.py -v`

---

### Step 9: Create CLI orchestrator (`run_fp_validation.py`)

#### 9a. RED: Write tests first (`test_run_fp_validation.py`)

```python
def test_cli_parses_experiment_timestamp():
    """CLI parses --experiment-timestamp argument."""
    args = parse_args(["--experiment-timestamp", "20251228_112332"])
    assert args.experiment_timestamp == "20251228_112332"

def test_cli_parses_sampling_strategy():
    """CLI parses --sampling-strategy argument."""
    args = parse_args(["--sampling-strategy", "pareto"])
    assert args.sampling_strategy == "pareto"

def test_cli_default_sampling_is_all():
    """CLI defaults to --sampling-strategy all."""
    args = parse_args([])
    assert args.sampling_strategy == "all"

def test_pipeline_runs_phases_in_order(mock_all_dependencies):
    """Pipeline executes phases 0→1→2→3 in order."""
    # Integration test with mocked dependencies
```

#### 9b. GREEN: Implement CLI orchestrator

```bash
# Full pipeline (recommended)
uv run python -m ai_services.scripts.experiments.control_detection.false_positive_validation.run_fp_validation \
    --experiment-timestamp 20251228_112332 \
    --original-prompts-dir control_centric_false_negatives \
    --gcp-project ai-team-gemini-dev

# With sampling (if >500 patterns after dedup)
uv run python -m ... --sampling-strategy pareto --max-patterns 200
```

#### 9c. Verify: `uv run pytest tests/.../test_run_fp_validation.py -v`

---

### Final Verification: All Tests Pass

```bash
# Run all tests for the module
uv run pytest tests/scripts/experiments/control_detection/false_positive_validation/ -v

# Run with coverage
uv run pytest tests/scripts/experiments/control_detection/false_positive_validation/ --cov=ai_services.scripts.experiments.control_detection.false_positive_validation
```

## Output Location

```
files/llm_outputs/fp_validation/{timestamp}/
├── detailed_results.json
├── fp_analysis_summary.json
├── fp_confirmed.csv
├── fp_uncertain.csv
├── run_metadata.json
└── {policy_name}/
    ├── fp_judge_{control_id}.json
    └── ...
```

## Sampling Strategy

> **Full details**: See [sampling_recommendation_v2.md](./sampling_recommendation_v2.md)

### The Problem (Original Assumption)

We originally expected **5,287 false positives** to deduplicate to **~300-500 patterns** (10-17x reduction).

### The Reality (Post-Implementation)

Testing on real experiment data revealed:
- Actual FP count: **4,104** (from experiment 5 with expanded IR rules)
- Evidence quotes are **unique per policy** (LLM cites different text from each document)
- `(control_id, IR_rule, evidence_hash)` yields only **1.0x reduction** (useless)
- `(control_id, IR_rule)` yields **2.2x reduction** (4,104 → 1,878 patterns)

### The Solution: Analyze All Patterns

| Stage | Count | Reduction |
|-------|-------|-----------|
| Raw FP instances | 4,104 | — |
| After pattern dedup | 1,878 | **2.2x reduction** |
| **Patterns to analyze** | **1,878** | — |

**Pattern signature**: `(control_id, IR_rule)` — evidence excluded

**Cost estimate**: ~$10-20 with Flash-tier models (Gemini 1.5 Flash)

**Recommendation**: Analyze ALL 1,878 patterns. The marginal cost difference vs sampling (~$15 vs ~$5) is negligible compared to having complete data.

### Execution Flow

```
Phase 0: Distribution Analysis (zero cost) ✅ COMPLETE
    ↓ IR-3 accounts for 32.8% of FPs
Phase 1: Pattern Deduplication (critical) ✅ COMPLETE
    ↓ 4,104 → 1,878 patterns (2.2x)
Phase 2: Judge ALL 1,878 patterns
    ↓ ~$10-20 total cost
Phase 3: Generate outputs and aggregate by root cause
```

### CLI Options

```bash
# Analyze all patterns (recommended default)
--sampling-strategy all

# Strategic sampling if cost is a concern (see sampling_recommendation_v2.md)
--sampling-strategy strategic --max-patterns 500

# Reproducible sampling
--seed 42
```

### Deduplication Tracking

Same control can be FP across many documents. Track stats both:
- **By instance**: Raw counts of FP judgments (4,104 total)
- **By pattern**: Unique `(control_id, IR_rule)` signatures (1,878 total)

### Key Finding: IR Rule Distribution

From distribution analysis (Phase 0):

| IR Rule | FP Count | % of Total |
|---------|----------|------------|
| IR-3 (Semantic Equivalence) | 1,345 | 32.8% |
| IR-1 (Hierarchical Scope) | 671 | 16.3% |
| IR-2 (Tech→Abstract) | 640 | 15.6% |
| IR-4 (Governance→Procedure) | 587 | 14.3% |
| IR-6 (Existence Inference) | 412 | 10.0% |
| Other | 449 | 10.9% |

**Insight**: IR-3 is the most abused rule, causing 1/3 of all FPs.

## Reuse Summary

| Component | Reuse From | Changes Needed |
|-----------|------------|----------------|
| Caching logic | `judge_decider.py` | Add original prompt to cache |
| Semaphore/retry | `judge_decider.py` | None |
| Output patterns | `output_generator.py` | Different columns/stats |
| CLI structure | `run_validation.py` | Different args |
| Dataclass patterns | `models.py` | Different fields |

## Key Files to Reference

- `ground_truth_validation/judge_decider.py:185-230` - Cache upload pattern
- `ground_truth_validation/gt_collector.py:70-130` - Collection pattern (invert logic)
- `ground_truth_validation/output_generator.py` - Output generation patterns
- `prompts/control_centric_false_negatives/system` - Original prompt to include
- `prompts/judge/system` - Judge prompt structure to follow
