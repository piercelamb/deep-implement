# Edge Cases & Rare Rules: Experiment 7 False Negatives

## Rare Guardrail Applications (≤3 instances each)

### G-9: Event-Driven vs Periodic (2 instances)
Control requires event-driven action, evidence is periodic review.

| Control | Policy | Issue |
|---------|--------|-------|
| DCF-911: Risk assessment after major change | Annual risk reviews | Missing event trigger |
| DCF-76: Post-implementation review for emergency changes | Expedited process described | No post-implementation review mandate |

**Prompt Status**: Correctly handled. These are legitimate FNs.

---

### G-8: Lifecycle Phase Mismatch (2 instances)
Control requires specific lifecycle phase, evidence addresses different phase.

| Control | Policy | Issue |
|---------|--------|-------|
| DCF-105: NDA signed prior to hire | Acknowledgment when "start" | "prior to" ≠ "when start" |
| DCF-381: Media physically secured (at rest) | Media secure during destruction/transport | At rest ≠ lifecycle phases |

**Prompt Status**: Correctly handled. These are legitimate FNs.

---

### G-3: Prevention vs Detection (2 instances)
Control requires prevention, evidence only describes detection.

| Control | Policy | Issue |
|---------|--------|-------|
| DCF-87: Threat detection system | Logging from security tools | Logging ≠ detection system |
| (Overlaps with G-1) | | |

**Prompt Status**: Correctly handled.

---

### G-12: External Reference Only (2 instances)
Evidence is reference to external standard without stated requirement.

| Control | Policy | Issue |
|---------|--------|-------|
| DCF-76: Emergency change review | "Refer to change control standard" | Reference ≠ requirement |
| DCF-156: Change releases approved | "Per change control standard" | Reference ≠ requirement |

**Prompt Status**: Correctly handled.

---

### G-5: Subset Scope (3 instances)
Evidence limited to subset, control requires broad coverage.

| Control | Policy | Issue |
|---------|--------|-------|
| DCF-52: Hard-disk encryption on all devices | Production systems only | Missing end-user devices |
| DCF-967: Application control on workstations | Operational systems only | "workstations" ≠ "operational systems" |
| (Similar pattern) | | |

**Prompt Status**: Correctly handled.

---

### G-2: User Rule vs System Behavior (3 instances)
Control requires system enforcement, evidence is user behavioral rule.

| Control | Policy | Issue |
|---------|--------|-------|
| DCF-49: Password manager installed | "Users may use password manager" | May use ≠ installed |
| DCF-574: MDM installed | "IT manager performs manual wipe" | Manual ≠ automated MDM |
| DCF-7: Separate environments enforced | Personnel separation (admin) | Admin ≠ technical enforcement |

**Prompt Status**: Correctly handled.

---

## Interesting Edge Cases

### 1. OR vs AND Compound Requirements
**DCF-737**: Protected Storage of Secret Keys
- Control: Keys stored in SCD *as* key shares (AND)
- Policy: Lists SCD and key shares as separate options (OR)
- Decision: NO_MATCH (correct)

**Takeaway**: Disjunctive policy ≠ conjunctive control.

---

### 2. Placeholder/Template Content
**DCF-660, DCF-807**: Risk Appetite and Tolerance
- Policy: Contains `<VALUE>` placeholders
- Decision: NO_MATCH (correct)

**Takeaway**: Placeholder text is automatically inadmissible.

---

### 3. Future Tense Promises
**DCF-150**: DLP Mechanisms
- Policy: "will implement" data leakage prevention
- Decision: NO_MATCH (correct)

**Takeaway**: Future tense = aspirational, not binding.

---

### 4. Example Text as Evidence
**DCF-681**: Phishing Simulations
- Policy: "training may include phishing simulations" (example)
- Decision: NO_MATCH (correct)

**Takeaway**: Examples ("e.g.", "such as") ≠ mandates.

---

### 5. Input vs Program (G-17 subtleties)

**Correctly rejected**:
- DCF-134: "Provide breach reporting instructions" → Policy mandates contract terms (input to instructions)
- DCF-868: "C-SCRM program with plan and milestones" → Policy lacks milestones

**Potentially over-rejected**:
- DCF-34: "Security team assigned" → Policy assigns ISM for incident response
  - Is ISM evidence of a security team? Debatable.

---

### 6. Artifact Type Mismatch (G-15)

| Control Requires | Document Type | Decision |
|-----------------|---------------|----------|
| "Information Security Policy" | Acceptable Use Policy | NO_MATCH |
| "Information Security Policy" | Code of Conduct | NO_MATCH |
| "Information Security Policy" | Breach Notification Policy | NO_MATCH |
| "Privacy reports" | Risk Assessment Report | NO_MATCH |

**Takeaway**: Document type matters. A section about X in document Y ≠ "X policy established".

---

### 7. Monitoring vs Implementation

**DCF-91**: IDS/IPS in place
- Policy: "Log IDS/IPS failures"
- Decision: NO_MATCH (G-1)

**Reasoning**: Logging failures of a system ≠ mandating the system exists.

---

### 8. Specific Technical Tool Requirements

Controls requiring specific tools that policies don't name:

| Control | Specific Requirement | Policy Provides |
|---------|---------------------|-----------------|
| DCF-886 | DHCP logging, IPAM tool | Asset inventory |
| DCF-784 | SCA tools | Vulnerability scanning |
| DCF-817 | Cloud security posture management | Vulnerability scanning |
| DCF-903 | Centrally managed anti-malware | Deployed anti-malware |

**Takeaway**: Tool-specific controls often fail because policies mandate outcomes, not tools.

---

## Patterns NOT Causing FNs (Working Well)

1. **Binding header inheritance (IR-5)**: Lists under "shall" headers are being mapped
2. **Hierarchical scope (IR-1)**: "All systems" correctly covers "production systems"
3. **Parameter abstraction (IR-2)**: Generic encryption mandates satisfying specific algorithm controls
4. **Positive→Prohibition (IR-4)**: "Must use approved software" → prohibition of unapproved

---

## Summary: What's Working vs What Needs Work

### Working Well
- G-15 artifact type discrimination
- G-8 lifecycle phase matching
- G-9 event-driven vs periodic
- G-3 prevention vs detection
- IR application for clear cases

### Over-Rejecting (Needs Loosening)
- G-10 for frequency qualifiers (33% of FNs)
- G-17 for program components
- G-16 for configuration details
- PARTIAL scope_gap decisions

### Correctly Rejecting (No Change Needed)
- Future tense promises
- Placeholder content
- Example text
- OR vs AND mismatches
- Admin for technical controls
