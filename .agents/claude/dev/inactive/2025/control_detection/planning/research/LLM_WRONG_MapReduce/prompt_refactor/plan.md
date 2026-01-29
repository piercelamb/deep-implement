# Plan: Prompt Refactor to Eliminate False Negatives

## Executive Summary

We analyzed 69 LLM false negatives (NO_MATCH and PARTIAL errors) across 22 template policies and extracted 23 failure avoidance rules (11 universal, 12 rare). This plan integrates these learnings into the existing `control_centric_false_negatives` prompt to reduce false negatives toward zero.

**Key Insight:** The existing prompt is *defensive* ("don't penalize for X") when it needs to be *offensive* ("actively accept when Y"). The LLM knows what NOT to reject for, but doesn't know when to ACCEPT.

---

## Analysis: Gap Assessment

### Current Prompt Strengths
- Clear 4-question framework (Mandate? Scope? Ownership? Contradictions?)
- Document hierarchy (Policy vs Standard vs Procedure)
- "What NOT to penalize" section
- Binding language taxonomy

### Current Prompt Gaps

| Gap | Universal Rule | Frequency | Current Coverage |
|-----|---------------|-----------|------------------|
| Hierarchical scope inheritance | Rule 1 | 9 policies | Mentioned but not actionable |
| Technical→Abstract correlation | Rule 2 | 8 policies | Passive ("don't penalize") |
| Semantic equivalence depth | Rule 3 | 7 policies | Surface-level only |
| Governance over procedure | Rule 4 | 6 policies | Passive ("don't penalize") |
| Activity over frequency | Rule 5 | 5 policies | Not explicitly covered |
| Material subset coverage | Rule 6 | 5 policies | Not covered |
| Entity existence inference | Rule 7 | 4 policies | Not covered |
| Binding preamble inheritance | Rule 11 | 2 policies | Not covered |

**Root Cause:** The prompt tells the LLM *what policies don't need to contain* but doesn't tell it *what to accept as sufficient evidence*.

---

## Strategy: Hybrid Approach

After reviewing Gemini 3's and ChatGPT's analyses, we adopt a **hybrid approach** combining the best ideas from each:

1. **Gemini's Compact Interpretive Rules Table** - Numbered rules for easy reference
2. **Gemini's "Cite the Rule" Output Requirement** - Forces explicit rule application
3. **Our Pre-Rejection Recovery Checklist** - Final verification before NO_MATCH
4. **Gemini's Phase 0 Enhancements** - Constitutive elements, templates/placeholders
5. **ChatGPT's Phase 0.5: Extract Policy Context** - Reusable facts extracted ONCE
6. **ChatGPT's 3-Pass Evidence Retrieval** - Structured A/B/C search with rescue pass
7. **ChatGPT's Directive Language** - Strong "do NOT" instructions

### Key Adoptions from Gemini 3

| Gemini Idea | Why We're Adopting It |
|-------------|----------------------|
| Interpretive Rules Table | Compact, numbered, easy to reference |
| "Cite rule in reasoning" | Forces explicit rule application |
| Constitutive Elements (Phase 0) | Decompose terms into definitions |
| Templates/Placeholders | Covers Rare Rule 11 we missed |
| Shorter overall structure | Better token efficiency |

### Key Adoptions from ChatGPT

| ChatGPT Idea | Why We're Adopting It |
|--------------|----------------------|
| Phase 0.5: Extract Policy Context | Extract reusable facts ONCE before evaluating controls |
| 3-Pass Evidence Retrieval | Structured search with explicit rescue pass |
| "do NOT" language | More directive than passive "don't penalize" |
| Activity Over Frequency | Clearer articulation of IR-5 |
| Indirect Binding Mechanisms | Highlights Rare Rule 12 (NDA equivalents) |

### What We're Keeping from Original Plan

| Original Idea | Why We're Keeping It |
|---------------|---------------------|
| Pre-Rejection Recovery Checklist | Critical "stop and think" mechanism |
| Semantic Equivalence Examples Table | More concrete than brief examples |
| Scope Decision Matrix | Explicit guidance on relationships |

---

## Detailed Changes

### Change 1: Add Phase 0 Enhancements (MODIFY)

**Location:** Phase 0 "Preparation" (lines 40-70)

**Add to 0.1 Extract Control Requirement Profile:**

