# Final Plan: From Descriptive Patterns to Decision Rules

## Synthesis of Three Analyses

We received feedback from three different AI systems (Opus 4.5, Gemini 3, ChatGPT 5.2 Pro). This document synthesizes their recommendations into a unified implementation plan.

### Universal Agreement (All 3 Analyses)

| Insight | Opus 4.5 | Gemini 3 | ChatGPT |
|---------|----------|----------|---------|
| Problem is **descriptive vs prescriptive** | ✓ | ✓ | ✓ |
| Need to **reframe prompts** from "find patterns" to "extract decision rules" | ✓ | ✓ | ✓ |
| Schema must **enforce actionability** | ✓ | ✓ | ✓ |
| Need **failure conditions/negatives** to enable discrimination | ✓ | ✓ | ✓ |

### Strong Agreement (2 of 3)

| Insight | Opus 4.5 | Gemini 3 | ChatGPT |
|---------|----------|----------|---------|
| **Atomic patterns** (1 evidence_type, 1 mapping_pattern) | | ✓ | ✓ |
| **Control signals** needed (abstracted, not IDs) | ✓ | ✓ | ✓ |
| Current **reduce over-merges** | ✓ | | ✓ |

### Unique Valuable Contributions

| Source | Key Insight |
|--------|-------------|
| **Gemini 3** | "Think like writing `def does_policy_map(control, policy):`" — algorithmic framing |
| **ChatGPT** | Specific schema: `control_triggers`, `policy_cues`, `insufficient_evidence`, `false_positive_risks` |
| **Opus 4.5** | Phased approach — test cheap changes first before restructuring data |

---

## The Core Problem (Consensus View)

All three analyses agree on the root cause:

> **We asked for abstraction and got abstraction.**

The prompts explicitly said:
- "Do NOT include control-specific details"
- "Aim for patterns that could be applied to ANY policy-control mapping"
- "Use the more general description when merging"

This naturally produced descriptions of what **all policies have in common**—which is precisely what we got. The patterns are correct but not discriminative.

**What we need instead**: Decision rules that help an auditor (or LLM) **decide** whether a specific policy maps to a specific control.

---

## Critical Constraint: Generalization vs Overfitting

### The New Risk

While fixing the "too generic" problem, we must avoid creating a new problem: **overfitting to the 780 training controls**.

Our ground truth was generated from 780 specific controls. But the endpoint could be invoked with **any controls**—including custom ones. If we get too specific, we:
- Overfit to terminology in those 780 controls
- Won't generalize to controls using different vocabulary
- Could end up with hundreds of narrow rules instead of ~15-20 actionable meta-rules

### The Sweet Spot: Meta-Rules About Evidence Structure

| Level | Example | Problem |
|-------|---------|---------|
| **Too Generic** | "Policy has technical specifications" | Matches everything, no discrimination |
| **Too Specific** | "Look for AES-256, RSA-2048, TLS 1.2" | Overfits to specific controls, won't generalize |
| **Sweet Spot** | "If control requires cryptographic protection, policy should specify named algorithms and key strengths (not just 'encrypted')" | Describes TYPE of evidence needed |

### The Principle

Rules should describe **what KIND of evidence satisfies what KIND of requirement**—not enumerate specific terms.

- **Control triggers** = semantic categories (what the control is *asking for*)
- **Policy cues** = evidence structure (what *type of specificity* is needed)
- **Not** = literal terms that overfit to 780 controls

**Bad (overfitting)**:
```
Control Triggers: ["AES", "RSA", "SHA-256", "TLS 1.2"]
Policy Cues: ["AES-256 encryption", "RSA-2048 keys"]
```

**Good (generalizable)**:
```
Control Triggers: ["encrypt", "cryptographic", "cipher", "protection mechanism"]
Policy Cues: ["named algorithms (not just 'encrypted')", "specified key lengths or strengths"]
```

The distinction: we describe the **structure** of evidence (named vs generic, quantified vs vague) rather than **specific terms**.

---

## Test-Driven Development Strategy

Before implementing any changes, we define tests that encode our success criteria. This ensures we know exactly what "good" looks like before writing code.

### TDD Workflow

```
1. Write failing tests that define expected behavior
2. Implement minimum code to make tests pass
3. Refactor while keeping tests green
4. Repeat for next component
```

### Test Categories

| Category | Purpose | Location |
|----------|---------|----------|
| **Unit Tests: Models** | Validate DecisionRule dataclass structure and validation | `tests/scripts/experiments/test_models.py` |
| **Unit Tests: Parsing** | Validate LLM response → DecisionRule conversion | `tests/scripts/experiments/test_parsing.py` |
| **Unit Tests: Quality Validators** | Validate rules meet actionability/discrimination criteria | `tests/scripts/experiments/test_quality_validators.py` |
| **Golden Examples** | Fixed input → expected output pairs | `tests/scripts/experiments/fixtures/` |
| **Integration Tests** | End-to-end aggregation pipeline | `tests/scripts/experiments/test_aggregation_integration.py` |

---

### Test Phase 1: Define Golden Examples (Write First)

Before any implementation, create test fixtures that represent **what good output looks like**:

```python
# tests/scripts/experiments/fixtures/golden_rules.py

GOLDEN_RULE_EXAMPLES = [
    {
        "rule_name": "Technical Specificity Requirement",
        "control_triggers": ["encrypt", "cryptographic", "protect confidentiality"],
        "policy_cues": ["named algorithms (not just 'encrypted')", "specified key lengths"],
        "decision_effect": "supports_mapping",
        "success_criteria": "Policy specifies HOW (named methods) not just THAT (generic statement)",
        "failure_mode": "Policy uses vague terms without technical specifics",
        "insufficient_evidence": "'Data is encrypted' without algorithm specification",
        "evidence_type": "technical_specification",
        "mapping_pattern": "implementation_detail",
        "observed_in": ["source_1", "source_2"],
    },
    # ... more golden examples
]

# Counter-examples: rules that should FAIL quality checks
BAD_RULE_EXAMPLES = [
    {
        # Too generic - matches everything
        "rule_name": "Comprehensive Scope",
        "control_triggers": ["scope", "applies to"],
        "policy_cues": ["defines scope"],  # All policies do this
        "decision_effect": "supports_mapping",
        "success_criteria": "Policy has a scope section",
        "failure_mode": "No scope section",
        "insufficient_evidence": "",
        "evidence_type": "scope_definition",
        "mapping_pattern": "scope_inclusion",
        "observed_in": ["source_1"],
    },
    {
        # Too specific - overfits to training data
        "rule_name": "AES Encryption Check",
        "control_triggers": ["AES-256", "RSA-2048"],  # Specific terms!
        "policy_cues": ["mentions AES-256"],  # Specific terms!
        "decision_effect": "supports_mapping",
        "success_criteria": "Policy mentions AES-256",
        "failure_mode": "No AES-256 mentioned",
        "insufficient_evidence": "",
        "evidence_type": "technical_specification",
        "mapping_pattern": "direct_terminology_match",
        "observed_in": ["source_1"],
    },
]
```

---

### Test Phase 2: Quality Validator Tests (Write Before Implementation)

Define tests for rule quality validation **before** implementing the validators:

```python
# tests/scripts/experiments/test_quality_validators.py

import pytest
from ai_services.scripts.experiments.control_detection.quality_validators import (
    is_actionable,
    is_discriminative,
    is_atomic,
    is_generalizable,
    has_failure_mode,
    validate_rule_quality,
    RuleQualityResult,
)
from .fixtures.golden_rules import GOLDEN_RULE_EXAMPLES, BAD_RULE_EXAMPLES


class TestActionabilityValidator:
    """Rules must be usable by an auditor to check a new policy."""

    def test_golden_rules_are_actionable(self):
        for rule in GOLDEN_RULE_EXAMPLES:
            assert is_actionable(rule), f"Golden rule should be actionable: {rule['rule_name']}"

    def test_rejects_vague_policy_cues(self):
        rule = {
            "policy_cues": ["has technical specifications"],  # Too vague
            "control_triggers": ["encrypt"],
        }
        assert not is_actionable(rule)

    def test_requires_specific_evidence_to_look_for(self):
        rule = {
            "policy_cues": ["named algorithms", "specified key lengths"],  # Specific
            "control_triggers": ["encrypt", "cryptographic"],
        }
        assert is_actionable(rule)


class TestDiscriminationValidator:
    """Rules must distinguish between control types, not match everything."""

    # Known phrases that indicate non-discriminative rules
    UNIVERSAL_PHRASES = [
        "defines scope",
        "uses mandatory language",
        "assigns responsibilities",
        "has procedures",
    ]

    def test_rejects_universal_patterns(self):
        for phrase in self.UNIVERSAL_PHRASES:
            rule = {"policy_cues": [phrase], "rule_name": "Test"}
            assert not is_discriminative(rule), f"Should reject universal phrase: {phrase}"

    def test_accepts_discriminative_patterns(self):
        rule = {
            "policy_cues": ["named algorithms", "specified key lengths"],
            "control_triggers": ["encrypt", "cryptographic"],
        }
        assert is_discriminative(rule)


class TestAtomicityValidator:
    """Rules must have exactly ONE evidence_type and ONE mapping_pattern."""

    def test_golden_rules_are_atomic(self):
        for rule in GOLDEN_RULE_EXAMPLES:
            assert is_atomic(rule), f"Golden rule should be atomic: {rule['rule_name']}"

    def test_rejects_array_evidence_types(self):
        rule = {
            "evidence_type": ["technical_specification", "scope_definition"],  # Array!
            "mapping_pattern": "implementation_detail",
        }
        assert not is_atomic(rule)


class TestGeneralizationValidator:
    """Rules must not overfit to specific terms from training data."""

    OVERFITTING_INDICATORS = [
        "AES-256", "RSA-2048", "TLS 1.2",  # Specific algorithms
        "24 hours", "72 hours", "annually",  # Specific time periods
        "CISO", "DPO", "ISO 27001",  # Specific roles/standards
    ]

    def test_rejects_overfitting_terms_in_triggers(self):
        for term in self.OVERFITTING_INDICATORS:
            rule = {"control_triggers": [term], "policy_cues": ["named algorithms"]}
            assert not is_generalizable(rule), f"Should reject overfitting term: {term}"

    def test_rejects_overfitting_terms_in_cues(self):
        for term in self.OVERFITTING_INDICATORS:
            rule = {"control_triggers": ["encrypt"], "policy_cues": [term]}
            assert not is_generalizable(rule), f"Should reject overfitting term: {term}"

    def test_accepts_structural_descriptions(self):
        rule = {
            "control_triggers": ["encrypt", "cryptographic"],
            "policy_cues": ["named algorithms", "specified key lengths"],
        }
        assert is_generalizable(rule)


class TestFailureModeValidator:
    """Rules must specify what would invalidate a match."""

    def test_golden_rules_have_failure_modes(self):
        for rule in GOLDEN_RULE_EXAMPLES:
            assert has_failure_mode(rule), f"Golden rule should have failure_mode: {rule['rule_name']}"

    def test_rejects_empty_failure_mode(self):
        rule = {"failure_mode": "", "insufficient_evidence": ""}
        assert not has_failure_mode(rule)


class TestFullQualityValidation:
    """Integration test for complete rule validation."""

    def test_golden_rules_pass_all_checks(self):
        for rule in GOLDEN_RULE_EXAMPLES:
            result = validate_rule_quality(rule)
            assert result.passes_all, f"Golden rule failed: {rule['rule_name']}, failures: {result.failures}"

    def test_bad_rules_fail_at_least_one_check(self):
        for rule in BAD_RULE_EXAMPLES:
            result = validate_rule_quality(rule)
            assert not result.passes_all, f"Bad rule should fail: {rule['rule_name']}"
```

