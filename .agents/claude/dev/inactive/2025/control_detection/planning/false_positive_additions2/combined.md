# Combined False Positive Analysis & Recommendations

This document merges insights from Claude's analysis, Gemini's system prompt rewrite, and ChatGPT's meta-analysis into a unified set of recommendations.

---

## Executive Summary

**Problem:** 28 false positives remain after first round of improvements (17.6% precision, 85.7% recall).

**Root Cause:** The LLM maps on keyword adjacency and plausible implication instead of explicit mandates with correct mechanism/scope.

**Solution Strategy:** Rather than adding many topic-specific guardrails, add 4-5 abstract, reusable guardrails that encode stable logical distinctions. This keeps the prompt robust across arbitrary policy/control sets.

---

## The False Positive Patterns (28 Total)

| Pattern | Count | Controls |
|---------|-------|----------|
| Document-IS-Policy | 4 | DCF-13, DCF-45, DCF-181, DCF-482 |
| Remote-Access→Network | 4 | DCF-206, DCF-223, DCF-342, DCF-822 |
| Encryption-Mention | 3 | DCF-52, DCF-108, DCF-149 |
| Antimalware-Overreach | 3 | DCF-294, DCF-296, DCF-730 |
| IR-Overreach | 6 | DCF-94, DCF-173, DCF-174, DCF-355, DCF-356, DCF-580 |
| Topic-Adjacency | 7 | DCF-10, DCF-11, DCF-326, DCF-381, DCF-528, DCF-589, DCF-627 |
| Behavioral→Technical | 1 | DCF-226 |

---

## Recommended Guardrail Additions

### G-15: Artifact Identity & Primary Purpose

**Consensus: All three sources agree this is critical.**

**Block when:** A control requires an artifact (policy/plan/standard/register), but the document under review is not that artifact by title/purpose/scope, or only addresses the topic as a subsection.

**Operational Test:**
1. Does the document's title/purpose explicitly indicate it establishes the required artifact?
2. Does the scope match the artifact's expected breadth (org-wide vs narrow behavioral rules)?
3. A section about X inside a different policy is NOT "the X policy"

**Key Principle:** A document that MENTIONS a topic ≠ a document that ESTABLISHES policy FOR that topic.

**Examples:**
| Control Requires | Evidence Found | Decision |
|-----------------|----------------|----------|
| "Information Security Policy established" | Acceptable Use Policy exists | NO_MATCH (different artifact type) |
| "Data Protection Policy established" | Clean desk rules in AUP | NO_MATCH (subsection ≠ policy) |
| "Network Security Policy established" | Remote Access section in AUP | NO_MATCH (section ≠ policy) |

---

### G-16: Presence vs Operational Characteristics

**Consensus: All three sources agree. Subsumes encryption, antimalware, firewall, mobile hardening FPs.**

**Block when:** The control requires HOW something operates/configures/is managed (e.g., automatic updates, default-deny, key rotation, hardening standards, scanning on insert), but the evidence only mandates:
- "use/enable/install/implement" (presence), or
- a high-level outcome without the required operational modifier

**Rule of Thumb:** If the control includes an operational qualifier like `automatically`, `configured to`, `default`, `managed`, `hardened`, `rotated`, `on insert`, then that qualifier must appear in the evidence sentence (or exact synonym). Otherwise NO_MATCH.

**Examples:**
| Control | Evidence | Gap | Decision |
|---------|----------|-----|----------|
| "Firewall configured to deny inbound by default" | "Users must enable firewall" | Missing config specifics | NO_MATCH |
| "Auto-scan removable media when inserted" | "Scan files before use" | "before use" ≠ "when inserted" | NO_MATCH |
| "Automatic signature updates" | "Install antimalware" | Installation ≠ configuration | NO_MATCH |
| "Key management procedures" | "Data must be encrypted" | Usage ≠ management | NO_MATCH |
| "Mobile devices hardened per standards" | "Users must set passcode" | User requirement ≠ device config | NO_MATCH |

**Time/Trigger Distinctions:**
- "before use" = user-initiated (behavioral)
- "when inserted" / "automatically" = system behavior (technical)

---

### G-17: Program Completeness / Input ≠ Program

**Consensus: All three sources agree. Addresses IR-Overreach and Training FPs.**

**Block when:** Evidence describes one input or component (e.g., "users report incidents") but control requires a formal program/artifact (incident response plan, breach notification procedure, training program, detection procedures, etc.).

**Operational Test:** If the control contains words like `plan`, `program`, `procedure`, `runbook`, `training (delivered)`, `exercises`, `roles/responsibilities for responders`, then evidence must explicitly mandate that artifact/program—not merely user reporting or awareness language.

**Key Principle:** REPORTING INTO a program ≠ THE PROGRAM ITSELF

**Examples:**
| Control | Evidence | Gap | Decision |
|---------|----------|-----|----------|
| "Formal incident response plan" | "Users must report incidents" | Reporting ≠ plan | NO_MATCH |
| "IR personnel receive training" | "Users must report incidents" | User duty ≠ IR training | NO_MATCH |
| "Security awareness training provided" | Policy document exists | Policy ≠ training delivery | NO_MATCH |
| "Breach notification procedures" | "Report incidents to IT" | Reporting channel ≠ notification procedure | NO_MATCH |

**Generalizes Beyond IR:** This applies to any "program" control (vulnerability management program, access governance program, vendor management program).

---

### G-18: Certainty Mismatch (May vs Must)

**Consensus: Gemini and ChatGPT emphasize this. Claude's analysis identified the pattern.**

**Hard Rule:** If the evidence sentence contains `may`, `might`, `can`, `should`, `recommended`, `encouraged`, `where applicable`, `as appropriate`, it is **inadmissible for MAPPED or PARTIAL** (unless the same sentence also contains a binding verb that clearly makes the requirement mandatory—which is rare).