```markdown
### 0.1 Extract the Control Requirement Profile

Identify the **core mandate** the control requires:

**Disjunctive Logic:** If a control says "Do A OR B," the policy only needs to mandate ONE to match.

**Constitutive Elements:** If a control requires a technical term (e.g., "Non-repudiation"), decompose it into its definition components (Identity + Action Attribution). Look for mandates covering the components even if the term is absent.

| Component | Question to Answer |
|-----------|-------------------|
| **Goal/Outcome** | What security result must be achieved? |
| **Mandate Type** | Must do / Must not do (prohibition) / Must ensure? |
| **Target Assets** | What systems, data, users, or environments are in scope? |
| **Responsible Party** | Who must own or be accountable? |
```

**Add to 0.2 Build Policy Evidence Map:**

```markdown
### 0.2 Build the Policy Evidence Map

Scan the policy for these **policy-level** elements:

- **Binding Preambles** - Headers like "The following is required:" that bind subsequent lists/tables
- **Templates/Placeholders** - Text like `[Value]` or `<PASSWORD_LENGTH>` implies a mandate to define that value—this counts as a match
- **Scope statements** (what it covers; what it excludes)
- **External Standard References** (ISO, NIST, CIS that inherit specific requirements)
```

---

### Change 2: Add Interpretive Rules Table (NEW - Gemini's Best Idea)

**Location:** Replace verbose Phase 3 with compact table

**Rationale:** Numbered rules are easier to reference and cite in reasoning.

```markdown
## Interpretive Rules (False Negative Prevention)

**CRITICAL:** Apply these rules before deciding NO_MATCH. Reference by number in your reasoning.

| # | Rule Name | When to Apply | Recovery Heuristic |
|---|-----------|---------------|-------------------|
| IR-1 | **Hierarchical Scope** | Control targets specific asset; policy covers broad category | If control target ⊂ policy scope → MAPPED |
| IR-2 | **Tech→Abstract** | Control asks for specific config (AES-256); policy gives outcome (encryption) | Abstract mandate covers specific method → MAPPED |
| IR-3 | **Semantic Equivalence** | Control uses Term A; policy uses different words for same function | Functional outcome equivalent → MAPPED |
| IR-4 | **Governance→Procedure** | Control asks How/When; policy says What/Who | Governance mandate exists → MAPPED (procedure lives elsewhere) |
| IR-5 | **Frequency Abstraction** | Control asks specific interval; policy says "regularly" or "always" | Continuous/general covers specific → MAPPED |
| IR-6 | **Inferred Existence** | Policy mandates using/managing X; control asks to have X | Mandate to use implies existence → MAPPED |
| IR-7 | **Positive→Prohibition** | Control prohibits Y; policy mandates opposite (all X must be Z) | Positive mandate implies prohibition → MAPPED |
| IR-8 | **Binding Inheritance** | List items lack verbs; section header has binding language | Header binds child items → MAPPED |
| IR-9 | **Standard Reference** | Policy cites CIS/NIST/ISO; control asks specific config in that standard | Reference inherits standard's requirements → MAPPED |
| IR-10 | **Disjunctive Logic** | Control requires A OR B; policy only mandates B | Meeting one branch = full match → MAPPED |

**Usage:** In your reasoning, cite the rule: "Mapped via IR-2: Policy mandates encryption outcome; AES-256 is implementation detail."
```

---

### Change 3: Add Pre-Rejection Recovery Checklist (NEW)

**Location:** Before Decision Logic section

**Rationale:** Forces LLM to run through rules before saying NO_MATCH. This is the critical "stop and think" mechanism that Gemini's approach lacks.

```markdown
## Pre-Rejection Recovery Checklist

**BEFORE returning NO_MATCH, run through these checks:**

| Check | Question | If YES → |
|-------|----------|----------|
| IR-1 | Is control target a SUBSET of policy scope? | MAPPED |
| IR-2 | Does abstract policy mandate cover specific control method? | MAPPED |
| IR-3 | Does policy mandate same OUTCOME in different words? | MAPPED |
| IR-4 | Does policy mandate WHAT/WHO even if HOW/WHEN is missing? | MAPPED |
| IR-5 | Does continuous mandate ("always") cover specific interval ("annually")? | MAPPED |
| IR-6 | Does mandate to USE/MANAGE imply thing must EXIST? | MAPPED |
| IR-7 | Does positive mandate imply the prohibition? | MAPPED |
| IR-8 | Does soft language appear under binding header? | MAPPED |
| IR-9 | Does policy reference standard containing the detail? | MAPPED |
| IR-10 | Does control allow alternatives, and policy addresses one? | MAPPED |
| Framework | Am I demanding details that belong in Standard/Procedure/Evidence? | MAPPED |

**If ANY check succeeds → upgrade to MAPPED or PARTIAL**
**Only return NO_MATCH if ALL checks fail**
```

