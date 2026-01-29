# False Negative Analysis: Experiment 7

**Experiment**: `experiment_7` (prompt: `control_centric_false_negatives_take2`)
**Date**: 2026-01-01
**Total FNs**: 141 (down from 188 in Exp 6 = 25% reduction)
**Recall**: 72.82%

---

## Executive Summary

### Decision Distribution
| Decision | Count | % of FNs |
|----------|-------|----------|
| NO_MATCH | 123 | 87.2% |
| PARTIAL | 18 | 12.8% |

### Top Blocking Guardrails
| Guardrail | Count | % of FNs | Description |
|-----------|-------|----------|-------------|
| **G-10** | 47 | 33.3% | Missing mandatory qualifiers |
| **G-17** | 16 | 11.3% | Input/component vs program |
| (no guardrail) | 15 | 10.6% | Various reasons |
| **G-4** | 13 | 9.2% | Domain/topic overlap but mechanism differs |
| **G-16** | 13 | 9.2% | Presence vs configuration |
| **G-1** | 10 | 7.1% | Technical vs administrative mismatch |
| **G-11** | 9 | 6.4% | Activity vs artifact |
| **G-15** | 6 | 4.3% | Wrong artifact type |

---

## Universal Themes

### 1. G-10: Missing Mandatory Qualifiers (47 instances, 33%)

**The Problem**: The current prompt treats ALL qualifiers as equally blocking. But many qualifiers are *operational details* that don't negate the core mandate.

**Pattern Categories**:

#### A. Frequency Qualifiers (Most Common)
The control specifies a frequency, the policy mandates the activity but doesn't specify timing.

| Control Requires | Policy Says | Current Decision | Should Be? |
|-----------------|-------------|------------------|------------|
| "reviewed annually" | "shall be maintained" | NO_MATCH (G-10) | MAPPED* |
| "at least daily" | "discovery tool implemented" | NO_MATCH (G-10) | Debatable |
| "within one month" | "patches shall be installed" | NO_MATCH (G-10) | Debatable |
| "at least weekly" | "logs reviewed" | NO_MATCH (G-10) | Debatable |

*Already addressed by G-10/G-16 Qualifier Gap Rule, but LLM not applying it consistently.

#### B. Specific Technical Parameters
The control specifies a technical detail the policy doesn't mention.

| Control Requires | Policy Says | Current Decision |
|-----------------|-------------|------------------|
| "DHCP logging, IPAM tool, weekly review" | "asset inventory maintained" | NO_MATCH |
| "network jacks" | "network equipment access restricted" | NO_MATCH |
| "PowerShell module, script block logging" | "interactive application logging" | NO_MATCH |

#### C. Example vs Mandate Problem
The control's specific requirement appears only as an *example* in the policy.

| Control | Policy Says | Why Rejected |
|---------|-------------|--------------|
| "Phishing simulations conducted" | "training may include phishing simulations" | Listed as example ("e.g.", "such as") |
| "Password manager installed" | "may use approved password manager" | Permissive language |

**Impact**: 47 FNs (33% of total). This is the #1 cause of false negatives.

---

### 2. G-17: Input/Component vs Program (16 instances, 11%)

**The Problem**: The LLM correctly identifies that a policy component ≠ the full program. But sometimes the component IS sufficient evidence at the policy level.

**Examples**:
| Control | Policy Evidence | LLM Reasoning |
|---------|----------------|---------------|
| "Security team assigned for policies" | "ISM manages incident response" | "ISM is a component, not the full team" |
| "AI Feedback Management program" | "Communication lines defined" | "Communication is an input to feedback" |
| "Unauthorized software removed/documented" | "Inventory facilitates tracking" | "Facilitates" is utility, not mandate |

**Root Cause**: G-17 was designed to catch "report incidents" ≠ "incident response plan". But it's being over-applied to cases where the policy DOES mandate the core behavior.

**Impact**: 16 FNs (11% of total).

---

### 3. G-16: Presence vs Configuration (13 instances, 9%)

**The Problem**: Controls require both implementation AND specific configuration. Policies mandate implementation but not configuration details.

