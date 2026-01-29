# Rare Failure Avoidance Rules

*18 rules*

## Prevent Functional Domain Conflation (20 examples)

**Pattern:** The LLM conflates distinct security domains (e.g., Backup vs. Versioning, Antivirus vs. Memory Protection) by treating them as interchangeable.

**Triggers:** `Antivirus`, `Backup`, `Inventory`, `encryption`, `vulnerability scanning`

**Block when:** Control requires a specific technical mechanism but evidence refers to a different functional domain without explicit linkage.

**Allow when:** Control explicitly lists the evidence's domain as a valid alternative implementation.

---

## Distinguish Policy Definitions from Contractual Processes (12 examples)

**Pattern:** The LLM maps controls requiring the definition/content of an internal Policy/Procedure to evidence describing the process for establishing Contracts/Agreements.

**Triggers:** `agreement`, `contract`, `BAA`, `business associate policy`, `clause`, `establishing a written agreement`, `stipulations`

**Block when:** Control requires the definition of an internal Policy/Procedure AND evidence describes the process for establishing Contracts/Agreements.

**Allow when:** Control explicitly governs contract definitions or vendor agreements.

---

## Enforce Exception Governance (10 examples)

**Pattern:** Control requires a primary rule AND a process for managing exceptions/bypasses, but evidence only states the primary rule.

**Triggers:** `bypass`, `exception`, `business justification`, `approval for`, `override`

**Block when:** Control requires a governance process for authorizing exceptions or bypasses, but Evidence only establishes the primary prohibition.

**Allow when:** Evidence explicitly describes the procedure for authorizing exceptions or explicitly states that no exceptions are permitted.

---

## Block Prerequisite Inference (10 examples)

**Pattern:** The LLM assumes that because a system component or process is mentioned, the foundational controls for finding/identifying it must exist.

**Triggers:** `production`, `deletion`, `rectification`, `monitoring`

**Block when:** Control requires a proactive identification/discovery process (e.g., scanning, tagging) AND evidence only describes reactive processes or states of existence.

**Allow when:** Evidence includes specific verbs related to identification (e.g., 'scan', 'discover', 'label', 'tag').

---

## Block Consequence as Process Definition (10 examples)

**Pattern:** The LLM confuses the mention of a consequence (e.g., disciplinary action) with the definition of the process required to reach that consequence.

**Triggers:** `disciplinary action`, `reported to`, `violation`, `subject to`

**Block when:** Control requires a 'defined process' or framework, but evidence only identifies the trigger event or the ultimate consequence.

**Allow when:** Evidence details the specific steps, levels, or adjudication procedures required by the control.

---

## Enforce Strict Frequency Compliance (10 examples)

**Pattern:** The LLM treats specific timing requirements as 'procedural details', mapping them to vague, conditional, or contradictory policy statements.

**Triggers:** `ongoing`, `as applicable`, `based on criticality`, `availability windows`, `at least annually`, `periodically`

**Block when:** Control mandates a specific numeric frequency, deadline, or continuous availability AND Evidence provides only vague, conditional, or conflicting timing.

**Allow when:** Evidence frequency is mathematically stricter than or equal to the control.

---

## Enforce Technical Term Definitions (10 examples)

**Pattern:** The LLM conflates distinct technical terms (e.g., Wireless Access Points vs Network Services) leading to invalid mappings.

**Triggers:** `wireless access points`, `workstations`, `laptops`, `network services`, `physical consoles`

**Block when:** Control targets specific infrastructure layers (e.g., 'network services') AND evidence targets edge devices or connectivity hardware (e.g., 'wireless access points').

**Allow when:** Evidence explicitly states the edge device definition includes the infrastructure layer.

---

## Enforce Explicit Diversity Requirements (10 examples)

**Pattern:** The LLM treats a single blanket mandate as satisfying a control requirement for multiple distinct methods or differentiated rules.

**Triggers:** `multiple methods`, `each type`, `distinct`, `variety of`, `different forms`

**Block when:** Control requires a plurality of methods or distinct rules for subtypes BUT Policy provides a single universal mandate.

**Allow when:** Policy text explicitly enumerates multiple required methods or subtypes matching the control's demand.

---

## Block Data Backup For Processing Redundancy (10 examples)

**Pattern:** The LLM confuses data storage redundancy (backups/replication) with processing/compute redundancy (high availability/load balancing).

**Triggers:** `backup`, `restore`, `replication`, `copy`, `source code`

**Block when:** Control requires redundancy for 'processing', 'equipment', 'transactions', or 'systems' AND Evidence only discusses 'data backup' or 'storage replication'.

**Allow when:** Evidence explicitly mentions redundant servers, active-active clusters, load balancing, or transaction-level recovery mechanisms.

---

## Distinguish Resolution from Validation (10 examples)

