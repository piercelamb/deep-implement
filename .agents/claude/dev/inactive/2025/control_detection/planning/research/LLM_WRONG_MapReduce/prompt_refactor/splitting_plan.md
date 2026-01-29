# Implementation Splitting Plan

This document splits the 11 changes from `plan.md` into 3 implementation phases targeting different files.

---

## Part 1: System Prompt Changes (`system.md`)

**Changes:** 1, 2, 3, 4, 5, 6, 9, 10, 11
**Estimated Lines:** +135

### Changes in Order of Application

| Order | Change # | Name | Type | Location in system.md |
|-------|----------|------|------|----------------------|
| 1 | Change 1 | Phase 0 Enhancements | Modify | Phase 0 "Preparation" |
| 2 | Change 9 | Phase 0.5 Policy Context | New | After Phase 0, before Phase 1 |
| 3 | Change 10 | 3-Pass Evidence Retrieval | New | Replace/restructure Phase 1.1 |
| 4 | Change 4 | Scope Examples | Modify | Phase 1.2 "Validate Scope Coverage" |
| 5 | Change 5 | Semantic Equivalence Examples | Modify | Phase 1.1 "Find Candidate Evidence" |
| 6 | Change 2 | Interpretive Rules Table | New | Replace verbose Phase 3 |
| 7 | Change 3 | Pre-Rejection Checklist | New | Before Decision Logic section |
| 8 | Change 6 | Decision Logic Update | Modify | Phase 4 Decision Logic |
| 9 | Change 11 | "Do NOT" Language | Modify | Throughout (IR-4, IR-5, PARTIAL section) |

### Implementation Notes

1. **Change 1** modifies existing Phase 0 sections:
   - Add Disjunctive Logic and Constitutive Elements to 0.1
   - Add Binding Preambles and Templates to 0.2

2. **Change 9** adds a new Phase 0.5 section with a table of 6 context elements to extract

3. **Change 10** restructures Phase 1 into 3 passes (A/B/C) with structured search

4. **Changes 4 & 5** add example tables to existing sections

5. **Change 2** replaces verbose rules with compact IR-1 to IR-10 table

6. **Change 3** adds a new Pre-Rejection Recovery Checklist section

7. **Change 6** updates decision logic to reference Interpretive Rules

8. **Change 11** strengthens language throughout:
   - IR-4: Add "Do NOT reject for missing procedural steps"
   - IR-5: Add "Do NOT reject for missing frequency"
   - PARTIAL: Add "Do NOT use PARTIAL for:" list

---

## Part 2: User Prompt Changes (`user.md`)

**Changes:** 8
**Estimated Lines:** +10

### Content

Replace the user prompt with updated instructions that:
1. Reference the Control-to-Policy Mapping Protocol
2. Include 4 numbered steps:
   - Analyze Control Intent
   - Search Policy (with IR-1, IR-8, IR-9 references)
   - Apply Interpretive Rules
   - Cite Rules in reasoning
3. Include focus statement about Strategic What/Who vs Technical How/When

### Full Replacement

```markdown
Evaluate the following security controls against the policy document.

<controls_to_evaluate>
{controls_xml}
</controls_to_evaluate>

Each control includes retrieval_hints with page numbers where semantic similarity was highest.

<instructions>
Apply the Control-to-Policy Mapping Protocol. For each control:

1. **Analyze Control Intent:** Is it asking for a specific configuration or a governance outcome?
2. **Search Policy:** Look for the Core Objective.
   - Check hierarchical scope (IR-1)
   - Check binding preambles (IR-8)
   - Check external standard references (IR-9)
3. **Apply Interpretive Rules:** Before NO_MATCH, run the Pre-Rejection Recovery Checklist.
4. **Cite Rules:** In your reasoning, reference which IR-X rules you applied.

**Focus:** If the policy mandates the *Strategic What* and *Who*, it maps to the control, even if the *Technical How* and *When* are vague.
</instructions>
```

---

## Part 3: Response Schema Changes (`response.json`)

**Changes:** 7
**Estimated Lines:** +5

### Schema Updates

1. **`reasoning` field description** - Update to require rule citation:
   - "Cite Interpretive Rules used. E.g., 'Mapped via IR-2: Policy mandates encryption outcome; AES-256 is implementation detail.'"

2. **Add examples to schema** (if supported):
   - MAPPED: "Mapped via IR-X: [explanation]"
   - PARTIAL: "Partial match. IR-X applies but [policy-level gap exists]"
   - NO_MATCH: "No match. Checked IR-1 through IR-10; [explanation of why all failed]"

### Specific Changes

```json
{
  "reasoning": {
    "type": "string",
    "description": "Cite Interpretive Rules used. Format: 'Mapped via IR-X: [explanation]' for MAPPED, 'Partial match. IR-X applies but [gap]' for PARTIAL, 'No match. Checked IR-1 through IR-10; [why all failed]' for NO_MATCH."
  }
}
```

---

## Implementation Order

**Recommended sequence:**

1. **Part 1: System Prompt** - Core logic changes
2. **Part 3: Response Schema** - Schema must match new reasoning format
3. **Part 2: User Prompt** - References system prompt concepts

**Alternative sequence (if testing incrementally):**

1. **Part 3: Response Schema** - Backwards compatible (just description change)
2. **Part 1: System Prompt** - Apply changes incrementally, test after each
3. **Part 2: User Prompt** - Final alignment

---

## File Locations

| Part | File | Path |
|------|------|------|
| 1 | system.md | `reason_aggregator/prompts/control_centric_expanded/system` or similar |
| 2 | user.md | `reason_aggregator/prompts/control_centric_expanded/user` |
| 3 | response.json | `reason_aggregator/prompts/control_centric_expanded/response.json` |

---

## Verification Checklist

After implementation:

- [ ] System prompt contains IR-1 through IR-10 table
- [ ] System prompt contains Pre-Rejection Recovery Checklist
- [ ] System prompt contains Phase 0.5 Policy Context section
- [ ] System prompt contains 3-Pass Evidence Retrieval structure
- [ ] User prompt references IR rules
- [ ] Response schema requires rule citation in reasoning
- [ ] All "Do NOT" language is directive, not passive
