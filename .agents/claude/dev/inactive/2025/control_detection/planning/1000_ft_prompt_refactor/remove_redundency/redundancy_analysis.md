# System Prompt Redundancy Analysis

> **Source**: `non_redundent_system.md` (849 lines)
> **Goal**: Identify redundancies that can be consolidated without losing information
> **Note**: Core concepts repeated at beginning and end as "reminders" are acceptable

---

## Comparison with Other Analyses

### Gemini's Analysis

Gemini proposed **aggressive consolidation**, removing Part 6.2, 6.3, and 6.4 entirely. Their rationale: "An LLM does not need a summary table if it has the full definition in context."

**Where I agree with Gemini:**
- Common Errors table (6.2) is highly redundant — upgrading to MEDIUM severity
- Reasoning examples could move from Part 6.1 into Part 5 (collocate criteria + output format)

**Where I differ from Gemini:**
- Quick Reference Indexes (6.3, 6.4) serve as a "closing summary" that reinforces rules before the task begins. One-line descriptions ≠ full paragraphs. Keeping as OPTIONAL removal.
- Gemini's version is ~125 lines (vs 849) — too aggressive; loses teaching depth and examples

### ChatGPT's Analysis

ChatGPT identified several redundancies I missed and proposed an elegant **"pointer pattern"**:

> **Canonical statement once** (where it belongs) → **Short reminder later** ("Reminder: default NO_MATCH") → **Pointer instead of re-explaining** ("See Part 1 Corollary / See G-6")

**New findings from ChatGPT I'm adding:**
- Decision labels (MAPPED/PARTIAL/NO_MATCH) defined twice (Part 1 + Part 5) → LOW
- "IRs only after guardrails" repeated verbatim (Part 4.1 + Part 6.4) → LOW
- "If found → Proceed to Part 4" duplicated in Pass A and Pass B → LOW
- Subset coverage logic repeated (G-6 + Part 5.2) → Already captured in #4

**ChatGPT's pointer pattern is the key insight:** Instead of deleting reminders entirely, replace re-explanations with pointers like "See Part 1 Corollary" or "See G-6"

---

## Summary of Findings

| Category | Severity | Lines Affected | Potential Savings |
|----------|----------|----------------|-------------------|
| Mass Mapping Table Duplication | HIGH | ~4 lines | Exact duplicate table |
| MAPPED Requirements Triple-Check | HIGH | ~30 lines | Three overlapping lists |
| Common Errors Table (6.2) | MEDIUM | ~15 lines | 6/11 are exact duplicates of Guardrail examples |
| Primary/Secondary Qualifiers Re-Explanation | MEDIUM | ~15 lines | Full re-explanation |
| "What is NOT a PARTIAL" Overlap | MEDIUM | ~8 lines | Overlaps Policies vs Procedures |
| Decision Labels Defined Twice (ChatGPT) | LOW | ~6 lines | Part 1 + Part 5 both define MAPPED/PARTIAL/NO_MATCH |
| "IRs only after guardrails" Repeated (ChatGPT) | LOW | ~2 lines | Part 4.1 + Part 6.4 verbatim |
| "If found → Proceed to Part 4" Duplicated (ChatGPT) | LOW | ~2 lines | Pass A + Pass B both have this |
| Quick Reference Indexes (6.3, 6.4) | OPTIONAL | ~50 lines | LLMs may not need lookup tables |

**Estimated consolidation potential: ~60-80 lines (conservative) or ~110+ lines (aggressive)**

---

## HIGH Severity Redundancies

### 1. Mass Mapping Expected Counts Table (EXACT DUPLICATE)

The policy type → typical mapping count table appears **verbatim twice**:

**First occurrence (Part 1, lines 73-77):**
```markdown
| Policy Type | Typical Mapping Count |
|-------------|----------------------|
| Narrow policy (e.g., Password Policy) | 2–5 controls |
| Acceptable Use Policy | 5–15 controls |
| Comprehensive Information Security Policy | 20–40 controls |
```

**Second occurrence (Part 5.4, lines 673-676):**
```markdown
- Narrow policy: 2–5 controls
- Acceptable Use Policy: 5–15 controls
- Comprehensive InfoSec Policy: 20–40 controls
```

**Recommendation:** In Part 5.4, replace with a reference:
> "As noted in Part 1 (Setting Expectations), most policies map to a small subset of controls. If you've mapped more than 30-40% of the controls in a batch, you're probably being too permissive."

---

### 2. MAPPED Requirements: Three Overlapping Lists

There are THREE lists that all attempt to define MAPPED requirements:

**List A: The Four Requirements (Part 1, lines 60-65)**
```
1. Mandate
2. Correct Scope
3. Type Match
4. No Critical Mismatch
```

**List B: Requirements for MAPPED (Part 5.1, lines 540-550)**
```
1. Binding evidence exists
2. Evidence is admissible
3. Evidence is localized
4. Type matches
5. Domain matches
6. Scope is satisfied
7. Qualifiers are satisfied
8. No guardrails violated
9. No contradictions
```

**List C: Before returning MAPPED, verify (Part 5.1, lines 553-557)**
```
- Type match?
- Domain match?
- Qualifiers satisfied?
- Binding language?
- Not a substitute?
```

**Analysis:**
- List B items 4-5 (type/domain) duplicate List C items 1-2
- List B items 6-7 (scope/qualifiers) duplicate List C items 3
- List B item 1 (binding) duplicates List C item 4
- List B items 8 (guardrails) subsumes List C item 5
- List B is just an expansion of List A

**Recommendation:** Keep List A in Part 1. In Part 5.1, keep ONLY List B (the detailed table) and DELETE List C entirely. List C adds nothing that List B doesn't already cover.

**Current (lines 552-557):**
```markdown
**Before returning MAPPED, verify:**
- [ ] Type match? Is evidence the same type as control (technical/admin/physical)?
- [ ] Domain match? Is evidence in the same domain (physical/logical/data)?
- [ ] Qualifiers satisfied? Are all primary qualifiers present?
- [ ] Binding language? Does it say "must/shall" (not "should/may")?
- [ ] Not a substitute? Am I accepting a review/policy for a technical mechanism?
```

**Recommendation:** DELETE entirely. Table above already covers all this.

---

## MEDIUM Severity Redundancies

### 3. Primary vs Secondary Qualifiers Re-Explanation

The primary/secondary qualifier distinction is **fully explained twice**:

**First occurrence (Part 2, lines 149-177):**
- Full tables of Primary Qualifiers (Standards, Audience, Scope, Mechanisms, Domain, Lifecycle)
- Full tables of Secondary Qualifiers (Frequencies, Numeric thresholds, Configuration details, Review cadences)
- Two examples showing the distinction

**Second occurrence (Part 4.3, lines 415-427):**
- Re-states the Core Mandate Test rule
- Another 5-row example table showing the same distinction

**Comparison of example tables:**

Part 2 (lines 173-175):
```
- Control: "FIPS-validated encryption" / Policy: "Data shall be encrypted" → NO_MATCH (FIPS is primary)
- Control: "Asset inventory reviewed annually" / Policy: "Asset inventory shall be maintained" → MAPPED (annual is secondary)
```

Part 4.3 (lines 421-427):
```
| "Asset inventory reviewed annually" | "Asset inventory shall be maintained" | MAPPED | Core artifact mandated; "annual" is secondary |
| "Patches installed within 30 days" | "Security patches shall be applied" | MAPPED | Core activity mandated; timing is secondary |
| "Anti-malware centrally managed" | "Anti-malware shall be deployed" | MAPPED | Core mechanism mandated; "centrally" is secondary |
| "FIPS-validated encryption" | "Data shall be encrypted" | NO_MATCH | FIPS is primary (G-13 blocks) |
| "Third-party penetration test" | "Penetration tests conducted" | NO_MATCH | "Third-party" is primary (G-13 blocks) |
```

**Recommendation:** In Part 4.3, keep only the 2-3 NEW examples (patches, anti-malware, third-party) and reference Part 2 for the concept:

```markdown
## 4.3 The Core Mandate Test (G-13 Application)

Apply the primary vs secondary qualifier distinction from Part 2.2:

> **Core Mandate Test:** If the policy mandates the ARTIFACT or MECHANISM, and the control only adds a frequency or operational detail, the policy satisfies the control at the governance level.

| Control | Policy Says | Decision | Why |
|---------|-------------|----------|-----|
| "Patches installed within 30 days" | "Security patches shall be applied" | **MAPPED** | Core activity mandated; timing is secondary |
| "Third-party penetration test" | "Penetration tests conducted" | **NO_MATCH** | "Third-party" is primary (G-13 blocks) |
```

---

### 4. "What is NOT a PARTIAL" Overlaps Policies vs Procedures

**Part 1 (lines 45-50):**
```markdown
| Policies Provide | Policies Do NOT Provide |
|------------------|-------------------------|
| **Mandates** (what must happen) | Technical parameters (AES-256, TLS 1.2) |
| **Scope** (what's covered) | Step-by-step procedures |
| **Ownership** (who's accountable) | Specific frequencies (unless regulatory) |
| **Principles and requirements** | Evidence artifacts |
```

