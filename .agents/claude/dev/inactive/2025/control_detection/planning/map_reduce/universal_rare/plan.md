# Map-Reduce Reason Aggregator: Universal/Rare Pattern Enhancement

## Executive Summary

This document describes enhancements to the Map-Reduce Reason Aggregator to improve pattern consolidation and produce actionable auditor guidance. The key changes are:

1. **Two-phase architecture**: Map-reduce collection (Phase 1) + distillation (Phase 2)
2. **Universal vs Rare pattern separation**: Patterns observed in multiple sources get merged; single-source patterns are preserved as edge cases
3. **Index-based pattern handling**: Both rare AND unchanged universal patterns use indices to avoid text regeneration
4. **Code-computed leftovers**: LLM only outputs merged patterns + unchanged universals; code computes still-rare deterministically

## Background

### What is the Reason Aggregator?

The Reason Aggregator is a map-reduce system that processes control-to-policy mapping reasons from 37 template policies. It iteratively combines and consolidates these reasons to identify universal patterns that can guide LLM-based control mapping.

**Location**: `ai_services/scripts/experiments/control_detection/reason_aggregator/`

### The Goal

Produce a small set (10-15) of explicit, actionable heuristics that an LLM can follow to map security controls to policy documents—the same task a human GRC auditor would perform.

### The Problem We Identified

The current implementation produces too many patterns because the prompts encourage **collection** rather than **distillation**:

```
"Extract ALL distinct abstract patterns found in EITHER source"
"DO NOT discard patterns just because they only appear in one source"
```

This results in pattern proliferation. With 37 policies, the system could produce 80-100+ patterns instead of the desired 10-15 actionable heuristics.

## Key Design Decisions

### Decision 1: Round 1 Produces RARE Patterns

A pattern extracted from a single policy has `source_count=1`, which is by definition **rare**.

- **Round 1**: All patterns go into `rare_patterns`. `universal_patterns` is empty.
- **Round 2+**: Rare patterns that match become universal; unmatched stay rare.

This makes the semantics consistent: "Universal" strictly means "observed in >1 original source."

### Decision 2: Three Categories of Output

For Round 2+, the LLM produces:

1. **`merged_patterns`**: Newly synthesized patterns (requires text generation)
2. **`unchanged_universal`**: Universal patterns that didn't merge (index only, no text generation)
3. **Still-rare patterns**: Computed by code as `input_indices - consumed` (not in LLM output)

This prevents "text drift" (patterns degrading over 5+ rounds of regeneration) and eliminates risk of LLM forgetting to list rare indices.

### Decision 3: Code-Computed Coverage Invariant

After each LLM call, code validates:

```python
consumed = set()
for p in merged_patterns:
    consumed.update(p.derived_from)
consumed.update(unchanged_universal)

# Validation
assert consumed <= input_indices, "Hallucinated indices detected"

leftover = input_indices - consumed
# leftover patterns are still-rare, carried forward verbatim
```

This guarantees no pattern loss and catches hallucinated indices.

### Decision 4: Stable Pattern IDs

Ephemeral indices like `U1_0`, `R2_3` are only meaningful within a single round. For cross-round provenance tracking, each pattern gets a stable `pattern_id` (hash of name + evidence_types + mapping_patterns).

### Decision 5: Runtime Schema Enum Injection for Index Fields

Index-based fields (`derived_from`, `unchanged_universal`) must be constrained at the schema level to prevent hallucinated indices. The valid set of indices is **injected into the response schema at runtime** via string placeholders.

**Why this matters:**
- Schema-level constraints are enforced by the LLM's structured output system
- Prevents hallucinated indices before they reach validation code
- Provides clear error messages when LLM attempts invalid values
- Reduces reliance on post-hoc validation and retry loops

**Implementation:**
- The base `response.json` contains string placeholders: `"VALID_INDICES"`, `"VALID_UNIVERSAL_INDICES"`
- At runtime, code replaces placeholder strings with actual enum arrays
- `minItems` and `maxItems` are also computed and injected based on input size

