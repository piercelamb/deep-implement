# Inverse Polarity Question Classification Fix

## Problem Statement

Questions like "Has the vendor experienced a security breach in the last 36 months?" are being misclassified. When evidence shows NO breach occurred, the LLM correctly identifies this but classifies it as `NOT_MET` instead of `MET`.

**Example from production:**
```json
{
  "vendor_compliance_classification": "NOT_MET",
  "classification_explanation": "The evidence explicitly states that no security incidents occurred during the audit period..."
}
```

The LLM's reasoning is correct (no breach occurred), but the classification is inverted because:
- The question asks about a **negative outcome** (breach occurred)
- A "NO" answer to this question is actually **positive for compliance**
- Current prompts assume affirmative logic: "answered positively" = MET

## Root Cause Analysis

### 1. criteria_to_questions Workflow

**Location:** `ai_services/vellum/support/vrm_agent_q3_fy26/criteria_to_questions/prompts/criteria_to_questions/user`

The prompt instructs (line 10-11):
> "Phrase the question in affirmative voice (Does/What/How...)"

This works for most criteria but creates semantic confusion for "inverse polarity" questions where the desirable answer is "no".

### 2. gather_evidence Workflow

**Location:** `ai_services/vellum/support/vrm_agent_q3_fy26/gather_evidence/prompts/gather_and_assess_evidence/user`

The classification definition (line 4):
> "MET: The vendor fully satisfies the security question. There is sufficient, coherent evidence in the excerpts that the question can be truthfully answered positively."

The phrase "answered positively" conflates two concepts:
1. A positive/affirmative answer ("yes")
2. A positive compliance outcome (good for security posture)

For inverse questions, these are opposites.

## Solution Strategy

Two-pronged approach targeting both workflows:

### Prong 1: Question Reframing in criteria_to_questions

**Goal:** Transform inverse-polarity questions into affirmative-polarity equivalents during question generation.

**Approach:** Add guidance to detect questions where a "NO" answer indicates compliance, then reframe them.

**Examples:**
| Original (Inverse Polarity) | Reframed (Affirmative Polarity) |
|---------------------------|--------------------------------|
| Has the vendor experienced a security breach in the last 36 months? | Has the vendor maintained a clean security record with no breaches in the last 36 months? |
| Has sensitive data been exposed publicly? | Is sensitive data properly protected from public exposure? |
| Have there been any compliance violations? | Has the vendor maintained compliance without violations? |
| Does the vendor lack encryption for data at rest? | Does the vendor implement encryption for data at rest? |

**Detection Heuristics:**
- Questions asking about incidents, breaches, violations, failures, exposures
- Questions with negative terms: "lack", "fail to", "not have"
- Questions where the ideal answer for compliance is "no"

### Prong 2: Classification Guardrails in gather_evidence

**Goal:** Help the LLM correctly reason about the compliance implication of its findings, regardless of question polarity.

**Approach:** Add explicit guidance for handling inverse-polarity questions in the classification prompt.

---

## Implementation Plan

### Phase 1: Update criteria_to_questions Prompts

**Files to modify:**
- `ai_services/vellum/support/vrm_agent_q3_fy26/criteria_to_questions/prompts/criteria_to_questions/user`
- `ai_services/vellum/support/vrm_agent_q3_fy26/criteria_to_questions/prompts/user_criteria_to_questions/user`

**Changes:**

Add new section to `<rag_optimization_principles>`:

```
8. **Reframe inverse-polarity questions into affirmative compliance terms**
   - Some questions ask about negative outcomes (breaches, incidents, violations, failures)
   - For these, a "NO" answer actually indicates good compliance
   - Reframe so that "YES" = compliant:
     - "Has the vendor experienced a security breach?" → "Has the vendor maintained a clean security record without breaches?"
     - "Have there been compliance violations?" → "Has the vendor maintained full compliance without violations?"
   - Detection triggers: breach, incident, violation, failure, exposure, leak, compromise, lack of, fail to
   - The goal: MET should always align with a "yes" answer
```

Add explicit instruction in `<instructions>`:
```
4. For each question, ensure that a "YES" answer indicates positive compliance (MET). If the original criterion asks about negative outcomes, reframe the question in affirmative compliance terms.
```

### Phase 2: Update gather_evidence Prompts

