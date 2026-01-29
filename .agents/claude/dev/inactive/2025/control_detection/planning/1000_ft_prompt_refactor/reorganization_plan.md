# System Prompt Reorganization Plan

> **Source**: `prompts/control_centric_plamb/system` (422 lines)
> **Goal**: Restructure as a coherent technical document that flows like a senior GRC analyst teaching a smart but new intern

---

## Current Structure Analysis

### What Exists Now (in order)

| Lines | Section | Content |
|-------|---------|---------|
| 1-3 | Role + Golden Rule | Auditor mindset, default NO_MATCH |
| 7-15 | Mapping Standard | 4 requirements + second golden rule |
| 19-30 | Document Hierarchy | Policy vs Procedure distinction |
| 34-52 | Phase 0 | Document classification, scope extraction |
| 55-93 | Phase 1 | Control profiling (type, qualifiers, logic) |
| 96-143 | Phase 2 | Evidence retrieval (admissibility, Pass A/B/C) |
| 147-241 | Phase 3 | Precision Guardrails (G-1 through G-17) |
| 244-271 | Phase 4 | Interpretive Rules (IR-1 through IR-8) |
| 274-349 | Phase 5 | Decision Logic (MAPPED/PARTIAL/NO_MATCH) |
| 352-380 | Output Format | JSON schema, reasoning format |
| 384-400 | Quick Reference | Checklists for MAPPED/NO_MATCH |
| 403-417 | Common Errors | Error table with guardrail refs |

### Problems Identified

1. **Redundancy**
   - Golden Rule stated twice (lines 3 and 15)
   - Quick Reference Checklist duplicates earlier content
   - Common Errors table duplicates guardrail examples
   - Qualifier examples repeated in multiple places

2. **Out-of-Order Concepts**
   - Mapping Standard (the success criteria) is stated early but disconnected from where it's applied
   - Guardrails presented before understanding the decision framework
   - Interpretive Rules come after guardrails but are actually "bridges" that should be understood alongside them

3. **Disconnected Sections**
   - Document Hierarchy Context orphaned between Role and Phase 0
   - Relationship between Guardrails and IRs unclear
   - Edge Cases buried in guardrails instead of prominent

4. **Mixed Abstraction Levels**
   - High-level principles mixed with detailed examples in same section
   - Some tables have 2 rows, others have 10+
   - Anti-patterns in decision logic instead of as early warnings

5. **Poor Teaching Flow**
   - Jumps straight into "phases" without explaining the overall approach
   - Doesn't explain WHY before HOW
   - "Phase" numbering implies linear execution but validation is iterative

---

## Proposed Structure

### The Teaching Metaphor

Imagine a senior GRC analyst sitting down with a new intern:

1. **"Let me tell you what we're doing and why it matters"** → FOUNDATIONS
2. **"Before you start, you need to understand what you're looking at"** → INPUTS
3. **"Here's how you find potential evidence"** → SEARCH
4. **"Here's how you decide if what you found is actually valid"** → JUDGMENT
5. **"Here's how you make the final call"** → DECISION
6. **"Here's the format and some quick references"** → EXECUTION

---

## Detailed Section Plan

### PART 1: FOUNDATIONS (The "Why" and Mindset)

**Purpose**: Establish context, mindset, and success criteria before diving into mechanics.

**Content to include**:
- Your role: Strict External Auditor (skeptical by default)
- The Golden Rule: Better to miss a mapping than falsely credit one (consolidate the two instances)
- What you're evaluating: Policies (governance) vs Procedures (operations) - the hierarchy table
- What makes a valid mapping: The 4-part standard (Mandate + Scope + Type Match + No Mismatch)
- Expected outcomes: Most policies map to 5-30 controls, not 50+ (anti-pattern warning upfront)

**Current content to merge**:
- Lines 1-3 (Role + Golden Rule)
- Lines 15 (second Golden Rule)
- Lines 19-30 (Document Hierarchy)
- Lines 7-14 (Mapping Standard)
- Lines 341-348 (Mass Mapping anti-pattern - move to set expectations early)

**Estimated length**: ~40-50 lines

---

### PART 2: UNDERSTAND YOUR INPUTS (Before You Evaluate)