**Example transformation:**

Base schema (template):
```json
"derived_from": {
  "type": "array",
  "items": {"type": "string", "enum": "VALID_INDICES"},
  "minItems": 1,
  "maxItems": "TOTAL_INDEX_COUNT"
}
```

Runtime schema (after injection):
```json
"derived_from": {
  "type": "array",
  "items": {"type": "string", "enum": ["U1_0", "U1_1", "R1_0", "U2_0", "R2_0", "R2_1"]},
  "minItems": 1,
  "maxItems": 6
}
```

## Architecture

### Phase 1: Map-Reduce Collection

```
Round 1: PolicyReasons → Patterns (all RARE)
  - Input: Raw generalized reasons from policies
  - Output: rare_patterns only (universal_patterns empty)
  - Prompt: aggregate_reasons (extracts patterns)

Round 2+: Patterns → Consolidated Patterns
  - Input: Indexed patterns (U* for universal, R* for rare)
  - Output: merged_patterns + unchanged_universal (code computes still-rare)
  - Prompt: consolidate_patterns (merges + classifies)
```

**Pattern Lifecycle:**
```
Round 1: Policy → R (rare, source_count=1)
Round 2: R + R (match) → U (universal, source_count=2)
         R (no match) → R (still rare)
Round 3: U + U (match) → U (merged universal)
         U + R (match) → U (rare absorbed into universal)
         U (no match) → U (via unchanged_universal index)
         R (no match) → R (still rare)
```

### Phase 2: Distillation (Future Work)

```
Input: Final RoundOutput with ~30-50 universal + ~50-80 rare patterns
Output: 10-15 actionable heuristics + edge case notes
```

## Data Model Changes

### Current AggregatedPattern

```python
@dataclass
class AggregatedPattern:
    name: str
    description: str
    evidence_types: tuple[str, ...]
    mapping_patterns: tuple[str, ...]
    source_policy_ids: tuple[str, ...] = ()
```

### New AggregatedPattern

```python
@dataclass
class AggregatedPattern:
    name: str
    description: str
    evidence_types: tuple[str, ...]
    mapping_patterns: tuple[str, ...]
    source_policy_ids: tuple[str, ...] = ()
    pattern_id: str = ""  # Stable ID: hash of (name, evidence_types, mapping_patterns)

    def __post_init__(self):
        if not self.pattern_id:
            # Generate stable ID from content
            content = f"{self.name}:{sorted(self.evidence_types)}:{sorted(self.mapping_patterns)}"
            self.pattern_id = hashlib.sha256(content.encode()).hexdigest()[:12]

    @property
    def merge_key(self) -> tuple[frozenset, frozenset]:
        """Canonical key for determining if two patterns should merge."""
        return (frozenset(self.evidence_types), frozenset(self.mapping_patterns))
```

### Current RoundOutput

```python
@dataclass
class RoundOutput:
    round_num: int
    pair_id: str
    patterns: tuple[AggregatedPattern, ...]
    source_policies: tuple[str, ...]
```

### New RoundOutput

```python
@dataclass
class RoundOutput:
    round_num: int
    pair_id: str
    universal_patterns: tuple[AggregatedPattern, ...]  # Merged/graduated patterns
    rare_patterns: tuple[AggregatedPattern, ...]       # Single-source patterns
    source_policies: tuple[str, ...]

    @property
    def all_patterns(self) -> tuple[AggregatedPattern, ...]:
        """All patterns for backward compatibility."""
        return self.universal_patterns + self.rare_patterns
```

## Prompt Design

### Round 1: aggregate_reasons (Minor changes)

Keep mostly as-is. Round 1 converts raw reasons to initial patterns.

**Changes:**
- Remove: `"DO NOT discard patterns just because they only appear in one source"`
- All output patterns are placed in `rare_patterns` (source_count=1 by definition)

