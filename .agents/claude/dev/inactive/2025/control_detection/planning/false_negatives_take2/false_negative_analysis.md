# False Negative Analysis: Experiment 6

**Date**: 2025-12-31
**Experiment**: `experiment_6` (False-Positive Focused Prompt)
**False Negatives**: 188 (164 NO_MATCH, 24 PARTIAL)
**Recall**: 64.79%

---

## Executive Summary

Analysis of 188 false negatives reveals **systematic over-strictness** in several categories:

| Root Cause | Count | % of FNs | Severity |
|------------|-------|----------|----------|
| G-14: General vs Specific Scope | 51 | 27% | **Critical** |
| G-10: Missing Hard Qualifiers | 41 | 22% | **Critical** |
| G-16: Presence vs Configuration | 17 | 9% | High |
| G-17: Input for Program | 12 | 6% | Medium |
| Permissive Language Blocking | ~15 | 8% | High |
| G-4: Domain Mismatch | 9 | 5% | Medium |
| G-15/G-11: Artifact Issues | 16 | 9% | Medium |
| G-12: Cross-Reference Only | 6 | 3% | Medium |
| Evidence Locality Rule | ~5 | 3% | Medium |
| Other (G-1, G-2, G-5, etc.) | ~16 | 9% | Low |

**Key Finding**: The top two guardrails (G-14 + G-10) account for **49% of false negatives** (92 of 188). These are the highest-impact targets for recall improvement.

---

## Theme 1: G-14 Over-Application (General vs Specific)

**Frequency**: ~45 instances (24% of FNs)
**Severity**: Critical — This is the single largest cause of recall loss

### The Problem

G-14 states: *"Evidence is general but control requires specific scope/qualifier not explicitly included"*

The LLM is applying G-14 too aggressively, rejecting controls when:
- The policy scope is **reasonably broader** than the control target
- The evidence uses **different but equivalent terminology**
- Minor phrasing differences exist between control and policy

### Examples of Over-Strict Application

**Example 1: DCF-73 (Network Security Policy)**
- **Control**: "Restrict public access to remote server administration ports to authorized IP addresses"
- **Policy**: "Restrict traffic to authorized services/ports"
- **LLM Rejection**: "G-14: Does not explicitly require restricting admin ports to 'authorized IP addresses' specifically"
- **Analysis**: The policy covers authorized services/ports which logically includes admin ports. This is a semantic equivalence the LLM should accept.

**Example 2: DCF-645 (Encryption Policy)**
- **Control**: "Communication at the session level is protected"
- **Policy**: "Encryption standards for VPN/SSL and cloud transit"
- **LLM Rejection**: "G-14: Lacks a general mandate to protect all communication at the session level"
- **Analysis**: VPN/SSL encryption IS session-level protection. The LLM is missing the semantic equivalence.

**Example 3: DCF-3 (Data Protection Policy)**
- **Control**: "Administrator access to web-based management interfaces is encrypted"
- **Policy**: "Encrypted internet/intranet connections"
- **LLM Rejection**: "G-14: General mandate lacks specific scope qualifier for administrative access"
- **Analysis**: If ALL internet connections must be encrypted, that inherently covers admin access.

### Recommended Fix

**Soften G-14 with IR-1 (Hierarchical Scope)**:
- If policy mandate covers a **superset** of the control's scope, apply IR-1
- Add explicit guidance: "G-14 does NOT apply when policy scope fully encompasses control scope"

**Example language**:
> G-14 blocks when evidence addresses a *different* scope than the control. G-14 does NOT block when evidence addresses a *broader* scope that fully includes the control's target. Use IR-1 in such cases.

---

## Theme 2: Permissive Language Over-Blocking

**Frequency**: ~35 instances (19% of FNs)
**Severity**: Critical — Second largest cause

### The Problem

The prompt contains:
> *"Permissive language (should, may, might, can, recommended, encouraged, where applicable, as appropriate) — these are hard blockers for MAPPED/PARTIAL"*

