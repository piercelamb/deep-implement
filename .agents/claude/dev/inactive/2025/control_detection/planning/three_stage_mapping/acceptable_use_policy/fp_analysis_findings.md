# False Positive Analysis: Acceptable Use Policy

> **Date**: 2026-01-01
> **Stage 3 Run**: `stage3_20260101_205445` (Pro model, strict prompt)
> **Document**: Acceptable Use Policy

## Summary

| Metric | Value |
|--------|-------|
| Stage 2 MAPPED | 61 controls |
| Stage 3 MAPPED | 29 controls |
| True Positives | 6 |
| False Positives | 23 |
| **Precision** | **20.7%** |
| Recall | 85.7% (6/7 ground truth) |

### Ground Truth Controls (7)
DCF-37, DCF-50, DCF-106, DCF-558, DCF-763, DCF-780, (+ 1 missed)

### True Positives (6)
DCF-37, DCF-50, DCF-106, DCF-558, DCF-763, DCF-780

### False Positives (23)
DCF-11, DCF-149, DCF-173, DCF-174, DCF-180, DCF-226, DCF-267, DCF-291, DCF-294, DCF-296, DCF-334, DCF-355, DCF-36, DCF-381, DCF-482, DCF-580, DCF-622, DCF-627, DCF-655, DCF-688, DCF-730, DCF-822, DCF-92

---

## Identified FP Patterns

### Pattern 1: State vs Mandate (9 FPs - 39%)

**Problem**: Control requires something IS IN PLACE (operational state), but the AUP only says it SHOULD BE done (policy mandate). An AUP cannot prove implementation.

| Control | Control Requires | Evidence Accepted |
|---------|-----------------|-------------------|
| DCF-11 | Management PERFORMS reviews | "Privileges must be reevaluated" |
| DCF-149 | Org ENCRYPTS removable media | "Treat devices as sensitive" |
| DCF-226 | Firewall IS INSTALLED with config | "Firewalls enabled" |
| DCF-267 | Data IS encrypted wherever stored | "Secure mass storage" |
| DCF-291 | Anti-malware IS DEPLOYED | "Must be installed" |
| DCF-294 | Anti-malware IS CONFIGURED | "Will scan computers" |
| DCF-355 | MFA IS REQUIRED for all access | "Mentions MFA" |
| DCF-655 | PROCEDURE exists for protection | "Prohibits user tampering" |
| DCF-730 | Controls ARE INSTALLED | "Firewalls enabled" |

**Root Cause**: The LLM accepts policy mandates as evidence of operational state. "Must be installed" ≠ "IS installed".

**Targetable**: YES - Add explicit rule that policy mandates ≠ operational state

---

### Pattern 2: User Policy vs Org Process (4 FPs - 17%)

**Problem**: The AUP tells users what to do, but the control requires an organizational process that the AUP cannot prove exists.

| Control | Control Requires | Evidence Accepted |
|---------|-----------------|-------------------|
| DCF-11 | Org performs access reviews | "User privileges will be reviewed" |
| DCF-334 | Org controls ID addition/deletion | "Inactive IDs revoked" |
| DCF-580 | Process for disabling risky accounts | "30-day inactivity revocation" |
| DCF-688 | Org tracks and documents asset return | "Offboarding includes duties" |

**Root Cause**: The LLM infers organizational process from user-facing statements. "Users will have privileges reviewed" doesn't prove a review process exists.

**Targetable**: YES - Add explicit rule about scope (user vs org perspective)

---

### Pattern 3: Artifact Type Mismatch (5 FPs - 22%)

**Problem**: The control requires a specific artifact type that an AUP is not.

| Control | Control Requires | Evidence Accepted |
|---------|-----------------|-------------------|
| DCF-36 | TRAINING PROGRAMS established | AUP mentions training |
| DCF-173 | Employment CONTRACTS/agreements | AUP references them |
| DCF-174 | TELEWORK POLICY defined | AUP has telework section |
| DCF-180 | Policies AND PROCEDURES | AUP only has policy statements |
| DCF-627 | Social media RULES defined | AUP mentions restrictions |

**Root Cause**: The LLM accepts a mention of something as evidence of its existence. "Employees sign contracts" ≠ having the contract document.

**Targetable**: PARTIALLY - G-15 (artifact type) exists but isn't applied strictly

---

### Pattern 4: Scope/Domain Mismatch (3 FPs - 13%)

**Problem**: Evidence is general but control requires specific scope, or different domain.

| Control | Control Requires | Evidence Accepted |
|---------|-----------------|-------------------|
| DCF-92 | PRODUCTION systems encryption | General remote access encryption |
| DCF-381 | Physical security of media | User instruction to lock items |
| DCF-622 | Org MANAGES access control | PIN code user instruction |

**Root Cause**: The LLM accepts evidence from a different scope/domain. "Use VPN for remote access" doesn't specifically address production systems.

**Targetable**: YES - Add explicit scope matching requirement

---

### Pattern 5: Partial Requirements (5 FPs - 22%)

**Problem**: Control has multiple specific requirements; evidence addresses only some.