### Round 2+: consolidate_patterns (NEW)

**System Prompt:**
```
You are consolidating mapping patterns from previous aggregation rounds.

Your task is to:
1. MERGE similar patterns into new universal patterns (requires text generation)
2. IDENTIFY universal patterns that have no match (pass through by index)

You do NOT need to list rare patterns that remain rare - the system will compute that automatically.
```

**User Prompt:**
```
## Source 1 Patterns

### Universal Patterns
{U1_0, U1_1, ... with full details}

### Rare Patterns
{R1_0, R1_1, ... with full details}

## Source 2 Patterns

### Universal Patterns
{U2_0, U2_1, ... with full details}

### Rare Patterns
{R2_0, R2_1, ... with full details}

## Task

### 1. Create Merged Patterns
For patterns that are conceptually similar, create a NEW merged pattern.

Patterns should merge if they:
- Share the same evidence_type AND mapping_pattern combination
- Would lead an auditor to the same mapping decision
- Differ only in description wording (use the more general description)

For each merged pattern:
- Write a new name and description (synthesized from inputs)
- List `derived_from` with ALL input indices that contributed

A pattern can only appear in ONE merged pattern's `derived_from`.

### 2. List Unchanged Universal Patterns
List indices of UNIVERSAL patterns (U*) that did not merge with anything.
These will pass through unchanged.

Do NOT list rare patterns (R*) here - the system handles those automatically.

## Important
- Every input index should either be in a `derived_from` list OR in `unchanged_universal`
- Rare patterns (R*) not in any `derived_from` will automatically remain rare
- Do not invent indices that weren't provided
```

**Response Schema (Template with Runtime Placeholders):**

The schema uses string placeholders that are replaced at runtime with actual valid values.
See **Decision 5** for details on runtime schema injection.

```json
{
  "type": "object",
  "properties": {
    "merged_patterns": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "description": {"type": "string"},
          "evidence_types": {
            "type": "array",
            "items": {"type": "string", "enum": ["explicit_mandate", "procedural_definition", ...]}
          },
          "mapping_patterns": {
            "type": "array",
            "items": {"type": "string", "enum": ["direct_terminology_match", "semantic_equivalence", ...]}
          },
          "derived_from": {
            "type": "array",
            "items": {"type": "string", "enum": "VALID_INDICES"},
            "minItems": 1,
            "maxItems": "TOTAL_INDEX_COUNT",
            "description": "Indices of input patterns merged into this (e.g., ['U1_0', 'R2_1'])"
          }
        },
        "required": ["name", "description", "evidence_types", "mapping_patterns", "derived_from"]
      }
    },
    "unchanged_universal": {
      "type": "array",
      "items": {"type": "string", "enum": "VALID_UNIVERSAL_INDICES"},
      "minItems": 0,
      "maxItems": "TOTAL_UNIVERSAL_COUNT",
      "description": "Indices of universal patterns (U*) that pass through unchanged"
    },
    "consolidation_notes": {
      "type": "string",
      "description": "Brief notes on merge decisions"
    }
  },
  "required": ["merged_patterns", "unchanged_universal"]
}
```

**Placeholder Definitions:**
| Placeholder | Runtime Value | Description |
|-------------|---------------|-------------|
| `"VALID_INDICES"` | `["U1_0", "U1_1", "R1_0", ...]` | All input indices (U* and R*) |
| `"VALID_UNIVERSAL_INDICES"` | `["U1_0", "U1_1", "U2_0", ...]` | Only universal input indices (U*) |
| `"TOTAL_INDEX_COUNT"` | `6` (integer) | Total number of input patterns |
| `"TOTAL_UNIVERSAL_COUNT"` | `3` (integer) | Number of universal input patterns |

## Implementation Plan (TDD Approach)

Each step follows Test-Driven Development: write failing tests first, then implement to make them pass.

---

