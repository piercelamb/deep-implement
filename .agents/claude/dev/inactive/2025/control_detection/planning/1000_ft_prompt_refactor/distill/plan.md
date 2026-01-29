# System Prompt Distillation Plan

> **Goal:** Distill the 752-line policy-to-control mapping system prompt to maximize precision/recall while reducing cognitive load on the LLM.
>
> **Approach:** Quality-focused consolidation, not arbitrary line targets. Think deeply about what can be merged, shortened, or sacrificed. Iterate as needed.

## Problem Analysis

### Current State
- **Source:** `distilled_system.md` (752 lines, after redundancy removal)
- **Structure:** 6 parts + intro + closing, pedagogically organized
- **Current Performance:** ~85% recall, ~17-20% precision (from Three-Stage plan context)
- **Freedom:** Can restructure entirely—not bound to current Parts 1-6 organization

### Root Cause Hypothesis

The prompt is **pedagogically structured** (teaching a methodology step-by-step) rather than **operationally structured** (providing rules to execute). This creates the classic **"Wall of Text" problem**—the LLM is likely to forget early instructions (the Golden Rule) by the time it reaches the JSON schema, or hallucinate mappings because it's trying to balance 17 different negative constraints simultaneously.

LLMs don't build mental models like humans—they process instructions in context. A teaching-oriented prompt creates:

1. **Cognitive interference**: Too much to hold in attention simultaneously
2. **Signal dilution**: Critical rules buried in explanatory text
3. **Redundant phrasing**: Same concepts stated multiple ways for human learning

### What Matters for Precision/Recall

**Critical for Precision (preventing false positives):**
- Default NO_MATCH stance (Golden Rule)
- Binding language requirement (must/shall/required)
- Hard blockers (may, might, can, recommended)
- Type matching (TECHNICAL ≠ ADMINISTRATIVE evidence)
- G-1, G-10, G-13 guardrails (likely highest impact)
- Evidence locality rule

