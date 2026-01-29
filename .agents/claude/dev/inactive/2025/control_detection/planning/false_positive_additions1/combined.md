# Combined False Positive Analysis & Recommendations

This document merges suggestions from Opus, Gemini, and ChatGPT analyses of the false positive problem.

---

## 1. Diagnosis (Consensus)

All three analyses agree on the core problem:

| Source | Key Insight |
|--------|-------------|
| **Opus** | "The IRs provide escape hatches that let almost any mapping through" |
| **Gemini** | "The IRs function as confirmation bias generators" |
| **ChatGPT** | "The confirmation stage is behaving like a permissive entailment classifier, and the IRs are functioning as yes-generators" |

### Root Cause Breakdown (Opus)

| Rule | FP Count | Problem |
|------|----------|---------|
| Direct match | 30 | Claims "direct match" for tangentially related topics |
| IR-3 (Semantic Equivalence) | 24 | "Different words, same outcome" - far too permissive |
| IR-4 (Governance→Procedure) | 16 | Being used to accept any governance language |
| IR-1 (Hierarchical Scope) | 14 | Over-generalizing scope containment |
| IR-2 (Parameter Abstraction) | 13 | Stripping away important qualifiers |
| IR-6 (Inferred Existence) | 10 | Inferring artifacts from mere references |

### Why Guardrails Aren't Firing (ChatGPT)

1. **Missing hard gating condition before IRs** - Model can grab any vaguely related sentence, declare it "direct" or run IR-3, then retrofit qualifiers/scope via IR-1/IR-2/IR-6
2. **"Direct match" is unconstrained** - Should mean: binding language + control-specific anchor + right domain/mechanism. Currently means "mentions topic somewhere"
3. **IR-3/IR-4/IR-6 are too powerful** - These collapse distinctions: IR-3 turns topic similarity into "equivalence", IR-4 turns governance language into "implementation", IR-6 turns references into "existence"

---

## 2. Philosophy Shift (Gemini)

**From:** "Search for a reason to say YES"
**To:** "Search for a reason to say NO"

### New Role Definition
> You are a **Strict External Auditor**. Your job is to audit a policy document against security controls. You are **skeptical**. Your default position is **NO_MATCH**. You only grant a **MAPPED** status if the evidence is irrefutable.

### The Golden Rule of Auditing
> It is better to return **NO_MATCH** (a finding) than to falsely credit a control (a security risk). **Do not "read between the lines."** If the policy doesn't explicitly mandate it, it doesn't exist.

---

## 3. Anti-Pattern Blocklist (Gemini) - Immediate Rejection

### Trap 1: The "Reference is not Compliance" Fallacy
- **Bad Logic:** The policy says "See the Access Control Standard." → Maps to specific access control requirements.
- **Rule:** A pointer to another document is **NOT** evidence. You can only map what is written in the text provided.
- **Verdict:** NO_MATCH

### Trap 2: The "Topic Association" Fallacy (Over-active Semantic Matching)
- **Bad Logic:** Control requires "Clean Desk Policy." Evidence discusses "Physical Security of Offices."
- **Bad Logic:** Control requires "Network Segmentation." Evidence discusses "Environment Isolation" (which could mean dev/prod, not network subnets).
- **Rule:** Topic overlap is not enough. The **specific mechanism** must match.
- **Verdict:** NO_MATCH

### Trap 3: The "General covering the Specific" Fallacy
- **Bad Logic:** Control requires "MFA for Remote Access." Evidence says "MFA shall be used for critical systems."
- **Rule:** Unless "Remote Access" is explicitly defined as a "critical system" in the text, you cannot assume coverage.
- **Verdict:** NO_MATCH (or PARTIAL at best)

### Trap 4: The "Admin covering the Technical" Fallacy
- **Bad Logic:** Control requires "Automated blocking of USB drives." Evidence says "The Security Team reviews device usage logs."
- **Rule:** Administrative review ≠ Technical enforcement.
- **Verdict:** NO_MATCH

---

## 4. Minimum Evidence Gate (ChatGPT) - Must Pass Before Any IR

Before any IR is allowed, require the model to extract an **Evidence Triple**:

1. **Binding verb** (must/shall/prohibited/required)
2. **Control anchor** (a noun phrase unique-ish to the control objective, not generic "security")
3. **Mechanism match** (technical vs administrative vs physical vs training vs monitoring)

If any of the three are missing → **NO_MATCH** (or at most PARTIAL if the control is explicitly governance/process and you have 1+2).

> "You may only return MAPPED if you can extract a single sentence that contains BOTH (1) binding language AND (2) a control-specific anchor for the control's objective/qualifier. If you need interpretive rules to invent either, return NO_MATCH."

---

## 5. Strict Mapping Criteria (Gemini) - Three Bars

### Bar 1: The "Mandate" Check
Does the text contain **binding** language?
- *Acceptable:* "Must," "Shall," "Required," "Will ensure," "Strictly prohibited."
- *Reject:* "Should," "May," "Recommended," "Best Practice," "Ideally," "Strives to."

### Bar 2: The "Specificity" Check
Does the evidence address the **distinct** requirement of the control?
- *Control:* "MFA for **Privileged** Accounts."
- *Evidence:* "MFA is required for **Remote** Access."
- *Result:* **NO_MATCH**. The scopes (Privileged vs Remote) are different intersections. One does not automatically cover the other.

### Bar 3: The "Restricted" Interpretive Rules
See Section 6 below.

---

## 6. Restricted Interpretive Rules (Consensus with Variations)

### Agreement: Remove or Heavily Restrict IRs

| Source | Recommendation |
|--------|----------------|
| **Opus** | "Remove or drastically restrict IRs - They're creating more FPs than they rescue FNs" |
| **Gemini** | Restrict to only 3 specific rules with tight definitions |
| **ChatGPT** | "Delete IR-3, IR-4, IR-6" - keep only narrow IR-1/IR-2/IR-8 with hard gates |

### Allowed Bridges (ChatGPT's Type-Specific Version)

#### Bridge 1: Scope Containment (old IR-1)
Only allowed if:
- Policy scope is explicitly broad ("all systems / all employees"), AND
- Control target is a clear subset, AND
- No explicit scoping restriction exists ("production only", "remote access only")

*Valid:* Control="Laptops", Policy="All Endpoints"
*Invalid:* Control="All Systems", Policy="Production Systems"

#### Bridge 2: Parameter Abstraction (old IR-2)
Only allowed for:
- Algorithm strength, cipher suite versions, password length, etc.

**Explicitly NOT allowed for:**
- FIPS, authenticated/credentialed, tamper-evidence, immutable logs, specific fields, third-party scope, etc.

*Valid:* Control="AES-256", Policy="Encryption required"
*Invalid:* Control="IPS", Policy="Firewall" (Different technologies)

#### Bridge 3: Binding Inheritance (old IR-8)
Only allowed if:
- Header is binding, AND
- The list item itself does not weaken it (no "should/may")

### Gemini's Restricted Version

- **Allowed IR-1 (Subset/Superset):** Only if the Policy scope is mathematically broader
- **Allowed IR-2 (Tech → Abstract):** Only if control asks for specific parameter, policy mandates technology
- **Allowed IR-3 (Strict Synonym):** Synonyms must be industry-standard equivalents
  - *Valid:* "Least Privilege" ≅ "Need-to-know"
  - *Invalid:* "Lock Workstation" ≠ "Console Timeout"

### Rules to DELETE (ChatGPT)
- **IR-3** (Semantic Equivalence) - turns topic similarity into "equivalence"
- **IR-4** (Governance→Procedure) - turns governance language into "implementation"
- **IR-6** (Inferred Existence) - turns references into "existence"

---

## 7. Kill Medium Confidence MAPPED (Consensus)

| Source | Recommendation |
|--------|----------------|
| **Opus** | "Remove 'medium confidence' for MAPPED - Only allow HIGH confidence mappings" |
| **Gemini** | "Confidence is BINARY: If you found a MAPPED result, you are High Confidence. If you have doubts, you are NO_MATCH. There is no 'Medium'." |
| **ChatGPT** | "MAPPED only if confidence = high. PARTIAL can be medium. NO_MATCH for everything else." |

---

## 8. Anchor Token Requirements (ChatGPT - Unique)

This fixes the "one MFA sentence maps to every MFA control" problem.