### Step 1: Data Models - `pattern_id` and `merge_key`

**Test first** (`test_models.py`):
```python
class TestPatternId:
    def test_pattern_id_auto_generated(self):
        """pattern_id is auto-generated from content hash."""
        pattern = AggregatedPattern(
            name="Test",
            description="Desc",
            evidence_types=("explicit_mandate",),
            mapping_patterns=("direct_terminology_match",),
        )
        assert pattern.pattern_id != ""
        assert len(pattern.pattern_id) == 12  # SHA256 prefix

    def test_pattern_id_stable_across_instances(self):
        """Same content produces same pattern_id."""
        p1 = AggregatedPattern(name="Test", description="Desc", ...)
        p2 = AggregatedPattern(name="Test", description="Desc", ...)
        assert p1.pattern_id == p2.pattern_id

    def test_pattern_id_differs_for_different_content(self):
        """Different content produces different pattern_id."""
        p1 = AggregatedPattern(name="Test1", ...)
        p2 = AggregatedPattern(name="Test2", ...)
        assert p1.pattern_id != p2.pattern_id

class TestMergeKey:
    def test_merge_key_is_frozenset_tuple(self):
        """merge_key returns canonical frozenset tuple."""
        pattern = AggregatedPattern(
            evidence_types=("b", "a"),
            mapping_patterns=("y", "x"),
            ...
        )
        key = pattern.merge_key
        assert key == (frozenset({"a", "b"}), frozenset({"x", "y"}))

    def test_merge_key_equal_for_same_types(self):
        """Patterns with same types have equal merge_key."""
        p1 = AggregatedPattern(evidence_types=("a", "b"), mapping_patterns=("x",), ...)
        p2 = AggregatedPattern(evidence_types=("b", "a"), mapping_patterns=("x",), ...)
        assert p1.merge_key == p2.merge_key
```

**Implement** (`models.py`):
1. Add `pattern_id: str = ""` field with `__post_init__` auto-generation
2. Add `merge_key` property returning `(frozenset, frozenset)`

---

### Step 2: Data Models - Universal/Rare Split

**Test first** (`test_models.py`):
```python
class TestRoundOutputSplit:
    def test_round_output_has_universal_and_rare(self):
        """RoundOutput has separate universal_patterns and rare_patterns."""
        output = RoundOutput(
            round_num=2,
            pair_id="test",
            universal_patterns=(pattern1,),
            rare_patterns=(pattern2, pattern3),
            source_policies=("policy1",),
        )
        assert len(output.universal_patterns) == 1
        assert len(output.rare_patterns) == 2

    def test_all_patterns_combines_both(self):
        """all_patterns property returns universal + rare."""
        output = RoundOutput(universal_patterns=(p1,), rare_patterns=(p2,), ...)
        assert output.all_patterns == (p1, p2)

    def test_to_dict_includes_both(self):
        """to_dict() serializes both pattern lists."""
        output = RoundOutput(...)
        d = output.to_dict()
        assert "universal_patterns" in d
        assert "rare_patterns" in d

    def test_from_dict_restores_both(self):
        """from_dict() restores both pattern lists."""
        d = {"universal_patterns": [...], "rare_patterns": [...], ...}
        output = RoundOutput.from_dict(d)
        assert len(output.universal_patterns) > 0
```

**Implement** (`models.py`):
1. Replace `patterns` with `universal_patterns` and `rare_patterns`
2. Add `all_patterns` property
3. Update `to_dict()` and `from_dict()`

---

### Step 3: Schema Enum Injection

