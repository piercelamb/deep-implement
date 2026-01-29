# False Positive Analysis - Acceptable Use Policy (Run 2)

## Summary

After implementing the changes from `false_positive_additions/combined.md`, we improved precision from 7.5% to 17.6% while maintaining 85.7% recall. However, we still have 28 false positives that need addressing.

**Results:**
- Ground Truth: 7 controls (DCF-106, DCF-32, DCF-37, DCF-50, DCF-558, DCF-763, DCF-780)
- Predictions: 34 MAPPED
- True Positives: 6 (DCF-37, DCF-50, DCF-106, DCF-558, DCF-763, DCF-780)
- False Negatives: 1 (DCF-32)
- False Positives: 28

## The 28 False Positives

| Control ID | Control Description | Pattern Category |
|------------|---------------------|------------------|
| DCF-13 | Information Security Policy | Document-IS-Policy |
| DCF-45 | Data Protection Policy | Document-IS-Policy |
| DCF-181 | Encryption Policy Communication | Document-IS-Policy |
| DCF-482 | Security Policy Mandate | Document-IS-Policy |
| DCF-206 | Outbound Traffic Filtering | Remote-Access-Overreach |
| DCF-223 | Traffic Filtering Implementation | Remote-Access-Overreach |
| DCF-342 | Network Configuration Standards | Remote-Access-Overreach |
| DCF-822 | Network Intrusion Protection | Remote-Access-Overreach |
| DCF-52 | Encryption Configuration | Encryption-Mention-Overreach |
| DCF-108 | Encryption Key Handling | Encryption-Mention-Overreach |
| DCF-149 | Encryption for Remote Communications | Encryption-Mention-Overreach |
| DCF-226 | Personal Firewall Configuration | Behavioral-vs-Technical |
| DCF-294 | Malware Detection Signatures | Antimalware-Overreach |
| DCF-296 | Antivirus Detection & Reporting | Antimalware-Overreach |
| DCF-730 | Malware Detection & Scanning | Antimalware-Overreach |
| DCF-94 | Reporting Security Weaknesses | IR-Overreach |
| DCF-173 | Incident Response Training | IR-Overreach |
| DCF-174 | Security Awareness Training | IR-Overreach |
| DCF-355 | Incident Identification & Response | IR-Overreach |
| DCF-356 | Security Breach Notification | IR-Overreach |
| DCF-580 | Incident Reporting | IR-Overreach |
| DCF-10 | Third-party Physical Security | Topic-Adjacency |
| DCF-11 | Remote Access Controls | Topic-Adjacency |
| DCF-326 | Network Device Monitoring | Topic-Adjacency |
| DCF-381 | Secure Communications | Topic-Adjacency |
| DCF-528 | Data Protection Controls | Evidence-Piecing |
| DCF-589 | User Activity Monitoring | Topic-Adjacency |
| DCF-627 | Mobile Device Hardening | Topic-Adjacency |

---

## Pattern 1: "Document IS Policy" Fallacy (4 FPs)

**Controls:** DCF-13, DCF-45, DCF-181, DCF-482

**Root Cause:** The LLM maps controls requiring "a policy" simply because the document being evaluated IS a policy document. This violates the fundamental requirement that the policy must MANDATE what the control requires.

### Example: DCF-13 (Information Security Policy)
```
Control: "An information security policy is established and communicated."
Evidence: The LLM cites that this IS an information security policy document.
Problem: The Acceptable Use Policy doesn't establish the organization's overall
         information security policy framework - it establishes behavioral rules
         for acceptable use of IT resources.
```

### Example: DCF-45 (Data Protection Policy)
```
Control: "A data protection policy is established that documents procedures
         and mechanisms for protecting and managing data."
Evidence: LLM finds "data protection" mentions in clean desk requirements.
Problem: Clean desk rules for hardcopy documents don't constitute a data
         protection policy with procedures for data lifecycle management.
```

**Proposed Rule Addition:**
```
G-XX: POLICY SCOPE VERIFICATION
When a control requires "a [topic] policy is established," evaluate whether:
1. The document's PRIMARY PURPOSE is to establish that policy topic
2. The document contains the COMPLETE scope required by the control

A document that MENTIONS a topic is not the same as a document that ESTABLISHES
policy FOR that topic. An Acceptable Use Policy is not an Information Security
Policy, even though it addresses security topics.

Examples of INCORRECT matching:
- Acceptable Use Policy → Information Security Policy control (wrong scope)
- Acceptable Use Policy → Data Protection Policy control (wrong scope)
- Remote Access section → Network Security Policy control (wrong scope)

The control asks: "Is there a policy FOR X?"
NOT: "Does this document mention X?"
```