---

### Change 4: Strengthen Scope Validation with Examples (MODIFY)

**Location:** Phase 1.2 "Validate Scope Coverage"

```markdown
### 1.2 Validate Scope Coverage (Apply IR-1)

**Hierarchical Scope Examples:**

| Control Target | Policy Scope | Relationship | Decision |
|---------------|--------------|--------------|----------|
| "DNS servers" | "All IT infrastructure" | Subset | **MAPPED** (IR-1) |
| "Laptops" | "All endpoint devices" | Subset | **MAPPED** (IR-1) |
| "Production databases" | "All company data" | Subset | **MAPPED** (IR-1) |
| "All systems" | "Production systems only" | Superset | **PARTIAL** (material subset) |
| "Vendors" | "Internal employees only" | Excluded | **NO_MATCH** or PARTIAL (gap) |

**Rule:** If control's target is logically contained within policy's scope → MAPPED
```

---

### Change 5: Strengthen Semantic Equivalence with Examples (MODIFY)

**Location:** Phase 1.1 "Find Candidate Evidence"

```markdown
### 1.1 Find Candidate Evidence (Apply IR-3)

**Semantic Equivalence Examples:**

| Control Term | Policy Equivalent | Why It's a Match |
|--------------|-------------------|------------------|
| "MFA" | "Strong authentication for remote access" | Functional outcome equivalent |
| "Non-repudiation" | "Logs capture user identity and action" | Components satisfy definition |
| "Central management" | "Only authorized personnel may modify" | Access restriction = central control |
| "Prohibit unowned assets" | "All assets must have an owner" | Positive mandate implies prohibition (IR-7) |
| "Asset inventory" | "Assets shall be tracked and monitored" | Tracking implies inventory (IR-6) |
| "AES-256 encryption" | "Data shall be encrypted at rest" | Abstract covers specific (IR-2) |

**Test:** Would a reasonable auditor accept the policy language as addressing the control's intent?
```

---

### Change 6: Update Decision Logic (MODIFY)

**Location:** Phase 4 Decision Logic

```markdown
## Phase 4: Decision Logic

### MAPPED
Return **MAPPED** if:
1. Policy mandates the **Core Objective** (explicit or via Interpretive Rules)
2. Scope encompasses target (explicitly or hierarchically via IR-1)
3. Binding language exists (direct or inherited via IR-8)
4. You applied the Interpretive Rules to bridge any gaps

### PARTIAL
Return **PARTIAL** only for genuine **policy-level** gaps:
- **Scope gap**: Policy explicitly excludes required assets (not a subset relationship)
- **Third-party gap**: Internal-only when vendor coverage required
- **Ownership gap**: No accountability implied

**Do NOT use PARTIAL for:** Missing technical specs, frequencies, procedures, or artifacts.

### NO_MATCH
Return **NO_MATCH** only if:
1. Subject matter is completely absent
2. Language is purely aspirational with no binding preambles
3. Policy contradicts the control
4. **ALL Pre-Rejection Recovery checks have been run and failed**
```

---

### Change 7: Update Output Format to Cite Rules (MODIFY)

**Location:** Output Format section

```markdown
## Output Format

| Field | Description |
|-------|-------------|
| `control_id` | The control ID from the input |
| `decision` | **MAPPED** / **PARTIAL** / **NO_MATCH** |
| `confidence` | **high** / **medium** / **low** |
| `evidence_quote` | **FIRST SENTENCE ONLY** of the binding evidence. Empty for NO_MATCH. |
| `location_reference` | Page number or section header. Empty for NO_MATCH. |
| `gaps_identified` | Array of policy-level gaps (for PARTIAL only). |
| `reasoning` | **Cite Interpretive Rules used.** E.g., "Mapped via IR-2: Policy mandates encryption outcome; AES-256 is implementation detail in standards." |

**Reasoning Format:**
- For MAPPED: "Mapped via IR-X: [explanation]"
- For PARTIAL: "Partial match. IR-X applies but [policy-level gap exists]"
- For NO_MATCH: "No match. Checked IR-1 through IR-10; [explanation of why all failed]"
```