| Control | Control Requires | Evidence Accepted |
|---------|-----------------|-------------------|
| DCF-226 | Specific configs + active + unalterable | Just "firewalls enabled" |
| DCF-294 | Periodic OR real-time + behavioral analysis | Just "will scan" |
| DCF-296 | Restrict disable + documented approval + limited time | Authorization only |
| DCF-482 | Explicit approval + acceptable uses + products list | Just acceptable use |
| DCF-822 | Usage + config + connection requirements per type | Generic encryption |

**Root Cause**: The LLM accepts partial satisfaction of compound requirements.

**Targetable**: YES - Add explicit rule requiring ALL components of compound controls

---

## Why True Positives Work

The 6 TPs share these characteristics:

1. **ARTIFACT match**: Document type matches control requirement (DCF-37: AUP → AUP)
2. **Direct mandate**: Control requires policy mandate, AUP has that mandate
3. **Scope alignment**: User-facing policy satisfies user-facing requirement
4. **Complete coverage**: Evidence addresses all parts of the control

| TP Control | Why It Works |
|------------|--------------|
| DCF-37 | "Has documented AUP" → Document IS an AUP |
| DCF-50 | "Anti-malware on devices" → AUP mandates installation (policy-level OK) |
| DCF-106 | "Clean desk policies defined" → AUP defines them |
| DCF-558 | "Identified allowed software + mechanism" → AUP has both |
| DCF-763 | "IP protection requirements" → AUP has licensing requirement |
| DCF-780 | "Web filtering mechanisms" → AUP mandates blocklisting |

**Key Insight**: TPs work because the control requirement is WITHIN the natural scope of what an AUP can legitimately address. FPs happen when the control requires something BEYOND what an AUP can prove.

---

## Recommendations

### Option A: Targeted Prompt Rules

Add these rules to Stage 3 verification prompt:

1. **STATE VS MANDATE RULE** (High Impact - addresses 39% of FPs)
   ```
   A policy statement mandating behavior (SHALL/MUST/WILL) is NOT evidence
   that the behavior IS occurring. For technical controls requiring deployed
   state, policy mandates alone are insufficient.
   ```

2. **SCOPE BOUNDARY RULE** (Medium Impact - addresses 30% of FPs)
   ```
   Evidence from user-facing policies cannot satisfy controls requiring
   organizational processes, management activities, or system-level state.
   AUP scope = user behavior, not org operations.
   ```

3. **COMPLETE REQUIREMENTS RULE** (Medium Impact - addresses 22% of FPs)
   ```
   For compound controls with multiple requirements (A + B + C), ALL
   components must be explicitly addressed. Partial satisfaction = NO_MATCH.
   ```

### Option B: Document-Type Anchoring (Recommended)

Rather than adding more rules, pre-filter controls by document type eligibility:

**Phase 0**: Classify document → "Acceptable Use Policy"

**Phase 1**: For each control, check: "Can an AUP legitimately address this?"

| Control Type | AUP Eligible? |
|--------------|---------------|
| "Has AUP" | YES (artifact match) |
| "Anti-malware IS DEPLOYED" | NO (requires operational evidence) |
| "Management PERFORMS reviews" | NO (requires process evidence) |
| "Clean desk policies defined" | YES (policy definition) |
| "Training programs established" | NO (requires training artifact) |

**Phase 2**: Only evaluate controls that pass the eligibility filter

**Expected Impact**: Would filter out ~70% of FPs before the LLM evaluates them.

### Option C: Accept Current Performance

If 20% precision is acceptable for the use case (e.g., generating candidates for human review), focus on:
- Increasing recall (catching more TPs)
- Reducing latency
- Scaling to more documents

---

## Next Steps

1. **Validate patterns on other documents**: Run same analysis on Encryption Policy, Access Control Policy to see if patterns hold
2. **Build document-type eligibility mapping**: Create matrix of which controls each policy type can legitimately address
3. **Test simplified Stage 3 prompt**: Try asking just "Is this control within scope for an AUP?" rather than full verification
4. **Consider hybrid approach**: Use embedding scores + document-type filtering as pre-filter, LLM only for borderline cases

---

## Appendix: Detailed FP Data

### DCF-11 (Periodic Access Reviews)
- **Control**: Management performs user access reviews periodically to validate user accounts and privileges remain appropriate
- **Evidence**: "The privileges granted to users must be reevaluated by management annually"
- **Why FP**: Policy mandate ≠ management actually performing reviews; also requires validation of physical access

### DCF-149 (Removable Media Device Encryption)
- **Control**: Org encrypts removable media devices containing sensitive data
- **Evidence**: "Treat mass storage devices such as external hard drives or USB drives as sensitive"
- **Why FP**: Instruction to "treat as sensitive" ≠ encryption is implemented

### DCF-173 (Employment Terms & Conditions)
- **Control**: Personnel responsibilities communicated via employment contracts
- **Evidence**: "Employees must agree and sign terms and conditions of their employment contract"
- **Why FP**: Mentioning contracts exist ≠ having the contract artifacts with security terms

