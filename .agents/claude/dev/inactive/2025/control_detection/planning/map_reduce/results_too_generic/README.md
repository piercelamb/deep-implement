# Map-Reduce Reason Aggregator: Experiment Results

## Executive Summary

We built a system to distill universal patterns from 37 security policy documents, aiming to create guidance that LLMs could follow when mapping policies to security controls. The system successfully reduced 195 initial patterns to 13 final patterns (8 universal, 5 rare). However, the universal patterns may be **too abstract to be useful for prediction**—they describe what policies *are* rather than how to map policy documents to security controls.

---

## Table of Contents

1. [The Problem](#the-problem)
2. [Our Solution](#our-solution)
3. [How the Map-Reduce Process Works](#how-the-map-reduce-process-works)
4. [The Prompts](#the-prompts)
5. [Execution Results](#execution-results)
6. [Output Patterns](#output-patterns)
7. [Analysis](#analysis)
8. [Discussion Questions](#discussion-questions)

---

## The Problem

### Context: GRC Compliance Automation

In Governance, Risk, and Compliance (GRC), organizations must demonstrate that their internal policies satisfy external security controls (e.g., SOC 2, ISO 27001). This involves mapping policy documents to specific control requirements—a task traditionally performed by human auditors.

We want to automate this with LLMs, but there's a challenge: **how do you teach an LLM the reasoning patterns that auditors use?**

### The Specific Challenge

We have 37 template security policies (Data Protection Policy, Incident Response Plan, etc.) that have been manually mapped to ~686 security controls. Each mapping includes a `generalized_reason`—an abstract explanation of *why* the policy satisfies the control.

**Example generalized reasons:**
- "The policy defines mandatory requirements for protecting sensitive data categories"
- "The policy specifies encryption standards for data at rest and in transit"
- "The policy assigns data stewardship responsibilities to specific roles"

These reasons are scattered across hundreds of individual mappings. We want to:
1. **Aggregate** them into universal patterns
2. **Distill** actionable heuristics an LLM could follow
3. **Produce** guidance like "Go through these steps in deciding if a policy maps to a control"

---

## Our Solution

### Approach: Map-Reduce Pattern Aggregation

We use a **map-reduce** approach with LLM-powered consolidation:

1. **Map Phase (Round 1)**: Take raw generalized reasons from policy pairs, extract initial patterns
2. **Reduce Phases (Rounds 2+)**: Iteratively merge similar patterns until convergence

### Why Map-Reduce?

- **Scalability**: Can't fit all 37 policies' reasons into a single prompt
- **Parallel Processing**: Multiple pairs can be processed simultaneously
- **Convergence**: Binary reduction guarantees completion in O(log N) rounds

### Key Design Decisions

1. **Binary Tree Reduction**: Each round pairs items and reduces by ~half
2. **Union + Consolidate**: Extract all patterns from both sources, merge duplicates
3. **Universal vs Rare**: Patterns seen in multiple sources are "universal"; single-source patterns are "rare"
4. **Index-Based Tracking**: Patterns reference their source indices to prevent "text drift" across rounds

---

## How the Map-Reduce Process Works

### Visual Overview

```
                         37 Policies (Input)
                                │
                         Shuffle Randomly
                                │
                    ┌───────────┴───────────┐
                    │     ROUND 1 (Map)     │
                    │   19 parallel pairs   │
                    └───────────┬───────────┘
                                │
                          195 patterns
                    (all "rare" - single source)
                                │
                    ┌───────────┴───────────┐
                    │    ROUND 2 (Reduce)   │
                    │   10 parallel pairs   │
                    └───────────┬───────────┘
                                │
                     112 patterns (69U + 43R)
                                │
                    ┌───────────┴───────────┐
                    │    ROUND 3 (Reduce)   │
                    │    5 parallel pairs   │
                    └───────────┬───────────┘
                                │
                      64 patterns (45U + 19R)
                                │
                            ... 3 more rounds ...
                                │
                      13 patterns (8U + 5R)
                                │
                    ┌───────────┴───────────┐
                    │     FINAL OUTPUT      │
                    │  8 Universal Patterns │
                    │   5 Rare Patterns     │
                    └───────────────────────┘
```

### Round-by-Round Mechanics

**Round 1 (Map Phase)**:
- Input: Raw `generalized_reason` text from policy-control mappings
- Process: Pair policies (e.g., Data_Protection + Asset_Management), ask LLM to extract patterns
- Output: All patterns are "rare" (source_count = 1 policy pair)

**Rounds 2+ (Reduce Phases)**:
- Input: Patterns from previous round (already structured)
- Process: Pair pattern sets, ask LLM to merge similar patterns
- Output: Patterns that merge become "universal"; unmerged stay "rare"

**Convergence**:
- Binary reduction: N → ceil(N/2) per round
- 37 → 19 → 10 → 5 → 3 → 2 → 1 = **6 rounds**

### Pattern Classification

| Type | Definition | Example Count |
|------|------------|---------------|
| **Universal** | Observed in 2+ original source policies | 8 patterns |
| **Rare** | Observed in only 1 source policy | 5 patterns |

---

## The Prompts

### Round 1: `aggregate_reasons` (Initial Pattern Extraction)

This prompt takes raw generalized reasons from two policies and extracts initial patterns.

#### System Prompt

```
You are a Governance, Risk and Compliance (GRC) expert analyzing patterns in how security controls map to policy documents.

You are given generalized reasons from multiple policy-to-control mappings. Your task is to identify UNIVERSAL PATTERNS that appear across multiple mappings.

Focus on:
1. Abstract patterns that apply regardless of specific control or policy
2. Common evidence types and how they indicate compliance
3. Linguistic markers and structural patterns in policy text
4. Mapping heuristics an auditor would find useful

Do NOT include policy-specific or control-specific details. Aim for patterns that could be applied to ANY policy-control mapping task.
```

#### User Prompt

```
Analyze the following generalized mapping reasons from {NUM_SOURCES} policy documents and extract all mapping patterns.

## Source 1: {SOURCE_1_NAME}
{SOURCE_1_REASONS}

## Source 2: {SOURCE_2_NAME}
{SOURCE_2_REASONS}

Your task is to create a MASTER LIST of unique mapping patterns using **Union + Consolidate** logic:

1. Extract ALL distinct abstract patterns found in EITHER source
2. If a pattern appears in both sources (conceptually similar), merge them into one entry and mark observed_in as both sources

For each pattern:
1. Give it a clear, descriptive name
2. Describe the pattern abstractly (no specific policy/control references)
3. Note which evidence types and mapping patterns it relates to (use ONLY values from the enums below)
4. Indicate which source(s) the pattern was observed in using "observed_in": ["source_1"], ["source_2"], or ["source_1", "source_2"] if found in both

## Valid Enum Values

**evidence_types** (use ONLY these values):
- explicit_mandate: Explicit "shall/must/will" language requiring specific actions
- procedural_definition: Detailed process or procedure descriptions
- responsibility_assignment: Assignment of roles or ownership
- scope_definition: Boundary or applicability statements
- frequency_timing: Periodic review or timing requirements
- technical_specification: Technical standards or configurations
- standard_reference: References to external standards/frameworks
- exception_handling: Exception or deviation procedures
- artifact_reference: References to documents, logs, or records

**mapping_patterns** (use ONLY these values):
- direct_terminology_match: Policy uses same/similar terms as control
- semantic_equivalence: Different words but same meaning
- scope_inclusion: Control topic falls within policy scope
- implementation_detail: Policy specifies how to implement control
- process_alignment: Policy process aligns with control objective
- ownership_alignment: Policy assigns ownership matching control requirements
- negative_constraint: Policy prohibits what control restricts

DO NOT invent new evidence_types or mapping_patterns - use only the values listed above.
```

#### Response Schema

```json
{
  "type": "object",
  "properties": {
    "patterns": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "Short, descriptive pattern name"
          },
          "description": {
            "type": "string",
            "description": "Abstract description of the pattern"
          },
          "evidence_types": {
            "type": "array",
            "items": {
              "type": "string",
              "enum": ["explicit_mandate", "procedural_definition", "responsibility_assignment", "scope_definition", "frequency_timing", "technical_specification", "standard_reference", "exception_handling", "artifact_reference"]
            },
            "description": "Which evidence types this pattern relates to"
          },
          "mapping_patterns": {
            "type": "array",
            "items": {
              "type": "string",
              "enum": ["direct_terminology_match", "semantic_equivalence", "scope_inclusion", "implementation_detail", "process_alignment", "ownership_alignment", "negative_constraint"]
            },
            "description": "Which mapping patterns this pattern relates to"
          },
          "observed_in": {
            "type": "array",
            "items": {
              "type": "string",
              "enum": ["source_1", "source_2"]
            },
            "description": "Which source(s) this pattern was observed in."
          }
        },
        "required": ["name", "description", "evidence_types", "mapping_patterns", "observed_in"]
      }
    },
    "consolidation_notes": {
      "type": "string",
      "description": "Notes on patterns merged or removed as duplicates"
    }
  },
  "required": ["patterns"]
}
```

---

### Rounds 2+: `consolidate_patterns` (Pattern Merging)

This prompt takes structured patterns from the previous round and merges similar ones.

#### System Prompt

```
You are consolidating mapping patterns from previous aggregation rounds.

Your task is to:
1. MERGE similar patterns into new universal patterns (requires text generation)
2. IDENTIFY universal patterns that have no match (pass through by index)

You do NOT need to list rare patterns that remain rare - the system will compute that automatically.

A pattern is considered "universal" if it was observed in multiple original sources.
A pattern is "rare" if it was only observed in a single original source.

When merging patterns:
- Combine patterns that share the same evidence_type AND mapping_pattern combination
- Patterns that would lead an auditor to the same mapping decision should merge
- Use the more general description when merging
- Preserve all source policy IDs from merged patterns

Your output should be minimal:
- Only generate new text for merged patterns
- Use indices to reference patterns that pass through unchanged
- The system handles rare patterns automatically
```

#### User Prompt

```
## Source 1 Patterns

### Universal Patterns
{SOURCE_1_UNIVERSAL_PATTERNS}

### Rare Patterns
{SOURCE_1_RARE_PATTERNS}

## Source 2 Patterns

### Universal Patterns
{SOURCE_2_UNIVERSAL_PATTERNS}

### Rare Patterns
{SOURCE_2_RARE_PATTERNS}

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

## Valid Enum Values

**evidence_types** (use ONLY these values):
- explicit_mandate: Explicit "shall/must/will" language requiring specific actions
- procedural_definition: Detailed process or procedure descriptions
- responsibility_assignment: Assignment of roles or ownership
- scope_definition: Boundary or applicability statements
- frequency_timing: Periodic review or timing requirements
- technical_specification: Technical standards or configurations
- standard_reference: References to external standards/frameworks
- exception_handling: Exception or deviation procedures
- artifact_reference: References to documents, logs, or records

**mapping_patterns** (use ONLY these values):
- direct_terminology_match: Policy uses same/similar terms as control
- semantic_equivalence: Different words but same meaning
- scope_inclusion: Control topic falls within policy scope
- implementation_detail: Policy specifies how to implement control
- process_alignment: Policy process aligns with control objective
- ownership_alignment: Policy assigns ownership matching control requirements
- negative_constraint: Policy prohibits what control restricts

## Important
- Every input index should either be in a `derived_from` list OR in `unchanged_universal`
- Rare patterns (R*) not in any `derived_from` will automatically remain rare
- Do not invent indices that weren't provided
- Use ONLY the evidence_types and mapping_patterns values listed above
```

#### Response Schema

```json
{
  "type": "object",
  "properties": {
    "merged_patterns": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "Short, descriptive name for the merged pattern"
          },
          "description": {
            "type": "string",
            "description": "Abstract description synthesized from merged patterns"
          },
          "evidence_types": {
            "type": "array",
            "items": {
              "type": "string",
              "enum": ["explicit_mandate", "procedural_definition", "responsibility_assignment", "scope_definition", "frequency_timing", "technical_specification", "standard_reference", "exception_handling", "artifact_reference"]
            }
          },
          "mapping_patterns": {
            "type": "array",
            "items": {
              "type": "string",
              "enum": ["direct_terminology_match", "semantic_equivalence", "scope_inclusion", "implementation_detail", "process_alignment", "ownership_alignment", "negative_constraint"]
            }
          },
          "derived_from": {
            "type": "array",
            "items": {
              "type": "string",
              "enum": "VALID_INDICES"
            },
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
      "items": {
        "type": "string",
        "enum": "VALID_UNIVERSAL_INDICES"
      },
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

**Note**: The `VALID_INDICES`, `VALID_UNIVERSAL_INDICES`, `TOTAL_INDEX_COUNT`, and `TOTAL_UNIVERSAL_COUNT` placeholders are replaced at runtime with actual values based on the input patterns.

---

## Execution Results

### Run Summary

```
Starting full aggregation...

############################################################
STARTING MAP-REDUCE AGGREGATION
############################################################
  Initial items: 37 policies
############################################################
```

### Round-by-Round Progress

| Round | Input Items | Pairs | Output Patterns | Universal | Rare |
|-------|-------------|-------|-----------------|-----------|------|
| 1 | 37 policies | 19 | 195 | 0 | 195 |
| 2 | 19 | 10 | 112 | 69 | 43 |
| 3 | 10 | 5 | 64 | 45 | 19 |
| 4 | 5 | 3 | 34 | 28 | 6 |
| 5 | 3 | 2 | 24 | 19 | 5 |
| 6 | 2 | 1 | 13 | 8 | 5 |

### Key Metrics

- **Total Rounds**: 6 (as predicted by log2(37))
- **Initial Patterns**: 195 (from Round 1)
- **Final Patterns**: 13 (93% reduction)
- **Final Universal**: 8 patterns
- **Final Rare**: 5 patterns
- **Source Policies**: 37

### Sample Progress Logs

```
Round 2 Pair 1/10 complete: [0U+12R] + [0U+13R] = 25 in -> 9U + 5R = 14 out (reduced by 11, 44.0%)
Round 2 Pair 2/10 complete: [0U+10R] + [0U+12R] = 22 in -> 8U + 1R = 9 out (reduced by 13, 59.1%)
...
Round 6 Pair 1/1 complete: [12U+5R] + [7U+0R] = 24 in -> 8U + 5R = 13 out (reduced by 11, 45.8%)
```

**Reading the logs**:
- `[0U+12R]` = 0 universal patterns + 12 rare patterns from source 1
- `25 in -> 14 out` = 25 input patterns reduced to 14 output patterns
- `reduced by 11, 44.0%` = 11 patterns were merged away (44% reduction)

---

## Output Patterns

### Universal Patterns (8 patterns)

*Patterns are sorted by number of source policies (most universal first).*

#### Pattern 1: Comprehensive Scope and Applicability

**Source Policy Count:** 36

**Description:** The policy explicitly defines the boundaries, assets, entities, or organizational units subject to the requirements, ensuring inclusive coverage of the control's targets.

**Evidence Types:** scope_definition, responsibility_assignment, artifact_reference
**Mapping Patterns:** scope_inclusion, ownership_alignment, direct_terminology_match

---

#### Pattern 2: Explicit Mandate and Strategic Alignment

**Source Policy Count:** 35

**Description:** The policy employs imperative language and specific terminology to establish binding obligations, governance structures, and high-level objectives that explicitly align with the control's intent and semantics.

**Evidence Types:** explicit_mandate, scope_definition, procedural_definition
**Mapping Patterns:** direct_terminology_match, semantic_equivalence, process_alignment, scope_inclusion

---

#### Pattern 3: Comprehensive Operational Procedures and Lifecycle

**Source Policy Count:** 35

**Description:** The policy outlines detailed operational workflows, timing constraints, exception handling, and lifecycle management steps to demonstrate how the control is executed, maintained, and verified.

**Evidence Types:** procedural_definition, frequency_timing, exception_handling, standard_reference, technical_specification
**Mapping Patterns:** process_alignment, implementation_detail, semantic_equivalence


---

#### Pattern 4: Roles, Responsibilities, and Competency

**Source Policy Count:** 31

**Description:** The policy assigns specific organizational roles for control oversight and execution, including requirements for the qualifications, expertise, or awareness of the personnel involved.

**Evidence Types:** responsibility_assignment, explicit_mandate, procedural_definition, technical_specification
**Mapping Patterns:** ownership_alignment, process_alignment, implementation_detail

---

#### Pattern 5: Technical Specifications and Performance Metrics

**Source Policy Count:** 29

**Description:** The policy mandates specific technical configurations, tools, classification schemes, or quantitative performance metrics to enforce security objectives and functional requirements.

**Evidence Types:** technical_specification, procedural_definition, explicit_mandate
**Mapping Patterns:** implementation_detail, semantic_equivalence

---

#### Pattern 6: Evidence and Artifact Generation

**Source Policy Count:** 28

**Description:** Mandates for the creation, maintenance, and retention of specific records, logs, or templates to serve as tangible evidence of compliance and provide an audit trail.

**Evidence Types:** artifact_reference, procedural_definition, explicit_mandate
**Mapping Patterns:** implementation_detail, process_alignment

---

#### Pattern 7: External Framework Alignment and Integration

**Source Policy Count:** 16

**Description:** The policy incorporates or references external industry standards, regulations, or third-party requirements to align internal mandates with broader compliance criteria.

**Evidence Types:** standard_reference, explicit_mandate, scope_definition, artifact_reference, procedural_definition
**Mapping Patterns:** scope_inclusion, semantic_equivalence, implementation_detail, process_alignment

---

#### Pattern 8: Operational Constraints and Prohibitions

**Source Policy Count:** 13

**Description:** The policy mandates segregation of duties, isolation, or explicitly forbids specific behaviors or configurations, defining compliance through exclusion or negative constraints.

**Evidence Types:** explicit_mandate, technical_specification, procedural_definition, frequency_timing
**Mapping Patterns:** negative_constraint, implementation_detail, process_alignment

---

### Rare Patterns (5 patterns)

*These patterns may represent policy-specific requirements or edge cases.*

#### Pattern 1: External Interaction and Reporting

**Source Policy Count:** 1

**Description:** Procedures and mandates for communicating with external entities (regulators, law enforcement, public) under defined conditions.

**Evidence Types:** explicit_mandate, procedural_definition
**Mapping Patterns:** process_alignment

---

#### Pattern 2: Qualitative Attribute Mandate

**Source Policy Count:** 1

**Description:** The policy establishes qualitative standards (e.g., clarity, transparency, availability) for organizational outputs or communications, ensuring specific non-functional requirements are met.

**Evidence Types:** explicit_mandate, technical_specification
**Mapping Patterns:** implementation_detail, semantic_equivalence

---

#### Pattern 3: Independent Verification

**Source Policy Count:** 1

**Description:** The policy mandates a validation step performed by a party other than the implementer (e.g., third party or separate role) to ensure integrity before a process is closed.

**Evidence Types:** responsibility_assignment, procedural_definition
**Mapping Patterns:** process_alignment

---

#### Pattern 4: Objective-Driven Performance Metrics

**Source Policy Count:** 1

**Description:** The policy requires the definition of measurable indicators linked to high-level organizational goals, ensuring the management system remains objective-driven.

**Evidence Types:** procedural_definition, explicit_mandate
**Mapping Patterns:** process_alignment

---

#### Pattern 5: Structural Standardization

**Source Policy Count:** 2

**Description:** The policy mandates the use of specific templates, centralized repositories, or standardized frameworks to ensure consistent execution of the control.

**Evidence Types:** technical_specification, standard_reference
**Mapping Patterns:** implementation_detail

---

## Analysis

### What's Working Well

1. **Genuine Abstraction Achieved**

   The patterns are truly meta-level "reasons why policies map to controls"—not policy-specific details. They capture a reasoning taxonomy that could theoretically guide an auditor.

2. **Good Coverage Gradient**

   - Pattern 1: 36/37 policies (near-universal)
   - Pattern 8: 13/37 policies (common but not ubiquitous)
   - Rare patterns: 1-2 policies (true edge cases)

3. **Provenance Preserved**

   Each pattern traces back to source policies, so the consolidation can be validated.

4. **Impressive Reduction**

   195 → 13 patterns (93% reduction) without losing the core taxonomy of evidence types and mapping patterns.

### Verdict

**Solid first pass, but the universal patterns may be too generic to be useful for prediction.** They're correct but not discriminative.

