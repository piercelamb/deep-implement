# Research: MapReduce for False Positive Rules Generation

## Background Context

We are building an LLM-based system to map security controls (like "DCF-107: Secure Disposal") to policy documents (like "Acceptable Use Policy"). The system determines whether a given policy document satisfies the requirements of a given control.

### The Problem: False Positives

A **false positive** (FP) occurs when the mapping LLM incorrectly decides that a policy MAPS to a control when it actually doesn't (according to human-labeled ground truth).

We have:
1. Run an experiment mapping ~686 controls against 37 policy documents
2. Collected 1,872 potential false positives (controls marked MAPPED but not in ground truth)
3. Run an "FP Judge" LLM to analyze each FP (1,870 judged successfully) and determine:
   - The root cause of the error (from a controlled vocabulary of 14 categories)
   - Which Interpretive Rules (IR-1 to IR-10) were misapplied
   - A reasoning explanation for why this was a false positive

### The Goal

Use a MapReduce-style approach (already implemented in `reason_aggregator/`) to distill "Failure Avoidance Rules" from the FP judge outputs. These rules will teach the mapping LLM what patterns to avoid.

---

## How the MapReduce Approach Works

This section explains the existing MapReduce implementation so an engineer unfamiliar with the system can understand how to extend it for false positives.

### Binary Tree Reduction Algorithm

The aggregator uses **binary tree reduction** with **non-overlapping pairs** to iteratively combine inputs until a single output remains.

**Pairing Function** (from `models.py:create_binary_pairs`):

```python
def create_binary_pairs(items):
    """
    Create non-overlapping pairs for binary tree reduction.
    Example: [A,B,C,D,E] -> [(A,B), (C,D), (E,None)]
    """
    iterator = iter(items)
    return list(itertools.zip_longest(iterator, iterator))
```

**Key insight:** This creates pairs `(1,2), (3,4), (5,6)...` - NOT overlapping pairs like `(1,2), (2,3), (3,4)`. Each item is consumed exactly once per round.

```
Round 1 (37 inputs → 19 outputs)
    ┌───────────────┬───────────────┬───────────────┬─────────┐
    │ Policy 1 + 2  │ Policy 3 + 4  │ Policy 5 + 6  │ ...     │
    └───────┬───────┴───────┬───────┴───────┬───────┴────┬────┘
            │               │               │            │
            ▼               ▼               ▼            ▼
         Output 1        Output 2        Output 3    Output N

Round 2 (19 outputs → 10 outputs)
    ┌───────────────────┬───────────────────┐
    │ Output 1 + 2      │ Output 3 + 4      │  ...
    └─────────┬─────────┴─────────┬─────────┘
              │                   │
              ▼                   ▼
           Output 1'           Output 2'

... continues until single output ...

Round 6 (2 outputs → 1 final output)
```

**Convergence:** N inputs converge in ~log₂(N) rounds. For 37 policies: 37→19→10→5→3→2→1 = **6 rounds**.

**Odd-count handling:** If a round has an odd number of items, the last item is paired with `None` and passes through unchanged to the next round (see `passthrough_solo` in `aggregator.py`).

### Two-Phase Prompt Strategy

The aggregator uses **different prompts** for Round 1 vs Round 2+:

| Phase | Prompt Directory | Purpose |
|-------|------------------|---------|
| **Round 1** | `false_negative_analysis/` | Extract rules from raw failure data |
| **Round 2+** | `consolidate_failure_patterns/` | Merge similar rules, preserve specificity |

This is critical: Round 1 transforms **raw data** into **structured rules**, while subsequent rounds **consolidate rules** without losing important patterns.

### Round 1: Rule Extraction

**Input:** Raw failure analyses grouped by policy
```
## Source 1: Asset Management Policy
- Dispute: NO_MATCH
  Control: Removable Media Encryption (DCF-149)
  Failure Analysis: The policy contains a binding mandate...
  Original LLM Error: Non-binding language used...
  Missed Evidence: Copies will be protected...

## Source 2: Data Protection Policy
- Dispute: PARTIAL
  Control: Data Classification (DCF-107)
  ...
```

**Task:** For each failure case, diagnose:
1. Which of the 4 Critical Questions did the LLM incorrectly answer? (Mandate? Scope? Ownership? Contradiction?)
2. Did the LLM demand details that belong in standards/procedures?
3. What linguistic pattern was missed?

**Output:** Structured `decision_rules` array:
```json
{
  "decision_rules": [
    {
      "rule_name": "Check Binding Preamble Inheritance",
      "failure_pattern": "LLM treats soft language as non-binding when it appears under a binding header",
      "recovery_heuristic": "When encountering 'should/may' language, check parent section headers for binding preambles",
      "control_triggers": ["requires", "mandates", "must implement"],
      "policy_cues": ["the following will be", "shall ensure", "must comply"],
      "decision_effect": "supports_mapping",
      "success_criteria": "IF soft_language AND binding_preamble THEN treat_as_binding",
      "evidence_type": "explicit_mandate",
      "dispute_categories": ["NO_MATCH"],
      "observed_in": ["source_1"]
    }
  ]
}
```

### Round 2+: Conservative Consolidation

**Key principle:** "Merge conservatively. When in doubt, prefer specificity over generality."