---

### Change 8: Update User Prompt (MODIFY)

**Location:** `user.md`

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

### Change 9: Add Phase 0.5 - Extract Policy Context (NEW - ChatGPT's Best Idea)

**Location:** After Phase 0, before Phase 1

**Rationale:** Extract reusable policy context ONCE before evaluating controls. This reduces redundant processing and ensures consistency across all control evaluations.

```markdown
## Phase 0.5: Extract Policy Context (Once Per Document)

Before evaluating controls, scan the policy document and extract these reusable facts:

| Context Element | What to Extract | Why It Matters |
|-----------------|-----------------|----------------|
| **Scope/Applicability** | What entities/systems/data the policy covers | Determines IR-1 hierarchical scope |
| **Definitions** | Synonyms, special terms, acronyms | Enables IR-3 semantic equivalence |
| **Roles/Responsibilities** | Who owns what, accountability structure | Answers Question 3 (Ownership) |
| **Review Cycle** | "Reviewed annually", "updated periodically" | Applies to all requirements (IR-5) |
| **External Standards** | References to CIS, NIST, ISO, vendor benchmarks | Enables IR-9 inherited requirements |
| **Binding Conventions** | "The following requirements apply:", "must include:" | Enables IR-8 binding inheritance |

**Reuse these facts** when evaluating each control—do NOT re-extract for every control.
```

---

### Change 10: Add 3-Pass Evidence Retrieval (NEW - ChatGPT's Structure)

**Location:** Replace or restructure Phase 1.1

**Rationale:** Structured search passes make the rescue search mandatory and explicit, not optional.

```markdown
## Phase 1: Evidence Retrieval (3 Passes)

### Pass A: Direct Binding Evidence (High Confidence)
Look for explicit binding language that directly addresses the control:
- Strong verbs: "must", "shall", "required", "prohibited", "will"
- Direct subject match or clear synonyms

**If found → proceed to validation**

### Pass B: Functional/Semantic Equivalence (Medium Confidence)
If Pass A fails, search for different wording that mandates the same function/outcome:
- Do NOT require exact terminology
- If policy mandates the outcome, and control is a recognized method → covered

**If found → proceed to validation with medium confidence**

### Pass C: False Negative Rescue Search (MANDATORY if leaning NO_MATCH)
If considering NO_MATCH, you MUST explicitly search for:

| Search Target | What to Look For |
|---------------|------------------|
| Hierarchical scope | Does policy's broad scope include control's specific target? (IR-1) |
| Binding preambles | Headers that bind subsequent lists/tables? (IR-8) |
| External standards | CIS/NIST/ISO references that imply technical settings? (IR-9) |
| Broad artifacts | "Log security events" covering specific fields? (IR-6) |
| Review cycles | Document-level review applying to child requirements? (IR-5) |
| Indirect binding | Equivalent legal mechanisms (acknowledgments, certifications)? |

**If ANY Pass C search succeeds → upgrade to at least PARTIAL**
```

---

### Change 11: Strengthen "Do NOT" Language Throughout (MODIFY)

**Location:** Throughout system prompt, especially Decision Logic

**Rationale:** ChatGPT's analysis shows that directive negative language ("do NOT reject") is more effective than passive language ("don't penalize").

**Updates to existing sections:**

In **IR-4 (Governance→Procedure)**:
```markdown
| IR-4 | **Governance→Procedure** | Control asks How/When; policy says What/Who | Governance mandate exists → MAPPED. **Do NOT reject for missing procedural steps.** |
```

In **IR-5 (Frequency Abstraction)**:
```markdown
| IR-5 | **Frequency Abstraction** | Control asks specific interval; policy mandates activity without interval | **Do NOT reject for missing frequency.** If activity is mandated, treat frequency as procedural. |
```