The LLM is treating **any** instance of "should" as a total blocker, even when:
- The "should" is in a **different section** than the binding mandate
- The policy contains **both** "must" and "should" for related requirements
- The "should" is for an **optional enhancement**, not the core requirement

### Examples of Over-Strict Application

**Example 1: DCF-5 (SDLC Policy)**
- **Control**: "Changes are peer-reviewed and approved prior to deployment"
- **Policy**: Contains binding "must" language for peer review, but adds "where possible" for automation
- **LLM Rejection**: "G-16: Requirement for automated enforcement is weakened by 'where possible'"
- **Analysis**: The CORE requirement (peer review) uses binding language. The automation is an enhancement.

**Example 2: DCF-6 (SDLC Policy)**
- **Control**: "Access to make changes in production is restricted"
- **Policy**: Uses "should" for separation requirements
- **LLM Rejection**: "Uses permissive language 'should', which is a hard blocker"
- **Analysis**: But does the policy have "must" language for the core access restriction?

**Example 3: DCF-712 (SDLC Policy)**
- **Control**: "SAST tool used in CI/CD pipeline"
- **Policy**: "SAST tools should be used"
- **LLM Rejection**: "Permissive language ('should be used')"
- **Analysis**: Legitimate rejection, but many SDLC requirements legitimately use "should" in policy templates.

### Recommended Fix

**Distinguish "should" types**:
1. **Total permissiveness**: "may" / "might" / "can" / "recommended" → Hard block (keep)
2. **Soft mandate**: "should" → Block only if no "must" alternative exists for core requirement
3. **Conditional**: "where applicable" / "as appropriate" → Check if condition is met

**Example language**:
> "Should" is a soft blocker. Before rejecting on "should": (1) Check if the CORE objective has "must/shall" language elsewhere, (2) If "should" applies to an enhancement/method rather than the objective itself, the core mandate may still satisfy the control.

---

## Theme 3: G-10 Missing Hard Qualifiers

**Frequency**: ~30 instances (16% of FNs)
**Severity**: High — Often legitimate rejections, but some are over-strict

### The Problem

G-10 states: *"Control has hard qualifiers absent from evidence (no inference allowed)"*

The LLM correctly identifies missing qualifiers like:
- Specific frequencies ("annually", "daily", "within one month")
- Specific technical terms ("FIPS validated", "authenticated scan")
- Specific actor types ("independent third party", "authorized personnel")

### Examples — Legitimate Rejections (Keep Strict)

**DCF-297 (Vulnerability Management Policy)**
- **Control**: "Critical patches installed within one month of release"
- **Policy**: Contains placeholders for SLAs, no specific timeframe
- **LLM Rejection**: "G-10: Does not mandate specific 'one month' qualifier"
- **Analysis**: CORRECT rejection — numeric qualifier is non-negotiable

**DCF-19 (Vulnerability Management Policy)**
- **Control**: "External penetration test by independent third party"
- **Policy**: "Allows for internal testers"
- **LLM Rejection**: "G-10: Mandates 'independent third party'"
- **Analysis**: CORRECT rejection — "third party" is a hard qualifier

### Examples — Over-Strict Application

**DCF-204 (Network Security Policy)**
- **Control**: "Dataflow diagram reviewed at least annually"
- **Policy**: Requires dataflow diagram, but doesn't specify annual review
- **LLM Rejection**: "G-10: Missing 'annual management approval' qualifier"
- **Analysis**: Could be PARTIAL instead of NO_MATCH

**DCF-21/22 (Network Security Policy)**
- **Control**: "Network/Architectural diagram reviewed annually by management"
- **Policy**: Requires the diagram, no annual review specified
- **LLM Rejection**: "G-10: Missing 'annual' frequency and 'management approval'"
- **Analysis**: The ARTIFACT exists; the REVIEW frequency is missing. Should be PARTIAL.

### Recommended Fix