**Part 5.2 (lines 603-608):**
```markdown
| Missing Element | Correct Decision | Why |
|-----------------|------------------|-----|
| Technical parameters (AES-256, TLS 1.2) | **MAPPED** | Policies don't specify parameters; IR-2 bridges |
| Step-by-step procedures | **MAPPED** | Policies set governance, not procedures |
| Specific frequencies | **MAPPED** | Secondary qualifier; Core Mandate Test applies |
| Operational details ("centrally managed") | **MAPPED** | Secondary qualifier when core mandate exists |
```

**Analysis:** The "What is NOT a PARTIAL" table repeats what was already established in Part 1's "Policies vs Procedures" table. Both say: don't penalize policies for missing technical parameters, procedures, or frequencies.

**Recommendation:** In Part 5.2, replace the table with a brief reference:

```markdown
### What is NOT a PARTIAL

As established in Part 1, policies provide mandates, not operational details. Do NOT use PARTIAL for:
- Missing technical parameters → **MAPPED** (IR-2 bridges)
- Missing procedures → **MAPPED** (policies set governance)
- Missing frequencies → **MAPPED** (Core Mandate Test)
- Missing core mandate → **NO_MATCH** (not PARTIAL)

**The test:** Is the policy *explicitly excluding* something, or just *not specifying details*?
```

---

### 5. Common Errors Table (6.2) — Upgraded to MEDIUM per Gemini

**Part 4.2 Guardrails (lines 367-400):** Each guardrail has a detailed example in the "Example" column.

**Part 6.2 Common Errors (lines 763-775):** Provides 11 error patterns with examples.

**Overlap Analysis:**

| Common Error (6.2) | Guardrail Example (4.2) | Duplicate? |
|-------------------|-------------------------|------------|
| "Review access controls" → "Automated access enforcement" | G-1 example | Similar |
| "Users must use proxy" → "Network IPS" | G-2 example | EXACT |
| "Log unauthorized attempts" → "Prevent unauthorized access" | G-3 example | Similar |
| "Report incidents" → "Incident response plan" | G-4 example | EXACT |
| "Badge access" → "Network segmentation" | G-5 example | Different mechanism focus |
| "Employee policy" → "Vendor requirements" | G-8 example | Similar |
| Acceptable Use Policy → InfoSec Policy | G-10 example | EXACT |
| "Encryption" → "FIPS-validated encryption" | G-13 example | EXACT |
| "Monitor assets" → "Asset inventory" | G-14 example | Similar |
| "Install antivirus" → "Auto-update signatures" | G-15 example | EXACT |
| "Per ISO 27001" → Specific control | G-16 example | EXACT |

**Assessment:** 6 of 11 common errors are exact duplicates of guardrail examples. Gemini correctly identified this as redundant.

**Recommendation:** DELETE Section 6.2 entirely, OR reduce to only the 3-4 error patterns NOT already in guardrail examples (e.g., "Badge access" as G-5 has different focus).

---

## LOW Severity Redundancies (from ChatGPT)

These are minor redundancies that can be fixed with the **pointer pattern**: replace re-explanation with a short reference.

### 6. Decision Labels Defined Twice

**Part 1 (lines 23-25):** Introduces MAPPED / PARTIAL / NO_MATCH as primary outputs.
**Part 5 (lines 534, 572, 617):** Re-defines each: "MAPPED means...", "PARTIAL means...", "NO_MATCH means..."

**Recommendation:** In Part 5, replace "MAPPED means..." with "See Part 1 for definitions; below are the decision criteria."

### 7. "IRs Only After Guardrails" Repeated Verbatim

**Part 4.1 (line 352):** "IRs can only be applied if NO guardrail is violated."
**Part 6.4 (line 818):** "IRs can ONLY be applied if NO guardrail is violated first."

**Recommendation:** In Part 6.4, replace with "See Part 4.1 (Order of operations)."

### 8. "If Found → Proceed to Part 4" Duplicated

**Pass A (line 265):** "If found: Proceed to Part 4 (Validate the Match)"
**Pass B (line 286):** "If found: Proceed to Part 4 (Validate the Match)"

**Recommendation:** Consolidate into single line after Pass B: "If Pass A or B yields binding evidence, proceed to Part 4."

### 9. Subset Coverage Logic Repeated

**G-6 (line 379):** Explains "subset without explicit exclusion can still be MAPPED"
**Part 5.2 (line 580):** Repeats "Policy covers a subset... is MAPPED"

**Recommendation:** In Part 5.2, shorten to "Subset coverage without explicit exclusion is not a gap (see G-6)."

---