**Merge conditions (ALL must be met):**
1. Same `failure_pattern` concept (the same type of LLM error)
2. Same `recovery_heuristic` approach (the same corrective action)
3. Materially the same `control_triggers`
4. Same `decision_effect`

**Do NOT merge** solely because `evidence_type` matches!

**Input format:** Rules are tagged with indices for tracking:
```
## Source 1 Failure Avoidance Rules

### Universal Rules
U1_0: Check Binding Preamble Inheritance
  failure_pattern: LLM treats soft language as non-binding...

U1_1: Verify Semantic Equivalence
  failure_pattern: LLM rejects valid matches due to different terminology...

### Rare Rules
R1_0: Check Standard Reference Inheritance
  failure_pattern: LLM misses implicit requirements from referenced standards...
```

**Universal vs Rare classification:**
- **Universal:** Rules observed in multiple sources (high confidence)
- **Rare:** Rules observed in only one source (lower confidence, preserved separately)

**Output:** Minimal delta - only new merged rules + indices of unchanged rules:
```json
{
  "merged_rules": [
    {
      "rule_name": "Verify Binding Language Inheritance",
      "failure_pattern": "Comprehensive description combining both sources...",
      "derived_from": ["U1_0", "U2_3"]
    }
  ],
  "unchanged_universal": ["U1_1", "U2_0", "U2_1"],
  "consolidation_notes": "Merged U1_0 and U2_3 - same binding inheritance pattern"
}
```

### Schema Enforcement

Each prompt has a `response.json` that enforces:
- Enum values for `evidence_type`, `decision_effect`, `dispute_categories`
- Required fields like `rule_name`, `failure_pattern`, `recovery_heuristic`
- Atomic rules: exactly ONE `evidence_type` per rule

This prevents LLM hallucination of invalid categories.

---

## Reusing for False Positives: Key Differences

| Aspect | False Negatives | False Positives |
|--------|-----------------|-----------------|
| **Error type** | LLM said NO_MATCH when GT says MAPPED | LLM said MAPPED when GT says NO_MATCH |
| **Root cause** | Missing evidence recognition | Over-aggressive pattern matching |
| **Dispute categories** | NO_MATCH, PARTIAL | (Need new: OVER_MAPPED?) |
| **Decision effect** | `supports_mapping` (missed evidence) | `blocks_mapping` (false evidence) |
| **Input data** | `detailed_results.json` with LLM_WRONG | `fp_judge_*.json` with CONFIRMED_FP |

### What the FP Judge Already Provides

The FP validation pipeline produces structured analyses with:
- `root_cause`: 14 categories (SEMANTIC_STRETCH, SCOPE_OVERREACH, etc.)
- `misapplied_rules`: Which IR rules were incorrectly applied
- `reasoning`: Why this is a false positive
- `evidence_critique`: Why the cited evidence doesn't actually support mapping

**This is more structured than the false negative input**, which required Round 1 to extract patterns. The FP judge has already done pattern extraction (via root_cause categorization).

---

## Data Analysis: FP Validation Outputs

**Source:** `files/llm_outputs/fp_validation/20251229_221006/`

### Volume Statistics

| Metric | Count |
|--------|-------|
| Total FPs analyzed | 1,872 |
| Successfully judged | 1,870 |
| Unique controls | 701 |
| Unique policies | 33 |
| CONFIRMED_FP verdicts | 1,868 (99.9%) |
| UNCERTAIN verdicts | 2 (0.1%) |
| Confidence distribution | 100% high |

The judge confirmed nearly all analyzed cases as true false positives with high confidence. Only 2 cases (0.1%) were marked UNCERTAIN.

### Root Cause Distribution

| Root Cause | Count | % | Primary Misapplied Rule |
|------------|-------|---|------------------------|
| SEMANTIC_STRETCH | 926 | 49.5% | IR-3 |
| SCOPE_OVERREACH | 285 | 15.2% | IR-1 |
| ABSTRACT_VS_SPECIFIC | 191 | 10.2% | IR-2 |
| EXISTENCE_NOT_IMPLIED | 155 | 8.3% | IR-6 |
| EVIDENCE_OUT_OF_CONTEXT | 86 | 4.6% | IR-9 |
| STANDARD_NOT_REFERENCED | 66 | 3.5% | IR-9 |
| WRONG_SUBJECT | 54 | 2.9% | - |
| DISJUNCTION_WRONG | 43 | 2.3% | IR-10 |
| NON_BINDING_LANGUAGE | 23 | 1.2% | - |
| PROHIBITION_NOT_IMPLIED | 11 | 0.6% | IR-7 |
| GOVERNANCE_NOT_PROCEDURE | 11 | 0.6% | IR-4 |
| FREQUENCY_UNSPECIFIED | 10 | 0.5% | IR-5 |
| BINDING_NOT_INHERITED | 5 | 0.3% | IR-8 |
| UNRELATED_DOMAIN | 4 | 0.2% | - |

**By Misapplied IR Rule (total citations):**

| IR Rule | Citations | Primary Root Cause |
|---------|-----------|-------------------|
| IR-3 | 934 | SEMANTIC_STRETCH |
| IR-1 | 363 | SCOPE_OVERREACH |
| IR-2 | 341 | ABSTRACT_VS_SPECIFIC |
| IR-6 | 218 | EXISTENCE_NOT_IMPLIED |
| IR-4 | 178 | GOVERNANCE_NOT_PROCEDURE |
| IR-9 | 165 | STANDARD_NOT_REFERENCED |
| IR-10 | 62 | DISJUNCTION_WRONG |
| IR-5 | 39 | FREQUENCY_UNSPECIFIED |
| IR-7 | 24 | PROHIBITION_NOT_IMPLIED |
| IR-8 | 17 | BINDING_NOT_INHERITED |