---

### Test Phase 3: Model Tests (Write Before models.py Changes)

```python
# tests/scripts/experiments/test_models.py

import pytest
from ai_services.scripts.experiments.control_detection.models import (
    DecisionRule,
    EvidenceType,
    MappingPattern,
    DecisionEffect,
)


class TestDecisionRuleModel:
    """Test the DecisionRule dataclass structure."""

    def test_creates_valid_rule(self):
        rule = DecisionRule(
            rule_name="Technical Specificity Requirement",
            control_triggers=["encrypt", "cryptographic"],
            policy_cues=["named algorithms", "specified key lengths"],
            decision_effect=DecisionEffect.SUPPORTS_MAPPING,
            success_criteria="Policy specifies HOW not just THAT",
            failure_mode="Vague terms without specifics",
            insufficient_evidence="'Data is encrypted' without algorithm",
            evidence_type=EvidenceType.TECHNICAL_SPECIFICATION,
            mapping_pattern=MappingPattern.IMPLEMENTATION_DETAIL,
            observed_in=["source_1", "source_2"],
        )
        assert rule.rule_name == "Technical Specificity Requirement"
        assert len(rule.control_triggers) == 2

    def test_evidence_type_is_single_value(self):
        """Enforce atomicity: evidence_type must be a single enum, not a list."""
        with pytest.raises((TypeError, ValueError)):
            DecisionRule(
                rule_name="Test",
                control_triggers=["test"],
                policy_cues=["test"],
                decision_effect=DecisionEffect.SUPPORTS_MAPPING,
                success_criteria="test",
                failure_mode="test",
                insufficient_evidence="test",
                evidence_type=[EvidenceType.TECHNICAL_SPECIFICATION],  # Should fail!
                mapping_pattern=MappingPattern.IMPLEMENTATION_DETAIL,
                observed_in=["source_1"],
            )

    def test_to_dict_serialization(self):
        rule = DecisionRule(
            rule_name="Test Rule",
            control_triggers=["encrypt"],
            policy_cues=["named algorithms"],
            decision_effect=DecisionEffect.SUPPORTS_MAPPING,
            success_criteria="test",
            failure_mode="test",
            insufficient_evidence="test",
            evidence_type=EvidenceType.TECHNICAL_SPECIFICATION,
            mapping_pattern=MappingPattern.IMPLEMENTATION_DETAIL,
            observed_in=["source_1"],
        )
        d = rule.to_dict()
        assert d["rule_name"] == "Test Rule"
        assert d["evidence_type"] == "technical_specification"

    def test_from_dict_deserialization(self):
        data = {
            "rule_name": "Test Rule",
            "control_triggers": ["encrypt"],
            "policy_cues": ["named algorithms"],
            "decision_effect": "supports_mapping",
            "success_criteria": "test",
            "failure_mode": "test",
            "insufficient_evidence": "test",
            "evidence_type": "technical_specification",
            "mapping_pattern": "implementation_detail",
            "observed_in": ["source_1"],
        }
        rule = DecisionRule.from_dict(data)
        assert rule.rule_name == "Test Rule"
        assert rule.evidence_type == EvidenceType.TECHNICAL_SPECIFICATION
```

---

### Test Phase 4: Parsing Tests (Write Before aggregator.py Changes)