In **Decision Logic - PARTIAL**:
```markdown
### PARTIAL
Return **PARTIAL** only for genuine **policy-level** gaps:
- **Scope gap**: Policy explicitly excludes required assets (not a subset relationship)
- **Third-party gap**: Internal-only when vendor coverage required
- **Ownership gap**: No accountability implied

**Do NOT use PARTIAL for:**
- Missing technical specifications (algorithms, configs) → use IR-2
- Missing frequencies (when activity is mandated) → use IR-5
- Missing procedures (when governance exists) → use IR-4
- Missing artifacts/evidence language → mandate to act implies documentation
```

---

## Implementation Summary

| Change | Type | Source | Impact | Lines |
|--------|------|--------|--------|-------|
| 1. Phase 0 Enhancements | Modify | Gemini | Setup mental model early | +15 |
| 2. Interpretive Rules Table | New | Gemini | Core rules, numbered | +25 |
| 3. Pre-Rejection Checklist | New | Original | Stop-and-think mechanism | +20 |
| 4. Scope Examples | Modify | Original | Concrete guidance | +10 |
| 5. Semantic Equivalence Examples | Modify | Original | Concrete guidance | +10 |
| 6. Decision Logic Update | Modify | Original | Reference rules | +5 |
| 7. Output Format Update | Modify | Gemini | Cite rules requirement | +5 |
| 8. User Prompt Update | Modify | Original | Reference rules | +10 |
| 9. Phase 0.5 Policy Context | New | **ChatGPT** | Extract reusable facts ONCE | +15 |
| 10. 3-Pass Evidence Retrieval | New | **ChatGPT** | Structured A/B/C search | +25 |
| 11. "Do NOT" Language | Modify | **ChatGPT** | Directive instructions | +10 |
| **Total** | | | | **+150** |

**Estimated Final Length:** ~400-430 lines (vs current 293)
**Length Increase:** ~40% (tradeoff: more comprehensive false negative prevention)

---

## Comparison: Original Plan vs Gemini vs ChatGPT vs Final

| Aspect | Original | Gemini 3 | ChatGPT | **Final (Hybrid)** |
|--------|----------|----------|---------|-------------------|
| Rules Format | Scattered tables | IR-1 to IR-10 table | Sections 2.2-2.8 | **IR-1 to IR-10 table** |
| Rule Citation | Not required | Required | Not required | **Required** |
| Recovery Mechanism | Verbose checklist | None | Phase 3 rescue pass | **Both: Checklist + 3-Pass** |
| Phase 0 | No changes | Constitutive elements | - | **Constitutive elements** |
| Phase 0.5 | Not covered | Not covered | Policy context extraction | **Policy context extraction** |
| Evidence Search | Single pass | Single pass | 3-pass A/B/C | **3-pass A/B/C** |
| Language Style | Passive | Mixed | Directive "do NOT" | **Directive "do NOT"** |
| Templates | Not covered | Covered | - | **Covered** |
| Estimated Lines | +107 | +100 | ~250 total | **+150** |
| Key Innovation | Recovery Checklist | IR Table + Citation | Rescue Pass + Context | **All combined** |

---

## Expected Impact

### Rules Addressed

| Interpretive Rule | Universal Rules Covered | Rare Rules Covered |
|-------------------|------------------------|-------------------|
| IR-1 (Hierarchical Scope) | U1, U6 | R5 |
| IR-2 (Tech→Abstract) | U2 | R8 |
| IR-3 (Semantic Equivalence) | U3 | R3, R7 |
| IR-4 (Governance→Procedure) | U4 | R10 |
| IR-5 (Frequency Abstraction) | U5, U10 | R6, R9 |
| IR-6 (Inferred Existence) | U7 | - |
| IR-7 (Positive→Prohibition) | - | R4 |
| IR-8 (Binding Inheritance) | U11 | R11 |
| IR-9 (Standard Reference) | U8 | R8 |
| IR-10 (Disjunctive Logic) | U9 | R1 |
| Phase 0 (Constitutive) | - | R7 |
| Phase 0 (Templates) | - | R11 |

### Coverage Summary
- **Universal Rules:** 11/11 addressed
- **Rare Rules:** 12/12 addressed (improved from 11/12)

---

## Next Steps

1. [x] Review plan
2. [x] Incorporate Gemini 3 feedback
3. [x] Incorporate ChatGPT feedback
4. [ ] Implement changes to `system.md` (11 changes)
5. [ ] Implement changes to `user.md`
6. [ ] Implement changes to `response.json`