---

## Pattern 2: Remote Access → Network Security Overreach (4 FPs)

**Controls:** DCF-206, DCF-223, DCF-342, DCF-822

**Root Cause:** The Acceptable Use Policy has a "Remote Access Tools" section requiring a proxy. The LLM extrapolates this to network security controls about traffic filtering, intrusion detection, and network device configuration.

### Example: DCF-206 (Outbound Traffic Filtering)
```
Control: "Outbound network traffic that could indicate compromised systems is
         filtered at the network boundaries."
Evidence: "All traffic must be routed through the company proxy."
Problem: A proxy requirement for USERS doesn't constitute network boundary
         filtering for COMPROMISED SYSTEM traffic detection. This is a G-2
         violation (behavioral rule vs. technical implementation).
```

### Example: DCF-822 (Network Intrusion Protection)
```
Control: "Network-based intrusion prevention systems are implemented."
Evidence: Proxy requirement from Remote Access section.
Problem: A user-facing proxy mandate doesn't implement IPS technology.
         Completely different control type and implementation mechanism.
```

**Proposed Rule Addition:**
```
G-XX: PROXY REQUIREMENTS VS NETWORK SECURITY CONTROLS
A policy requiring users to route traffic through a proxy is NOT evidence of:
- Network boundary filtering (DCF-206, DCF-223)
- Intrusion detection/prevention systems (DCF-822)
- Network device configuration standards (DCF-342)
- Traffic inspection capabilities

Proxy requirements are USER BEHAVIORAL rules enforced through policy.
Network security controls are TECHNICAL implementations enforced through systems.

The presence of proxy language satisfies controls about:
✓ User remote access procedures
✗ Network architecture security
✗ Technical traffic filtering
✗ Intrusion detection systems
```

---

## Pattern 3: Encryption Mention → All Encryption Controls (3 FPs)

**Controls:** DCF-52, DCF-108, DCF-149

**Root Cause:** The policy mentions encryption requirements for remote access tools and mobile devices. The LLM maps this to technical encryption configuration controls.

### Example: DCF-52 (Encryption Configuration)
```
Control: "Strong encryption is used for wireless networks and configured
         in accordance with industry best practices."
Evidence: "Remote access tools must use encrypted connections."
Problem: Remote access encryption requirements don't address WIRELESS NETWORK
         encryption configuration. Different scope, different technical domain.
```

### Example: DCF-108 (Encryption Key Handling)
```
Control: "Processes are implemented for the secure handling of encryption keys."
Evidence: General encryption requirements in the policy.
Problem: Requiring encryption doesn't establish key handling processes
         (key generation, rotation, storage, destruction procedures).
```

**Proposed Rule Addition:**
```
G-XX: ENCRYPTION REQUIREMENTS VS ENCRYPTION CONTROLS
A policy requiring the USE of encryption is different from a policy establishing:
- Encryption configuration standards (algorithms, key lengths)
- Key management procedures (generation, rotation, destruction)
- Specific encryption protocol requirements
- Cryptographic implementation details

"Use encryption" satisfies: "Encryption must be used for X"
"Use encryption" does NOT satisfy: "Encryption must be configured according to..."

The gap: WHAT encryption vs. HOW encryption is managed.
```

---

## Pattern 4: Behavioral Rules → Technical Controls (1 FP)

**Controls:** DCF-226

**Root Cause:** The LLM maps user behavioral requirements (must enable firewall) to technical implementation controls (firewall must be configured to X).

### Example: DCF-226 (Personal Firewall Configuration)
```
Control: "A personal software firewall is configured to deny inbound
         network traffic by default and block outbound traffic except
         for explicitly authorized connections."
Evidence: "Workstations must have the firewall enabled."
Problem: "Enable firewall" is a user behavioral requirement.
         "Configure firewall to deny inbound by default" is a technical
         configuration requirement. The policy doesn't specify HOW the
         firewall should be configured - just that users must enable it.
```

**Proposed Rule Enhancement (strengthen existing G-2):**
```
G-2 ENHANCEMENT: BEHAVIORAL VS TECHNICAL SPECIFICITY
When the control specifies technical configuration parameters:
- "deny inbound by default"
- "block outbound except authorized"
- "configured to [specific setting]"

A behavioral mandate like "enable firewall" or "use firewall" does NOT satisfy
the control because it lacks the specific configuration requirements.

The control tests: "Is the firewall configured THIS WAY?"
The evidence says: "Users must have firewall on"
Gap: Configuration specifics are missing.
```

