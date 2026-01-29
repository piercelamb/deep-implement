# Prompt Recommendations to Improve Recall

Based on analysis of 188 false negatives from Experiment 6.

---

## Priority 1: G-14 Refinement (51 FNs, 27%)

### Current Behavior (Over-Strict)
G-14 is rejecting controls when policy scope **encompasses** control scope, treating broader-than-required coverage as a mismatch.

### Recommended Change

**Add clarification to G-14:**

```markdown
| **G-14** | Evidence is general but control requires specific scope/qualifier not explicitly included | ... |
```

**Change to:**

```markdown
| **G-14** | Evidence addresses a *different* scope than control requires. **Does NOT apply when evidence addresses a broader scope that fully includes the control target** (use IR-1 instead). | ... |
```

**Add example:**
```markdown
| G-14 Correct | Control: "MFA for remote access" / Evidence: "MFA for internal systems only" | Different scope |
| G-14 Incorrect | Control: "MFA for remote access" / Evidence: "MFA for all access" | Broader scope → IR-1 |
```

---

## Priority 2: G-10 Partitioning (41 FNs, 22%)

### Current Behavior (Over-Strict)
G-10 returns NO_MATCH when ANY qualifier is missing, even when the core artifact/mechanism exists.

### Recommended Change

**Add guidance to PARTIAL section:**

```markdown
### When to Use PARTIAL for G-10 Cases

If the control has two components: (1) ARTIFACT/MECHANISM + (2) OPERATIONAL QUALIFIER (frequency, specific parameter), and:
- Component 1 is satisfied (artifact exists, mechanism is mandated)
- Component 2 is missing (no frequency, missing specific qualifier)

→ Return **PARTIAL** with gap_type: `qualifier_gap`, NOT NO_MATCH

Example:
- Control: "Asset inventory reviewed annually"
- Policy: "Asset inventory shall be maintained" (no annual review)
- Correct: PARTIAL (qualifier_gap: missing annual review)
- Incorrect: NO_MATCH (G-10)
```

---

## Priority 3: Permissive Language Nuance (~15 FNs)

### Current Behavior (Over-Strict)
Any "should" in the evidence path triggers hard block, even when:
- Core requirement uses "must/shall"
- "Should" applies to enhancement, not objective

### Recommended Change

**Modify Phase 2.0 Admissibility Filter:**

Current:
```markdown
- Permissive language (should, may, might, can, recommended, encouraged, where applicable, as appropriate) — these are **hard blockers** for MAPPED/PARTIAL.
```

Change to:
```markdown
- **Hard blockers**: may, might, can, recommended, encouraged
- **Soft blockers**: should, where applicable, as appropriate
  - For "should": Check if the CORE objective has binding language elsewhere
  - If "should" modifies only the METHOD (not the objective), core mandate may still satisfy
  - Example: "Code must be reviewed. Automation should be used where possible." → The review mandate is binding.
```

---

## Priority 4: Evidence Locality Clarification (~5 FNs)

### Current Behavior (Over-Strict)
Rejecting compound controls when requirements are in **organized sections** of the same policy.

### Recommended Change

**Add clarification to Evidence Locality Rule:**

Current:
```markdown
**Evidence Locality Rule:** Evidence must come from one contiguous location in the document—a paragraph, a section, a bulleted list, or consecutive statements that were written together as a unit.
```

Add:
```markdown
**Compound Control Exception:** For controls with AND requirements (multiple sub-requirements), each sub-requirement may be satisfied by its appropriate policy section. This is structured organization, not evidence assembly.

Evidence assembly (BLOCK): "Page 2 says X about topic A, page 5 says Y about topic B, so together they satisfy control about topic C"
Structured organization (ALLOW): "The Risk Assessment section addresses risk identification; the Risk Treatment section addresses risk response—both required by the compound control."
```

---

## Priority 5: G-16 Partial Credit (17 FNs)

### Current Behavior
G-16 often returns NO_MATCH when artifact exists but operational characteristic is missing.

### Recommended Change

Similar to G-10 partitioning:

```markdown
### G-16 Partial Credit

If control requires PRESENCE + CONFIGURATION, and:
- Presence is mandated ("Install antivirus")
- Configuration is NOT mandated ("auto-update signatures")

→ Return **PARTIAL** (scope_gap: missing configuration requirement)
```

---

## Priority 6: G-12 Cross-Reference Handling (6 FNs)

### Current Behavior (Over-Strict)
G-12 returns NO_MATCH when a policy delegates requirements to another document, even when:
- The cross-reference clearly identifies the correct control area
- The policy set is intentionally modular (common in enterprise environments)

### Recommended Change

**Add guidance for cross-references:**

```markdown
### G-12 Cross-Reference Exception

When policy explicitly references another document for requirements:
- Return **PARTIAL** (not NO_MATCH)
- Set gap_type: `reference_gap`
- Note: "Requirements delegated to [Referenced Policy]"

Example:
- Control: "Audit logs retained for 1 year"
- Policy: "Log retention per Logging and Monitoring Policy"
- Correct: PARTIAL (reference_gap: requirements in referenced policy)
- Incorrect: NO_MATCH (G-12)

This allows the pipeline to:
1. Credit the reference as partial coverage
2. Flag for multi-document verification
3. Respect intentional modularity in enterprise policy sets
```

---

## Implementation Approach

### Option A: Modify Guardrail Definitions
Directly edit G-14 and G-10 definitions in the system prompt.

**Risk**: May reduce precision if changes are too permissive.

### Option B: Add "Recovery Pass" Section
After Phase 3 (Guardrails), add a new section:

```markdown
## Phase 3.5: Guardrail Recovery Pass

Before returning NO_MATCH due to G-10 or G-14, verify:

1. **G-14 Check**: Is the policy scope a SUPERSET of the control target?
   - YES → Override G-14, apply IR-1
   - NO → G-14 stands

2. **G-10 Check**: Does the control have ARTIFACT + QUALIFIER structure?
   - If artifact is present but qualifier is missing → PARTIAL (qualifier_gap)
   - If artifact is absent → NO_MATCH (G-10 stands)
```

**Benefit**: Adds nuance without changing core guardrail definitions.

### Option C: Targeted Examples Only
Add examples to "Common Mapping Errors" section showing when G-14/G-10 should NOT block.

**Benefit**: Minimal prompt disruption.
**Risk**: LLM may not generalize from examples.

---

## Expected Impact

| Change | Est. FNs Recovered | New Recall |
|--------|-------------------|------------|
| Baseline | 0 | 64.8% |
| G-14 refinement | 25-30 | ~70% |
| G-10 partitioning | 20-25 | ~74% |
| Permissive language | 8-12 | ~76% |
| Locality clarification | 3-5 | ~77% |
| G-16 partial credit | 5-8 | ~78% |
| G-12 cross-references | 3-5 | ~79% |
| **Combined** | **65-85** | **~76-81%** |

---

## Testing Strategy

1. **Single-document test**: Run on one policy that has multiple FNs (e.g., SDLC Policy with 12 FNs)
2. **Compare precision/recall**: Ensure precision stays above 45%
3. **If successful**: Run full E2E on all 37 documents
4. **Target**: Recall ≥ 75%, Precision ≥ 45%, F1 ≥ 55%
