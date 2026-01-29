# Prompt Improvement Plan: From Generic to Discriminative Patterns

## Problem Statement

The current prompts produce patterns that are **correct but not discriminative**. They describe what policies *are* rather than what helps map policies to *specific controls*.

### Evidence of the Problem

| Pattern | Source Count | Problem |
|---------|--------------|---------|
| "Policy defines scope" | 36/37 | Tautological—all policies define scope |
| "Policy uses imperative language" | 35/37 | Tautological—all policies use "shall/must" |
| "Policy has procedures" | 35/37 | Tautological—all policies describe procedures |

These patterns don't help an LLM decide: "Does this policy map to **encryption controls** vs **access control** vs **incident response**?"

### Root Cause Analysis

The current prompts explicitly instruct:

> "Do NOT include policy-specific or control-specific details. Aim for patterns that could be applied to ANY policy-control mapping task."

This instruction naturally produces descriptions of what **all policies have in common**—which is exactly what we got. The prompts optimized for universality at the expense of discrimination.

**Key insight**: We threw away the control context entirely. The input only contains `generalized_reason` strings without any information about which controls they mapped to. The LLM has no basis for learning discriminative patterns.

---

## Goal Restatement

We want patterns that help an LLM answer:

> "Given this policy text and this control requirement, should they be mapped? Why or why not?"

This requires **discriminative** patterns—patterns that distinguish between:
- Policies that map to encryption controls vs. those that don't
- Policies that map to incident response vs. access control
- What makes a mapping valid vs. invalid

---

## Proposed Approaches

### Approach 1: Control-Family-Aware Aggregation

**Idea**: Instead of aggregating ALL reasons together, group by control family first, then extract patterns per group.

```
Current Flow:
  All Policies × All Controls → Mixed Reasons → Generic Patterns

Proposed Flow:
  Encryption Mappings → Encryption-Specific Patterns
  Access Control Mappings → Access-Specific Patterns
  Incident Response Mappings → IR-Specific Patterns
  → Contrastive Analysis → Discriminative Patterns
```

**Prompt Change**:
```
You are analyzing reasons why policies map to ENCRYPTION controls specifically.
What characteristics of policy text indicate a mapping to encryption requirements?
What linguistic markers, technical specifications, or procedural elements are unique
to encryption control mappings (as opposed to other control types)?
```

**Pros**:
- Naturally produces domain-specific patterns
- Patterns would be actionable: "When mapping to encryption controls, look for X"
- Leverages control taxonomy we already have

**Cons**:
- Requires restructuring input data by control family
- May produce many control-specific patterns that are hard to generalize
- Need to define control families (DCF has categories we could use)

**Implementation Complexity**: Medium (requires input reorganization)

---

### Approach 2: Contrastive Prompting

**Idea**: Change the question from "what patterns exist?" to "what distinguishes X from Y?"

**Current Prompt Goal**:
> "Identify UNIVERSAL PATTERNS that appear across multiple mappings"

**Proposed Prompt Goal**:
> "Identify what DISTINGUISHES policies that map to specific controls from those that don't"

**Example Prompt**:
```
You are given two sets of mapping reasons:

## Set A: Reasons why policies mapped to ENCRYPTION controls
{ENCRYPTION_REASONS}

## Set B: Reasons why policies mapped to ACCESS CONTROL controls
{ACCESS_CONTROL_REASONS}

Your task is to identify DISCRIMINATIVE FEATURES:
1. What characteristics appear in Set A but NOT in Set B?
2. What characteristics appear in Set B but NOT in Set A?
3. What would help an auditor quickly decide which category a new mapping belongs to?

Focus on features that DIFFERENTIATE, not features that are common to both.
```

**Pros**:
- Directly optimizes for discrimination
- Produces actionable decision criteria
- Natural fit for binary classification

**Cons**:
- Requires paired comparison (N choose 2 combinations?)
- May miss patterns that appear in both but at different frequencies
- Computationally more complex

**Implementation Complexity**: High (requires pairwise comparisons)

---

### Approach 3: Include Control Context in Aggregation

**Idea**: The current input strips control information. Add it back.

**Current Input Format**:
```
## Source 1: Data_Protection_Policy
- "The policy defines mandatory requirements for protecting sensitive data"
- "The policy specifies encryption standards for data at rest"
```

**Proposed Input Format**:
```
## Source 1: Data_Protection_Policy

### Mappings to Encryption Controls (DCF-201, DCF-203, DCF-207)
- "The policy specifies encryption standards for data at rest and in transit"
- "The policy mandates AES-256 for sensitive data encryption"

### Mappings to Access Controls (DCF-101, DCF-105)
- "The policy defines role-based access requirements"
- "The policy specifies authentication procedures"
```

**Prompt Change**:
```
For each control category, identify:
1. What patterns in the reasons are SPECIFIC to that control category?
2. What would help distinguish mappings to this category from others?
3. What linguistic/structural markers signal this type of control?
```