For each control, derive 2-4 anchor tokens/phrases that must appear in the evidence sentence or immediately adjacent context:

| Control | Required Anchors |
|---------|------------------|
| MFA for remote access | "remote"/"VPN"/"offsite"/"external" or equivalent |
| MFA for privileged/admin | "admin"/"privileged"/"root" or equivalent |
| MFA for all users | "all users"/"all accounts" etc. |

**Rule:** If the control has a qualifier, require an anchor for that qualifier.

---

## 9. Batch-Level Sanity Check (Opus + ChatGPT)

### Opus Version
> "Add a batch-level sanity check - If >30% of a batch is MAPPED, something is wrong"

### ChatGPT Version (More Nuanced)
Implement as:
- **Soft fail:** Downgrade all MAPPED to PARTIAL unless they pass an extra confirmation step
- OR trigger a second-pass "batch consistency check" prompt

**Rationale:** Some docs (e.g., an all-encompassing InfoSec Policy) really can map to a lot. But an AUP mapping to ~80 is almost certainly wrong.

---

## 10. Document-Type Priors (Opus + ChatGPT)

| Source | Recommendation |
|--------|----------------|
| **Opus** | "Consider document-type priors - An AUP realistically maps to 5-15 controls, not 80+" |
| **ChatGPT** | "Make it explicit in prompt: 'AUPs generally map to a small number of controls; treat mass mapping as suspicious.'" |

---

## 11. Fix Candidate Generation (ChatGPT - Unique)

> "This is under-discussed but it matters"

**Problem:** If embeddings retrieve 200 candidates, and you ask the LLM 200 times "does this match?", the model will say yes too often.

**Solutions:**
1. Use embeddings to retrieve, then **lexical pre-filter by required anchors/qualifiers** before LLM
2. OR ask the LLM to **select top-N controls that are most strongly supported** before doing per-control confirmation

> "Your architecture is currently incentivizing over-confirmation."

---

## 12. Require Evidence Sentence Constraints (Gemini + ChatGPT)

### Gemini
> "Evidence_quote: Exact sentence from text (max 1 sentence). Empty if NO_MATCH."

### ChatGPT
> "MAPPED only if you can extract a **single sentence** that contains BOTH binding language AND control-specific anchor"

**Implication:** If you need to combine three different sentences from different pages, return NO_MATCH.

---

## 13. Reasoning Must Cite Failure Mode (Gemini)

For NO_MATCH decisions, reasoning MUST cite the specific "Trap" or "Bar" that failed:
- "No Match. Trap 2: Evidence discusses physical security, control requires logical security."
- "No Match. Bar 2: Policy covers 'Remote Access', control requires 'Privileged Access'. Scopes do not align."
- "No Match. Trap 1: Evidence refers to an external standard but does not list requirements."

---

## 14. Fastest Precision Win (ChatGPT)

Do these three changes first:

1. **MAPPED requires:** binding verb + anchor + qualifier present (MEG)
2. **No medium/low MAPPED**
3. **Delete IR-3, IR-4, IR-6**

> "That combo usually drops FP volume dramatically in these 'confirm a candidate' pipelines."

---

## 15. Caution on "Exact Terminology" (ChatGPT)

> "I'd be careful with 'require exact terminology' as the main fix. That will absolutely raise precision, but it'll also nuke portability/generalization and you'll reintroduce FNs that your FN analysis already exposed (synonyms, abstract outcomes, binding headers, etc.)."

**Better approach:** "Make 'YES' expensive, not 'YES' literal."

Instead of exact phrases, require **control anchors** - noun phrases specific to the control objective.

---

## Summary: Prioritized Action Items

### High Priority (All Three Agree)
1. Kill medium confidence MAPPED
2. Remove/heavily restrict IR-3, IR-4, IR-6
3. Add hard gating before any IR (Minimum Evidence Gate)

### Medium Priority (Two Sources)
4. Add batch-level sanity check
5. Add document-type priors
6. Require single-sentence evidence

### Worth Considering (One Source, High Value)
7. Anchor token requirements per control family (ChatGPT)
8. Fix candidate generation pipeline (ChatGPT)
9. Explicit anti-pattern blocklist with trap names (Gemini)
10. Reasoning must cite specific failure mode (Gemini)