```python
# tests/scripts/experiments/test_parsing.py

import pytest
from ai_services.scripts.experiments.control_detection.aggregator import (
    parse_llm_response,
    ParseError,
)


class TestLLMResponseParsing:
    """Test parsing LLM JSON responses into DecisionRule objects."""

    def test_parses_valid_response(self):
        llm_response = {
            "decision_rules": [
                {
                    "rule_name": "Test Rule",
                    "control_triggers": ["encrypt"],
                    "policy_cues": ["named algorithms"],
                    "decision_effect": "supports_mapping",
                    "success_criteria": "test",
                    "failure_mode": "test",
                    "insufficient_evidence": "test",
                    "evidence_type": "technical_specification",
                    "mapping_pattern": "implementation_detail",
                    "observed_in": ["source_1"],
                }
            ]
        }
        rules = parse_llm_response(llm_response)
        assert len(rules) == 1
        assert rules[0].rule_name == "Test Rule"

    def test_handles_missing_required_field(self):
        llm_response = {
            "decision_rules": [
                {
                    "rule_name": "Test Rule",
                    # Missing control_triggers!
                    "policy_cues": ["named algorithms"],
                    "decision_effect": "supports_mapping",
                }
            ]
        }
        with pytest.raises(ParseError):
            parse_llm_response(llm_response)

    def test_handles_invalid_enum_value(self):
        llm_response = {
            "decision_rules": [
                {
                    "rule_name": "Test Rule",
                    "control_triggers": ["encrypt"],
                    "policy_cues": ["named algorithms"],
                    "decision_effect": "invalid_value",  # Invalid!
                    "success_criteria": "test",
                    "failure_mode": "test",
                    "insufficient_evidence": "test",
                    "evidence_type": "technical_specification",
                    "mapping_pattern": "implementation_detail",
                    "observed_in": ["source_1"],
                }
            ]
        }
        with pytest.raises(ParseError):
            parse_llm_response(llm_response)

    def test_handles_old_patterns_format_gracefully(self):
        """If LLM returns old 'patterns' format, raise clear error."""
        llm_response = {
            "patterns": [  # Old format!
                {"name": "Old Pattern", "description": "..."}
            ]
        }
        with pytest.raises(ParseError, match="Expected 'decision_rules'"):
            parse_llm_response(llm_response)
```

---

### Test Phase 5: Integration Tests (Write Before Running Full Pipeline)

```python
# tests/scripts/experiments/test_aggregation_integration.py

import pytest
from ai_services.scripts.experiments.control_detection.aggregator import ReasonAggregator
from ai_services.scripts.experiments.control_detection.quality_validators import validate_rule_quality


class TestAggregationPipelineIntegration:
    """End-to-end tests for the aggregation pipeline."""

    @pytest.fixture
    def sample_input_reasons(self):
        """Minimal realistic input for testing."""
        return {
            "source_1": [
                "Policy specifies AES-256 encryption for data at rest",
                "Policy mandates TLS for data in transit",
            ],
            "source_2": [
                "Policy defines role-based access controls",
                "Policy assigns data protection responsibilities to named owners",
            ],
        }

    @pytest.mark.integration
    async def test_produces_valid_decision_rules(self, sample_input_reasons):
        """Output should be valid DecisionRule objects."""
        aggregator = ReasonAggregator()
        results = await aggregator.aggregate(sample_input_reasons)

        assert len(results.decision_rules) > 0
        for rule in results.decision_rules:
            # All rules should be valid DecisionRule instances
            assert hasattr(rule, "rule_name")
            assert hasattr(rule, "control_triggers")
            assert hasattr(rule, "policy_cues")

    @pytest.mark.integration
    async def test_rules_pass_quality_checks(self, sample_input_reasons):
        """All output rules should pass quality validation."""
        aggregator = ReasonAggregator()
        results = await aggregator.aggregate(sample_input_reasons)

        failing_rules = []
        for rule in results.decision_rules:
            quality = validate_rule_quality(rule.to_dict())
            if not quality.passes_all:
                failing_rules.append((rule.rule_name, quality.failures))

        assert len(failing_rules) == 0, f"Rules failed quality checks: {failing_rules}"

    @pytest.mark.integration
    async def test_no_universal_patterns_in_output(self, sample_input_reasons):
        """Output should not contain the generic patterns we're trying to eliminate."""
        aggregator = ReasonAggregator()
        results = await aggregator.aggregate(sample_input_reasons)

        universal_pattern_names = [
            "Comprehensive Scope",
            "Explicit Mandate",
            "Procedural Definition",
        ]

        for rule in results.decision_rules:
            assert rule.rule_name not in universal_pattern_names, \
                f"Should not produce universal pattern: {rule.rule_name}"
```

---

## Implementation Plan (TDD Approach)

### Phase 1: Schema + Prompt Overhaul (Highest Impact)

This is the **most impactful change** according to all three analyses. If we change the shape of the container, the LLM will change the shape of the output.

#### 1.1 New Response Schema (Round 1)

Replace the current `patterns` schema with a `decision_rules` schema that **enforces** actionable structure:

```json
{
  "type": "object",
  "properties": {
    "decision_rules": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "rule_name": {
            "type": "string",
            "description": "Action-oriented name (e.g., 'Verify Encryption Algorithm Specification')"
          },
          "control_triggers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Phrases/verbs/nouns in a control that activate this rule (e.g., ['encrypt', 'cryptographic', 'cipher'])"
          },
          "policy_cues": {
            "type": "array",
            "items": {"type": "string"},
            "description": "What to look for in policy text (e.g., ['algorithm names', 'key lengths', 'encryption at rest/transit'])"
          },
          "decision_effect": {
            "type": "string",
            "enum": ["supports_mapping", "weak_support", "blocks_mapping"],
            "description": "How this evidence affects the mapping decision"
          },
          "success_criteria": {
            "type": "string",
            "description": "Logical condition that confirms the match (e.g., 'Policy specifies algorithm AND key length')"
          },
          "failure_mode": {
            "type": "string",
            "description": "What would invalidate or weaken this match"
          },
          "insufficient_evidence": {
            "type": "string",
            "description": "What does NOT count as sufficient evidence"
          },
          "evidence_type": {
            "type": "string",
            "enum": ["explicit_mandate", "procedural_definition", "responsibility_assignment", "scope_definition", "frequency_timing", "technical_specification", "standard_reference", "exception_handling", "artifact_reference"],
            "description": "Exactly ONE evidence type (atomic)"
          },
          "mapping_pattern": {
            "type": "string",
            "enum": ["direct_terminology_match", "semantic_equivalence", "scope_inclusion", "implementation_detail", "process_alignment", "ownership_alignment", "negative_constraint"],
            "description": "Exactly ONE mapping pattern (atomic)"
          },
          "observed_in": {
            "type": "array",
            "items": {"type": "string", "enum": ["source_1", "source_2"]}
          }
        },
        "required": ["rule_name", "control_triggers", "policy_cues", "decision_effect", "success_criteria", "failure_mode", "evidence_type", "mapping_pattern", "observed_in"]
      }
    }
  },
  "required": ["decision_rules"]
}
```

**Key changes from current schema**:
1. **Atomic**: Single `evidence_type` and `mapping_pattern` (not arrays)
2. **Control context**: `control_triggers` brings back what we stripped out
3. **Actionable**: `policy_cues` tells you what to look for
4. **Failure-aware**: `failure_mode` and `insufficient_evidence` enable discrimination
5. **Decision-oriented**: `decision_effect` and `success_criteria` make it a rule, not a description

#### 1.2 New System Prompt (Round 1)

Combines the best framing from all three analyses, with generalization constraints:

```text
You are a Senior GRC Auditor teaching a junior auditor how to decide whether a policy satisfies a security control.

Your goal is NOT to describe what policies generally contain.
Your goal IS to extract DECISION RULES—the specific checks an auditor performs.

Think of it this way: You are writing a function `def does_policy_map(control, policy) -> bool`.
For each reason provided, reverse-engineer the "test step" the auditor performed:
1. What in the CONTROL triggered this check? (verbs, nouns, obligations)
2. What in the POLICY confirmed the match? (sections, keywords, artifacts)
3. What would FAIL this check? (missing elements, weak language, scope gaps)

## Abstraction Level (Critical)

Rules must generalize to ANY control set, not just the ones in this training data.

DO NOT reference specific:
- Algorithm names (AES, RSA) — instead say "named algorithms"
- Time periods (24 hours, annually) — instead say "explicit time bounds"
- Role titles (CISO, DPO) — instead say "named roles with defined authority"

DO describe:
- The TYPE of specificity required (named vs generic, quantified vs vague)
- The STRUCTURE of evidence (explicit section vs implied, mandatory vs optional language)
- The RELATIONSHIP that must hold (policy scope >= control scope, policy frequency >= control frequency)

Think: "What makes ANY cryptography control satisfied?" not "What makes one specific control satisfied?"

## Output Quality

Output rules must be ACTIONABLE but GENERALIZABLE:
- BAD (too generic): "The policy defines scope and applicability" (all policies do this)
- BAD (too specific): "Policy mentions AES-256 and RSA-2048" (overfits to specific terms)
- GOOD: "If control requires cryptographic protection, policy must specify named algorithms and key strengths—not just 'data is encrypted'"

Each rule must have exactly ONE evidence_type and ONE mapping_pattern.
If a reason implies multiple, split into multiple atomic rules.
```

#### 1.3 New User Prompt (Round 1)

```text
Analyze the following generalized mapping reasons and extract DECISION RULES.

## Source 1: {SOURCE_1_NAME}
{SOURCE_1_REASONS}

## Source 2: {SOURCE_2_NAME}
{SOURCE_2_REASONS}

Your task: Create a MASTER LIST of auditor decision rules using Union + Consolidate logic.

For EACH rule, you must provide:
1. **rule_name**: Action-oriented (e.g., "Check Ownership Assignment", not "Roles and Responsibilities")
2. **control_triggers**: Semantic categories that activate this rule (verbs, requirement types)
3. **policy_cues**: Evidence structure to look for (not specific terms)
4. **decision_effect**: supports_mapping | weak_support | blocks_mapping
5. **success_criteria**: The logical condition that confirms a match
6. **failure_mode**: What would invalidate or weaken this match
7. **insufficient_evidence**: What does NOT count (common false positives)
8. **evidence_type**: Exactly ONE from the enum
9. **mapping_pattern**: Exactly ONE from the enum
10. **observed_in**: Which source(s)

## Atomicity Requirement
Each rule MUST map to exactly ONE evidence_type and ONE mapping_pattern.
If a reason supports multiple, output multiple separate rules.

## Generalization Requirement (Critical)
Rules must work for ANY control set, not just the training controls.

DO NOT output rules with specific terms:
- BAD: "Control triggers: ['AES', 'RSA', 'SHA-256']" (specific algorithm names)
- BAD: "Policy cues: ['24-hour notification', 'annual review']" (specific time periods)

DO output rules with evidence structure:
- GOOD: "Control triggers: ['encrypt', 'cryptographic', 'cipher']" (semantic category)
- GOOD: "Policy cues: ['named algorithms', 'specified key lengths']" (type of specificity)

## Discrimination Requirement
Do NOT output rules like:
- "Policy has scope" (all policies do)
- "Policy uses mandatory language" (all policies do)
- "Policy assigns responsibilities" (all policies do)

DO output rules like:
- "If control requires cryptographic protection → Policy must name specific algorithms and strengths (not just 'encrypted')"
- "If control requires record retention → Policy must specify artifact types AND retention periods (not just 'records maintained')"
- "If control requires role assignment → Policy must name specific roles with explicit duties (not just 'management responsible')"

## Valid Enum Values
[Include existing enums here]
```