---

## Pattern 5: Antimalware Section Overreach (3 FPs)

**Controls:** DCF-294, DCF-296, DCF-730

**Root Cause:** The Acceptable Use Policy has a "Malware Protection" section. The LLM maps this to technical antimalware controls that require specific implementation details.

### Example: DCF-294 (Malware Detection Signatures)
```
Control: "Malware detection software is configured to receive automatic
         signature updates."
Evidence: "Anti-malware must be installed" from the policy.
Problem: Installation requirement ≠ automatic update configuration.
         The policy doesn't mandate automatic signature updates.
```

### Example: DCF-730 (Malware Detection & Scanning)
```
Control: "Systems are configured to automatically scan removable media
         when inserted."
Evidence: "Scan any files on any storage medium before use."
Problem: "Before use" (user action) vs. "when inserted" (automatic).
         The policy requires USER scanning, not AUTOMATIC system scanning.
```

**Proposed Rule Addition:**
```
G-XX: ANTIMALWARE INSTALLATION VS CONFIGURATION CONTROLS
A policy requiring antimalware installation satisfies:
✓ Controls requiring antimalware presence
✓ Controls requiring malware protection capability

A policy requiring antimalware installation does NOT satisfy:
✗ Automatic signature update requirements (needs explicit mandate)
✗ Automatic scanning configuration (needs explicit mandate)
✗ Specific detection capability requirements
✗ Reporting and alerting requirements

Watch for temporal triggers:
- "before use" = user-initiated (behavioral)
- "when inserted" = automatic (technical)
- "automatically" = system behavior (technical)
```

---

## Pattern 6: Incident Response Overreach (6 FPs)

**Controls:** DCF-94, DCF-173, DCF-174, DCF-355, DCF-356, DCF-580

**Root Cause:** The policy mentions incident reporting requirements (users must report security incidents). The LLM extrapolates this to comprehensive incident response program controls.

### Example: DCF-355 (Incident Identification & Response)
```
Control: "Security incidents are identified and responded to in accordance
         with a formal incident response plan."
Evidence: User incident reporting requirements.
Problem: USER REPORTING is one input to incident response. It doesn't
         constitute the incident response plan itself (identification
         procedures, escalation, containment, eradication, recovery).
```

### Example: DCF-173 (Incident Response Training)
```
Control: "Incident response personnel receive training on incident handling."
Evidence: Users must report incidents.
Problem: Requiring users to report doesn't establish training programs
         for incident response personnel.
```

### Example: DCF-174 (Security Awareness Training)
```
Control: "Security awareness training is provided to all personnel."
Evidence: The policy communicates security expectations.
Problem: A policy document is not a training program. G-3 addresses this -
         artifact publication ≠ training delivery verification.
```

**Proposed Rule Addition:**
```
G-XX: INCIDENT REPORTING VS INCIDENT RESPONSE PROGRAM
User incident reporting requirements satisfy:
✓ Controls requiring incident reporting mechanisms
✓ Controls requiring user awareness of reporting procedures

User incident reporting requirements do NOT satisfy:
✗ Formal incident response plans (needs plan documentation)
✗ Incident response training (needs training program)
✗ Incident identification procedures (needs detection mechanisms)
✗ Breach notification procedures (needs notification process)
✗ Security awareness training programs (policy ≠ training)

The gap: REPORTING INTO the IR program vs. the IR PROGRAM ITSELF.
```

---

## Pattern 7: Topic Adjacency (7 FPs)

**Controls:** DCF-10, DCF-11, DCF-326, DCF-381, DCF-528, DCF-589, DCF-627

**Root Cause:** The LLM maps controls that share topic keywords but have different scope or requirements.

### Example: DCF-627 (Mobile Device Hardening)
```
Control: "Mobile devices are hardened according to security configuration
         standards."
Evidence: Mobile device section requiring passcodes and encryption.
Problem: User requirements (set passcode, enable encryption) ≠ device
         hardening standards (specific configurations, restrictions,
         enterprise management).
```

### Example: DCF-528 (Data Protection Controls)
```
Control: "Personal data protection controls are implemented in accordance
         with legal and regulatory requirements."
Evidence: LLM pieced together clean desk + data handling mentions.
Problem: Clean desk procedures for hardcopy don't constitute comprehensive
         data protection controls per legal/regulatory requirements.
```

### Example: DCF-589 (User Activity Monitoring)
```
Control: "User activity on systems is monitored and logged."
Evidence: Policy states "activity may be monitored."
Problem: Policy warns that monitoring MAY occur (notice to users).
         Control requires monitoring IS implemented (technical capability).
```

