# Generalizable False Positive Patterns

> **Source**: Analysis of Stage 3 FPs across policy documents
> **Last Updated**: 2026-01-01
> **Validation Status**: Validated on AUP, needs validation on 2-3 additional document types

These patterns are **document-type agnostic** and should apply across all 37 policy documents in the ground truth set.

---

## Pattern 1: Policy Mandate ≠ Operational State (HIGH IMPACT)

**The Problem**: The LLM accepts policy language mandating behavior as evidence that the behavior is actually occurring. Policy documents describe what SHOULD happen, not what IS happening.

### Signal Words

| Policy Language | What It Proves | What It Does NOT Prove |
|-----------------|----------------|------------------------|
| "shall be encrypted" | Policy requires encryption | Data IS encrypted |
| "must be installed" | Policy requires installation | Software IS installed |
| "will be reviewed" | Policy requires reviews | Reviews ARE performed |
| "are required to complete" | Policy requires completion | Training IS completed |

### Control Language That Requires State

Controls containing these phrases typically require operational evidence, not policy mandates:
- "[Org] **performs**..." (requires evidence of performance)
- "[Org] **has deployed**..." (requires evidence of deployment)
- "...solution **is configured**..." (requires configuration evidence)
- "...controls **are installed**..." (requires implementation evidence)
- "[Org] **tracks and documents**..." (requires process evidence)

### The Rule

```
A policy statement mandating behavior (SHALL/MUST/WILL/ARE REQUIRED TO)
is NOT evidence that the behavior IS occurring.

For controls requiring operational/deployed state:
  - Policy mandate alone → NO_MATCH
  - Policy mandate + implementation evidence → MAPPED

Examples:
  ✗ "Anti-malware must be installed" does NOT satisfy "Anti-malware IS deployed"
  ✗ "Access shall be reviewed" does NOT satisfy "Management PERFORMS reviews"
  ✗ "Data will be encrypted" does NOT satisfy "Data IS encrypted"
  ✓ "Anti-malware is installed on all endpoints" DOES satisfy deployment controls
```

### Estimated Impact
~35-40% of FPs across document types

---

## Pattern 2: Artifact Reference ≠ Artifact Existence (MEDIUM IMPACT)

**The Problem**: The LLM accepts a document's reference to another artifact as evidence that the artifact exists and contains appropriate content.

### Examples

| Document States | What It Proves | What It Does NOT Prove |
|-----------------|----------------|------------------------|
| "Employees sign employment contracts" | Contracts are mentioned | Contract content includes security terms |
| "Training is provided during onboarding" | Training is mentioned | Training program is established |
| "Procedures are documented in the wiki" | Procedures are referenced | Procedures exist and are complete |
| "See the Key Management Policy" | Another policy is referenced | That policy exists and addresses control |

### The Rule

```
A reference TO an artifact is NOT evidence OF that artifact.

For controls requiring specific artifact types:
  - Reference to artifact → NO_MATCH
  - Artifact itself being evaluated → Evaluate content
  - Section within broader document → Usually NO_MATCH (G-15)

Examples:
  ✗ "Employees sign contracts with security terms" does NOT satisfy
    "Employment contracts include security responsibilities" (need the contract)
  ✗ "Training is provided" does NOT satisfy
    "Training programs are established" (need the training materials)
  ✗ A "Remote Access" section in an AUP does NOT satisfy
    "Telework Policy is defined" (need standalone policy or sufficient depth)
```

### Estimated Impact
~20-25% of FPs across document types

---

## Pattern 3: Evidence Scope ≠ Control Scope (MEDIUM IMPACT)

**The Problem**: The LLM accepts evidence from a narrower or different scope than what the control requires.

### Scope Dimensions

1. **System Scope**: General vs specific systems
   - "Remote access is encrypted" vs "Remote access to **production systems** is encrypted"
   - "Devices have firewalls" vs "**Portable devices connecting outside the network** have firewalls"

2. **Actor Scope**: Some actors vs all actors
   - "Users require MFA" vs "**All remote access (users, admins, vendors, maintenance)**"
   - "Employees complete training" vs "**Personnel including contractors**"