#### 1.4 New Reduce Prompt (Round 2+)

Tighten merge criteria per ChatGPT's recommendation:

```text
You are consolidating decision rules from previous aggregation rounds.

MERGE CONSERVATIVELY. Only merge rules if ALL of these conditions are met:
1. Same decision_effect (supports_mapping, weak_support, or blocks_mapping)
2. Materially the same control_triggers (same verbs/nouns activate the rule)
3. Materially the same policy_cues (same evidence confirms the match)
4. Same failure_mode logic

Do NOT merge solely because evidence_type/mapping_pattern match.
If two rules share evidence_type but apply to different control intents, KEEP THEM SEPARATE.

When in doubt, prefer specificity over generality.
We want a "toolbox of specific moves," not "8 generic buckets."

When merging:
- Combine control_triggers and policy_cues lists
- Preserve the most specific failure_mode
- Keep the narrower success_criteria
```

---

### Phase 2: Add Negative Examples (If Phase 1 Insufficient)

If Phase 1 produces rules that are still too generic, add contrast data.

#### Option A: Near-Miss Negatives (Lower Effort)

For each policy, include 3-5 controls it does NOT satisfy and why:

```text
## Source 1: Data_Protection_Policy

### MAPS: Encryption Controls (DCF-201, DCF-203)
- "Policy specifies AES-256 for data at rest"
- "Policy mandates TLS 1.2+ for data in transit"

### DOES NOT MAP: Physical Security Controls (DCF-401)
- "Policy addresses data handling but not facility access"
- "No mention of physical barriers, badges, or visitor logs"

Extract rules that DISTINGUISH the mappings from the non-mappings.
```

#### Option B: Synthetic Negatives (Higher Effort, Higher Quality)