**Pattern:** The LLM treats the requirement to verify, validate, or re-test a fix as a technical detail of the general mandate to resolve vulnerabilities.

**Triggers:** `resolve`, `remediate`, `fix`, `address vulnerabilities`

**Block when:** Control requires 'validation', 'verification', 're-scanning', or 're-testing' of a fix AND evidence only mandates the initial 'resolution' or 'remediation'.

**Allow when:** Evidence explicitly mandates post-remediation validation steps, follow-up scans, or verification workflows.

---

## Require Explicit Maintenance Mandates (10 examples)

**Pattern:** The LLM infers maintenance/configuration requirements (updates, signatures) from a mandate to simply 'use' or 'employ' a tool.

**Triggers:** `employ`, `use`, `utilize`, `must have`, `adoption`

**Block when:** Control requires specific maintenance actions (e.g., 'keep up-to-date') AND Policy only mandates the existence or usage of the tool.

**Allow when:** Policy includes maintenance keywords like 'maintain', 'update', 'current', 'patch', or 'lifecycle management'.

---

## Differentiate Notification from Remediation (10 examples)

**Pattern:** The LLM confuses external breach notification procedures with internal data spill discovery and remediation.

**Triggers:** `breach notification`, `assess harm`, `communicate to public`, `notify affected parties`

**Block when:** Control requires internal remediation/discovery of data AND Policy focuses on external notification, legal assessment, or public communication.

**Allow when:** Policy mentions 'containment', 'removal', 'scrubbing', 'secure deletion', or 'internal discovery' procedures.

---

## Enforce Strict Control Qualifiers (10 examples)

**Pattern:** The LLM ignores specific qualifiers in the control (e.g., 'Authenticated', 'Internal') and accepts generic evidence that is insufficient.

**Triggers:** `authenticated`, `internal`, `external`, `ASV`, `approved scanning vendor`, `credentialed`

**Block when:** Control requirement contains a limiting qualifier (e.g., 'Authenticated', 'Internal') that is absent from the Evidence text.

**Allow when:** Evidence explicitly contains the qualifier, a direct synonym, or context that explicitly satisfies the specific scope.

---

## Distinguish Device Hardening from User Access (9 examples)

**Pattern:** The LLM confused device-level initial configuration (hardening) with ongoing user account management policies.

**Triggers:** `vendor defaults`, `default passwords`, `hardening standards`, `device setup`, `infrastructure devices`

**Block when:** Control requires 'password expiration', 'rotation', or 'lifecycle management' for user accounts AND evidence refers to disabling 'vendor defaults' or initial 'device hardening'.

**Allow when:** Control specifically targets 'default credentials', 'system accounts', or 'device provisioning'.

---

## Differentiate Asset Return from Access Revocation (5 examples)

**Pattern:** Evidence regarding the return of physical assets is mapped to controls requiring the disabling of logical access.

**Triggers:** `disable`, `deactivate`, `revoke`, `terminate access`, `remove access`

**Block when:** Evidence only mandates the 'return', 'collection', or 'surrender' of physical assets, hardware, or devices, while Control requires disabling logical access.

**Allow when:** Evidence explicitly mentions 'accounts', 'credentials', 'tokens', 'logins', or 'electronic access' being disabled or revoked.

---

## Distinguish NDA from Security Agreements (5 examples)

**Pattern:** Basic Non-Disclosure Agreement (NDA) mapped to controls requiring specific security, privacy, or data processing agreements.

**Triggers:** `security agreement`, `privacy agreement`, `data processing agreement`, `DPA`, `BAA`

**Block when:** Evidence relies solely on 'Non-Disclosure Agreement', 'NDA', or 'Confidentiality Agreement' while Control requires specific security/privacy agreements.

**Allow when:** Evidence explicitly states the agreement includes 'security controls', 'data protection standards', or 'privacy processing obligations'.

---

## Block Process Inputs as Mandates (5 examples)

**Pattern:** The LLM confuses a requirement to *consider* a factor with a requirement to *implement* that factor.

**Triggers:** `identify requirements`, `factors`, `inputs`, `utilizing different methods`, `considerations`, `analysis`

**Block when:** Evidence mandates a process of identification, analysis, or selection where the control topic is listed merely as a potential method or input.

**Allow when:** Text explicitly mandates the implementation of the results of the analysis or requires the specific method be used.

---

## Verify Binding Scope of List Items (2 examples)

**Pattern:** LLM incorrectly assumes a binding introductory header applies mandatory force to list items that use conditional/permissive language.

**Triggers:** `will be observed`, `must be followed`, `adhere to the following`, `compliance with`

**Block when:** A binding header introduces a list of items where the specific item cited uses non-binding verbs (e.g., 'should').

**Allow when:** The individual list item mirrors the binding strength of the header by using mandatory language.

---