**Examples**:
| Control | What Policy Says | What Control Requires |
|---------|-----------------|----------------------|
| "Automated software inventory tool" | "Automated system for infrastructure assets" | Tool for *installed software* discovery |
| "Cloud storage lifecycle rules" | "Data removed after retention period" | *Automated* lifecycle configuration |
| "Centrally manage anti-malware" | "Deploy and auto-update antivirus" | *Central* management |
| "Deny wireless by default" | "Block unauthorized wireless" | *Default deny* configuration |

**Root Cause**: This is a legitimate gap—policies don't specify configuration details. But should a policy-level evaluation penalize for this?

**Impact**: 13 FNs (9% of total).

---

### 4. G-4: Domain/Topic Overlap but Mechanism Differs (13 instances, 9%)

**The Problem**: Policy addresses the same topic but uses a different mechanism than the control specifies.

**Examples**:
| Control | Policy Topic | Mechanism Mismatch |
|---------|-------------|-------------------|
| "Key Risk Indicators (KRIs)" | "Risk scoring methodology" | KRIs ≠ risk matrix |
| "Integrated ERM" | "Info sec risk management" | Not integrated with enterprise |
| "Software Composition Analysis" | "Vulnerability scanning" | SCA ≠ general vuln scanning |
| "E-commerce agreements" | "Vendor management" | E-commerce ≠ general vendor |

**Root Cause**: These are legitimate G-4 blocks—the mechanism genuinely differs. But are we being too specific? "Vulnerability scanning" could arguably cover SCA.

**Impact**: 13 FNs (9% of total).

---

### 5. G-1: Technical vs Administrative (10 instances, 7%)

**The Problem**: Control requires a technical mechanism, policy only provides administrative oversight.

**Examples**:
| Control | Policy Says | Why NO_MATCH |
|---------|-------------|--------------|
| "Leak detection system" | "Monitoring for water" | Monitoring (activity) ≠ system (technical) |
| "Threat intelligence mechanisms" | "Threat assessment process" | Process ≠ technical collection |
| "IDS/IPS in place" | "Log IDS/IPS failures" | Logging failures ≠ having the system |

**Root Cause**: These are mostly legitimate—the policy genuinely doesn't mandate the technical system. But some cases are borderline (e.g., "monitoring for water" could imply a detection system).

**Impact**: 10 FNs (7% of total).

---

### 6. PARTIAL Decisions (18 instances, 13%)

**Gap Type Distribution**:
| Gap Type | Count |
|----------|-------|
| scope_gap | 15 |
| contradiction | 2 |
| ownership_gap | 1 |

**The Problem**: The LLM correctly identifies binding evidence but downgrades to PARTIAL due to:
- Missing annual frequency (onboarding only)
- Limited scope (cloud providers only, not all vendors)
- Missing specific qualifier (accessibility for disabled)

**Examples**:
| Control | Evidence | Gap |
|---------|----------|-----|
| "Annual policy acknowledgment" | "Sign during onboarding" | Missing "annually thereafter" |
| "Exit strategies for suppliers" | "Exit strategies for cloud providers" | Limited to cloud, not all suppliers |
| "Notices accessible to disabled" | "Clear and conspicuous notices" | Missing disability accessibility |

**Should These Be MAPPED?**:
- If we're only evaluating whether the *core mandate* exists → MAPPED
- If exact scope match is required → PARTIAL is correct

**Impact**: 18 FNs (13% of total). Converting these to MAPPED would boost recall by ~3pp.

---

## Rare Rules & Edge Cases

### 1. Soft Blockers Applied Inconsistently
Several NO_MATCH decisions cite non-binding language ("should", "where possible") as the blocker:
- DCF-156: "human approval by authorized owner (Page 4) uses non-binding language ('should')"
- DCF-7: "primary technical requirement on page 4 uses non-binding 'should' language"

**Issue**: The prompt already has a soft blocker exception—check if core objective has binding language elsewhere. This isn't being applied consistently.

### 2. Placeholder/Template Content (2 cases)
- DCF-660: "Risk Appetite section consists entirely of template placeholders ('<VALUE>')"
- DCF-807: "Risk Tolerance section consists entirely of template placeholders"