3. **Action Scope**: Related action vs specific action
   - "Secure sensitive materials" vs "**Encrypt** sensitive data on removable media"
   - "Protect output devices" vs "**Manage physical access control** for output devices"

### The Rule

```
Evidence scope must MATCH OR EXCEED control scope.

Scope narrower than control → NO_MATCH
Scope different domain than control → NO_MATCH
Scope matches or exceeds control → Continue evaluation

Examples:
  ✗ "Remote access uses VPN" does NOT satisfy "Production system access is encrypted"
    (general remote ≠ production-specific)
  ✗ "Users require MFA" does NOT satisfy "All remote access requires MFA"
    (users only ≠ users + admins + vendors + maintenance)
  ✗ "Lock away sensitive materials" does NOT satisfy "Media is physically secured"
    (user instruction ≠ organizational control)
```

### Estimated Impact
~15-20% of FPs across document types

---

## Pattern 4: Partial Match ≠ Full Match (MEDIUM IMPACT)

**The Problem**: The LLM accepts evidence that addresses some but not all components of a compound control requirement.

### Identifying Compound Controls

Controls with multiple requirements often use:
- Conjunctions: "A **and** B **and** C"
- Lists: "including: (a) X, (b) Y, (c) Z"
- Multiple qualifiers: "with specific configurations that are defined, active, and unalterable"

### Examples

| Control Requires | Evidence Provides | Gap |
|------------------|-------------------|-----|
| "explicit approval + acceptable uses + approved products list" | "acceptable uses" | Missing approval process, products list |
| "specific configs + active + unalterable" | "firewalls enabled" | Missing config details, unalterable requirement |
| "usage + configuration + connection requirements per type" | "encryption required" | Missing per-type breakdown |
| "restrict disable + documented approval + limited time" | "authorization required" | Missing documentation, time limit |

### The Rule

```
For compound controls with multiple requirements (A + B + C):
  ALL components must be explicitly addressed.

  Evidence for A only → NO_MATCH (missing B, C)
  Evidence for A + B → NO_MATCH (missing C)
  Evidence for A + B + C → MAPPED

Do NOT infer missing components. Each must be explicit.

Examples:
  ✗ "Acceptable use is defined" does NOT satisfy
    "AUP with explicit approval + acceptable uses + products list"
  ✗ "Firewalls are enabled" does NOT satisfy
    "Firewall with defined settings + active + unalterable by users"
  ✗ "Anti-malware will scan" does NOT satisfy
    "Anti-malware configured for periodic OR real-time scans + behavioral analysis"
```

### Estimated Impact
~20-25% of FPs across document types

---

## Summary: Generalizable Rules for Stage 3

### Rule G1: State vs Mandate
```
Policy mandates (SHALL/MUST/WILL) ≠ Operational state (IS/ARE/HAS)
```

### Rule G2: Reference vs Existence
```
Reference to artifact ≠ Artifact exists with required content
```

### Rule G3: Scope Match
```
Evidence scope must match or exceed control scope (system, actor, action)
```

### Rule G4: Complete Match
```
Compound controls require ALL components explicitly addressed
```

---

## Validation Checklist

To confirm these patterns are generalizable, validate on:

- [ ] Technical policy (e.g., Encryption Policy, Network Security Policy)
- [ ] Governance policy (e.g., Information Security Policy, Risk Management Policy)
- [ ] Procedural document (e.g., Incident Response Procedures, Change Management Procedures)

If patterns hold across these document types with similar FP distribution, they are confirmed generalizable.

---

## Non-Generalizable Patterns (Document-Specific)

The following pattern was identified but is **NOT generalizable**:

### User Policy vs Org Process (AUP-Specific)
This pattern ("user-facing policy cannot satisfy org-level process requirements") only applies to user-facing documents like Acceptable Use Policy. Governance documents like Information Security Policy ARE org-level and wouldn't have this issue.

For document-specific patterns, see individual analysis files:
- [acceptable_use_policy/fp_analysis_findings.md](acceptable_use_policy/fp_analysis_findings.md)