**Test first** (`test_aggregator.py`):
```python
class TestSchemaEnumInjection:
    def test_injects_valid_indices_enum(self):
        """VALID_INDICES placeholder replaced with index list."""
        template = {"items": {"enum": "VALID_INDICES"}}
        result = _inject_schema_enums(template, ["U1_0", "R1_0"], ["U1_0"])
        assert result["items"]["enum"] == ["U1_0", "R1_0"]

    def test_injects_valid_universal_indices_enum(self):
        """VALID_UNIVERSAL_INDICES placeholder replaced."""
        template = {"items": {"enum": "VALID_UNIVERSAL_INDICES"}}
        result = _inject_schema_enums(template, ["U1_0", "R1_0"], ["U1_0"])
        assert result["items"]["enum"] == ["U1_0"]

    def test_injects_total_index_count(self):
        """TOTAL_INDEX_COUNT placeholder replaced with integer."""
        template = {"maxItems": "TOTAL_INDEX_COUNT"}
        result = _inject_schema_enums(template, ["U1_0", "R1_0", "R1_1"], [])
        assert result["maxItems"] == 3

    def test_injects_total_universal_count(self):
        """TOTAL_UNIVERSAL_COUNT placeholder replaced with integer."""
        template = {"maxItems": "TOTAL_UNIVERSAL_COUNT"}
        result = _inject_schema_enums(template, ["U1_0", "R1_0"], ["U1_0"])
        assert result["maxItems"] == 1

    def test_handles_nested_placeholders(self):
        """Placeholders in nested structures are replaced."""
        template = {
            "properties": {
                "derived_from": {
                    "items": {"enum": "VALID_INDICES"},
                    "maxItems": "TOTAL_INDEX_COUNT"
                }
            }
        }
        result = _inject_schema_enums(template, ["U1_0", "U1_1"], ["U1_0", "U1_1"])
        assert result["properties"]["derived_from"]["items"]["enum"] == ["U1_0", "U1_1"]
        assert result["properties"]["derived_from"]["maxItems"] == 2

    def test_empty_universal_indices(self):
        """Handles Round 2 case where no universals exist yet."""
        template = {"items": {"enum": "VALID_UNIVERSAL_INDICES"}, "maxItems": "TOTAL_UNIVERSAL_COUNT"}
        result = _inject_schema_enums(template, ["R1_0", "R1_1"], [])
        assert result["items"]["enum"] == []
        assert result["maxItems"] == 0
```

**Implement** (`aggregator.py`):
1. Add `_inject_schema_enums(schema_template, all_indices, universal_indices)` method

---

### Step 4: Pattern Index Formatting

**Test first** (`test_aggregator.py`):
```python
class TestPatternIndexFormatting:
    def test_format_indexed_patterns_universal(self):
        """Universal patterns get U prefix with source index."""
        patterns = [pattern1, pattern2]
        result = _format_indexed_patterns(patterns, prefix="U", source_num=1)
        assert "U1_0:" in result
        assert "U1_1:" in result

    def test_format_indexed_patterns_rare(self):
        """Rare patterns get R prefix."""
        patterns = [pattern1]
        result = _format_indexed_patterns(patterns, prefix="R", source_num=2)
        assert "R2_0:" in result

    def test_build_pattern_index_map(self):
        """Index map correctly maps indices to patterns."""
        left_output = RoundOutput(universal_patterns=(p1,), rare_patterns=(p2,), ...)
        right_output = RoundOutput(universal_patterns=(p3,), rare_patterns=(), ...)

        index_map = _build_pattern_index_map(left_output, right_output)

        assert index_map["U1_0"] == p1
        assert index_map["R1_0"] == p2
        assert index_map["U2_0"] == p3
```

**Implement** (`aggregator.py`):
1. Add `_format_indexed_patterns(patterns, prefix, source_num)` method
2. Add `_build_pattern_index_map(left, right)` method

---

### Step 5: Consolidation Response Parsing