**These are correct rejections**—placeholders aren't evidence.

### 3. Future Tense (1 case)
- DCF-150: "Evidence uses future-tense language ('will implement') which acts as an aspirational promise"

**Correct rejection**—future tense ≠ current implementation.

### 4. Example Text in Policy (4 cases)
Controls where the specific requirement appears only as an example:
- DCF-681: Phishing simulations listed as example ("e.g.", "such as")
- This is a legitimate rejection per the prompt rules.

### 5. OR vs AND Misinterpretation (1 case)
- DCF-737: "Control requires keys stored in SCD *as* key shares (AND), policy lists these as disjunctive options (OR)"

**Edge case**: Compound requirements where policy uses OR but control uses AND.

### 6. G-11 Activity vs Artifact (9 cases)
Controls requiring a *document/list* but policy only mandates the *activity*:
- "List of in-scope facilities" vs "Policy applies to facilities"
- "Job descriptions documented" vs "Briefing personnel on roles"
- "List of new hires" vs "Retention of training records"

**These are often legitimate**—the artifact isn't explicitly mandated.

---

## Recommendations

### High-Impact Changes (Address 50%+ of FNs)

#### 1. Relax G-10 for Secondary Qualifiers
**Current**: ANY missing qualifier → NO_MATCH
**Proposed**: Distinguish between:
- **Primary qualifiers** (domain, scope, audience): Must match → NO_MATCH if absent
- **Secondary qualifiers** (frequency, specific parameters): Core mandate sufficient → MAPPED

**Targeting**: ~30 of 47 G-10 FNs (frequency-related)

#### 2. Tighten G-10/G-16 Qualifier Gap Rule Application
The rule already exists in the prompt:
> "If control has two components: (1) ARTIFACT/MECHANISM + (2) OPERATIONAL QUALIFIER, and Component 1 is satisfied → Return MAPPED"

**Issue**: LLM not applying this consistently.
**Fix**: Add explicit examples showing when to apply this rule.

#### 3. Convert Scope-Gap PARTIALs to MAPPED
**Rationale**: If the mandate exists for a subset of scope, the policy-to-control mapping is valid—the scope limitation is an implementation detail.

**Targeting**: 15 of 18 PARTIAL decisions

### Medium-Impact Changes

#### 4. Refine G-17 to Distinguish "Component" from "Sufficient Evidence"
**Current**: Any partial program element → NO_MATCH
**Proposed**: If the component IS the policy-level requirement (e.g., "roles assigned"), allow mapping. Only block when policy provides mere input (e.g., "report incidents" for IR plan).

**Targeting**: ~8 of 16 G-17 FNs

#### 5. Soften G-4 for Closely Related Mechanisms
Some G-4 rejections are overly strict:
- "Network equipment" could reasonably include network jacks
- "Vulnerability scanning" could reasonably include SCA

**Proposed**: Add IR for mechanism subsumption—broader mechanism includes specific one.

**Targeting**: ~5 of 13 G-4 FNs

### Low-Impact / Edge Cases

#### 6. Clarify Soft Blocker Application
Add explicit instruction: When "should" is found, search for binding language in same section before rejecting.

#### 7. Handle OR vs AND Compound Requirements
Add guidance for when control uses AND but policy uses OR—this is typically NO_MATCH unless policy satisfies BOTH branches.

---

## Impact Projection

| Change | Est. FNs Recovered | New Recall |
|--------|-------------------|------------|
| Relax G-10 for frequencies | ~30 | 77.9% |
| Convert scope-gap PARTIAL→MAPPED | ~15 | 80.5% |
| Refine G-17 | ~8 | 81.9% |
| Soften G-4 | ~5 | 82.7% |
| **Total** | **~58** | **82.7%** |

**Caveat**: These changes will also increase false positives. Expect precision to drop by 5-10pp. The Stage 3 verification layer becomes more critical.

---

## Files for Reference

- **False Negatives Data**: `false_negatives_take3/false_negatives.json`
- **Current Prompt**: `prompts/control_centric_false_negatives_take2/system`
- **Experiment Results**: `results/experiment_7/results.json`