**Key Finding:** Strong correlation between root cause and misapplied IR rule. This suggests the root_cause categorization already captures the primary failure mode.

### FPs Per Policy (Top 15)

| Policy | FPs |
|--------|-----|
| Acceptable Use Policy | 212 |
| Asset Management Policy | 158 |
| AI Governance Policy | 157 |
| Information Security Policy | 126 |
| AI Risk Management Policy | 114 |
| Data Protection Policy | 95 |
| PCI DSS Compliance Policy | 90 |
| Code of Conduct | 82 |
| Change Management Policy | 72 |
| Information Governance Policy | 72 |
| AI System Development and Evaluation Policy | 70 |
| Data Classification Policy | 60 |
| Business Associate Policy | 46 |
| Shared Responsibility Policy | 40 |
| Backup Policy | 39 |
| (18 more policies...) | 337 |

**Observation:** Narrow-scope policies (AI-specific, Code of Conduct, PCI DSS) generate many FPs because the LLM incorrectly applies them to org-wide control requirements.

---

## Consolidation Analysis

### Question: Can we reduce the input volume before MapReduce?

We explored several consolidation strategies:

### Strategy 1: Deduplicate by Control ID

**Hypothesis:** Same control appearing as FP in multiple policies has the same error pattern.

**Finding:** FALSE. The same control can have different root causes across policies.

Example: DCF-741 (Logging & Monitoring Policy) appears as FP in 6 policies:
- AI Governance Policy: SEMANTIC_STRETCH (metrics ≠ logging)
- AI Risk Management Policy: SEMANTIC_STRETCH (AI monitoring ≠ system logging)
- Acceptable Use Policy: SEMANTIC_STRETCH (monitoring right ≠ logging mandate)
- Asset Management Policy: EXISTENCE_NOT_IMPLIED (enabling logging ≠ logging policy)
- Code of Conduct: STANDARD_NOT_REFERENCED (InfoSec reference ≠ logging policy)
- Information Security Policy: BINDING_NOT_INHERITED (example ≠ mandate)

**Conclusion:** Cannot consolidate by control ID alone.

### Strategy 2: Deduplicate by (Control ID, Root Cause)

**Rationale:** If a control has the same root cause across policies, the lessons are likely similar.

| Metric | Value |
|--------|-------|
| Controls with single root cause | 271 (39%) |
| Controls with multiple root causes | 430 (61%) |
| Unique (control_id, root_cause) pairs | 1,347 |
| **Reduction** | 1,870 → 1,347 (28.0%) |

**Conclusion:** Modest reduction. Not transformative.

### Strategy 3: Deduplicate by (Root Cause, Policy)

**Rationale:** All FPs of the same root cause in the same policy document are likely similar since they stem from the same document characteristics.

| Metric | Value |
|--------|-------|
| Unique (root_cause, policy) pairs | 229 |
| **Reduction** | 1,870 → 229 (87.8%) |

**Conclusion:** Significant reduction while preserving diversity.

### Strategy 4: Sample by Root Cause

**Rationale:** Sample N examples per root cause category to capture the diversity of error patterns within each category.

| Root Cause | Total | Suggested Sample |
|------------|-------|------------------|
| SEMANTIC_STRETCH | 926 | 40-60 |
| SCOPE_OVERREACH | 285 | 25-35 |
| ABSTRACT_VS_SPECIFIC | 191 | 20-30 |
| EXISTENCE_NOT_IMPLIED | 155 | 15-25 |
| (others <100) | ~313 | All |

**Conclusion:** Could reduce to ~200-250 samples with good coverage.

---

## Within-Category Diversity Analysis

### Question: Are FPs within the same root cause similar enough to consolidate?

We examined 5 random SEMANTIC_STRETCH examples:

1. **DCF-706 | Data Retention**: "safeguarding measures" ≠ "logical separation"
2. **DCF-161.AI | AI Governance**: "policy applicability" ≠ "management system boundaries"
3. **DCF-539 | AI Development**: "privacy metrics" ≠ "Records of Processing Activities"
4. **DCF-921 | Change Management**: "CM training" ≠ "InfoSec training"
5. **DCF-800 | AI Risk Management**: "AI Risk Management" ≠ "AI Governance"

**Finding:** While all share the same root cause (semantic stretch), the specific lessons are different. The **pattern** is the same ("words seem similar but functional outcomes differ"), but the **specific domain pairs** vary.

**Implication:** MapReduce should focus on extracting the **generalizable pattern** rather than specific examples. The volume of examples helps the LLM identify what the pattern is.

---

## Recommendations for Rule Extraction

### Key Insight: Binary Tree Reduction is Overkill

The FP Judge has already performed **pattern extraction** via structured categorization:
- `root_cause`: The error category (14 distinct patterns)
- `misapplied_rules`: Which IR rules were over-applied
- `reasoning`: Explanation of why this is an FP
- `evidence_critique`: Why the evidence doesn't support mapping

This is fundamentally different from the false negative case, where Round 1 had to extract patterns from unstructured failure analyses. **We can skip the pairwise reduction entirely and use batch summarization.**