**Test first** (`test_aggregator.py`):
```python
class TestConsolidationParsing:
    def test_parses_merged_patterns(self):
        """Merged patterns are created with merged source_policy_ids."""
        response = {
            "merged_patterns": [{
                "name": "Merged",
                "description": "Combined",
                "evidence_types": ["explicit_mandate"],
                "mapping_patterns": ["direct_terminology_match"],
                "derived_from": ["U1_0", "R2_0"]
            }],
            "unchanged_universal": []
        }
        index_map = {
            "U1_0": AggregatedPattern(..., source_policy_ids=("policy1",)),
            "R2_0": AggregatedPattern(..., source_policy_ids=("policy2",)),
        }

        universal, rare = _parse_consolidation_response(response, index_map, {"U1_0", "R2_0"})

        assert len(universal) == 1
        assert set(universal[0].source_policy_ids) == {"policy1", "policy2"}

    def test_unchanged_universal_passed_through(self):
        """Unchanged universal patterns are passed through verbatim."""
        response = {"merged_patterns": [], "unchanged_universal": ["U1_0"]}
        index_map = {"U1_0": original_pattern, "R1_0": rare_pattern}

        universal, rare = _parse_consolidation_response(response, index_map, {"U1_0", "R1_0"})

        assert original_pattern in universal
        assert rare_pattern in rare  # Computed as leftover

    def test_still_rare_computed_from_leftover(self):
        """Rare patterns not in derived_from remain rare."""
        response = {"merged_patterns": [], "unchanged_universal": []}
        index_map = {"R1_0": rare1, "R1_1": rare2}

        universal, rare = _parse_consolidation_response(response, index_map, {"R1_0", "R1_1"})

        assert len(universal) == 0
        assert len(rare) == 2

    def test_invalid_indices_ignored_with_warning(self):
        """Invalid indices in derived_from are ignored."""
        response = {
            "merged_patterns": [{
                "derived_from": ["U1_0", "INVALID_99"],
                ...
            }],
            "unchanged_universal": []
        }
        index_map = {"U1_0": pattern}

        # Should not raise, should log warning
        universal, rare = _parse_consolidation_response(response, index_map, {"U1_0"})
        assert len(universal) == 1

    def test_coverage_invariant_holds(self):
        """Every input index is accounted for (no pattern loss)."""
        response = {
            "merged_patterns": [{"derived_from": ["U1_0", "R1_0"], ...}],
            "unchanged_universal": ["U1_1"]
        }
        index_map = {"U1_0": p1, "U1_1": p2, "R1_0": p3, "R1_1": p4}
        input_indices = {"U1_0", "U1_1", "R1_0", "R1_1"}

        universal, rare = _parse_consolidation_response(response, index_map, input_indices)

        # R1_1 should appear in rare (leftover)
        all_output_ids = {p.pattern_id for p in universal + rare}
        all_input_ids = {p.pattern_id for p in index_map.values()}
        assert all_output_ids == all_input_ids  # No loss
```

**Implement** (`aggregator.py`):
1. Add `_parse_consolidation_response(response, index_map, input_indices)` method

---

### Step 6: Round 1 Produces Only Rare

**Test first** (`test_aggregator.py`):
```python
class TestRound1Semantics:
    def test_round1_outputs_only_rare_patterns(self):
        """Round 1 places all patterns in rare_patterns."""
        # Mock LLM response with patterns
        mock_response = {"patterns": [{"name": "P1", ...}, {"name": "P2", ...}]}

        result = aggregator.aggregate_pair(left_reasons, right_reasons, round_num=1, ...)

        assert len(result.universal_patterns) == 0
        assert len(result.rare_patterns) == 2

    def test_round1_patterns_have_source_count_1(self):
        """Round 1 patterns have single source policy."""
        result = aggregator.aggregate_pair(..., round_num=1, ...)

        for pattern in result.rare_patterns:
            assert len(pattern.source_policy_ids) == 1
```

**Implement** (`aggregator.py`):
1. Update `aggregate_pair()` to place all Round 1 patterns in `rare_patterns`

---

### Step 7: Output Writer - Separate Files