**Separate artifact existence from operational cadence**:
- If control requires ARTIFACT + FREQUENCY, and policy has artifact but not frequency → **PARTIAL** (not NO_MATCH)
- Only NO_MATCH when the core artifact/mechanism is absent

---

## Theme 4: Evidence Locality Rule Over-Enforcement

**Frequency**: ~25 instances (13% of FNs)
**Severity**: High — The rule is valid but applied too strictly

### The Problem

The prompt states:
> *"Evidence must come from one contiguous location in the document—a paragraph, a section, a bulleted list, or consecutive statements that were written together as a unit."*

The LLM is rejecting controls where:
- Policy sections are **clearly related** but on different pages
- The policy has a **layered structure** (principles in one section, specifics in another)
- Multiple requirements of a compound control are addressed in **logically organized** separate sections

### Examples

**Example 1: DCF-16 (Risk Assessment Policy)**
- **Control**: "Periodic risk assessments with threat/vulnerability analysis, risk owners, treatment options, documented results"
- **LLM Rejection**: "Information distributed across non-contiguous sections (Risk Assessment pages 1-2, Risk Remediation page 3, Regular Reviews page 4), violating Evidence Locality Rule"
- **Analysis**: A Risk Assessment Policy SHOULD have these in organized sections. This is document structure, not evidence assembly.

**Example 2: DCF-375 (Physical Security Policy)**
- **Control**: "Personnel badges + visitor badges that distinguish visitors"
- **LLM Rejection**: "Employee badge requirements (Page 1) and visitor badge requirements (Page 2) are in separate, non-contiguous sections"
- **Analysis**: Logically, personnel and visitor policies may be separate sections. Both are present.

### Recommended Fix

**Distinguish evidence assembly from document structure**:

> Evidence Locality applies when: (1) Combining claims from unrelated topics, (2) Stitching quotes that weren't written as a unit.
>
> Evidence Locality does NOT apply when: (1) A policy has organized sections for related sub-topics, (2) A compound control has multiple requirements addressed in their natural policy sections.

Add: "For compound controls (AND requirements), each requirement may be satisfied by its appropriate policy section. This is not evidence assembly."

---

## Theme 5: G-15/G-11 Artifact Type Issues

**Frequency**: ~20 instances (11% of FNs)
**Severity**: Medium — Some legitimate, some over-strict

### G-15: Wrong Artifact Type

**Example: DCF-800 (AIMS Plan)**
- **Control**: "AI Governance Policy documented"
- **Document**: AIMS Plan (references AI Governance Policy as separate)
- **LLM Rejection**: "G-15: Document is 'AIMS Plan', not 'AI Governance Policy'"
- **Analysis**: CORRECT rejection — the plan is not the policy

**Example: DCF-187 (Change Management Policy)**
- **Control**: "Configuration Management Plan"
- **Document**: Change Management Policy
- **LLM Rejection**: "G-15: Document is Change Management Policy; references Configuration Management Plan as separate"
- **Analysis**: CORRECT rejection

### G-11: Activity for Artifact

**Example: DCF-569 (Data Classification Policy)**
- **Control**: "Labeling procedures implemented"
- **LLM Rejection**: "G-11: Provides classification scheme but labeling rows are empty/placeholders"
- **Analysis**: CORRECT — placeholders don't satisfy artifact requirement

### Recommended Fix

These are generally **legitimate rejections**. Keep the guardrails.

However, consider: When a document REFERENCES another required document, should that be PARTIAL instead of NO_MATCH?

---

## Theme 6: G-12 Cross-Reference Rejections

**Frequency**: 6 instances (3% of FNs)
**Severity**: Medium — Distinct pattern worth addressing

### The Problem

G-12 states: *"Evidence only provides external reference/pointer without stating actual requirements"*

The LLM rejects policies that **delegate to other documents** via cross-references, even when:
- The cross-reference clearly identifies the correct control area
- The policy set is intentionally **modular** (common in enterprise environments)
- The referenced document likely contains the full requirements

### Examples