### Option A: Batched Summarization (Recommended)

```
┌─────────────────────────────────────────────────────────────────┐
│  Batched Summarization Approach                                  │
├─────────────────────────────────────────────────────────────────┤
│  Phase 1: Per-Root-Cause Batch Summarization (parallelizable)   │
│                                                                  │
│  SEMANTIC_STRETCH (926) ─────► 13 batches of ~75 each           │
│    → 13 summarization calls + 1 consolidation = 14 calls        │
│                                                                  │
│  SCOPE_OVERREACH (285) ──────► 4 batches → 5 calls              │
│  ABSTRACT_VS_SPECIFIC (191) ─► 3 batches → 4 calls              │
│  EXISTENCE_NOT_IMPLIED (155) ► 3 batches → 4 calls              │
│  (10 smaller root causes) ───► 1 batch each → 10 calls          │
│                                                                  │
│  Phase 1 Total: 39 LLM calls → 14 rule sets                     │
│                                                                  │
│  Phase 2: Cross-Root-Cause Synthesis                            │
│                                                                  │
│  14 rule sets ───────────────► 1-2 calls → Final Rules          │
└─────────────────────────────────────────────────────────────────┘

Total: ~41 LLM calls (vs 1,869 for binary tree = 97.8% reduction)
```

**How it works:**
1. Group all FPs by `root_cause`
2. For root causes with >75 examples, batch into chunks of ~75
3. Each batch gets 1 LLM call: "Summarize these 75 FPs into failure avoidance rules"
4. If >1 batch, consolidate batch outputs into 1 rule set for that root cause
5. Final synthesis combines 14 root cause rule sets into unified output

**Advantages:**
- **97.8% fewer LLM calls** (41 vs 1,869)
- Parallelizable (all 14 root causes can run simultaneously)
- Each root cause produces focused rules for that failure mode
- Leverages the FP Judge's existing categorization work
- Batching allows LLM to see diverse examples within each category

**Phase 1 Breakdown:**

| Root Cause | Items | Batches | LLM Calls |
|------------|-------|---------|-----------|
| SEMANTIC_STRETCH | 926 | 13 | 14 |
| SCOPE_OVERREACH | 285 | 4 | 5 |
| ABSTRACT_VS_SPECIFIC | 191 | 3 | 4 |
| EXISTENCE_NOT_IMPLIED | 155 | 3 | 4 |
| EVIDENCE_OUT_OF_CONTEXT | 86 | 2 | 3 |
| STANDARD_NOT_REFERENCED | 66 | 1 | 1 |
| WRONG_SUBJECT | 54 | 1 | 1 |
| DISJUNCTION_WRONG | 43 | 1 | 1 |
| NON_BINDING_LANGUAGE | 23 | 1 | 1 |
| PROHIBITION_NOT_IMPLIED | 11 | 1 | 1 |
| GOVERNANCE_NOT_PROCEDURE | 11 | 1 | 1 |
| FREQUENCY_UNSPECIFIED | 10 | 1 | 1 |
| BINDING_NOT_INHERITED | 5 | 1 | 1 |
| UNRELATED_DOMAIN | 4 | 1 | 1 |
| **Phase 1 Total** | **1,870** | **34** | **39** |

### Option B: (Root Cause, Policy) Sampling + Batched Summarization

If we want even fewer calls, sample 1 representative FP per (root_cause, policy) pair:
- 229 samples (one per unique combination)
- All fit in ~3-4 batches
- **~5-6 LLM calls total**

**Advantages:**
- Minimal cost (~5-6 calls)
- Preserves diversity across both root causes and policy types

**Disadvantages:**
- May lose nuance from edge cases
- Single sample per (rc, policy) may not capture within-group variation

### Option C: Binary Tree MapReduce (Not Recommended)

The original binary tree approach would require:
- 1,869 LLM calls across 11 rounds
- Designed for unstructured input that needs iterative pattern extraction

**Why it's overkill:** The FP Judge already categorized each FP into structured patterns. We don't need N-1 pairwise merges to discover patterns - they're already labeled.

---

## LLM Call Estimation

### Cost Comparison Summary

| Option | LLM Calls | Approach | Parallelizable | Cost Ratio |
|--------|-----------|----------|----------------|------------|
| **Option A (Recommended)** | ~41 | Batched summarization | Yes | **2.2%** |
| **Option B** | ~5-6 | Sampled + batched | Yes | **0.3%** |
| **Option C (Not Recommended)** | 1,869 | Binary tree reduction | Partially | 100% |

### Why Batched Summarization Works Here

Binary tree reduction is designed for **unstructured input** where patterns must be discovered through iterative pairwise comparison. The formula is N-1 merges to reduce N items to 1 output.

However, the FP Judge has already:
1. **Categorized** each FP into 1 of 14 root causes
2. **Identified** which IR rules were misapplied
3. **Explained** the reasoning in structured fields

This pre-structuring means we can use **batch summarization** instead:
- Group by root cause (already done by FP Judge)
- Feed batches of ~75 examples to the LLM
- Ask it to extract failure avoidance rules from each batch
- Consolidate if multiple batches per root cause

### Option A: Batched Summarization (Detailed)

**Phase 1: 39 LLM calls (parallelizable across 14 root causes)**

For each root cause, batch examples into groups of ~75 and summarize:

| Root Cause | Items | Batches | Summarize Calls | Consolidate | Total |
|------------|-------|---------|-----------------|-------------|-------|
| SEMANTIC_STRETCH | 926 | 13 | 13 | 1 | 14 |
| SCOPE_OVERREACH | 285 | 4 | 4 | 1 | 5 |
| ABSTRACT_VS_SPECIFIC | 191 | 3 | 3 | 1 | 4 |
| EXISTENCE_NOT_IMPLIED | 155 | 3 | 3 | 1 | 4 |
| EVIDENCE_OUT_OF_CONTEXT | 86 | 2 | 2 | 1 | 3 |
| STANDARD_NOT_REFERENCED | 66 | 1 | 1 | 0 | 1 |
| WRONG_SUBJECT | 54 | 1 | 1 | 0 | 1 |
| DISJUNCTION_WRONG | 43 | 1 | 1 | 0 | 1 |
| NON_BINDING_LANGUAGE | 23 | 1 | 1 | 0 | 1 |
| PROHIBITION_NOT_IMPLIED | 11 | 1 | 1 | 0 | 1 |
| GOVERNANCE_NOT_PROCEDURE | 11 | 1 | 1 | 0 | 1 |
| FREQUENCY_UNSPECIFIED | 10 | 1 | 1 | 0 | 1 |
| BINDING_NOT_INHERITED | 5 | 1 | 1 | 0 | 1 |
| UNRELATED_DOMAIN | 4 | 1 | 1 | 0 | 1 |
| **Total** | **1,870** | **34** | **34** | **5** | **39** |

**Phase 2: 1-2 LLM calls**
- Combine 14 root cause rule sets into unified failure avoidance rules

**Grand Total: ~41 LLM calls**

### Option B: Sampled + Batched (Minimal Cost)

Sample 1 FP per (root_cause, policy) pair:
- 229 unique samples covering all combinations
- Fit into 3-4 batches of ~75 each
- 3-4 summarization calls + 1-2 synthesis calls
- **Total: ~5-6 LLM calls**

### Option C: Binary Tree MapReduce (Reference Only)

For completeness, the binary tree approach would require:
- **1,869 LLM calls** (N-1 pairwise merges)
- 11 sequential rounds
- Designed for unstructured input where patterns aren't pre-labeled

This is **not recommended** because the FP Judge has already done the pattern extraction work.

---

## Prompt Design Considerations

### Key Difference from False Negatives

For false negatives, Round 1 had to **extract** patterns from raw failure analyses.

For false positives, the FP Judge has already **categorized** each error with:
- `root_cause` (the error pattern)
- `misapplied_rules` (which IR rules were over-applied)
- `reasoning` and `evidence_critique` (the explanation)

**Option 1: Skip Round 1, Start with Consolidation**

Since root_cause is already a pattern categorization, we could:
1. Group FPs by root_cause
2. Use consolidation prompts directly to merge similar reasoning within each category
3. No need for separate "extraction" phase

**Option 2: Keep Two Phases but Adapt**

Round 1 would transform FP judge outputs into "anti-rules" (what NOT to do):
- Input: FP judge JSON with root_cause, reasoning, evidence_critique
- Output: Failure avoidance rules with `decision_effect: blocks_mapping`

### Input Format for FP Rules Aggregation

```json
{
  "control_id": "DCF-741",
  "policy_name": "Acceptable Use Policy",
  "root_cause": "SEMANTIC_STRETCH",
  "misapplied_rules": ["IR-3", "IR-4"],
  "reasoning": "The control requires a policy that outlines requirements for audit logging...",
  "evidence_critique": "The quote 'Use of computing systems is subject to monitoring'..."
}
```

### Key Fields for Rule Extraction

1. **root_cause** - The error category (already a generalization)
2. **reasoning** - Explains WHY this is an FP
3. **evidence_critique** - Explains what's WRONG with the evidence
4. **misapplied_rules** - Which IR rules the LLM misused

### Output Schema (Failure Avoidance Rules)

```json
{
  "failure_avoidance_rules": [
    {
      "rule_name": "Verify Semantic Domain Match",
      "failure_pattern": "LLM maps based on word similarity when functional domains differ",
      "recovery_heuristic": "Verify that matching terms serve the same functional purpose in both control and policy",
      "root_causes_addressed": ["SEMANTIC_STRETCH"],
      "ir_rules_involved": ["IR-3"],
      "control_triggers": ["audit", "logging", "monitoring"],
      "policy_cues": ["subject to monitoring", "tracking", "metrics"],
      "decision_effect": "blocks_mapping",
      "frequency": "very_common"
    }
  ]
}
```

---

## Implementation Plan

### Phase 1: FP Loader (New)

Create `false_positive_loader.py` (similar to `false_negative_loader.py`) that:
1. Loads all `fp_judge_*.json` files from validation output
2. Groups by policy (for per-document batching)
3. Formats for aggregation prompt

### Phase 2: Config Extension

Add to `config.py`:
```python
mode: Literal["mapping-reasons", "false-negatives", "false-positives"] = "mapping-reasons"
false_positive_results_dir: Path = FP_VALIDATION_OUTPUTS_DIR / "{timestamp}"
false_positive_prompts_dir: Path = SCRIPT_DIR / "prompts" / "false_positive_analysis"
```

### Phase 3: Prompts