## OPTIONAL Severity (Aggressive Consolidation)

### 10. Quick Reference Indexes (6.3, 6.4)

**Part 6.3 (lines 777-812):** Guardrail Index — one-line descriptions of G-1 through G-17
**Part 6.4 (lines 814-829):** IR Index — one-line descriptions of IR-1 through IR-8

**Gemini's view:** Remove entirely. "An LLM does not need a summary table if it has the full definition in context."

**Counter-argument:**
- One-line descriptions ≠ full paragraphs with examples
- Serves as "closing summary" before the task begins
- May help with pattern-matching during inference

**Assessment:** OPTIONAL removal. If you need aggressive line reduction, these can go. If you value closing reinforcement, keep them.

**Recommendation:** If keeping, add a note: "See Part 4.2/4.4 for full details." If removing, no changes needed to Part 4.

---

## Acceptable Redundancies (Intentional Reminders)

The following redundancies appear to be **intentional reminders** at key decision points:

### The Golden Rule
- Line 33: Initial statement (Part 1)
- Line 634: Reminder before NO_MATCH checklist (Part 5.3)
- Line 848: Final reminder in Closing

**Assessment:** KEEP. These are strategically placed at: (1) introduction, (2) decision point, (3) closing. This is appropriate emphasis.

### Default NO_MATCH Position
- Line 27: "Your default position is NO_MATCH"
- Line 617: "This is your default position"

**Assessment:** KEEP. One establishes the rule, one reinforces at decision time.

### Type/Domain Matching
Mentioned in: Four Requirements, Control Classification, Pass A criteria, MAPPED requirements, Guardrails

**Assessment:** KEEP. Each mention serves a different purpose in the teaching flow. This is reinforcement, not redundancy.

---

## Implementation Priority

### Recommended Approach: The Pointer Pattern

ChatGPT's insight: Instead of deleting content entirely, **replace re-explanations with pointers**:
- ❌ Delete "IRs only after guardrails" from Part 6.4
- ✅ Replace with "See Part 4.1 (Order of operations)"

This preserves the reminder while eliminating the redundant text.

---

### Tier 1: HIGH Severity (Do First)
- [ ] Delete duplicate mapping count table in Part 5.4 (replace with "See Part 1")
- [ ] Delete "Before returning MAPPED, verify" checklist (lines 552-557)

### Tier 2: MEDIUM Severity (Do Soon)
- [ ] DELETE or heavily trim Section 6.2 (Common Errors) — 6/11 are exact duplicates
- [ ] Consolidate Part 4.3 examples with Part 2.2 (remove duplicates, keep new examples)
- [ ] Replace "What is NOT a PARTIAL" table with brief reference + pointer

### Tier 3: LOW Severity (Quick Wins via Pointer Pattern)
- [ ] Part 5 decision definitions → "See Part 1; below are criteria"
- [ ] Part 6.4 IR reminder → "See Part 4.1"
- [ ] Pass A/B "If found" → single line after Pass B
- [ ] Part 5.2 subset logic → "see G-6"

### Tier 4: OPTIONAL (Aggressive)
- [ ] Remove Section 6.3 (Guardrail Index) — ~35 lines
- [ ] Remove Section 6.4 (IR Index) — ~15 lines

---

## Estimated Line Count After Consolidation

### Conservative Approach (Tier 1 + Tier 2 + Tier 3)

| Section | Current | After | Saved |
|---------|---------|-------|-------|
| Part 5.4 Mass Mapping | 16 lines | 8 lines | 8 |
| Part 5.1 MAPPED Checklist | 6 lines | 0 lines | 6 |
| Part 6.2 Common Errors | 17 lines | 0 lines | 17 |
| Part 4.3 Core Mandate Test | 13 lines | 8 lines | 5 |
| Part 5.2 What is NOT PARTIAL | 11 lines | 6 lines | 5 |
| Part 5 Decision Definitions (pointer) | 6 lines | 2 lines | 4 |
| Part 6.4 IR Reminder (pointer) | 2 lines | 1 line | 1 |
| Pass A/B consolidation | 4 lines | 2 lines | 2 |
| Part 5.2 Subset Logic (pointer) | 2 lines | 1 line | 1 |
| **Total** | ~77 lines | ~28 lines | **~49 lines** |

**Conservative result: ~800 lines** (down from 849)

### Aggressive Approach (+ Tier 4)

| Section | Additional Savings |
|---------|-------------------|
| Part 6.3 Guardrail Index | ~35 lines |
| Part 6.4 IR Index | ~15 lines |
| **Additional** | **~50 lines** |

**Aggressive result: ~750 lines** (down from 849)