**Example 1: DCF-79 (Logging & Monitoring)**
- **Control**: "Logging system captures specific audit events"
- **Policy**: "Logging requirements defined per Logging and Monitoring Policy"
- **LLM Rejection**: "G-12: Only provides a pointer to another policy without restating requirements"
- **Analysis**: This is intentional modularity. The Logging Policy exists and likely covers the control.

**Example 2: DCF-590 (Access Control Policy)**
- **Control**: "Audit log file access restricted"
- **Policy**: "Access to logs controlled per Logging Policy"
- **LLM Rejection**: "G-12: Only contains an external pointer without stating actual requirements"
- **Analysis**: Cross-reference to the correct domain policy. Not missing evidence—delegated evidence.

### Why This Causes False Negatives

Many enterprise policy sets are **intentionally modular**:
- Information Security Policy → references Access Control Policy, Logging Policy, etc.
- Each policy covers its domain without duplicating requirements

If cross-references are treated as "no evidence," you'll systematically under-map unless running multi-document retrieval.

### Recommended Fix

**Return PARTIAL with `reference_gap` instead of NO_MATCH**:

```markdown
When policy explicitly references another document for requirements:
- Return PARTIAL (not NO_MATCH)
- Set gap_type: "reference_gap"
- Note: "Requirements delegated to [Referenced Policy]"
```

This allows the pipeline to:
1. Credit the reference as partial coverage
2. Flag for multi-document verification
3. Avoid false negatives from intentional modularity

---

## Theme 7: G-16 Presence vs Configuration

**Frequency**: ~15 instances (8% of FNs)
**Severity**: Medium

### The Problem

G-16 states: *"Control requires operational characteristics (how something is configured/managed) but evidence only mandates presence/use."*

### Examples — Legitimate Rejections

**DCF-50 (Acceptable Use Policy)**
- **Control**: "Anti-malware installed on all company-managed devices"
- **Policy**: "Anti-malware on endpoint systems (workstations/laptops/servers)"
- **LLM Rejection**: "scope_gap: Limited to endpoints, not 'all company-managed devices'"
- **Analysis**: PARTIAL is correct; scope limitation is real

**DCF-614 (Maintenance Management Policy)**
- **Control**: "Automated mechanisms to conduct maintenance"
- **Policy**: "Mentions use of maintenance tools (diagnostic equipment)"
- **LLM Rejection**: "G-16: Mentions tools but doesn't mandate automated mechanisms"
- **Analysis**: CORRECT — presence vs configuration

### Recommended Fix

G-16 is generally applied correctly. Keep as-is.

---

## Theme 8: Template/Placeholder Content

**Frequency**: ~10 instances (5% of FNs)
**Severity**: Medium — These are legitimate rejections

### The Problem

Many Drata template policies contain:
- `<FREQUENCY>` placeholders
- `<COMPANY NAME>` tags (acceptable)
- Empty tables with "insert values here"
- Example data marked as templates

### Examples

**DCF-660 (Risk Assessment Policy)**
- **Control**: "Risk appetite statements defined"
- **LLM Rejection**: "G-15: Risk appetite section has placeholders (<APPETITE LEVEL/etc.>)"
- **Analysis**: CORRECT — placeholders ≠ defined statements

**DCF-77 (Backup Policy)**
- **Control**: "Backups performed at least daily"
- **LLM Rejection**: "G-10: Policy uses placeholder ('<BACKUP FREQUENCY>')"
- **Analysis**: CORRECT — no specific frequency defined

### Recommended Fix

These are **legitimate rejections**. Template policies with placeholders shouldn't map to controls requiring specific values.

Note: This is a data quality issue, not a prompt issue.

---

## Summary: Recommended Prompt Changes

### High Priority (Critical Impact)

1. **Soften G-14 with IR-1 guidance** (~45 FNs potentially recoverable)
   - Clarify that broader policy scope can satisfy narrower control scope
   - Add: "G-14 does NOT apply when evidence scope fully encompasses control target"