**Purpose**: Teach the analyst to fully understand both the document and the control before attempting to match them.

**Subsections**:

#### 2.1 Understand the Document (Once Per Document)
- Document classification (CRITICAL - what type of document is this?)
- Key principle: "An Acceptable Use Policy is not an Information Security Policy"
- Extract: Scope, roles, binding conventions, exclusions, standard references

#### 2.2 Understand the Control (Per Control)
- Core objective: Summarize in one clause
- Control type classification (the 7-type table: TECHNICAL, ADMINISTRATIVE, etc.)
- Mandatory qualifiers extraction (the category table)
- Compound logic (AND vs OR)

**Current content to merge**:
- Lines 34-52 (Phase 0)
- Lines 55-93 (Phase 1)

**Estimated length**: ~60-70 lines

---

### PART 3: FIND THE EVIDENCE (The Search Process)

**Purpose**: Teach how to systematically search for evidence and what counts as admissible.

**Subsections**:

#### 3.1 What Counts as Evidence (Admissibility Filter)
- Auto-reject list: definitions, disclaimers, aspirational language, external pointers, future tense
- Hard blockers: may, might, can, recommended
- Soft blockers: should (with the CRITICAL nuance about checking same section)

#### 3.2 The Search Process
- **Pass A**: Direct binding evidence (must/shall + direct match)
- **Pass B**: Strict synonyms only (with the synonym table)
- **Pass C**: Final verification (not a rescue mission)

#### 3.3 Evidence Quality Requirements
- Locality Rule: Must come from single contiguous location
- Sufficiency Test: Would this section alone satisfy the control?
- Compound Control Exception: When multi-section evidence is OK

**Current content to merge**:
- Lines 96-143 (Phase 2)
- Lines 279-294 (Evidence Locality from Phase 5)

**Estimated length**: ~70-80 lines

---

### PART 4: VALIDATE THE MATCH (The Judgment Framework)

**Purpose**: Teach the validation rules - both what blocks a mapping and what bridges gaps.

**Introduction**:
"You've found potential evidence. Now validate it against these rules. Guardrails BLOCK invalid mappings. Interpretive Rules BRIDGE acceptable gaps. Guardrails always take precedence."

**Subsections**:

#### 4.1 Blocking Guardrails (If ANY applies → NO_MATCH)

Reorganize by failure mode (more intuitive than current categories):

**Type Mismatches** (G-1, G-2, G-3, G-17)
- Technical control needs technical evidence
- User behavior rules don't satisfy infrastructure controls
- Detection doesn't satisfy prevention
- Input to program doesn't satisfy program requirement