### DCF-174 (Telework and Endpoint Devices)
- **Control**: Defined policy for remote work and device use
- **Evidence**: "Secure remote access must be strictly controlled with encryption"
- **Why FP**: Generic remote access statement ≠ comprehensive telework policy

### DCF-180 (Secure Information Transfer)
- **Control**: Defined policies AND procedures for secure transfer
- **Evidence**: "All email messages containing sensitive data will be encrypted"
- **Why FP**: Policy statement only; no procedures documented

### DCF-226 (Personal Firewall on Portable Devices)
- **Control**: Firewall installed with specific configurations (settings defined, active, unalterable)
- **Evidence**: "All workstations have firewalls enabled"
- **Why FP**: Generic "enabled" ≠ specific configuration requirements met

### DCF-267 (Sensitive Data on Removable Media Encrypted)
- **Control**: Sensitive data IS encrypted wherever stored on removable media
- **Evidence**: "Treat mass storage devices as sensitive and always secure"
- **Why FP**: Instruction to secure ≠ data is actually encrypted

### DCF-291 (Anti-Malware on All System Components)
- **Control**: Anti-malware solution IS deployed on all system components
- **Evidence**: "Anti-malware must be installed and enabled on all endpoint systems"
- **Why FP**: Policy mandate ≠ actual deployment

### DCF-294 (Anti-Malware Tools Behavior)
- **Control**: Anti-malware configured for periodic/real-time scans OR behavioral analysis
- **Evidence**: "Malware detection software will scan computers"
- **Why FP**: "Will scan" is generic; doesn't specify periodic vs real-time vs behavioral

### DCF-296 (Access to Anti-Virus Configuration)
- **Control**: Restrict access to disable + documented approval + limited time period
- **Evidence**: "Process to authorize temporarily disable measures against malware"
- **Why FP**: Mentions authorization but missing documented approval and time limit requirements

### DCF-334 (Privileged and General User ID Authorization)
- **Control**: Org controls addition, deletion, modification of user IDs
- **Evidence**: "All user IDs inactive for 30 days will be revoked"
- **Why FP**: User inactivity rule ≠ organizational control over ID lifecycle

### DCF-355 (MFA for Remote Access)
- **Control**: MFA required for ALL remote access (users, admins, third parties, maintenance)
- **Evidence**: "Multi-factor authentication such as tokens and smart cards"
- **Why FP**: Mentions MFA but doesn't cover all access types

### DCF-36 (Periodic Security Training)
- **Control**: Established training programs for onboarding + periodic refreshers
- **Evidence**: "Employees go through onboarding process with security requirements"
- **Why FP**: Mentioning onboarding ≠ having established training programs

### DCF-381 (Media Physically Secured)
- **Control**: Media with sensitive data IS physically secured
- **Evidence**: "Authorized users will ensure materials are locked away"
- **Why FP**: User instruction ≠ media is actually secured

### DCF-482 (Acceptable Use Policy for End-User Technologies)
- **Control**: AUP with explicit approval + acceptable uses + approved products list
- **Evidence**: "This policy specifies acceptable use of end-user computing devices"
- **Why FP**: Has acceptable uses but missing explicit approval process and products list

### DCF-580 (Disabling High Risk User Accounts)
- **Control**: Process for disabling accounts of users who pose security risk
- **Evidence**: "User IDs inactive for 30 days will be revoked"
- **Why FP**: Inactivity rule ≠ process for high-risk users

### DCF-622 (Access Control for Output Devices)
- **Control**: Org manages physical access control for output devices
- **Evidence**: "PIN code function will be used on printers"
- **Why FP**: User instruction to use PIN ≠ org managing access control

### DCF-627 (Social Media Rules)
- **Control**: Defined rules of behavior for restricting social media/external sites
- **Evidence**: "Employees will ensure no corporate data is transmitted via digital communications"
- **Why FP**: Data protection statement ≠ social media restriction rules

### DCF-655 (Tamper Protection Procedures)
- **Control**: Procedure for protection against systems tampering
- **Evidence**: "Personnel prohibited from disabling endpoint security controls"
- **Why FP**: User prohibition ≠ organizational procedure

### DCF-688 (Return of Assets)
- **Control**: Org tracks and documents asset return during offboarding
- **Evidence**: "Offboarding includes reiterating duties and responsibilities"
- **Why FP**: Mentioning offboarding ≠ asset tracking/documentation process

### DCF-730 (Security Controls on Devices)
- **Control**: Security controls ARE installed on devices connecting to internet
- **Evidence**: "All workstations have firewalls enabled"
- **Why FP**: Policy mandate ≠ controls are actually installed

### DCF-822 (Remote Access Management)
- **Control**: Documented usage, configuration, connection requirements for EACH TYPE of remote access
- **Evidence**: "Secure remote access must be controlled with encryption"
- **Why FP**: Generic encryption requirement ≠ per-type documentation

### DCF-92 (Encrypted Remote Production Access)
- **Control**: Remote access to PRODUCTION systems via encrypted connection
- **Evidence**: "Secure remote access must be controlled with encryption (VPNs)"
- **Why FP**: General remote access ≠ specifically production systems
