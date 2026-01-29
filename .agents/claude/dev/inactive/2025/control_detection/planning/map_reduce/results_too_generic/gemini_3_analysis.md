Based on the Executive Summary and Analysis in your README, the core issue is a misalignment between **intent** (prediction/automation) and **instruction** (abstraction/classification).

You asked the LLM to identify "universal patterns" and "linguistic markers." The LLM succeeded: it told you *what the data looks like* (descriptive). However, to automate GRC mapping, you need to know *how to make the decision* (prescriptive).

Here are four specific strategies to change your prompts to produce actionable heuristics rather than abstract descriptions.

---

### 1. Shift from "Descriptive Nouns" to "Imperative Verbs"

**The Diagnosis:**
Your current patterns are Nouns (e.g., "Comprehensive Scope," "Explicit Mandate"). These describe the *state* of a valid policy.
**The Fix:**
Force the LLM to generate Verbs (e.g., "Verify Scope," "Check for Mandate"). You want algorithms, not categories.

**Changes to Round 1 (Map) System Prompt:**
*   **Remove:** "Focus on Abstract patterns... Linguistic markers..."
*   **Add:** "Focus on **Decision Logic**. Imagine you are writing a python function `def does_policy_map(control, policy):`. What specific checks must return `True` for the mapping to be valid? Formulate every pattern as an **instruction** to a junior auditor."

### 2. Introduce "Counter-Factual" Reasoning

**The Diagnosis:**
The current patterns explain why a mapping is *good*. They don't explain what would make it *bad*. Without the "failure condition," an LLM using these patterns for prediction will likely be too permissive (false positives).
**The Fix:**
Ask the LLM to identify the "Critical Necessity."

**Changes to Round 1 (Map) User Prompt:**
Add a new requirement to the extraction logic:
> "For every reasoning pattern you identify, you must explicitly state the **Failure Condition**. If this specific element were missing from the policy, why would the mapping be rejected?
>
> *Example:*
> *Pattern:* Semantic Equivalence
> *Logic:* Policy uses different terms but implies same outcome.
> *Failure Condition:* If the policy terminology implies a *narrower* scope than the control (e.g., control says 'external media' but policy only says 'USB drives'), the mapping fails."

### 3. Redefine the Output Schema (The most impactful change)

Change your JSON schema to enforce the "Algorithm" structure. If you change the shape of the container, the LLM will change the shape of the liquid.

**New Schema Proposal:**

```json
{
  "type": "object",
  "properties": {
    "heuristics": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "rule_name": { "type": "string" },
          "auditor_instruction": {
            "type": "string",
            "description": "An imperative step-by-step instruction on what to look for."
          },
          "required_evidence": {
            "type": "string",
            "description": "The specific text or structure that MUST be present."
          },
          "success_criteria": {
             "type": "string",
             "description": "The logical condition that confirms the match (e.g., 'Policy scope >= Control scope')."
          },
          "failure_mode": {
            "type": "string",
            "description": "The specific condition that invalidates the match."
          }
        }
      }
    }
  }
}
```

### 4. Revised "Map Phase" Prompt (Full Example)

Here is how I would rewrite your `aggregate_reasons` prompt to fix the "too abstract" issue.

#### New System Prompt
```text
You are a Senior IT Auditor teaching a junior auditor how to validate security controls.
You are analyzing 'Generalized Reasons' that explain why a specific Policy maps to a specific Control.

Your goal is NOT to describe the text. Your goal is to extract the **Verification Logic**.
For each reason provided, reverse-engineer the "Test Step" the auditor performed.

Ask yourself:
1. What specific check did the auditor perform?
2. What distinct piece of information confirmed the match?
3. What is the logic: Is it a keyword match? A hierarchy check? A generic fallback?
```

#### New User Prompt
```text
Analyze the following generalized reasons from {NUM_SOURCES} mappings.

## Source 1: {SOURCE_1_NAME}
{SOURCE_1_REASONS}

... [Sources] ...

Your task: Extract **Actionable Mapping Heuristics**.
Do not create generic categories like "Scope Definition."
Create specific rules like "Verify Policy Scope encompasses Control Entity."

For each heuristic, provide:
1. **Rule Name**: Short, action-oriented name (e.g., "Check Mandate Strength").
2. **Logic**: The step-by-step reasoning (e.g., "1. Identify control verb. 2. Scan policy for 'must/shall'. 3. Ensure policy action is not optional.").
3. **mapping_pattern**: (Use existing Enum).
4. **observed_in**: (Use existing Enum).

## Constraint on Abstraction
Do not become SO abstract that the rule is meaningless.
BAD: "The policy aligns with the control." (Too generic)
BAD: "The policy mentions USB drives." (Too specific)
GOOD: "The policy explicitly restricts the specific asset class mentioned in the control."
```

### Expected Result Difference

**Current Result (from your README):**
> **Pattern:** Comprehensive Scope and Applicability
> **Description:** The policy explicitly defines the boundaries...

**Predicted New Result:**
> **Heuristic:** Scope Coverage Verification
> **Logic:** Compare the "Applicability" section of the Policy against the "Target" of the Control. If the Control targets "All Systems" but the Policy Applicability lists only "Production Servers," reject the mapping. The Policy set must be a superset or equal to the Control set.

This new output allows you to prompt a future LLM with: *"Apply the 'Scope Coverage Verification' heuristic to these documents. Does the policy fail the check?"*