**Critical for Recall (not missing true positives):**
- Primary vs secondary qualifier distinction
- Interpretive Rules (IR-1, IR-5 especially)
- Policy vs Procedure understanding (don't penalize missing details)

---

## Distillation Strategy

### Core Principle: Rules Over Education

Transform from **"Teaching the reasoning"** to **"Enforcing the rules."**

**The Guiding Principle:** The LLM does not need to know *why* a policy is not a procedure; it just needs a rule. We retain only **definitions**, **constraints**, and **output schema**.

**General Removal Candidates:**
- Extended explanations of "why"
- Multiple examples per rule (one max, zero if rule is self-evident)
- Coaching language ("this is one of the most common errors")
- Verification checklists (LLM either applies rules or doesn't)
- Pedagogical scaffolding ("Before you begin...", "Now that you understand...")
- Meta-process descriptions (three-pass search process)
- Motivational text ("Why does this matter?")

**General Keep Candidates:**
- Direct rules and requirements
- Critical distinctions (binding vs non-binding, primary vs secondary qualifiers)
- Decision criteria (merged with output format)
- JSON output format

### Proposed New Structure (Reorganized)

Organization by **function** rather than **learning sequence**. Decision criteria merged into output format (per Gemini's suggestion):

```
1. ROLE & CONSTRAINTS (The Prime Directive)
   - Who you are: Skeptical Auditor, default NO_MATCH
   - What you output: MAPPED / PARTIAL / NO_MATCH
   - The Golden Rule (as system constraint, not motivation)
   - Four Requirements for valid mapping (brief)

2. EVIDENCE ADMISSIBILITY
   - Binding language (must/shall/required)
   - Hard blockers (may/might/can/recommended) - blacklist
   - Soft blocker rule for "should" (simplified)
   - Inadmissible sources (definitions, aspirational, future tense)
   - Locality requirement
   - Sufficiency test (brief)

3. MATCHING RULES
   - Document type matters (G-10 dependency)
   - Control type classification (7 types, brief)
   - Primary qualifiers (blocking) vs Secondary (non-blocking)

4. BLOCKING GUARDRAILS (G-1 to G-17)
   - Grouped by category
   - One-line descriptions (<15 words each)
   - "If ANY applies → NO_MATCH"

5. BRIDGING RULES (IR-1 to IR-8)
   - One-line descriptions
   - "Apply ONLY if no guardrail violated"

6. OUTPUT FORMAT & DECISION CRITERIA
   - JSON schema
   - Decision definitions inline (MAPPED/PARTIAL/NO_MATCH)
   - rules_cited guidance
   - One reasoning example per decision type (max)
```

---

## Detailed Distillation Decisions

For each area of the current prompt, analyze what's essential vs verbose/redundant.

### Area 1: Role & Foundations (Current: Intro + Part 1)

**Essential - Keep:**
- Skeptical Auditor role framing
- Golden Rule as constraint: "Default NO_MATCH. Only MAPPED when evidence is irrefutable."
- Three decision types with one-line definitions
- Four Requirements for valid mapping (Mandate, Scope, Type, No Mismatch) - headers only

**Can Be Shortened:**
- Policies vs Procedures → one sentence: "Policies mandate requirements; don't penalize missing procedures, technical parameters, or frequencies."

**Remove:**
- "Why does this matter?" paragraph
- Key Concepts definitions (Policy, Control, Mapping)
- "Policy-to-Control mapping is performed by GRC experts..." background
- "Setting Expectations" mapping count ranges
- "What It Means" column from requirements table

### Area 2: Document & Control Analysis (Current: Part 2)

**Essential - Keep:**
- Document type classification rule: "An Acceptable Use Policy is not an Information Security Policy"
- Control type classification (7 types) - names and brief descriptions only
- Primary vs Secondary qualifier distinction

**Shortened Format:**
- Control types → single column (type + brief description), no "Valid Evidence Type" column
- Primary qualifiers → comma list: FIPS, authenticated, credentialed, tamper-evident, immutable, third-party, specific tools
- Secondary qualifiers → comma list: frequencies, numeric thresholds, configuration details

**Remove:**
- "Extract Document Context" table
- "Build a requirement profile before searching" preamble
- Compound logic section (AND/OR) - LLM handles implicitly
- "Core Objective" examples table

### Area 3: Evidence Requirements (Current: Part 3)

**Essential - Keep:**
- Binding verbs: must / shall / required / prohibited
- Hard blockers (blacklist): may, might, can, recommended, encouraged
- Soft blocker rule for "should"
- Inadmissible sources list
- Evidence locality rule

**Simplified Rules (from Gemini):**
- **"should" handling:** "Reject 'should' unless explicitly overridden by 'must/shall' in the same clause."
- **Locality:** Two sentences max
- **Sufficiency Test:** Keep brief version (per ChatGPT - distinct from locality). "If the policy contained ONLY this section, would the control still be satisfied?"

**Remove:**
- Three-pass search process (Pass A/B/C) - meta-process
- Extended "should" examples
- Compound Control Exception details
- Synonym tables

### Area 4: Guardrails (Current: Part 4.2)

**Keep ALL guardrails, but compress to <15 words each.**

Target format (Cheatsheet style from Gemini):

**Type Mismatches:**
- **G-1:** Control is TECHNICAL/AUTOMATED; evidence is ADMIN/MANUAL/POLICY.
- **G-2:** Control requires SYSTEM enforcement; evidence relies on USER behavior/rules.
- **G-3:** Control requires PREVENTION; evidence provides DETECTION/LOGGING only.
- **G-4:** Control requires PROGRAM/PLAN; evidence is only a component/input.

**Scope/Domain Mismatches:**
- **G-5:** Evidence domain (physical/logical/data) doesn't match control domain.
- **G-6:** Evidence explicitly excludes required scope ("only X", "does not apply to Y").
- **G-7:** Control requires INTERNAL action; evidence assigns to VENDORS (or vice versa).
- **G-8:** Control targets specific audience; evidence governs different audience.
- **G-9:** Evidence addresses DIFFERENT scope than control (not just narrower).
- **G-10:** Control requires specific ARTIFACT TYPE; document is different type.

**Qualifier/Lifecycle Mismatches:**
- **G-11:** Control requires specific lifecycle phase; evidence addresses different phase.
- **G-12:** Control requires EVENT-DRIVEN action; evidence describes PERIODIC (or vice versa).
- **G-13:** Control has PRIMARY QUALIFIER absent from evidence.
- **G-14:** Control requires static ARTIFACT; evidence mandates dynamic ACTIVITY.
- **G-15:** Control requires operational CONFIG; evidence only mandates PRESENCE.

**Evidence Quality:**
- **G-16:** Evidence is external reference without stated requirement.
- **G-17:** Evidence describes risk assessment; control requires implementation.

**Remove:**
- Edge Cases table
- Detailed examples for each guardrail
- Extended descriptions

### Area 5: Interpretive Rules (Current: Part 4.4)

**Keep ALL IRs, compress to one-liners:**

- **IR-1 (Hierarchical Scope):** Policy says "all X"; control target is a subset of X. → MAPPED
- **IR-2 (Parameter Abstraction):** Policy requires "strong/secure"; control asks for specific algo (AES-256). → MAPPED (NOT for FIPS/third-party)
- **IR-3 (Frequency Abstraction):** Policy mandates "regular/continuous"; control asks for specific interval. → MAPPED
- **IR-4 (Positive → Prohibition):** "All X must have Y" implies "X without Y prohibited." → MAPPED
- **IR-5 (Binding Inheritance):** Binding header ("shall/must/required") applies to bulleted list items. → MAPPED
- **IR-6 (Standard Reference):** Explicit compliance mandate with named standard may satisfy. → MAPPED (NOT "align with")
- **IR-7 (Disjunctive Logic):** Control is A OR B; one branch sufficient. → MAPPED
- **IR-8 (Mechanism Subsumption):** Broader mechanism necessarily includes specific. → MAPPED

**Remove:**
- Full "Apply When / Do NOT Apply" tables
- Multiple examples per IR
- IR-8 examples table

### Area 6: Decision Criteria + Output Format (Current: Parts 5 & 6) - MERGED

**Keep:**
- JSON schema
- rules_cited guidance

**Decision definitions as one-liners (from Gemini):**
- **MAPPED:** Binding evidence + type match + no guardrail violated + localized. Cite IR if used.
- **PARTIAL:** Use ONLY for: explicit scope gaps, third-party gaps, or contradictions. Missing details = MAPPED. Missing mandates = NO_MATCH.
- **NO_MATCH:** Default. Any doubt = NO_MATCH. Cite blocking guardrail(s).

**Keep (brief):**
- One reasoning example per decision type
- **Single mass-mapping warning** (per ChatGPT): "If mapping >30-40% of controls in a batch, re-verify each has its own binding evidence and control-specific anchor." Low cost, prevents precision collapse.

**Remove:**
- 9-requirement MAPPED checklist (redundant with one-liner)
- "Before returning NO_MATCH, verify" checklist
- "Confidence is binary" section
- Extended anti-patterns section (keep only mass-mapping warning)
- Closing summary
- Multiple reasoning examples

---

## Risk Analysis

### Precision Risks (false positives)
- **LOW RISK**: Core guardrails (G-1, G-10, G-13) preserved
- **LOW RISK**: Golden Rule, default NO_MATCH preserved
- **MEDIUM RISK**: Removing detailed examples may cause edge case misses

### Recall Risks (false negatives)
- **LOW RISK**: All IRs preserved
- **MEDIUM RISK**: Removing "don't penalize for procedures" emphasis may cause over-rejection
- **MITIGATION**: Keep one-sentence reminder about policy vs procedure distinction

### Mitigation Strategy
- A/B test distilled vs original on ground truth
- Track which guardrails are cited in errors
- Iterate based on error analysis
- Multiple rounds of consolidation if needed

---

## Implementation Approach

### Round 1: Initial Distillation

Work through the prompt section by section:

1. **Write Section 1**: Role & Constraints
   - Skeptical Auditor, Golden Rule as constraint, decision types, four requirements (brief)

2. **Write Section 2**: Evidence Admissibility
   - Binding verbs, hard blockers (blacklist), simplified "should" rule, inadmissible list, locality

3. **Write Section 3**: Matching Rules
   - Document type rule, control types (brief), primary vs secondary qualifiers

4. **Write Section 4**: Guardrails
   - All 17 as one-liners grouped by category
   - Cheatsheet format

5. **Write Section 5**: Interpretive Rules
   - All 8 as one-liners

6. **Write Section 6**: Output Format & Decision Criteria
   - JSON schema, decision definitions, rules_cited guidance, one example per type

### Round 2: Review & Coherence Check

7. Read the full distilled prompt end-to-end
8. Ensure flow makes sense with new structure
9. Check no critical rules were accidentally dropped
10. Remove any remaining redundancy

### Round 3 (If Needed): Further Consolidation

11. If still too long after testing, identify next tier of cuts
12. Apply and re-test

---

## Files to Modify

| File | Action |
|------|--------|
| `.agents/claude/dev/active/control_detection/planning/1000_ft_prompt_refactor/distill/distilled_system.md` | Create distilled version |

---

## Expected Outcome

**No specific line target.** Focus is on:
- Removing everything that doesn't directly help precision/recall
- Keeping all rules that do help
- Making rules more scannable (one-liners vs paragraphs)
- Restructuring for operational use vs pedagogical learning

**Hypothesis:** A shorter, operationally-focused prompt will:
1. Reduce cognitive interference on the LLM
2. Keep critical rules more salient (less signal dilution)
3. Improve precision without sacrificing recall

**Success Criteria:**
- Precision improves (or stays same)
- Recall stays same (or improves)
- If both degrade, analyze which removed content caused it and restore

---

## Incorporated from Gemini's Analysis

Key suggestions adopted:

1. **"Wall of Text" / Cognitive Interference framing** - Added to problem analysis
2. **"Rules over Education" as explicit guiding principle** - Adopted as core principle name
3. **"The LLM doesn't need to know why"** - Integrated into strategy
4. **Simplified "should" handling** - One-liner rule adopted
5. **PARTIAL redefinition** - Gemini's clean one-liner adopted
6. **Cheatsheet format for guardrails** - Adopted <15 word target
7. **Merge Decision Criteria into Output Format** - Adopted, reduced from 7 to 6 sections

**Not adopted:**
- Removing Part 2 (Document/Control Analysis) entirely - Document type classification is critical for G-10; control type classification is critical for G-1
- Reducing to 4 sections - More granular structure (6 sections) provides clearer separation for LLM parsing
- 60% token reduction target - User explicitly requested no line/token targets

---

## Incorporated from ChatGPT's Analysis

Key suggestions adopted:

1. **Keep Sufficiency Test** - ChatGPT identifies as non-negotiable invariant. Distinct from locality: locality = "one contiguous location"; sufficiency = "evidence must stand alone without importing context from elsewhere"
2. **Single mass-mapping warning** - Low-cost prevention of catastrophic precision collapse: "If mapping >30-40% of controls, re-verify each has own binding evidence and control-specific anchor"
3. **Ablation-based validation** - Testing methodology reinforcement: define "must pass" control suite, each cut justified by no regression

**Not adopted:**
- Two-layer structure (Core Algorithm + ID Cheat Sheet) - My 6-section structure is already operational and provides clearer separation
- Guardrail buckets (5-7 instead of 17) - Risk losing specific G-X IDs required for JSON output citation
- 250-450 token target - User explicitly requested no token targets