2. **Refine permissive language handling** (~35 FNs potentially recoverable)
   - Distinguish "should" in core requirement vs enhancement
   - Allow PARTIAL when "should" applies to method, not objective

3. **Adjust Evidence Locality Rule** (~25 FNs potentially recoverable)
   - Allow compound controls to have evidence in related policy sections
   - Clarify: structured document organization ≠ evidence assembly

### Medium Priority (Moderate Impact)

4. **G-10 Artifact vs Review separation** (~10 FNs potentially recoverable)
   - If artifact exists but operational cadence is missing → PARTIAL
   - Don't NO_MATCH just for missing frequency when artifact is present

5. **G-12 Cross-reference handling** (~6 FNs potentially recoverable)
   - Return PARTIAL with `reference_gap` instead of NO_MATCH
   - Allows pipeline to flag for multi-document verification
   - Respects intentional modularity in enterprise policy sets

### Low Priority (Keep Current Behavior)

6. **G-15, G-16, G-11** — Generally applied correctly
7. **Template/placeholder rejections** — These are legitimate rejections

---

## Quantified Recovery Potential

If the recommended changes are implemented:

| Change | Est. Recoverable FNs | New Recall |
|--------|---------------------|------------|
| Current state | 0 | 64.79% |
| Soften G-14 | ~30-35 | ~70% |
| Refine "should" handling | ~20-25 | ~74% |
| Adjust locality rule | ~15-20 | ~77% |
| G-10 artifact separation | ~5-10 | ~78-79% |
| G-12 cross-reference handling | ~3-5 | ~79-80% |
| **Total potential** | **~75-95** | **~77-81%** |

This would bring recall to ~76-80% while maintaining precision gains from the strict auditor framing.

---

## Appendix: False Negatives by Guardrail Cited (Actual Counts)

| Guardrail | Count | Description |
|-----------|-------|-------------|
| G-14 | 51 | General vs specific scope |
| G-10 | 41 | Missing hard qualifiers |
| G-16 | 17 | Presence vs configuration |
| G-17 | 12 | Input for program |
| G-4 | 9 | Domain mismatch |
| G-11 | 8 | Activity for artifact |
| G-15 | 8 | Wrong artifact type |
| G-5 | 7 | Scope limitation |
| G-12 | 6 | External reference only |
| G-1 | 6 | Admin for technical |
| G-2 | 4 | User rule for system |
| G-3 | 2 | Detection for prevention |
| G-13 | 2 | Risk assessment for implementation |
| G-9 | 1 | Event-driven vs periodic |
| G-8 | 1 | Wrong lifecycle phase |
| IR citations | 14 | IRs cited in PARTIAL decisions |

### By Control Type

| Type | Count |
|------|-------|
| TECHNICAL | 69 |
| ADMINISTRATIVE | 52 |
| ARTIFACT | 28 |
| MONITORING | 24 |
| PHYSICAL | 7 |
| TRAINING | 5 |
| PRIVACY | 3 |

---

## Appendix: Decision Distribution Analysis

### NO_MATCH Decisions (164)

The 164 NO_MATCH decisions break down as:
- **~100**: Guardrail-based rejections (G-X cited)
- **~40**: Permissive language blocking
- **~15**: Evidence locality violations
- **~9**: No binding mandate found (legitimate)

### PARTIAL Decisions (24)

The 24 PARTIAL decisions (also FNs) are:
- **~15**: `scope_gap` — Policy scope is limited vs control
- **~6**: `ownership_gap` or `third_party_gap`
- **~3**: Missing periodic review/update requirements

Many PARTIAL decisions appear **correct** — the policy genuinely has a gap. These should remain PARTIAL, but the system should track them as "partial credit" rather than full false negatives.

---

## Next Steps

1. **Implement prompt adjustments** targeting G-14, permissive language, and locality rule
2. **Re-run experiment** with adjusted prompt
3. **Measure impact** on precision (should stay ~48-50%) and recall (target ~75-80%)
4. **If successful**, proceed to Stage 3 verification implementation