Create `prompts/false_positive_analysis/`:
- `system`: Explain FP analysis task, reference root cause taxonomy and IR rules
- `user`: Template with FP details
- `response.json`: Schema for failure avoidance rules

Create `prompts/consolidate_fp_patterns/` (or reuse existing consolidation prompts with minor tweaks)

### Phase 4: CLI Extension

Add `--mode false-positives` flag to `run.py`

---

## Summary

| Strategy | LLM Calls | Cost Ratio | Recommendation |
|----------|-----------|------------|----------------|
| **Batched Summarization** | ~41 | **2.2%** | **Recommended** |
| Sampled + Batched | ~5-6 | 0.3% | Minimal cost option |
| Binary Tree MapReduce | 1,869 | 100% | Not recommended |

**Recommendation:** Use **Batched Summarization** (Option A):
1. Group FPs by root_cause (already done by FP Judge)
2. Batch ~75 examples per LLM call for summarization
3. Consolidate batches within each root cause
4. Final synthesis across 14 root cause rule sets

**Why this works:** The FP Judge has already performed pattern extraction by categorizing each FP into 1 of 14 root causes with structured reasoning. We don't need iterative pairwise merging to discover patterns - they're already labeled. Batched summarization leverages this structure for a **97.8% reduction in LLM calls** (41 vs 1,869).

---

## Appendix A: FP Judge Prompts

The FP Judge uses three prompt files located at `prompts/fp_judge/`:

### System Prompt (`system`)

```
You are a Security Compliance Auditor analyzing false positive mappings from a policy-to-control mapping system.

## Your Task

A mapping LLM previously determined that a control MAPS to a policy document. However, ground truth (human-labeled data) indicates this is a **false positive** - the control should NOT have mapped.

Your job is to analyze WHY the mapping LLM made this error. In addition to explaining why, you should determine:
1. **Which Interpretive Rules were misapplied if any?** (IR-1 through IR-10)
2. **What is the root cause pattern?** (from controlled vocabulary below)

## Root Cause Categories

When identifying the root cause, select EXACTLY ONE of these values:

### IR Rule Misapplication

| Code | Description | Related IR |
|------|-------------|------------|
| SCOPE_OVERREACH | Policy scope doesn't actually cover control's target assets | IR-1 |
| ABSTRACT_VS_SPECIFIC | LLM incorrectly applied Tech→Abstract rule | IR-2 |
| SEMANTIC_STRETCH | Words seem similar but functional outcome differs | IR-3 |
| GOVERNANCE_NOT_PROCEDURE | Policy states intent but control needs actionable procedure | IR-4 |
| FREQUENCY_UNSPECIFIED | Control requires specific timing; policy is silent | IR-5 |
| EXISTENCE_NOT_IMPLIED | Using X doesn't imply having X documented/established | IR-6 |
| PROHIBITION_NOT_IMPLIED | Positive mandate doesn't imply prohibition of alternatives | IR-7 |
| BINDING_NOT_INHERITED | List items don't inherit header's binding language | IR-8 |
| STANDARD_NOT_REFERENCED | Referenced standard doesn't actually cover this control | IR-9 |
| DISJUNCTION_WRONG | Control requires A AND B; policy only provides one | IR-10 |

### Basic Errors (Not IR-Related)

| Code | Description |
|------|-------------|
| NON_BINDING_LANGUAGE | Evidence uses "should/may/can" not "shall/must/required" |
| WRONG_SUBJECT | Policy applies to different entity than control requires |
| UNRELATED_DOMAIN | Policy and control are in completely different domains |
| EVIDENCE_OUT_OF_CONTEXT | Quote came from definitions/objectives/background, not requirements |

## APPENDIX: Original Mapping System Prompt

<original_mapping_prompt>
{ORIGINAL_MAPPING_PROMPT}
</original_mapping_prompt>
```

**Key Design Decisions:**
- The original mapping system prompt is injected into the FP Judge's context so it can evaluate whether IR rules were correctly applied
- Root causes map 1:1 to IR rules for traceability
- Two verdict options: `CONFIRMED_FP` or `UNCERTAIN`

### User Prompt Template (`user`)

```xml
The mapping LLM determined this control MAPS to the policy document (uploaded in context).
However, ground truth indicates this is a false positive - the control should NOT map to this policy.

Analyze why this is a false positive.

<control>
  <id>{control_id}</id>
  <name>{control_name}</name>
  <description>{control_description}</description>
</control>

<original_llm_evaluation>
  <decision>{llm_decision}</decision>
  <confidence>{llm_confidence}</confidence>
  <reasoning>{llm_reasoning}</reasoning>
  <evidence_quote>{llm_evidence_quote}</evidence_quote>
  <location>{llm_evidence_location}</location>
  <gaps_identified>{llm_gaps}</gaps_identified>
</original_llm_evaluation>
```

### Response Schema (`response.json`)

```json
{
  "type": "object",
  "properties": {
    "control_id": { "type": "string" },
    "verdict": { "enum": ["CONFIRMED_FP", "UNCERTAIN"] },
    "confidence": { "enum": ["high", "medium", "low"] },
    "misapplied_rules": { "type": "array", "items": { "type": "string" } },
    "root_cause": { "enum": "ROOT_CAUSE_VALUES" },
    "reasoning": { "type": "string" },
    "evidence_critique": { "type": "string" }
  },
  "required": ["control_id", "verdict", "confidence", "misapplied_rules", "root_cause", "reasoning", "evidence_critique"]
}
```