**Pros**:
- Preserves control context that enables discrimination
- Minimal change to existing infrastructure
- Can still use map-reduce architecture

**Cons**:
- Larger input (more tokens per policy)
- May still converge to generic patterns without explicit contrast instruction
- Need to categorize controls

**Implementation Complexity**: Low-Medium (input restructuring only)

---

### Approach 4: Two-Phase Architecture

**Idea**: Keep current extraction as Phase 1, add discriminative distillation as Phase 2.

```
Phase 1 (Current): Extract all patterns via map-reduce
  Output: 13 patterns (8 universal, 5 rare)

Phase 2 (New): Discriminative distillation
  Input: Phase 1 patterns + control mapping metadata
  Task: "Which patterns predict specific control families?"
  Output: 10-15 discriminative heuristics
```

**Phase 2 Prompt**:
```
You have extracted these universal patterns from policy-control mappings:
{UNIVERSAL_PATTERNS}

And these rare/edge-case patterns:
{RARE_PATTERNS}

Given the following control family distribution:
- Encryption controls: Patterns 1, 3, 5 appear in 80%+ of mappings
- Access controls: Patterns 2, 4, 6 appear in 90%+ of mappings
- Incident response: Patterns 1, 7, 8 appear in 70%+ of mappings

Your task is to synthesize DISCRIMINATIVE HEURISTICS:
1. For each control family, what combination of patterns best predicts a mapping?
2. What is UNIQUE to each control family (not shared with others)?
3. Create decision rules an auditor could follow.

Output format:
- "If policy has [X] AND [Y] but NOT [Z], likely maps to [control family]"
```

**Pros**:
- Leverages existing work (Phase 1 complete)
- Clear separation of concerns
- Can iterate on Phase 2 independently

**Cons**:
- Adds complexity
- Phase 1 patterns may still be too generic to enable discrimination
- Requires control family metadata we'd need to compute

**Implementation Complexity**: Medium (new phase, but reuses Phase 1 output)

---

### Approach 5: Negative Examples

**Idea**: Include examples of policies that DON'T map to certain controls. Learn from contrast.

**Current Data**: Only includes positive mappings (policy X maps to control Y because Z)

**Proposed Addition**: Include non-mappings or weak mappings

**Example Input**:
```
## Strong Mappings (Encryption Controls)
- Data_Protection_Policy: "Policy mandates AES-256 encryption" → MAPS
- Encryption_Policy: "Policy specifies key management procedures" → MAPS

## Weak/Non-Mappings (Encryption Controls)
- Code_of_Conduct: "Policy mentions data handling but no encryption specifics" → DOES NOT MAP
- Physical_Security_Policy: "Policy addresses facility access, not cryptographic controls" → DOES NOT MAP

What distinguishes the strong mappings from the weak/non-mappings?
```

**Pros**:
- Classic supervised learning approach (positive vs negative examples)
- Naturally produces decision boundaries
- Could improve precision in mapping predictions

**Cons**:
- We don't have explicit negative examples in our data
- Would need to generate or infer non-mappings
- Risk of teaching model what "bad" looks like rather than what "good" looks like

**Implementation Complexity**: High (requires generating/curating negative examples)

---

### Approach 6: Question Reframing

**Idea**: Simple prompt reframe without changing architecture.

**Current Question**:
> "What patterns exist in how policies map to controls?"

**Reframed Question**:
> "What should an auditor look for in a policy to decide if it maps to a specific control?"

**Specific Prompt Changes**:

| Current | Proposed |
|---------|----------|
| "Identify UNIVERSAL PATTERNS" | "Identify DECISION CRITERIA" |
| "Abstract patterns that apply regardless of control" | "Specific signals that indicate mapping to particular control types" |
| "Do NOT include control-specific details" | "Include control-family-specific signals when relevant" |
| "Patterns that could be applied to ANY mapping" | "Patterns that help DISCRIMINATE between control types" |

**System Prompt (Revised)**:
```
You are a GRC expert teaching an auditor how to decide whether a policy maps to a control.

Your goal is NOT to describe what policies generally contain.
Your goal IS to identify what SIGNALS indicate a mapping to SPECIFIC control types.

Think like a decision tree:
- "If the policy mentions X, it likely maps to encryption controls"
- "If the policy has Y procedure, it likely maps to incident response controls"
- "If the policy assigns Z role, it likely maps to access management controls"

Be SPECIFIC. Be DISCRIMINATIVE. Help the auditor DECIDE.
```

**Pros**:
- Minimal implementation change (prompt text only)
- Directly addresses the abstraction problem
- Easy to test quickly

**Cons**:
- May not be enough—model might still gravitate toward generic patterns
- Doesn't add control context to input
- Relies on prompt following being strong enough

**Implementation Complexity**: Very Low (prompt text changes only)

---

## Recommendation

### Recommended Path: Hybrid of Approaches 3 + 6