**Test first** (`test_output_writer.py`):
```python
class TestSeparateOutputFiles:
    def test_writes_final_output_json(self, tmp_path):
        """final_output.json contains complete RoundOutput."""
        writer = AggregatorOutputWriter(output_dir=tmp_path)
        output = RoundOutput(universal_patterns=(...), rare_patterns=(...), ...)

        writer.write_final_output(output)

        assert (tmp_path / "final_output.json").exists()
        data = json.loads((tmp_path / "final_output.json").read_text())
        assert "universal_patterns" in data
        assert "rare_patterns" in data

    def test_writes_universal_patterns_md(self, tmp_path):
        """universal_patterns.md contains only universal patterns."""
        writer = AggregatorOutputWriter(output_dir=tmp_path)
        output = RoundOutput(
            universal_patterns=(p1, p2),
            rare_patterns=(p3,),
            ...
        )

        writer.write_final_output(output)

        md_path = tmp_path / "universal_patterns.md"
        assert md_path.exists()
        content = md_path.read_text()
        assert "# Universal Patterns" in content
        assert p1.name in content
        assert p3.name not in content  # Rare should not appear

    def test_writes_rare_patterns_md(self, tmp_path):
        """rare_patterns.md contains only rare patterns."""
        writer = AggregatorOutputWriter(output_dir=tmp_path)
        output = RoundOutput(
            universal_patterns=(p1,),
            rare_patterns=(p2, p3),
            ...
        )

        writer.write_final_output(output)

        md_path = tmp_path / "rare_patterns.md"
        assert md_path.exists()
        content = md_path.read_text()
        assert "# Rare Patterns" in content
        assert p2.name in content
        assert p1.name not in content  # Universal should not appear

    def test_universal_patterns_sorted_by_source_count(self, tmp_path):
        """Universal patterns sorted by source_policy_ids count descending."""
        p_high = AggregatedPattern(..., source_policy_ids=("a", "b", "c"))
        p_low = AggregatedPattern(..., source_policy_ids=("x",))
        output = RoundOutput(universal_patterns=(p_low, p_high), ...)

        writer.write_final_output(output)

        content = (tmp_path / "universal_patterns.md").read_text()
        # p_high should appear before p_low
        assert content.index(p_high.name) < content.index(p_low.name)
```

**Implement** (`output_writer.py`):
1. Update `write_final_output()` to write three files
2. Add `_format_universal_patterns_md()` method
3. Add `_format_rare_patterns_md()` method

---

### Step 8: Configuration

**Test first** (`test_config.py`):
```python
class TestConsolidationConfig:
    def test_consolidation_prompts_dir_exists(self):
        """consolidation_prompts_dir points to valid directory."""
        config = AggregatorConfig()
        assert config.consolidation_prompts_dir.exists()

    def test_consolidation_temperature_default(self):
        """consolidation_temperature defaults to 0.3."""
        config = AggregatorConfig()
        assert config.consolidation_temperature == 0.3

    def test_max_retry_on_invalid_default(self):
        """max_retry_on_invalid defaults to 1."""
        config = AggregatorConfig()
        assert config.max_retry_on_invalid == 1
```

**Implement** (`config.py`):
1. Add `consolidation_prompts_dir` path
2. Add `consolidation_temperature: float = 0.3`
3. Add `max_retry_on_invalid: int = 1`

---

### Step 9: Create Round 2+ Prompts

**No automated tests** (prompt files are static assets).

**Implement**:
1. Create `prompts/consolidate_patterns/` directory
2. Write `system` prompt
3. Write `user` prompt with placeholders for indexed patterns
4. Write `response.json` schema template with enum placeholders

---

### Step 10: Validation & Retry

**Test first** (`test_aggregator.py`):
```python
class TestValidationAndRetry:
    def test_retries_on_high_invalid_index_rate(self, mock_genai):
        """Retries once when >20% of indices are invalid."""
        # First call returns many invalid indices
        # Second call returns valid response
        mock_genai.side_effect = [bad_response, good_response]

        result = aggregator.aggregate_pair(...)

        assert mock_genai.call_count == 2

    def test_proceeds_after_retry_exhausted(self, mock_genai):
        """After retry, proceeds with best-effort parsing."""
        mock_genai.return_value = response_with_some_invalid

        # Should not raise
        result = aggregator.aggregate_pair(...)
        assert result is not None
```