---

## Appendix B: FP Judge Output Examples

### Directory Structure

```
files/llm_outputs/fp_validation/20251229_221006/
├── detailed_results.json          # All 1,870 results in one file
├── fp_analysis_summary.json       # Aggregate statistics
├── fp_confirmed.csv               # CSV export of confirmed FPs
├── fp_uncertain.csv               # CSV export of uncertain cases
├── run_metadata.json              # Run configuration
├── Acceptable_Use_Policy/
│   ├── fp_judge_DCF-741.json
│   ├── fp_judge_DCF-107.json
│   └── ... (212 files)
├── Asset_Management_Policy/
│   └── ... (158 files)
├── AI_Governance_Policy/
│   └── ... (157 files)
├── Information_Security_Policy/
│   └── ... (126 files)
└── ... (33 policy directories total, 1,870 fp_judge_*.json files)
```

Each `fp_judge_*.json` file contains a structured analysis of why a specific MAPPED decision was incorrect.

### Example 1: SEMANTIC_STRETCH (Most Common - 49.5%)

**File:** `Acceptable_Use_Policy/fp_judge_DCF-741.json`

```json
{
  "control_id": "DCF-741",
  "policy_name": "Acceptable Use Policy",
  "verdict": "CONFIRMED_FP",
  "confidence": "high",
  "reasoning": "The control requires a policy that outlines requirements for the creation, retention, and review of audit logs (an IT/Security governance mandate). The cited evidence is a standard Acceptable Use Policy clause informing users they have no expectation of privacy ('subject to monitoring'). While the words match, the functional outcome is different: one is a user waiver, the other is a system configuration mandate.",
  "misapplied_rules": ["IR-3", "IR-4"],
  "root_cause": "SEMANTIC_STRETCH",
  "evidence_critique": "The quote 'Use of... computing systems is subject to monitoring' establishes the organization's right to monitor users (negating privacy expectations), but it does not mandate that systems *must* be configured to capture audit logs, nor does it establish requirements for what must be logged.",
  "original_fp": {
    "llm_confidence": "high",
    "llm_reasoning": "Mapped via IR-4: Policy establishes the governance mandate for monitoring; specific logging parameters are considered technical/procedural implementation details.",
    "llm_evidence_quote": "Use of [COMPANY NAME] computing systems is subject to monitoring by [COMPANY NAME] IT and/or Security teams.",
    "llm_evidence_location": "Page 5 - Procedures",
    "batch_file": "batch_024.json"
  }
}
```

**Lesson:** "monitoring" (user privacy waiver) ≠ "logging" (system configuration mandate)

### Example 2: SCOPE_OVERREACH (15.2%)

**File:** `Software_Development_Life_Cycle_Policy/fp_judge_DCF-987.json`

```json
{
  "control_id": "DCF-987",
  "policy_name": "Software Development Life Cycle Policy",
  "verdict": "CONFIRMED_FP",
  "confidence": "high",
  "reasoning": "The control requires the organization to perform backups of applications and settings generally (operational/production scope). The cited policy is strictly an SDLC policy, and the specific evidence refers only to the configuration of the 'Secure development environment'. Requirements for development environment backups do not satisfy the broader organizational mandate for production application and setting backups.",
  "misapplied_rules": ["IR-1"],
  "root_cause": "SCOPE_OVERREACH",
  "evidence_critique": "The quoted text 'backups are stored at secure offsite locations' is a sub-bullet defining criteria specifically for the 'Secure development environment' (Page 3). It does not apply to the organization's general production applications or settings.",
  "original_fp": {
    "llm_confidence": "high",
    "llm_reasoning": "Mapped via IR-4 and IR-6: The policy mandates that the secure development environment includes backups stored at secure offsite locations.",
    "llm_evidence_quote": "backups are stored at secure offsite locations;",
    "llm_evidence_location": "Page 3 - SDLC Security Control Guidelines",
    "batch_file": "batch_037.json"
  }
}
```

**Lesson:** Development environment requirements ≠ Production environment requirements

### Example 3: ABSTRACT_VS_SPECIFIC (10.2%)

**File:** `System_Security_Planning_Policy/fp_judge_DCF-215.json`

```json
{
  "control_id": "DCF-215",
  "policy_name": "System Security Planning Policy",
  "verdict": "CONFIRMED_FP",
  "confidence": "high",
  "reasoning": "The control requires operational measures to secure network security configuration files and keep them consistent. The mapping LLM incorrectly applied IR-2 (Abstract vs Specific) by equating a requirement to 'describe the overall philosophy' regarding information protection with a mandate to actually secure specific technical assets. A requirement to document a security philosophy is a governance meta-requirement, not an operational mandate.",
  "misapplied_rules": ["IR-2"],
  "root_cause": "ABSTRACT_VS_SPECIFIC",
  "evidence_critique": "The cited evidence mandates the content of an 'Information Security Architecture' document (specifically, that it must describe the organization's philosophy). It does not mandate the actual security configuration or consistency checks of network devices.",
  "original_fp": {
    "llm_confidence": "medium",
    "llm_reasoning": "Mapped via IR-2: The policy mandates an architecture focused on protecting the confidentiality, integrity, and availability of all organizational information.",
    "llm_evidence_quote": "Describe the overall philosophy, requirements, and approach to be taken with regard to protecting the confidentiality, integrity, and availability of organizational information.",
    "llm_evidence_location": "Section: Information Security Architecture, Page 2",
    "batch_file": "batch_012.json"
  }
}
```