Generate "hard negatives" by modifying control requirements:
- Original: "Review access rights annually"
- Synthetic negative: "Review access rights quarterly" (policy says annual → doesn't map)

Then ask: "What evidence would FAIL this stricter control?"

---

### Phase 3: Control-Family Clustering (If Still Needed)

If Phases 1-2 don't produce discriminative rules, restructure input by control family:

```
Instead of: All reasons mixed together
Do: Encryption reasons → Encryption-specific rules
    Access Control reasons → Access-specific rules
    Incident Response reasons → IR-specific rules
```

Then add a final **contrastive pass**:
```text
Given these control-family-specific rules, what DISTINGUISHES:
- Encryption rules from Access Control rules?
- Incident Response rules from Vendor Management rules?
```

---

## Implementation Order (TDD Approach)

The implementation follows Red-Green-Refactor: write failing tests first, then implement to make them pass.

### Sprint 1: Foundation (Tests First)

| Step | Description | Type | Depends On |
|------|-------------|------|------------|
| **1.1** | Create `tests/scripts/experiments/fixtures/golden_rules.py` | TEST | — |
| **1.2** | Create `tests/scripts/experiments/test_models.py` | TEST | 1.1 |
| **1.3** | Create `tests/scripts/experiments/test_quality_validators.py` | TEST | 1.1 |
| **1.4** | Create `tests/scripts/experiments/test_parsing.py` | TEST | 1.2 |
| **1.5** | Run tests (all should FAIL - Red phase) | VERIFY | 1.2, 1.3, 1.4 |

### Sprint 2: Implementation (Make Tests Pass)

| Step | Description | Type | Depends On |
|------|-------------|------|------------|
| **2.1** | Update `models.py`: Add `DecisionRule`, enums | CODE | 1.2 (tests exist) |
| **2.2** | Run model tests (should PASS - Green phase) | VERIFY | 2.1 |
| **2.3** | Create `quality_validators.py`: Implement validators | CODE | 1.3 (tests exist) |
| **2.4** | Run quality validator tests (should PASS) | VERIFY | 2.3 |
| **2.5** | Update `aggregator.py`: Add parsing logic | CODE | 1.4 (tests exist) |
| **2.6** | Run parsing tests (should PASS) | VERIFY | 2.5 |

### Sprint 3: Prompts (No Unit Tests, Integration Tested)

| Step | Description | Type | Depends On |
|------|-------------|------|------------|
| **3.1** | Update `prompts/aggregate_reasons/response.json` | PROMPT | 2.6 |
| **3.2** | Update `prompts/aggregate_reasons/system` | PROMPT | 3.1 |
| **3.3** | Update `prompts/aggregate_reasons/user` | PROMPT | 3.2 |
| **3.4** | Update `prompts/consolidate_patterns/*` | PROMPT | 3.3 |
| **3.5** | Update `output_writer.py` for new structure | CODE | 3.4 |

### Sprint 4: Integration Testing

| Step | Description | Type | Depends On |
|------|-------------|------|------------|
| **4.1** | Create `tests/scripts/experiments/test_aggregation_integration.py` | TEST | 3.5 |
| **4.2** | Run integration tests with mocked LLM responses | VERIFY | 4.1 |
| **4.3** | Run full aggregation on small sample (2-3 policies) | E2E | 4.2 |
| **4.4** | Validate output rules pass quality checks | VERIFY | 4.3 |
| **4.5** | Run full aggregation on all 37 policies | E2E | 4.4 |

### Sprint 5: Iterate If Needed

| Step | Description | Type | Depends On |
|------|-------------|------|------------|
| **5.1** | Analyze output quality using quality validators | ANALYZE | 4.5 |
| **5.2** | If rules still generic: Add negative examples (Phase 2) | CODE | 5.1 |
| **5.3** | If rules overfit: Tune generalization validators | CODE | 5.1 |
| **5.4** | If needed: Control-family clustering (Phase 3) | CODE | 5.2, 5.3 |

### TDD Checkpoints

After each sprint, verify:

```bash
# Sprint 1: All tests should FAIL (Red)
uv run pytest tests/scripts/experiments/ -v
# Expected: FAILED (tests exist but no implementation)

# Sprint 2: Model and validator tests should PASS (Green)
uv run pytest tests/scripts/experiments/test_models.py -v
uv run pytest tests/scripts/experiments/test_quality_validators.py -v
uv run pytest tests/scripts/experiments/test_parsing.py -v
# Expected: PASSED

# Sprint 4: Integration tests should PASS
uv run pytest tests/scripts/experiments/test_aggregation_integration.py -v -m integration
# Expected: PASSED
```

**Estimated Total Effort**: 2-3 days for Sprints 1-4. Sprint 5 only if results are unsatisfactory.

---

## Success Criteria

After implementation, each output rule should pass these tests:

| Test | Question | Pass Example | Fail Example |
|------|----------|--------------|--------------|
| **Actionable** | Can an auditor use this to check a new policy? | "Check for named algorithms in Encryption section" | "Policy has technical specifications" |
| **Discriminative** | Does this distinguish control families? | "If control requires cryptographic protection → look for named algorithms" | "Policy defines scope" (all policies do) |
| **Atomic** | Single evidence_type and mapping_pattern? | 1 evidence_type, 1 mapping_pattern | 3 evidence_types, 2 mapping_patterns |
| **Failure-aware** | Does it say what DOESN'T count? | "Insufficient: 'data is secured' without specifics" | No failure mode |
| **IF/THEN structure** | Is it a decision rule? | "IF control asks X AND policy has Y THEN supports mapping" | "Policies generally contain..." |
| **Generalizable** | Would this work for a custom control using different terminology? | "Policy cues: named algorithms, specified strengths" | "Policy cues: AES-256, RSA-2048, TLS 1.2" |

### The Generalization Test

For each rule, ask: **"If someone wrote a custom control about the same topic using completely different words, would this rule still apply?"**

- ✅ "Named algorithms and key strengths" → Works for any crypto control
- ❌ "AES-256 and RSA-2048" → Only works if control uses those exact terms

---

## Expected Output Transformation

### Current Output (Too Generic)

```
Pattern: Comprehensive Scope and Applicability
Description: The policy explicitly defines the boundaries, assets, entities,
or organizational units subject to the requirements...
Evidence Types: [scope_definition, responsibility_assignment, artifact_reference]
Mapping Patterns: [scope_inclusion, ownership_alignment, direct_terminology_match]
Source Count: 36/37
```

**Problem**: This describes what 36/37 policies have. Not useful for discrimination.

### Target Output (Actionable + Generalizable Rules)

Note how these rules describe **evidence structure** (named, quantified, explicit) rather than **specific terms** (AES-256, 24 hours, CISO):

```
Rule: Scope Coverage Verification
Control Triggers: ["applies to", "scope", "target", "covered systems/entities"]
Policy Cues: ["explicit applicability section", "enumerated assets or systems", "defined boundaries"]
Decision Effect: supports_mapping
Success Criteria: Policy scope >= Control scope (policy covers at least what control requires)
Failure Mode: Policy scope is narrower than control requirement
Insufficient Evidence: Generic "applies to the organization" without specific enumeration
Evidence Type: scope_definition
Mapping Pattern: scope_inclusion
```

```
Rule: Technical Specificity Requirement
Control Triggers: ["encrypt", "cryptographic", "protect confidentiality", "secure transmission"]
Policy Cues: ["named algorithms (not just 'encrypted')", "specified key lengths or strengths", "identified protection contexts (at rest, in transit)"]
Decision Effect: supports_mapping
Success Criteria: Policy specifies HOW (named methods) not just THAT (generic statement)
Failure Mode: Policy uses vague terms ("protected", "secured") without technical specifics
Insufficient Evidence: "Data is encrypted" without algorithm or strength specification
Evidence Type: technical_specification
Mapping Pattern: implementation_detail
```

```
Rule: Timing Requirement Verification
Control Triggers: ["periodic", "regular", "review", "at least every", "within X time"]
Policy Cues: ["explicit time bounds", "defined frequency", "specified deadlines or intervals"]
Decision Effect: supports_mapping
Success Criteria: Policy frequency >= Control frequency (policy is at least as frequent)
Failure Mode: Policy frequency is less than control requires, or no frequency specified
Insufficient Evidence: "Regular reviews" without defined interval; "timely" without specific bounds
Evidence Type: frequency_timing
Mapping Pattern: process_alignment
```

```
Rule: Role Assignment Verification
Control Triggers: ["assign", "designate", "responsible for", "accountable", "owner"]
Policy Cues: ["named roles (not just 'management')", "explicit duties per role", "defined authority"]
Decision Effect: supports_mapping
Success Criteria: Specific role + specific duty + authority to act
Failure Mode: Generic ownership ("management responsible") without named role or duties
Insufficient Evidence: Titles listed without duties; department named without individual accountability
Evidence Type: responsibility_assignment
Mapping Pattern: ownership_alignment
```

**Key difference from overfitted output**: These rules use phrases like "named algorithms", "explicit time bounds", "specified strengths"—describing the **type of evidence** needed, not enumerating specific terms like "AES-256" or "annual".

---

## Files to Create/Modify

### Test Files (Create First - TDD)

| File | Purpose | Sprint |
|------|---------|--------|
| `tests/scripts/experiments/__init__.py` | Package init | 1.1 |
| `tests/scripts/experiments/fixtures/__init__.py` | Fixtures package | 1.1 |
| `tests/scripts/experiments/fixtures/golden_rules.py` | Golden examples + bad examples | 1.1 |
| `tests/scripts/experiments/test_models.py` | DecisionRule dataclass tests | 1.2 |
| `tests/scripts/experiments/test_quality_validators.py` | Quality validation tests | 1.3 |
| `tests/scripts/experiments/test_parsing.py` | LLM response parsing tests | 1.4 |
| `tests/scripts/experiments/test_aggregation_integration.py` | End-to-end pipeline tests | 4.1 |

### Source Files (Implement to Pass Tests)

| File | Change | Sprint |
|------|--------|--------|
| `models.py` | Add `DecisionRule`, `DecisionEffect` enum, update `EvidenceType`/`MappingPattern` | 2.1 |
| `quality_validators.py` | **NEW**: Implement `is_actionable`, `is_discriminative`, `is_atomic`, `is_generalizable`, `has_failure_mode`, `validate_rule_quality` | 2.3 |
| `aggregator.py` | Add `parse_llm_response`, `ParseError`, update aggregation logic | 2.5 |
| `output_writer.py` | Update markdown formatting for DecisionRule structure | 3.5 |

### Prompt Files (No Unit Tests)

| File | Change | Sprint |
|------|--------|--------|
| `prompts/aggregate_reasons/response.json` | Replace with new decision_rules schema | 3.1 |
| `prompts/aggregate_reasons/system` | Replace with new auditor-focused prompt | 3.2 |
| `prompts/aggregate_reasons/user` | Replace with new discriminative extraction prompt | 3.3 |
| `prompts/consolidate_patterns/system` | Update merge criteria | 3.4 |
| `prompts/consolidate_patterns/user` | Update to reference decision_rules structure | 3.4 |
| `prompts/consolidate_patterns/response.json` | Update schema to match | 3.4 |

---

## Summary

The three analyses converge on a clear diagnosis and prescription:

**Diagnosis**: We asked for "universal patterns" and got descriptions of policy anatomy. The prompts optimized for abstraction at the expense of discrimination.

**Prescription**:
1. **Change the schema** to enforce actionable structure (control_triggers, policy_cues, failure_mode)
2. **Change the prompts** to ask for decision rules, not descriptions
3. **Enforce atomicity** (1 evidence_type, 1 mapping_pattern per rule)
4. **Enforce generalization** — rules must describe evidence structure, not specific terms
5. **Tighten merging** to preserve discriminative details
6. **Add negatives** if still too generic

**Critical Constraint**: While making rules more actionable, we must avoid overfitting to the 780 training controls. Rules should describe **types of evidence** (named algorithms, explicit time bounds, specified roles) not **specific terms** (AES-256, 24 hours, CISO). This ensures rules generalize to custom controls.

**Target Output**: ~15-25 meta-rules that are:
- **Actionable**: An auditor can use them to check a new policy
- **Discriminative**: They distinguish between control types
- **Generalizable**: They work for any control set, not just training data

### TDD Approach

This implementation uses **Test-Driven Development** to ensure quality:

1. **Tests First**: Golden examples and quality validators are defined before any code changes
2. **Red-Green-Refactor**: Write failing tests → implement minimum code → refactor
3. **Quality Gates**: Automated validators catch generic, overfitting, or non-atomic rules
4. **Integration Testing**: Full pipeline tested with real LLM calls before production use

**Key Test Artifacts**:
- `golden_rules.py` — Examples of what good output looks like
- `test_quality_validators.py` — Automated checks for actionability, discrimination, atomicity, generalization
- `test_aggregation_integration.py` — End-to-end pipeline validation

**Implementation Flow**:
```
Sprint 1: Write Tests (all fail)     → ~4 hours
Sprint 2: Implement Code (tests pass) → ~4 hours
Sprint 3: Update Prompts              → ~2 hours
Sprint 4: Integration Testing         → ~4 hours
Sprint 5: Iterate if needed           → variable
```

The highest-impact changes are **schema + prompt** (Phase 1). With TDD, these can be implemented in 2-3 days with confidence that quality criteria are met. Only proceed to data restructuring (negatives, control-family clustering) if integration tests show rules are still too generic.