**Files to modify:**
- `ai_services/vellum/support/vrm_agent_q3_fy26/gather_evidence/prompts/gather_and_assess_evidence/user`

**Changes:**

Revise the `<vendor_compliance_classifications>` section:

```xml
<vendor_compliance_classifications>
MET: The vendor demonstrates positive compliance with the security question. The evidence supports that the vendor meets the security expectation implied by the question.
NOT_MET: The vendor fails to demonstrate compliance. Evidence shows the vendor does not meet the security expectation implied by the question.
INCONCLUSIVE: Evidence is relevant but insufficient to determine compliance, or all evidence is irrelevant to the question.
NOT_APPLICABLE: The vendor explicitly states the criterion is not applicable to them.
CONTRADICTORY: Evidence provides mixed or conflicting signals about compliance.

IMPORTANT - Inverse Polarity Questions:
Some questions ask about negative outcomes (breaches, incidents, violations). For these questions:
- Evidence showing NO breach/incident occurred = MET (good compliance)
- Evidence showing a breach/incident DID occur = NOT_MET (poor compliance)

Example: "Has the vendor maintained a clean security record without breaches in the last 36 months?"
- Evidence states "no security incidents occurred" → MET
- Evidence states "the vendor experienced a breach" → NOT_MET

Always classify based on the COMPLIANCE OUTCOME, not literal yes/no answer matching.
</vendor_compliance_classifications>
```

Add to `<instructions>`:
```
3.5. Before classifying, identify whether this is an inverse-polarity question (asking about negative outcomes). If so, remember: evidence of NO negative outcome = MET, evidence OF negative outcome = NOT_MET.
```

### Phase 3: Testing

1. **Unit tests for question reframing:**
   - Test that inverse-polarity criteria get reframed correctly
   - Add test cases in `tests/vellum/workflows/vrm_agent_q3_fy26/criteria_to_questions/`

2. **Integration tests for classification:**
   - Test the specific security breach scenario
   - Add test cases with known inverse-polarity questions
   - Add test cases in `tests/vellum/workflows/vrm_agent_q3_fy26/gather_evidence/`

3. **Manual validation:**
   - Run sandbox with the specific failing criterion
   - Verify classification is now correct

---

## Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| `ai_services/vellum/support/vrm_agent_q3_fy26/criteria_to_questions/prompts/criteria_to_questions/user` | Edit | Add inverse-polarity reframing guidance |
| `ai_services/vellum/support/vrm_agent_q3_fy26/criteria_to_questions/prompts/user_criteria_to_questions/user` | Edit | Add inverse-polarity reframing guidance |
| `ai_services/vellum/support/vrm_agent_q3_fy26/gather_evidence/prompts/gather_and_assess_evidence/user` | Edit | Revise classification definitions and add inverse-polarity handling |

---

## Risk Assessment

**Low Risk:**
- Changes are limited to prompt text only
- No schema changes required
- No code logic changes
- Easy to roll back by reverting prompt files

**Potential Edge Cases:**
- Questions that appear inverse but aren't (false positive detection)
- Double-negatives creating confusion
- Context-dependent interpretation

**Mitigation:**
- Focus on clear, common patterns (breach, incident, violation)
- Test thoroughly with diverse question types
- Monitor classification accuracy after deployment

---

## Alternative Approaches Considered

### Alternative 1: Schema-based Approach
Add `is_inverse: bool` flag to `CriteriaQuestionDTO`, set by criteria_to_questions, and flip classification in gather_evidence.

**Rejected because:**
- Requires schema changes across multiple DTOs
- More complex implementation
- Prompt-based approach is simpler and more flexible

### Alternative 2: Post-processing Classification Flip
Detect inverse questions in gather_evidence output processing and flip MET/NOT_MET.

**Rejected because:**
- Heuristic detection is error-prone
- Doesn't fix the root cause
- LLM reasoning would still be confusing in explanations

### Alternative 3: Semantic Analysis Node
Add a dedicated node to analyze question semantics and determine polarity before classification.

**Rejected because:**
- Over-engineering for this problem
- Additional latency and cost
- Prompt guidance is sufficient

---

## Success Criteria

1. The specific "security breach" question classifies as `MET` when evidence shows no breaches
2. Other inverse-polarity questions are handled correctly
3. Normal (affirmative-polarity) questions continue to work correctly
4. No regression in overall classification accuracy