**Proposed Rule Addition:**
```
G-XX: TOPIC KEYWORD MATCHING IS INSUFFICIENT
When control and evidence share keywords but differ in:

1. SCOPE:
   - Control: "mobile devices are hardened"
   - Evidence: "users must set passcodes"
   - Gap: User requirement vs. device configuration standard

2. CERTAINTY:
   - Control: "activity IS monitored"
   - Evidence: "activity MAY be monitored"
   - Gap: Implementation vs. possibility

3. MECHANISM:
   - Control: "controls ARE implemented"
   - Evidence: "users must follow rules"
   - Gap: Technical implementation vs. behavioral policy

Keyword overlap alone is NOT sufficient for mapping.
```

---

## Pattern 8: Evidence Piecing Violation (1 FP)

**Controls:** DCF-528

**Root Cause:** The LLM combines evidence from multiple unrelated sections to construct a match, violating the single-sentence evidence rule.

### Example: DCF-528
```
Control: "Personal data protection controls are implemented in accordance
         with legal and regulatory requirements."
Evidence: Combined clean desk + paper shredding + data handling mentions.
Problem: Each individual section addresses a narrow topic. Combining them
         doesn't create comprehensive data protection controls per
         legal requirements.
```

**The existing IR-3 rule should handle this, but clearly isn't being applied strictly enough.**

---

## Recommended Prompt Changes

### New Guardrails to Add

```markdown
### G-XX: POLICY SCOPE VERIFICATION

When a control requires "a [topic] policy is established," the document must:
1. Have establishing that policy as its PRIMARY PURPOSE
2. Contain the COMPLETE scope required by the control

A document that MENTIONS a topic is not the same as establishing policy FOR that topic.

EXAMPLES:
- Acceptable Use Policy → Information Security Policy = NO MATCH (different scope)
- Acceptable Use Policy → Data Protection Policy = NO MATCH (different scope)
- Remote Access section → Network Security Policy = NO MATCH (section ≠ policy)

### G-XX: PROXY REQUIREMENTS VS NETWORK CONTROLS

User proxy requirements are NOT evidence of:
- Network boundary filtering
- Intrusion detection/prevention systems
- Network device configuration standards
- Traffic inspection capabilities

Proxy mandates = USER behavioral rules
Network security controls = TECHNICAL system implementations

### G-XX: ENCRYPTION USE VS ENCRYPTION MANAGEMENT

Requiring encryption USE does not satisfy:
- Encryption configuration standards
- Key management procedures
- Cryptographic protocol requirements

"Use encryption" ≠ "Encryption is configured according to standards"

### G-XX: ANTIMALWARE PRESENCE VS CONFIGURATION

Requiring antimalware installation does NOT satisfy:
- Automatic update configuration
- Automatic scanning on media insert
- Specific detection capabilities
- Reporting and alerting requirements

Watch for: "before use" (user-initiated) vs. "automatically" (system behavior)

### G-XX: INCIDENT REPORTING VS IR PROGRAM

User incident reporting does NOT satisfy:
- Formal incident response plans
- Incident response training
- Incident identification procedures
- Breach notification procedures
- Security awareness training programs

REPORTING INTO IR program ≠ IR PROGRAM ITSELF

### G-XX: TOPIC KEYWORD MATCHING INSUFFICIENT

Reject matches where control and evidence share keywords but differ in:
- SCOPE: Control scope exceeds evidence scope
- CERTAINTY: Control requires IS, evidence says MAY
- MECHANISM: Control requires technical, evidence provides behavioral
```

### Rules to Strengthen

1. **G-2 (Behavioral vs Technical)**: Add explicit examples of configuration controls that require technical specifics, not just "enable X".

2. **IR-3 (Single Sentence)**: This rule exists but isn't preventing evidence piecing. Need stronger enforcement language.

3. **G-3 (Artifact Publication)**: Strengthen - a policy document existing is not the same as training being delivered.

---

## False Negative Analysis: DCF-32

DCF-32 was not predicted but is in ground truth. Need to analyze why.

**DCF-32**: Based on the ground truth, this control should have been detected. The LLM may have:
1. Not received it in any batch (retrieval issue)
2. Received but rejected it (decision issue)

This needs investigation in the batch files to determine root cause.

---

## Summary of Recommendations

1. **Add 6 new guardrails** addressing the specific patterns identified
2. **Strengthen G-2** with configuration specificity examples
3. **Strengthen IR-3** enforcement language
4. **Strengthen G-3** to clarify policy publication ≠ training delivery
5. **Investigate DCF-32** false negative for root cause