**Lesson:** "Describe the philosophy" (documentation requirement) ≠ "Secure the asset" (operational requirement)

### Example 4: EXISTENCE_NOT_IMPLIED (8.3%)

**File:** `Software_Development_Life_Cycle_Policy/fp_judge_DCF-509.json`

```json
{
  "control_id": "DCF-509",
  "policy_name": "Software Development Life Cycle Policy",
  "verdict": "CONFIRMED_FP",
  "confidence": "high",
  "reasoning": "The control specifically requires a responsibility matrix or document that delineates which security requirements are managed by the entity versus the service provider (a specific PCI DSS requirement). The policy only mandates including security requirements within contracts. The existence of contractual clauses does not imply the existence or maintenance of a specific responsibility matrix document.",
  "misapplied_rules": ["IR-6"],
  "root_cause": "EXISTENCE_NOT_IMPLIED",
  "evidence_critique": "The cited evidence requires that contracts include provisions for secure design, coding, and testing. It does not mandate the creation or maintenance of a document that specifically maps out the division of security responsibilities.",
  "original_fp": {
    "llm_confidence": "medium",
    "llm_reasoning": "Mapped via IR-6: The mandate to establish contractual requirements for secure practices implies the maintenance of documented information regarding which security responsibilities are managed by the provider.",
    "llm_evidence_quote": "Contractual requirements for secure design, coding and testing practices.",
    "llm_evidence_location": "Page 5 - SDLC Security Control Guidelines",
    "batch_file": "batch_019.json"
  }
}
```

**Lesson:** "Include in contract" ≠ "Maintain a responsibility matrix"

### Example 5: DISJUNCTION_WRONG (2.3%)

**File:** `Software_Development_Life_Cycle_Policy/fp_judge_DCF-301.json`

```json
{
  "control_id": "DCF-301",
  "policy_name": "Software Development Life Cycle Policy",
  "verdict": "CONFIRMED_FP",
  "confidence": "high",
  "reasoning": "The control explicitly mandates a conjunctive set of requirements, including that 'Code-review results are reviewed and approved by management prior to release.' While the policy mandates peer review and general change approval by an environment owner, it fails to explicitly require management review and approval of the code review findings/results themselves. The mapping LLM treated the partial match (peer review only) as a complete mapping.",
  "misapplied_rules": ["IR-10"],
  "root_cause": "DISJUNCTION_WRONG",
  "evidence_critique": "The cited evidence ('Code changes are reviewed by individuals other than the originating code author...') only establishes the peer review requirement. It does not contain any language addressing the control's distinct requirement for management review and approval of the code-review results.",
  "original_fp": {
    "llm_confidence": "high",
    "llm_reasoning": "Mapped via direct binding evidence: The policy explicitly mandates peer review by knowledgeable individuals and implementation of corrections prior to release.",
    "llm_evidence_quote": "Code changes are reviewed by individuals other than the originating code author and by individuals who are knowledgeable in code review techniques and secure coding practices.",
    "llm_evidence_location": "Page 3 - SDLC Security Control Guidelines",
    "batch_file": "batch_036.json"
  }
}
```

**Lesson:** "Peer review" (requirement A) ≠ "Management approval of review results" (requirement B). Control needs BOTH.

### Example 6: Same Control, Different Root Causes Across Policies

DCF-741 (Logging & Monitoring Policy) appears as an FP in 6 different policies, each with a **different root cause**:

| Policy | Root Cause | Why |
|--------|------------|-----|
| Acceptable Use Policy | SEMANTIC_STRETCH | "monitoring users" ≠ "logging mandate" |
| Asset Management Policy | EXISTENCE_NOT_IMPLIED | "enable logging" ≠ "logging policy" |
| Code of Conduct | STANDARD_NOT_REFERENCED | InfoSec reference ≠ logging policy |
| Information Security Policy | BINDING_NOT_INHERITED | Example ≠ mandate |
| AI Governance Policy | SEMANTIC_STRETCH | AI metrics ≠ system logging |
| AI Risk Management Policy | SEMANTIC_STRETCH | AI monitoring ≠ audit logging |

This demonstrates why **control ID alone cannot consolidate FPs** - the same control fails for different reasons in different policy contexts.

---

## Appendix C: False Negative Round 1 Prompt (Reference)

The false negative analysis prompt provides a template for FP analysis:

**Key elements to adapt:**
1. **Decision Framework:** Replace "4 Critical Questions for valid mapping" with "IR Rules that should NOT be over-applied"
2. **Failure Patterns:** Flip from "what LLM missed" to "what LLM incorrectly accepted"
3. **Recovery Heuristics:** Focus on "when to reject" rather than "when to accept"

**System prompt structure:**
- Role definition (GRC Auditor analyzing LLM errors)
- Context (what FPs are, why they happen)
- The Original Decision Framework (IR Rules 1-10)
- Common Failure Patterns (mapped to IR rules)
- Output Quality criteria (actionable, generalizable)

**User prompt structure:**
- Source 1 and Source 2 FP data
- Task: Create master list using Union + Consolidate
- Output format table
- Valid enum values