**Key Principle:** "Activity MAY be monitored" (legal notice) ≠ "Activity IS monitored" (implementation)

**Examples:**
| Control | Evidence | Gap | Decision |
|---------|----------|-----|----------|
| "User activity is monitored" | "Activity may be monitored" | Possibility ≠ implementation | NO_MATCH |
| "Access is logged" | "We may log access" | Permissive language | NO_MATCH |

---

### Enhanced G-2: Behavioral vs Technical Enforcement

**Consensus: All three sources recommend strengthening G-2.**

**Enhancement:** Add explicit "Who/What enforces" test:

1. If evidence is phrased as "Users/personnel must..." it is ADMINISTRATIVE evidence
2. It can only satisfy a TECHNICAL control if the same sentence also states system enforcement/configuration (e.g., "systems are configured to," "technology enforces," "access is technically restricted by...")
3. Time/trigger mismatch defaults to NO_MATCH

**Additional Anti-Pattern (from analysis):** User proxy requirements do NOT satisfy network infrastructure controls:
- Proxy requirement = USER behavioral rule
- Network boundary filtering/IPS/IDS = TECHNICAL system implementation

**Examples:**
| Control (Technical) | Evidence | Problem | Decision |
|---------------------|----------|---------|----------|
| "Network intrusion prevention implemented" | "Users must route traffic via proxy" | User rule ≠ IPS technology | NO_MATCH |
| "Outbound traffic filtered at boundary" | "Use company proxy" | Behavioral ≠ infrastructure | NO_MATCH |

---

## Additional Enforcement Improvements

### Quote Sufficiency Test (Strengthens Single-Sentence Rule)

**Source: ChatGPT (unique insight)**

**Before returning MAPPED/PARTIAL, apply this test:**

> "Assume the policy contained ONLY this sentence. Would the control still be satisfied without importing context from elsewhere?"

If NO → NO_MATCH (cite single-sentence rule)

**Why this helps:** Even with the single-sentence rule, models mentally combine context. This explicit test stops "clean desk + shredding + handling" → "privacy program controls" type errors.

---

### Phase 0: Document Classification (Simple)

**The Problem:** The LLM sees security content and gradually convinces itself an "Acceptable Use Policy" satisfies "Information Security Policy" controls.

**The Solution:** Classify the document type from the title/first page, then remember that classification.

#### Prompt Addition

```
DOCUMENT CLASSIFICATION (Do this first)

Look at the document title and first page. What type of document is this?
Examples: Acceptable Use Policy, Information Security Policy, Data Protection
Policy, Incident Response Plan, Access Control Policy, etc.

Remember this classification. When you encounter a control requiring
"a [X] policy/plan is established," check: does this document's type match [X]?
If not, it's NO_MATCH regardless of content.

An Acceptable Use Policy is not an Information Security Policy, even if it
contains security rules.
```

#### G-15 Reference

When evaluating artifact-type controls, the LLM should ask:
> "Does this document's classification match what the control requires?"

If the document is classified as "Acceptable Use Policy" and the control requires "Information Security Policy established" → NO_MATCH.

---

### Narrow IR-6 (Standard Reference)

**Source: ChatGPT (precision improvement)**

**Current risk:** IR-6 allows mapping when policies reference standards, but many policies say "align with ISO/NIST" without making specific requirements auditable.

**Safer rule:** Only apply IR-6 if the policy mandates compliance AND either:
- Includes the requirement text inline, OR
- The referenced standard is explicitly incorporated by reference as binding requirements

Otherwise treat as G-12 (reference-only evidence).

---

## Summary: New/Enhanced Guardrails

| ID | Name | Addresses |
|----|------|-----------|
| **G-15** | Artifact Identity & Primary Purpose | Document-IS-Policy fallacy |
| **G-16** | Presence vs Operational Characteristics | Encryption, antimalware, firewall, mobile hardening |
| **G-17** | Program Completeness / Input ≠ Program | IR-Overreach, training |
| **G-18** | Certainty Mismatch | "May" vs "Must" confusion |
| **G-2 (enhanced)** | Behavioral vs Technical Enforcement | Proxy→network, user rules→technical controls |

**Additional improvements:**
- Quote Sufficiency Test (explicit single-sentence enforcement)
- Phase 0: Document Context Extraction
- Narrowed IR-6 for precision

---

## False Negative: DCF-32

**Needs investigation.** Most likely causes:
1. Retrieval issue: Control not in any batch sent to LLM
2. Decision issue: LLM rejected due to overly strict interpretation

**Suggested fix (if synonym issue):** Expand Pass B synonym table in controlled way for true equivalences (e.g., "security incident" ↔ "information security event" if defined).

---

## Design Principles Applied

1. **Abstract over specific:** Instead of proxy-specific or encryption-specific rules, use mechanism-type rules that generalize
2. **Few rules, well-enforced:** 4-5 new guardrails rather than 8+ topic-specific ones
3. **Explicit operational tests:** Each guardrail has a concrete yes/no test
4. **Framework-agnostic:** These distinctions hold across NIST/ISO/CIS/SOC2/custom control libraries

---

## Implementation Priority

1. **Structural (Do First):** Phase 0 Document Classification — forcing function that enables G-15
2. **High Impact:** G-15 (Artifact Identity, gated on Phase 0) + G-17 (Input ≠ Program) — addresses 10 FPs
3. **High Impact:** G-16 (Presence vs Operational) — addresses 7 FPs
4. **Medium Impact:** Enhanced G-2 + G-18 — addresses 5 FPs
5. **Precision:** Quote Sufficiency Test + Narrowed IR-6 — prevents edge cases