**Phase 1**: Quick test of Approach 6 (Question Reframing)
- Modify prompts to emphasize discrimination
- Rerun aggregation
- Evaluate if patterns become more specific

**Phase 2**: If still too generic, implement Approach 3 (Include Control Context)
- Restructure input to include control family metadata
- Group reasons by control category within each policy
- Modify prompts to ask for category-specific patterns

**Phase 3**: If needed, add Approach 4 (Two-Phase Architecture)
- Add discriminative distillation step
- Use control family distribution to weight patterns

### Why This Order?

1. **Approach 6 is cheap to test** (hours, not days)
2. **Approach 3 adds information** the model needs for discrimination
3. **Approach 4 uses existing work** and adds a focused distillation step

### What We'd Need for Full Implementation

| Approach | Data Needed | Code Changes | Time Estimate |
|----------|-------------|--------------|---------------|
| Approach 6 | None | Prompt text only | 1-2 hours |
| Approach 3 | Control family mapping | Input loader refactor | 1-2 days |
| Approach 4 | Control family distribution stats | New distillation module | 2-3 days |

---

## Concrete Prompt Drafts

### Draft: Revised System Prompt (Approach 6)

```
You are a GRC expert analyzing how to DECIDE whether a policy maps to a security control.

Your task is NOT to describe what policies generally contain—all policies have scope, procedures, and mandates.

Your task IS to identify DISCRIMINATIVE SIGNALS:
- What specific features indicate mapping to ENCRYPTION controls vs ACCESS controls vs INCIDENT RESPONSE controls?
- What linguistic markers, technical terms, or procedural elements are UNIQUE to certain control families?
- What decision criteria would help an auditor quickly classify a mapping?

Output patterns should be ACTIONABLE:
- BAD: "The policy defines scope and applicability" (all policies do this)
- GOOD: "Mention of specific cryptographic algorithms (AES, RSA, SHA) signals encryption control relevance"
- GOOD: "Defined escalation timelines (24h, 72h) signal incident response control relevance"
- GOOD: "Role-based permission matrices signal access management control relevance"

Focus on patterns that DIFFERENTIATE, not patterns that are universal.
```

### Draft: Revised User Prompt (Approach 6)

```
Analyze the following mapping reasons and extract DISCRIMINATIVE patterns.

## Source 1: {SOURCE_1_NAME}
{SOURCE_1_REASONS}

## Source 2: {SOURCE_2_NAME}
{SOURCE_2_REASONS}

For each pattern you identify:
1. Name it specifically (e.g., "Cryptographic Algorithm Mention" not "Technical Specification")
2. Describe what control families it predicts (encryption? access? incident response?)
3. Explain why this feature is discriminative (doesn't appear in other control mappings)
4. Provide example linguistic markers

DO NOT output patterns like:
- "Policy has scope" (all policies do)
- "Policy uses mandatory language" (all policies do)
- "Policy assigns responsibilities" (all policies do)

DO output patterns like:
- "Specific algorithm references (AES-256, RSA-2048) → predicts encryption controls"
- "Breach notification timelines (24-72 hours) → predicts incident notification controls"
- "Segregation of duties requirements → predicts access management controls"
```

---

## Success Criteria

After prompt improvements, we should see:

1. **Fewer near-universal patterns** (no more 35/37 patterns)
2. **Control-family specificity** (patterns should mention what they predict)
3. **Actionable decision criteria** (IF X THEN likely Y)
4. **Linguistic markers** (specific terms, not abstract categories)

### Evaluation Questions

For each output pattern, ask:
- Does this help decide which control family a policy maps to?
- Is this discriminative (not true of all policies)?
- Could an auditor use this as a decision rule?

If the answer is "no" to any of these, the pattern is too generic.

---

## Next Steps

1. [ ] Review this plan and decide on approach priority
2. [ ] Implement Approach 6 prompt changes (quick test)
3. [ ] Run aggregation with new prompts
4. [ ] Evaluate output against success criteria
5. [ ] If still too generic, proceed to Approach 3 (add control context)
6. [ ] If still insufficient, implement Approach 4 (distillation phase)

---

## Appendix: Control Family Examples

For reference, here are example control families from DCF that could anchor discriminative patterns:

| Control Family | Example Controls | Discriminative Signals |
|----------------|------------------|------------------------|
| Cryptographic | DCF-201, DCF-203 | Algorithm names, key lengths, encryption at rest/transit |
| Access Management | DCF-101, DCF-105 | RBAC, permissions, authentication methods |
| Incident Response | DCF-301, DCF-305 | Timelines, escalation, notification requirements |
| Asset Management | DCF-401, DCF-403 | Inventory, classification, ownership |
| Change Management | DCF-501, DCF-505 | Approval workflows, testing, rollback |
| Vendor Management | DCF-601, DCF-605 | Third-party assessment, SLAs, contracts |

These categories could be used to:
- Group input data (Approach 3)
- Compute distribution statistics (Approach 4)
- Frame contrastive comparisons (Approach 2)