**Scope & Domain Mismatches** (G-4, G-5, G-6, G-7, G-14, G-15)
- Wrong domain (physical/logical/data)
- Wrong scope (subset when broad required)
- Wrong actor (internal vs vendor)
- Wrong audience (employees vs customers)
- Wrong artifact type (AUP isn't InfoSec Policy)

**Qualifier & Lifecycle Mismatches** (G-8, G-9, G-10, G-11, G-16)
- Wrong lifecycle phase
- Event-driven vs periodic mismatch
- Missing primary qualifiers (FIPS, third-party, etc.)
- Activity vs artifact mismatch
- Presence vs configuration mismatch

**Evidence Quality Issues** (G-12, G-13)
- External reference without requirement
- Risk assessment vs implementation

#### 4.2 Bridging Rules (Apply ONLY if no guardrail violated)

The 8 Interpretive Rules with clear "Apply When" / "Do NOT Apply When":
- IR-1: Hierarchical Scope
- IR-2: Parameter Abstraction
- IR-3: Frequency Abstraction
- IR-4: Positive→Prohibition
- IR-5: Binding Inheritance
- IR-6: Standard Reference
- IR-7: Disjunctive Logic
- IR-8: Mechanism Subsumption

#### 4.3 Primary vs Secondary Qualifiers

Move this important distinction into a clear subsection:
- Primary (G-10 blocks if missing): FIPS, third-party, CUI, authenticated, etc.
- Secondary (OK to bridge): frequencies, numeric thresholds, review cadences
- The Core Mandate Test

**Current content to merge**:
- Lines 147-241 (Phase 3 Guardrails) - reorganized
- Lines 244-271 (Phase 4 IRs)
- Lines 191-221 (Qualifier distinction)

**Estimated length**: ~120-140 lines

---

### PART 5: MAKE THE DECISION (The Three Outcomes)

**Purpose**: Clear criteria for each decision type.

**Subsections**:

#### 5.1 MAPPED
- All 4 mapping standard requirements met
- Confidence is BINARY (high or NO_MATCH)
- No medium confidence MAPPED

#### 5.2 PARTIAL (Rare)
- Only for material policy-level gaps
- The 4 gap types: scope_gap, third_party_gap, ownership_gap, contradiction
- The Subset Rule (subset ≠ gap)
- Examples of what is NOT partial

#### 5.3 NO_MATCH
- Any guardrail violated
- Missing mandatory qualifier that can't be bridged
- Only topic similarity, no binding mandate
- Any doubt = NO_MATCH

#### 5.4 Anti-Patterns
- One Quote → Many Controls
- Mass Mapping (moved from earlier, brief reminder)

**Current content to merge**:
- Lines 274-349 (Phase 5) - reorganized, deduplicated

**Estimated length**: ~50-60 lines

---

### PART 6: OUTPUT & REFERENCE (Practical Execution)

**Purpose**: Format requirements and quick-lookup reference material.

**Subsections**:

#### 6.1 Output Format
- JSON schema
- rules_cited guidance
- Reasoning format examples

#### 6.2 Quick Reference: Common Errors
- The error table (consolidated, no duplicates)

#### 6.3 Quick Reference: Guardrail Index
- One-line description of each G-1 through G-17

#### 6.4 Quick Reference: IR Index
- One-line description of each IR-1 through IR-8

**Current content to merge**:
- Lines 352-380 (Output Format)
- Lines 403-417 (Common Errors)
- Lines 384-400 (Quick Reference Checklist) - integrate into relevant sections or consolidate

**Estimated length**: ~50-60 lines

---

## Summary: Before vs After

### Current Flow (Disjointed)
```
Role → Mapping Standard → Document Hierarchy → Phase 0 → Phase 1 → Phase 2 →
Phase 3 (Guardrails) → Phase 4 (IRs) → Phase 5 (Decisions) → Output → Checklists → Errors
```

### Proposed Flow (Teaching Narrative)
```
FOUNDATIONS (why, mindset, what's valid)
    ↓
UNDERSTAND INPUTS (document + control)
    ↓
FIND EVIDENCE (search process)
    ↓
VALIDATE MATCH (guardrails block, IRs bridge)
    ↓
MAKE DECISION (MAPPED / PARTIAL / NO_MATCH)
    ↓
OUTPUT & REFERENCE (format, quick lookups)
```

---

## Key Changes Summary

| Change | Rationale |
|--------|-----------|
| Consolidate two Golden Rules | Redundancy |
| Move anti-patterns to Foundations | Set expectations early |
| Move Evidence Locality to Part 3 | It's about evidence quality, not decision logic |
| Reorganize guardrails by failure mode | More intuitive than arbitrary categories |
| Create clear Primary vs Secondary Qualifiers section | This is a critical distinction buried in current text |
| Remove Phase numbering | Implies linear execution; validation is iterative |
| Merge Quick Reference into relevant sections | Avoid duplication |
| Add guardrail/IR indexes at end | Quick lookup without cluttering main text |

---

## Estimated Final Length

| Part | Lines |
|------|-------|
| 1. Foundations | ~45 |
| 2. Understand Inputs | ~65 |
| 3. Find Evidence | ~75 |
| 4. Validate Match | ~130 |
| 5. Make Decision | ~55 |
| 6. Output & Reference | ~55 |
| **Total** | **~425** |

Similar length to current (422), but more coherent and teachable.

---

## Next Steps

1. [ ] Review this plan with stakeholder
2. [ ] Draft Part 1 (Foundations) as proof of concept
3. [ ] Iterate on structure based on feedback
4. [ ] Complete full rewrite
5. [ ] A/B test new prompt vs old prompt on same document set