**Implement** (`aggregator.py`):
1. Add validation check for invalid index rate
2. Add retry logic with error message
3. Proceed with best-effort after retry

---

### Step 11: Observability

**Test first** (`test_aggregator.py`):
```python
class TestObservability:
    def test_logs_pattern_counts(self, caplog):
        """Logs universal and rare counts per round."""
        aggregator.aggregate_pair(...)

        assert "universal_count" in caplog.text
        assert "rare_count" in caplog.text

    def test_logs_merge_rate(self, caplog):
        """Logs merge rate (consumed/total)."""
        aggregator.aggregate_pair(...)

        assert "merge_rate" in caplog.text
```

**Implement** (`aggregator.py`):
1. Add structured logging for pattern counts
2. Add merge rate calculation and logging
3. Add invalid index rate logging

## File Changes Summary

| File | Changes |
|------|---------|
| `models.py` | Add `pattern_id`, `merge_key`, split universal/rare |
| `aggregator.py` | Round-aware prompts, index-based parsing, schema injection, validation, retry |
| `output_writer.py` | Separate output files: `universal_patterns.md`, `rare_patterns.md`, `final_output.json` |
| `config.py` | Add consolidation config |
| `prompts/consolidate_patterns/*` | NEW: Round 2+ prompts with schema placeholders |
| `prompts/aggregate_reasons/user` | Remove anti-consolidation language |
| `test_*.py` | Update for new data model + validation + schema injection tests |

## Phase 1 Output Files

When Phase 1 (map-reduce collection) completes, the following files are written:

```
aggregated_patterns/
├── round_1/
│   ├── pair_0.json
│   ├── pair_1.json
│   └── ...
├── round_2/
│   └── ...
├── ...
├── final_output.json           # Complete RoundOutput (universal + rare)
├── universal_patterns.md       # Human-readable universal patterns
└── rare_patterns.md            # Human-readable rare/edge-case patterns
```

## Success Criteria

1. **No pattern loss**: Coverage invariant holds (every input accounted for)
2. **No text drift**: Universal patterns only regenerated when merged
3. **Correct semantics**: Round 1 produces rare, Round 2+ graduates to universal
4. **Pattern count**: 37 policies → ~30-50 universal + ~50-80 rare (not 100+ total)
5. **Provenance**: Every pattern traces to source policies via `pattern_id` chain
6. **Validation**: Invalid indices logged and handled gracefully
7. **Schema-level constraints**: Index fields constrained via runtime enum injection; LLM cannot output indices not in the input set

## Future Work (Phase 2: Distillation)

After this implementation, add a distillation step:

```python
def distill(final_output: RoundOutput) -> DistilledHeuristics:
    """
    Take ~30-50 universal patterns + ~50-80 rare patterns.
    Produce exactly 10-15 actionable heuristics.
    """
```

Distillation considerations (from ChatGPT review):
- May need chunking if patterns are verbose
- Could distill universal first, then attach edge-case notes from top rare patterns
- Should prioritize by `len(source_policy_ids)`

## Appendix: Review Synthesis

This plan incorporates feedback from external reviews:

**From Gemini 3 Analysis:**
- Added `unchanged_universal` to prevent text drift
- Changed Round 1 to produce rare patterns
- Added eager provenance resolution guidance
- Added hallucinated index validation

**From ChatGPT Analysis:**
- Removed `still_rare` from schema (code-computed instead)
- Added stable `pattern_id` for cross-round provenance
- Added `merge_key` for canonical merge comparison
- Added coverage invariant with hard assertions
- Added validation + retry behavior
- Added observability recommendations
